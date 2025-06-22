import os
import base64
import pymysql
import asyncio
import json
import time
from dotenv import load_dotenv
import aiohttp
from telethon.errors import ChatForwardsRestrictedError
from telethon.sessions import StringSession
from telethon import TelegramClient, events
from telethon.tl.types import InputDocument,MessageMediaDocument
from telethon import events
from telethon.tl.types import InputMessagesFilterEmpty
from telethon.tl.types import PeerUser
from datetime import datetime

# Aiogram 相关
from aiogram import F, Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import ContentType
from aiohttp import web

from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

import re
import os



# 常量
MAX_PROCESS_TIME = 15 * 60  # 最大运行时间 20 分钟


# ================= 1. 载入 .env 中的环境变量 =================

# 加载环境变量
if not os.getenv('GITHUB_ACTIONS'):
    from dotenv import load_dotenv
    # load_dotenv(dotenv_path='.24690454.queue.env')
    load_dotenv(dotenv_path='.28817994.luzai.env')


config = {}
# 嘗試載入 JSON 並合併參數
try:
    configuration_json = json.loads(os.getenv('CONFIGURATION', '') or '{}')
    if isinstance(configuration_json, dict):
        config.update(configuration_json)  # 將 JSON 鍵值對合併到 config 中
except Exception as e:
    print(f"⚠️ 無法解析 CONFIGURATION：{e}")

API_ID          = int(config.get('api_id', os.getenv('API_ID', 0)))
API_HASH        = config.get('api_hash', os.getenv('API_HASH', ''))
PHONE_NUMBER    = config.get('phone_number', os.getenv('PHONE_NUMBER', ''))
BOT_TOKEN       = config.get('bot_token', os.getenv('BOT_TOKEN', ''))
TARGET_GROUP_ID = int(config.get('target_group_id', os.getenv('TARGET_GROUP_ID', 0)))
MYSQL_HOST      = config.get('db_host', os.getenv('MYSQL_DB_HOST', 'localhost'))
MYSQL_USER      = config.get('db_user', os.getenv('MYSQL_DB_USER', ''))
MYSQL_PASSWORD  = config.get('db_password', os.getenv('MYSQL_DB_PASSWORD', ''))
MYSQL_DB        = config.get('db_name', os.getenv('MYSQL_DB_NAME', ''))
MYSQL_DB_PORT   = int(config.get('db_port', os.getenv('MYSQL_DB_PORT', 3306)))
SESSION_STRING  = os.getenv("USER_SESSION_STRING")
BOT_MODE        = os.getenv("BOT_MODE", "polling").lower()
WEBHOOK_SECRET  = os.getenv("WEBHOOK_SECRET", "")  
WEBHOOK_PATH    = os.getenv("WEBHOOK_PATH", "/")       
WEBHOOK_HOST    = os.getenv("WEBHOOK_HOST")  # 确保设置为你的域名或 IP                                   
USER_SESSION    = str(API_ID) + 'session_name'  # 确保与上传的会话文件名匹配

# ================= 2. 初始化 MySQL 连接 =================
mysql_config = {
    'host'      : MYSQL_HOST,
    'user'      : MYSQL_USER,
    'password'  : MYSQL_PASSWORD,
    'database'  : MYSQL_DB,
    "port"      : MYSQL_DB_PORT,
    'charset'   : 'utf8mb4',
    'autocommit': True
}
db = pymysql.connect(**mysql_config)
cursor = db.cursor()

lz_var_start_time = time.time()
lz_var_cold_start_flag = True

# file_unique_id 通常是 base64 编码短字串，长度 20~35，字母+数字组成
file_unique_id_pattern = re.compile(r'^[A-Za-z0-9_-]{12,64}$')
# doc_id 是整数，通常为 Telegram 64-bit ID
doc_id_pattern = re.compile(r'^\d{10,20}$')


def safe_execute(sql, params=None):
    try:
        db.ping(reconnect=True)  # 检查连接状态并自动重连
        cursor.execute(sql, params or ())
        return cursor
    except Exception as e:
        print(f"⚠️ 数据库执行出错: {e}")
        return None

async def heartbeat():
    while True:
        print("💓 Alive (Aiogram polling still running)")
        try:
            db.ping(reconnect=True)
            print("✅ MySQL 连接正常")
        except Exception as e:
            print(f"⚠️ MySQL 保活失败：{e}")
        await asyncio.sleep(600)

async def health(request):
    uptime = time.time() - lz_var_start_time
    if lz_var_cold_start_flag or uptime < 10:
        return web.Response(text="⏳ Bot 正在唤醒，请稍候...", status=503)
    return web.Response(text="✅ Bot 正常运行", status=200)


async def on_startup(bot: Bot):
    webhook_url = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
    print(f"🔗 設定 Telegram webhook 為：{webhook_url}")
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(webhook_url)
    lz_var_cold_start_flag = False  # 启动完成


# ================= 3. Helper：从 media.attributes 提取文件名 =================
def get_file_name(media):
    from telethon.tl.types import DocumentAttributeFilename
    for attr in getattr(media, 'attributes', []):
        if isinstance(attr, DocumentAttributeFilename):
            return attr.file_name
    return None

# ================= 4. Upsert 函数：统一 Insert/Update 逻辑 =================
def upsert_file_record(fields: dict):
    """
    fields: dict, 键是列名, 值是要写入的内容。
    自动生成 INSERT ... ON DUPLICATE KEY UPDATE 语句。
    """
    if not fields:
        return
    cols = list(fields.keys())
    placeholders = ["%s"] * len(cols)
    update_clauses = [f"{col}=VALUES({col})" for col in cols]
    sql = f"""
        INSERT INTO file_records ({','.join(cols)})
        VALUES ({','.join(placeholders)})
        ON DUPLICATE KEY UPDATE {','.join(update_clauses)}
    """
    values = list(fields.values())
    try:
        safe_execute(sql, values)
    except Exception as e:
        print(f"110 Error: {e}")

# ================= 5.1 send_media_by_doc_id 函数 =================
async def send_media_by_doc_id(client, to_user_id, doc_id, client_type,msg_id=None):
    print(f"【send_media_by_doc_id】开始处理 doc_id={doc_id}，目标用户：{to_user_id}",flush=True)

    try:
        safe_execute(
            "SELECT chat_id, message_id, doc_id, access_hash, file_reference, file_id, file_unique_id,file_type "
            "FROM file_records WHERE doc_id = %s",
            (doc_id,)
        )
        row = cursor.fetchone()
    except Exception as e:
        print(f"121 Error: {e}")
        return

    if not row:
        if client_type == 'man':
            try:
                # 尝试将 user_id 解析成可用的 InputPeer 实体
                to_user_entity = await client.get_input_entity(to_user_id)
                await client.send_message(to_user_entity, f"未找到 doc_id={doc_id} 对应的文件记录。(176)")
            except Exception as e:
                print(f"获取用户实体失败: {e}")
                await client.send_message('me', f"无法获取用户实体: {to_user_id}")
        else:
            await client.send_message(to_user_id, f"未找到 doc_id={doc_id} 对应的文件记录。(181)")
        return

    if client_type == 'bot':
        # 机器人账号发送
        await send_media_via_bot(client, to_user_id, row, msg_id)
    else:
        await send_media_via_man(client, to_user_id, row, msg_id)

# ================= 5.2 send_media_by_file_unique_id 函数 =================
async def send_media_by_file_unique_id(client, to_user_id, file_unique_id, client_type, msg_id):
    print(f"【send_media_by_file_unique_id】开始处理 file_unique_id={file_unique_id}，目标用户：{to_user_id}",flush=True)
    try:
        safe_execute(
            "SELECT chat_id, message_id, doc_id, access_hash, file_reference, file_id, file_unique_id,file_type FROM file_records WHERE file_unique_id = %s",
            (file_unique_id,)
        )
        row = cursor.fetchone()

        if not row:
            # await client.send_message(to_user_id, f"未找到 file_unique_id={file_unique_id} 对应的文件。(201)")
            return
    
    except Exception as e:
        print(f"148 Error: {e}")
        return
    if client_type == 'bot':
        # 机器人账号发送
        await send_media_via_bot(client, to_user_id, row, msg_id)
    else:
        await send_media_via_man(client, to_user_id, row, msg_id)

# ================= 6.1 send_media_via_man 函数 =================
async def send_media_via_man(client, to_user_id, row, msg_id=None):
    # to_user_entity = await client.get_input_entity(to_user_id)
    chat_id, message_id, doc_id, access_hash, file_reference_hex, file_id, file_unique_id, file_type = row
    try:
        file_reference = bytes.fromhex(file_reference_hex)
    except:
        import base64
        try:
            file_reference = base64.b64decode(file_reference_hex)
        except:
            await client.send_message(to_user_id, "文件引用格式异常，无法发送。")
            return

    input_doc = InputDocument(
        id=doc_id,
        access_hash=access_hash,
        file_reference=file_reference
    )
    try:
        await client.send_file(to_user_id, input_doc, reply_to=msg_id)
    except Exception:
        # file_reference 过期时，重新从历史消息拉取
        try:
            msg = await client.get_messages(chat_id, ids=message_id)
            media = msg.document or msg.photo or msg.video
            if not media:
                print(f"历史消息中未找到对应媒体，可能已被删除。",flush=True)
                await client.send_message(to_user_id, "历史消息中未找到对应媒体，可能已被删除。")
                return
            print(f"重新获取文件引用：{media.id}, {media.access_hash}, {media.file_reference.hex()}",flush=True)
            # 区分 photo 和 document
            if msg.document:
                new_input = InputDocument(
                    id=msg.document.id,
                    access_hash=msg.document.access_hash,
                    file_reference=msg.document.file_reference
                )
            elif msg.photo:
                new_input = msg.photo  # 直接发送 photo 不需要构建 InputDocument
            else:
                await client.send_message(to_user_id, "暂不支持此媒体类型。")
                return
            
            
            print(f"重新获取文件引用成功，准备发送。",flush=True)
          

            await client.send_file(to_user_id, new_input, reply_to=msg_id)
        except Exception as e:
            print(f"发送文件时出错：{e}",flush=True)
            await client.send_message(to_user_id, f"发送文件时出错：{e}")

# ================= 6.2 send_media_via_bot 函数 =================
async def send_media_via_bot(bot_client, to_user_id, row,msg_id=None):
    """
    bot_client: Aiogram Bot 实例
    row: (chat_id, message_id, doc_id, access_hash, file_reference_hex, file_id, file_unique_id)
    """
    chat_id, message_id, doc_id, access_hash, file_reference_hex, file_id, file_unique_id, file_type = row


    try:
        if file_type== "photo":
            # 照片（但不包括 GIF）
            await bot_client.send_photo(to_user_id, file_id, reply_to_message_id=msg_id)
      
        elif file_type == "video":
            # 视频
            await bot_client.send_video(to_user_id, file_id, reply_to_message_id=msg_id)
        elif file_type == "document":
            # 其他一律当文件发
            await bot_client.send_document(to_user_id, file_id, reply_to_message_id=msg_id)

    except Exception as e:
        await bot_client.send_message(to_user_id, f"⚠️ 发送文件失败：{e}")
    



# ================= 7. 初始化 Telethon 客户端 =================

if SESSION_STRING:
    user_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    print("【Telethon】使用 StringSession 登录。",flush=True)
else:
    user_client = TelegramClient(USER_SESSION, API_ID, API_HASH)







# ================= 8. 私聊文字处理：人类账号 =================



@user_client.on(events.NewMessage(incoming=True))
async def handle_user_private_text(event):
    msg = event.message
    if not msg.is_private or msg.media or not msg.text:
        return

    to_user_id = msg.from_id

    
    # if isinstance(msg.from_id, PeerUser) and msg.from_id.user_id:
    #     to_user_id = msg.from_id.user_id
    # else:
    #     print("⚠️ 无效的 from_id，跳过")
    #     await msg.delete()
    #     return

    # print(f"【Telethon】收到私聊文本：来自 {to_user_id}",flush=True)
    text = msg.text.strip()

    if text:
        try:
            match = re.search(r'\|_kick_\|\s*(.*?)\s*(bot)', text, re.IGNORECASE)
            if match:
                botname = match.group(1) + match.group(2)
                await user_client.send_message(botname, "/start")
                await user_client.send_message(botname, "[~bot~]")
                await msg.delete()
                return
        except Exception as e:
                print(f"Error kicking bot: {e} {botname}", flush=True)

    await msg.delete()

    # if file_unique_id_pattern.fullmatch(text):
    #     file_unique_id = text
    #     await send_media_by_file_unique_id(user_client, to_user_id, file_unique_id, 'man', msg.id)
    # elif doc_id_pattern.fullmatch(text):
    #     doc_id = int(text)
    #     await send_media_by_doc_id(user_client, to_user_id, doc_id, 'man', msg.id)
       
    # else:
    #     await msg.delete()

    # if text.isdigit():
    #     doc_id = int(text)
    #     await send_media_by_doc_id(user_client, to_user_id, doc_id, 'man', msg.id)
    # else:
    #     file_unique_id = text
    #     await send_media_by_file_unique_id(user_client, to_user_id, file_unique_id, 'man', msg.id)

    # await event.delete()

# ================= 9. 私聊媒体处理：人类账号 =================
@user_client.on(events.NewMessage(incoming=True))
async def handle_user_private_media(event):
    msg = event.message
    if not msg.is_private or not (msg.document or msg.photo or msg.video):
        # print(f"【Telethon】收到私聊媒体，但不处理：，来自 {event.message.from_id}",flush=True)
        return
    print(f"【Telethon】收到私聊媒体：{event.message.media}，来自 {event.message.from_id}",flush=True)
    exit(0)  # ⚠️ 直接退出，避免处理私聊媒体
    print(f"{msg}",flush=True)
    print(f"{event.message.text}",flush=True)
    

    if msg.document:
        media = msg.document
        file_type = 'document'
    elif msg.video:
        media = msg.video
        file_type = 'video'
    else:
        media = msg.photo
        file_type = 'photo'

    doc_id         = media.id
    access_hash    = media.access_hash
    file_reference = media.file_reference.hex()
    mime_type      = getattr(media, 'mime_type', 'image/jpeg' if msg.photo else None)
    file_size      = getattr(media, 'size', None)
    file_name      = get_file_name(media)
    caption        = event.message.text or ""



    match = re.search(r'\|_forward_\|\@(-?\d+|[a-zA-Z0-9_]+)', caption, re.IGNORECASE)
    if match:
        print(f"【Telethon】匹配到的转发模式：{match}",flush=True)
        captured_str = match.group(1).strip()  # 捕获到的字符串
        print(f"【Telethon】捕获到的字符串：{captured_str}",flush=True)

        if captured_str.startswith('-100') and captured_str[4:].isdigit():
            destination_chat_id = int(captured_str)  # 正确做法，保留 -100
        elif captured_str.isdigit():
            print(f"【Telethon】捕获到的字符串是数字：{captured_str}",flush=True)
            destination_chat_id = int(captured_str)
        else:
            print(f"【Telethon】捕获到的字符串不是数字：{captured_str}",flush=True)
            destination_chat_id = str(captured_str)
        
        try:
            ret = await user_client.send_file(destination_chat_id, msg.media)
            print(f"【Telethon】已转发到目标群组：{destination_chat_id}，消息 ID：{ret.id}",flush=True)
            print(f"{ret}",flush=True)
        except ChatForwardsRestrictedError:
            print(f"⚠️ 该媒体来自受保护频道，无法转发，已跳过。msg.id = {msg.id}", flush=True)
            return  # ⚠️ 不处理，直接跳出
        except Exception as e:
            print(f"❌ 其他发送失败：{e}", flush=True)
            return

    # 检查：TARGET_GROUP_ID 群组是否已有相同 doc_id
    try:
        safe_execute(
            "SELECT 1 FROM file_records WHERE doc_id = %s AND chat_id = %s AND file_unique_id IS NOT NULL",
            (doc_id, TARGET_GROUP_ID)
        )
    except Exception as e:
        print(f"272 Error: {e}")
        
    if cursor.fetchone():
        await event.delete()
        return

    # 转发到群组，并删除私聊
    try:
        # 这里直接发送 msg.media，如果受保护会被阻止
        ret = await user_client.send_file(TARGET_GROUP_ID, msg.media)
    except ChatForwardsRestrictedError:
        print(f"🚫 跳过：该媒体来自受保护频道 msg.id = {msg.id}", flush=True)
        return
    except Exception as e:
        print(f"❌ 其他错误：{e}", flush=True)
        return

    



    # 插入或更新 placeholder 记录 (message_id 自动留空，由群组回调补全)
    upsert_file_record({
        'chat_id'       : ret.chat_id,
        'message_id'    : ret.id,
        'doc_id'        : doc_id,
        'access_hash'   : access_hash,
        'file_reference': file_reference,
        'mime_type'     : mime_type,
        'file_type'     : file_type,
        'file_name'     : file_name,
        'file_size'     : file_size,
        'uploader_type' : 'user'
    })
    await event.delete()



async def process_private_media_msg(msg):
    
    # ✅ 没有媒体，直接跳过
    if not (msg.document or msg.photo or msg.video or msg.text):
        msg.delete()
        return
   
    print(f"【Telethon】来自私聊媒体回溯处理：{msg.media}，chat_id={msg.chat_id}", flush=True)
    


    if msg.document:
        media = msg.document
        file_type = 'document'
    elif msg.video:
        media = msg.video
        file_type = 'video'
    else:
        media = msg.photo
        file_type = 'photo'

    doc_id = media.id
    access_hash = media.access_hash
    file_reference = media.file_reference.hex()
    mime_type = getattr(media, 'mime_type', 'image/jpeg' if msg.photo else None)
    file_size = getattr(media, 'size', None)
    file_name = get_file_name(media)
    caption = msg.text or ""

    match = re.search(r'\|_forward_\|\@(-?\d+|[a-zA-Z0-9_]+)', caption, re.IGNORECASE)
    if match:
        print(f"【Telethon】匹配到的转发模式：{match}",flush=True)
        captured_str = match.group(1).strip()  # 捕获到的字符串
        print(f"【Telethon】捕获到的字符串：{captured_str}",flush=True)

        if captured_str.startswith('-100') and captured_str[4:].isdigit():
            destination_chat_id = int(captured_str)  # 正确做法，保留 -100
        elif captured_str.isdigit():
            print(f"【Telethon】捕获到的字符串是数字：{captured_str}",flush=True)
            destination_chat_id = int(captured_str)
        else:
            print(f"【Telethon】捕获到的字符串不是数字：{captured_str}",flush=True)
            destination_chat_id = str(captured_str)
        
        try:
            ret = await user_client.send_file(destination_chat_id, msg.media)
            print(f"【Telethon】已转发到目标群组：{destination_chat_id}，消息 ID：{ret.id}",flush=True)
            print(f"{ret}",flush=True)
        except ChatForwardsRestrictedError:
            print(f"⚠️ 该媒体来自受保护频道，无法转发，已跳过。msg.id = {msg.id}", flush=True)
            return  # ⚠️ 不处理，直接跳出
        except Exception as e:
            print(f"❌ 其他发送失败：{e}", flush=True)
            return

    # 检查是否已处理
    safe_execute(
        "SELECT 1 FROM file_records WHERE doc_id = %s AND chat_id = %s AND file_unique_id IS NOT NULL",
        (doc_id, TARGET_GROUP_ID)
    )
    if cursor.fetchone():
        print(f"【Telethon】媒体重覆已删除 {file_name}", flush=True)
        await msg.delete()
        return

    try:
        ret = await user_client.send_file(TARGET_GROUP_ID, media)
        print(f"【Telethon】媒体收录 {file_name}", flush=True)
        await msg.delete()
    except ChatForwardsRestrictedError:
        print(f"🚫 跳过：受保护来源，无法转发 msg.id = {msg.id}", flush=True)
        msg.delete()
        return
    except Exception as e:
        print(f"❌ 错误：{e}", flush=True)
        await msg.delete()
        return
    finally:
        # 确保删除原始消息
        await msg.delete()

    upsert_file_record({
        'chat_id'       : ret.chat_id,
        'message_id'    : ret.id,
        'doc_id'        : doc_id,
        'access_hash'   : access_hash,
        'file_reference': file_reference,
        'mime_type'     : mime_type,
        'file_type'     : file_type,
        'file_name'     : file_name,
        'file_size'     : file_size,
        'uploader_type' : 'user'
    })




# ================= 12. 群组媒体处理：人类账号 =================
@user_client.on(events.NewMessage(chats=TARGET_GROUP_ID, incoming=True))
async def handle_user_group_media(event):
    msg = event.message
    if not (msg.document or msg.photo or msg.video):
        return

    if msg.document:
        media = msg.document
        file_type = 'document'
    elif msg.video:
        media = msg.video
        file_type = 'video'
    else:
        media = msg.photo
        file_type = 'photo'

    chat_id        = msg.chat_id
    message_id     = msg.id
    doc_id         = media.id
    access_hash    = media.access_hash
    file_reference = media.file_reference.hex()
    mime_type      = getattr(media, 'mime_type', 'image/jpeg' if msg.photo else None)
    file_size      = getattr(media, 'size', None)
    file_name      = get_file_name(media)

    # —— 步骤 A：先按 doc_id 查库 —— 
    try:
        # 检查是否已存在相同 doc_id 的记录
        safe_execute(
            "SELECT chat_id, message_id FROM file_records WHERE doc_id = %s",
            (doc_id,)
        )
    except Exception as e:
        print(f"332 Error: {e}")
   
    row = cursor.fetchone()
    if row:
        existing_chat_id, existing_msg_id = row
        if not (existing_chat_id == chat_id and existing_msg_id == message_id):
            print(f"【Telethon】在指定群组，收到群组媒体：{event.message.media}，来自 {event.message.from_id}",flush=True)
   
            # 重复上传到不同消息 → 更新并删除新消息
            upsert_file_record({
                'doc_id'        : doc_id,
                'access_hash'   : access_hash,
                'file_reference': file_reference,
                'mime_type'     : mime_type,
                'file_type'     : file_type,
                'file_name'     : file_name,
                'file_size'     : file_size,
                'uploader_type' : 'user',
                'chat_id'       : chat_id,
                'message_id'    : message_id
            })
            await event.delete()
        else:
            # 同一条消息重复触发 → 仅更新，不删除
            upsert_file_record({
                'chat_id'       : chat_id,
                'message_id'    : message_id,
                'access_hash'   : access_hash,
                'file_reference': file_reference,
                'mime_type'     : mime_type,
                'file_type'     : file_type,
                'file_name'     : file_name,
                'file_size'     : file_size,
                'uploader_type' : 'user'
            })
        return

    # —— 步骤 B：若 A 中没找到，再按 (chat_id, message_id) 查库 ——
    try:
        safe_execute(
            "SELECT id FROM file_records WHERE chat_id = %s AND message_id = %s",
            (chat_id, message_id)
        )
    except Exception as e:
        print(f"372 Error: {e}")
    if cursor.fetchone():
        # 已存在同条消息 → 更新并保留
        upsert_file_record({
            'chat_id'       : chat_id,
            'message_id'    : message_id,
            'doc_id'        : doc_id,
            'access_hash'   : access_hash,
            'file_reference': file_reference,
            'mime_type'     : mime_type,
            'file_type'     : file_type,
            'file_name'     : file_name,
            'file_size'     : file_size,
            'uploader_type' : 'user'
        })
    else:
        # 全新媒体 → 插入并保留
        upsert_file_record({
            'chat_id'       : chat_id,
            'message_id'    : message_id,
            'doc_id'        : doc_id,
            'access_hash'   : access_hash,
            'file_reference': file_reference,
            'mime_type'     : mime_type,
            'file_type'     : file_type,
            'file_name'     : file_name,
            'file_size'     : file_size,
            'uploader_type' : 'user'
        })
    # B 分支保留消息，不删除


async def process_group_media_msg(msg):
    print(f"【Telethon】来自群组媒体回溯处理：{msg.media}，chat_id={msg.chat_id}", flush=True)

    if msg.document:
        media = msg.document
        file_type = 'document'
    elif msg.video:
        media = msg.video
        file_type = 'video'
    else:
        media = msg.photo
        file_type = 'photo'

    chat_id = msg.chat_id
    message_id = msg.id
    doc_id = media.id
    access_hash = media.access_hash
    file_reference = media.file_reference.hex()
    mime_type = getattr(media, 'mime_type', 'image/jpeg' if msg.photo else None)
    file_size = getattr(media, 'size', None)
    file_name = get_file_name(media)

    try:
        safe_execute("SELECT chat_id, message_id FROM file_records WHERE doc_id = %s", (doc_id,))
    except Exception as e:
        print(f"[process_group_media_msg] doc_id 查库失败: {e}", flush=True)
        return

    row = cursor.fetchone()
    if row:
        existing_chat_id, existing_msg_id = row
        upsert_file_record({
            'chat_id': chat_id,
            'message_id': message_id,
            'doc_id': doc_id,
            'access_hash': access_hash,
            'file_reference': file_reference,
            'mime_type': mime_type,
            'file_type': file_type,
            'file_name': file_name,
            'file_size': file_size,
            'uploader_type': 'user'
        })
    else:
        upsert_file_record({
            'chat_id': chat_id,
            'message_id': message_id,
            'doc_id': doc_id,
            'access_hash': access_hash,
            'file_reference': file_reference,
            'mime_type': mime_type,
            'file_type': file_type,
            'file_name': file_name,
            'file_size': file_size,
            'uploader_type': 'user'
        })


bot_client = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()

# —— 9.1 Aiogram：Bot 私聊 文本 处理 —— 

@dp.message(F.chat.type == "private", F.content_type.in_({ContentType.TEXT}))
async def aiogram_handle_private_text(message: types.Message):
    print(f"【Aiogram】收到私聊文本：{message.text}，来自 {message.from_user.id}",flush=True)
    # 只处理“私聊里发来的文本”
    if message.chat.type != "private" or message.content_type != ContentType.TEXT:
        return
    text = message.text.strip()
    to_user_id = message.chat.id
    reply_to_message = message.message_id

    # 检查 text 的长度是否少于 40 个字符
   

    if len(text)<40 and file_unique_id_pattern.fullmatch(text):
        await send_media_by_file_unique_id(bot_client, to_user_id, text, 'bot', reply_to_message)
    elif len(text)<40 and doc_id_pattern.fullmatch(text):
        await send_media_by_doc_id(bot_client, to_user_id, int(text), 'bot', reply_to_message)
    else:
        await message.delete()

# —— 9.2 Aiogram：Bot 私聊 媒体 处理 —— 
# 私聊媒体（图片/文档/视频）
@dp.message(F.chat.type == "private", F.content_type.in_({ContentType.PHOTO, ContentType.DOCUMENT, ContentType.VIDEO}))
async def aiogram_handle_private_media(message: types.Message):
    print(f"【Aiogram】收到私聊媒体：{message.content_type}，来自 {message.from_user.id}",flush=True)
    # 只处理“私聊里发来的媒体”
    if message.chat.type != "private" or message.content_type not in {
        ContentType.PHOTO, ContentType.DOCUMENT, ContentType.VIDEO
    }:
        return
    


    if message.photo:
        largest = message.photo[-1]
        file_id = largest.file_id
        file_unique_id = largest.file_unique_id
        mime_type = 'image/jpeg'
        file_type = 'photo'
        file_size = largest.file_size
        file_name = None
        # 用 Bot API 发到目标群组
      

    elif message.document:
        file_id = message.document.file_id
        file_unique_id = message.document.file_unique_id
        mime_type = message.document.mime_type
        file_type = 'document'
        file_size = message.document.file_size
        file_name = message.document.file_name
       

    else:  # 视频
        file_id = message.video.file_id
        file_unique_id = message.video.file_unique_id
        mime_type = message.video.mime_type or 'video/mp4'
        file_type = 'video'
        file_size = message.video.file_size
        file_name = getattr(message.video, 'file_name', None)
       

    # ⬇️ 检查是否已存在
    if await check_file_exists_by_unique_id(file_unique_id):
        print(f"已存在：{file_unique_id}，跳过转发",flush=True)

    else:
        ret = None
        # ⬇️ 发到群组
        if message.photo:
            ret = await bot_client.send_photo(TARGET_GROUP_ID, file_id)
        elif message.document:
            ret = await bot_client.send_document(TARGET_GROUP_ID, file_id)
        else:
            ret = await bot_client.send_video(TARGET_GROUP_ID, file_id)

        if ret.photo:
            largest = ret.photo[-1]
            file_unique_id = largest.file_unique_id
            file_id = largest.file_id
            file_type = 'photo'
            mime_type = 'image/jpeg'
            file_size = largest.file_size
            file_name = None

        elif ret.document:
            file_unique_id = ret.document.file_unique_id
            file_id = ret.document.file_id
            file_type = 'document'
            mime_type = ret.document.mime_type
            file_size = ret.document.file_size
            file_name = ret.document.file_name

        else:  # msg.video
            file_unique_id = ret.video.file_unique_id
            file_id = ret.video.file_id
            file_type = 'video'
            mime_type = ret.video.mime_type or 'video/mp4'
            file_size = ret.video.file_size
            file_name = getattr(ret.video, 'file_name', None)

        chat_id = ret.chat.id
        message_id = ret.message_id
        upsert_file_record({
                'file_unique_id': file_unique_id,
                'file_id'       : file_id,
                'file_type'     : file_type,
                'mime_type'     : mime_type,
                'file_name'     : file_name,
                'file_size'     : file_size,
                'uploader_type' : 'bot',
                'chat_id'       : chat_id,
                'message_id'    : message_id
            })

    # print(f"{ret} 已发送到目标群组：{TARGET_GROUP_ID}")
   
    await message.delete()

async def check_file_exists_by_unique_id(file_unique_id):
    """
    检查 file_unique_id 是否已存在于数据库中。
    """
    try:
        safe_execute("SELECT 1 FROM file_records WHERE file_unique_id = %s AND doc_id IS NOT NULL LIMIT 1", (file_unique_id,))
    except Exception as e:
        print(f"528 Error: {e}")
        
    return cursor.fetchone() is not None

# —— 9.3 Aiogram：Bot 群组 媒体 处理 —— 
# 群组媒体（图片/文档/视频），只处理指定群组
@dp.message(F.chat.id == TARGET_GROUP_ID, F.content_type.in_({ContentType.PHOTO, ContentType.DOCUMENT, ContentType.VIDEO}))
async def aiogram_handle_group_media(message: types.Message):
    
    # 只处理“指定群组里发来的媒体”
    if message.chat.id != TARGET_GROUP_ID or message.content_type not in {
        ContentType.PHOTO, ContentType.DOCUMENT, ContentType.VIDEO
    }:
        return

    
    msg = message

    if msg.photo:
        
        largest = msg.photo[-1]
        file_unique_id = largest.file_unique_id
        file_id = largest.file_id
        file_type = 'photo'
        mime_type = 'image/jpeg'
        file_size = largest.file_size
        file_name = None

    elif msg.document:
        file_unique_id = msg.document.file_unique_id
        file_id = msg.document.file_id
        file_type = 'document'
        mime_type = msg.document.mime_type
        file_size = msg.document.file_size
        file_name = msg.document.file_name

    else:  # msg.video
        file_unique_id = msg.video.file_unique_id
        file_id = msg.video.file_id
        file_type = 'video'
        mime_type = msg.video.mime_type or 'video/mp4'
        file_size = msg.video.file_size
        file_name = getattr(msg.video, 'file_name', None)

    chat_id = msg.chat.id
    message_id = msg.message_id

    try:
        # 检查是否已存在相同 file_unique_id 的记录
        safe_execute(
            "SELECT chat_id, message_id FROM file_records WHERE file_unique_id = %s",
            (file_unique_id,)
        )
    except Exception as e:
        print(f"578 Error: {e}")
   
    row = cursor.fetchone()
    if row:
        existing_chat_id, existing_msg_id = row
        if not (existing_chat_id == chat_id and existing_msg_id == message_id):
            upsert_file_record({
                'file_unique_id': file_unique_id,
                'file_id'       : file_id,
                'file_type'     : file_type,
                'mime_type'     : mime_type,
                'file_name'     : file_name,
                'file_size'     : file_size,
                'uploader_type' : 'bot',
                'chat_id'       : chat_id,
                'message_id'    : message_id
            })
            await bot_client.delete_message(chat_id, message_id)
        else:
            print(f"【Aiogram】新增 {message_id} by file_unique_idd",flush=True)
            upsert_file_record({
                'chat_id'       : chat_id,
                'message_id'    : message_id,
                'file_unique_id': file_unique_id,
                'file_id'       : file_id,
                'file_type'     : file_type,
                'mime_type'     : mime_type,
                'file_name'     : file_name,
                'file_size'     : file_size,
                'uploader_type' : 'bot'
            })
        return

    try:
        safe_execute(
            "SELECT id FROM file_records WHERE chat_id = %s AND message_id = %s",
            (chat_id, message_id)
        )
    except Exception as e:
        print(f"614 Error: {e}")

    if cursor.fetchone():
        upsert_file_record({
            'chat_id'       : chat_id,
            'message_id'    : message_id,
            'file_unique_id': file_unique_id,
            'file_id'       : file_id,
            'file_type'     : file_type,
            'mime_type'     : mime_type,
            'file_name'     : file_name,
            'file_size'     : file_size,
            'uploader_type' : 'bot'
        })
    else:
        print(f"【Aiogram】新增 {message_id} by chat_id+message_id",flush=True)
        upsert_file_record({
            'chat_id'       : chat_id,
            'message_id'    : message_id,
            'file_unique_id': file_unique_id,
            'file_id'       : file_id,
            'file_type'     : file_type,
            'mime_type'     : mime_type,
            'file_name'     : file_name,
            'file_size'     : file_size,
            'uploader_type' : 'bot'
        })


async def keep_alive_ping():
    url = f"{WEBHOOK_HOST}{WEBHOOK_PATH}" if BOT_MODE == "webhook" else f"{WEBHOOK_HOST}/"
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    print(f"🌐 Keep-alive ping {url} status {resp.status}")
        except Exception as e:
            print(f"⚠️ Keep-alive ping failed: {e}")
        await asyncio.sleep(300)  # 每 5 分鐘 ping 一次


# ================= 14. 启动两个客户端 =================
async def man_bot_loop():
    
    async for dialog in user_client.iter_dialogs():
        entity = dialog.entity

        if entity.id == 7294369541: 
            continue
        current_entiry_title = None
        entity_title = getattr(entity, 'title', None)
        if not entity_title:
            first_name = getattr(entity, 'first_name', '') or ''
            last_name = getattr(entity, 'last_name', '') or ''
            entity_title = f"{first_name} {last_name}".strip() or getattr(entity, 'title', f"Unknown entity {entity.id}")
        await asyncio.sleep(1)
        if dialog.unread_count >= 0:
            if dialog.is_user:
                # print(f"当前对话: {entity_title} ({entity.id})", flush=True)
                async for message in user_client.iter_messages(
                    entity,  limit=100, reverse=True, filter=InputMessagesFilterEmpty()
                ):
                   
                    # 先处理文字
                    if message.document or message.photo or message.video:
                        await process_private_media_msg(message)
                    elif message.text:
                        # 构造临时 event 对象调用现有 handler
                        class TempEvent:
                            pass
                        temp_event = TempEvent()
                        temp_event.message = message
                        await handle_user_private_text(temp_event)
                        continue
                    # 再处理媒体
                    elif isinstance(message.media, MessageMediaDocument):
                        # print(f"🗑️ 删除 MessageMediaDocument 消息 {message.id} from {entity.id}", flush=True)
                        await message.delete()
                        continue
                    else:
                        # print(f"【Telethon】跳过非媒体消息：{message} ", flush=True)
                        continue
                                    
            # ✅ 群组媒体补充处理
            elif dialog.is_group and dialog.entity.id == TARGET_GROUP_ID:
                if dialog.unread_count > 0:
                    # print(f"当前对话: {entity_title} ({entity.id})", flush=True)
                    async for message in user_client.iter_messages(
                        entity,
                        offset_id=dialog.read_marked_id,
                        limit=dialog.unread_count,
                        reverse=True,
                        filter=InputMessagesFilterEmpty()
                    ):
                        if message.document or message.photo or message.video:
                            await process_group_media_msg(message)               
            
   



async def main():

    await user_client.start(PHONE_NUMBER)
    # await keep_db_alive()

    me = await user_client.get_me()

       
    
    print(f'你的用户名: {me.username}',flush=True)
    print(f'你的ID: {me.id}')
    print(f'你的名字: {me.first_name} {me.last_name or ""}')
    print(f'是否是Bot: {me.bot}',flush=True)


    


    # Aiogram 任务
   
    aiogram_task = asyncio.create_task(dp.start_polling(bot_client))

    # Telethon 循环任务
    async def telethon_loop():
        start_time = time.time()
        while (time.time() - start_time) < MAX_PROCESS_TIME:
            try:
                await asyncio.wait_for(man_bot_loop(), timeout=600)
            except asyncio.TimeoutError:
                print("⚠️ 任务超时，跳过本轮", flush=True)
            finally:
                print("🔄 循环等待 30 秒后继续...", flush=True)
                await asyncio.sleep(30)
           
        print("🛑 Telethon 循环结束，准备取消 Aiogram...", flush=True)
        aiogram_task.cancel()

    try:
        await asyncio.gather(aiogram_task, telethon_loop())
    except asyncio.CancelledError:
        print("✅ Aiogram polling 已被取消。", flush=True)
    finally:
        print("🧹 清理完成，准备退出程序...", flush=True)
        await bot_client.session.close()
        await user_client.disconnect()
    

    

if __name__ == "__main__":
    with user_client:
        user_client.loop.run_until_complete(main())


