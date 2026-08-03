import os
import base64
import pymysql
import asyncio
import json
import time

import aiohttp
from telethon.errors import ChatForwardsRestrictedError
from telethon.sessions import StringSession
from telethon import TelegramClient, events
from telethon.tl.types import InputDocument,MessageMediaDocument
from telethon import events
from telethon.tl.types import InputMessagesFilterEmpty


# Aiogram 相关
from aiogram import F, Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import ContentType
from aiohttp import web

from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

import re

from utils import MediaUtils

# 常量
MAX_PROCESS_TIME = 40 * 60  # 最大运行时间 20 分钟


# ================= 1. 载入 .env 中的环境变量 =================



# 加载环境变量
if not os.getenv('GITHUB_ACTIONS'):
    from dotenv import load_dotenv,find_dotenv
    # env_path = find_dotenv('.25299903.warehouse.env', raise_error_if_not_found=True)
    # env_path = find_dotenv('.24690454.queue.env', raise_error_if_not_found=True)
    # load_dotenv(env_path, override=True)
    # load_dotenv(dotenv_path='.24690454.queue.env')
    load_dotenv(dotenv_path='.28817994.luzai.env')
    # load_dotenv(dotenv_path='.a25299903.warehouse.env')
    # print("✅ 成功加载 .env 文件", flush=True)




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


# ================= H. 初始化 Telethon 客户端 =================

# 初始化 Telethon 客户端
if SESSION_STRING:
    user_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    print(f"【Telethon】使用 StringSession 登录。",flush=True)
else:
    user_client = TelegramClient(USER_SESSION, API_ID, API_HASH)

# 初始化 Aiogram 客户端
bot_client = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()

media_utils = MediaUtils(
    db=db,
    bot_client=bot_client,
    user_client=user_client,
    lz_var_start_time=lz_var_start_time,
    config=config,
)

async def on_startup(bot: Bot):
    webhook_url = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
    print(f"🔗 設定 Telegram webhook 為：{webhook_url}")
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(webhook_url)
    lz_var_cold_start_flag = False  # 启动完成

# ================= H1. 私聊 Message 文字处理：人类账号 =================
@user_client.on(events.NewMessage(incoming=True))
async def handle_user_private_text(event):
    await media_utils.handle_user_private_text(event)
    return
    

# ================= H2-1. 私聊 Media 媒体处理：人类账号 =================
@user_client.on(events.NewMessage(incoming=True))
async def handle_user_private_media(event):
    await media_utils.handle_user_private_media(event)
    

# ================= H2-2. 私聊 Media 媒体处理：人类账号 =================
async def process_private_media_msg(msg):
    await media_utils.process_private_media_msg(msg)
    return
    
# ================= H3-1. 群组媒体处理：人类账号 =================
@user_client.on(events.NewMessage(chats=TARGET_GROUP_ID, incoming=True))
async def handle_user_group_media(event):
    await media_utils.handle_user_group_media(event)
    return
    

# ================= H3-2. 群组媒体处理：人类账号 =================
async def process_group_media_msg(msg):
    await media_utils.process_group_media_msg(msg)
    return
   
# ================= B1P. 私聊 Message 文字处理：Aiogram：BOT账号 =================
@dp.message(F.chat.type == "private", F.content_type.in_({ContentType.TEXT}))
async def aiogram_handle_private_text(message: types.Message):
    await media_utils.aiogram_handle_private_text(message)

# ================= B2P. 私聊 Message 媒体处理：Aiogram：BOT账号 =================
@dp.message(F.chat.type == "private", F.content_type.in_({ContentType.PHOTO, ContentType.DOCUMENT, ContentType.VIDEO, ContentType.ANIMATION}))
async def aiogram_handle_private_media(message: types.Message):
    await media_utils.aiogram_handle_private_media(message)
    return

# ================= B3G. 群聊 Message 图片/文档/视频处理：Aiogram：BOT账号 =================
@dp.message(F.chat.id == TARGET_GROUP_ID, F.content_type.in_({ContentType.PHOTO, ContentType.DOCUMENT, ContentType.VIDEO, ContentType.ANIMATION}))
async def aiogram_handle_group_media(message: types.Message):
    await media_utils.aiogram_handle_group_media(message)
    return
    

# ================= C. 启动两个客户端 =================


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
            
async def run_aiogram_60s():
    # 创建后台任务

    polling_task = asyncio.create_task(dp.start_polling(bot_client))
    print("▶️ Aiogram polling 启动", flush=True)

    try:
        await asyncio.sleep(120)  # 运行 60 秒
        print("⏱ Aiogram polling 60 秒到，准备终止...", flush=True)
    finally:
        polling_task.cancel()
        await dp.stop_polling()
        try:
            await polling_task
        except asyncio.CancelledError:
            print("✅ Aiogram polling 已取消", flush=True)

async def main():

    await user_client.start(PHONE_NUMBER)
    media_utils.start_media_forward_worker()
    # await keep_db_alive()
    await media_utils.set_bot_info()


    print(f'你的用户名: {media_utils.man_username} / {media_utils.bot_username}',flush=True)
    print(f'你的ID: {media_utils.man_id} / {media_utils.bot_id}',flush=True)
    # print(f'你的名字: {me.first_name} {me.last_name or ""}')
    # print(f'是否是Bot: {me.bot}',flush=True)




    


    # Aiogram 任务
    start_time = time.time()
   
    # await run_aiogram_60s()
    # Telethon 循环任务
   
       
    while (time.time() - start_time) < MAX_PROCESS_TIME:
        try:
            await asyncio.wait_for(man_bot_loop(), timeout=600)
        except asyncio.TimeoutError:
            print("⚠️ man_bot_loop 超时，跳过本轮", flush=True)

        print(f"【Telethon】等待 30 秒后继续...", flush=True)
        await asyncio.sleep(30)  # 确保有时间间隔
        

    await run_aiogram_60s()
    print("🛑 达到运行时间上限，正在清理...", flush=True)
    await bot_client.session.close()
    await user_client.disconnect()
    print("✅ 所有连接关闭，程序结束", flush=True)

if __name__ == "__main__":
    with user_client:
        user_client.loop.run_until_complete(main())

