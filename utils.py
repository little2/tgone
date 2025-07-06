import re
import asyncio
import aiohttp
from typing import Union
from aiogram import types, Bot
from telethon import events
from aiogram.types import ContentType
from telethon.tl.types import InputDocument, MessageMediaDocument, PeerUser
import time
from aiohttp import web
from telethon.errors import ChatForwardsRestrictedError

"""
telegram_media_utils.py
-----------------------
本模块包含 Telegram 媒体处理项目中 main.py 与 main2.py 共用的函数，供多客户端共用调用。

功能涵盖：
- Aiogram 与 Telethon 的媒体消息处理
- 重复判断
- 文本格式识别
- 关键常量定义

使用前提：
- 外部应提供 bot 实例、数据库连接、Telethon/Aiogram Dispatcher 等上下文环境
"""





class MediaUtils:


    def __init__(self, db, bot_client, user_client, lz_var_start_time, config):
        self.db = db
        self.bot_client = bot_client
        self.user_client = user_client
        self.lz_var_start_time = lz_var_start_time

        self.file_unique_id_pattern = re.compile(r'^[A-Za-z0-9_-]{14,}$')
        self.doc_id_pattern = re.compile(r'^\d+$')
        self.bot_id = 0
        self.man_username = None
        self.man_id = 0
        self.bot_username = None
        self.bot_id = 0
        self.config = config

        self.receive_file_unique_id = None

        


    async def set_bot_info(self):
        man_info = await self.user_client.get_me()
        self.man_id = man_info.id
        self.man_username = man_info.username

        bot_info = await self.bot_client.get_me()
        self.bot_id = bot_info.id
        self.bot_username = bot_info.username



    def safe_execute(self, sql, params=None):
        try:
            self.db.ping(reconnect=True)  # 使用 self.db
            cursor = self.db.cursor()     # 正确获取 cursor
            cursor.execute(sql, params or ())
            return cursor
        except Exception as e:
            print(f"⚠️ 数据库执行出错: {e}")
            return None

    def get_file_name(self, media):
        from telethon.tl.types import DocumentAttributeFilename
        for attr in getattr(media, 'attributes', []):
            if isinstance(attr, DocumentAttributeFilename):
                return attr.file_name
        return None

    def upsert_file_record(self, fields: dict):
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
            self.safe_execute(sql, values)
        except Exception as e:
            print(f"110 Error: {e}")

    async def heartbeat(self, ):
        while True:
            print("💓 Alive (Aiogram polling still running)")
            try:
                self.db.ping(reconnect=True)
                print("✅ MySQL 连接正常")
            except Exception as e:
                print(f"⚠️ MySQL 保活失败：{e}")
            await asyncio.sleep(600)

    async def health(self, request):
        uptime = time.time() - self.lz_var_start_time
        if self.lz_var_cold_start_flag or uptime < 10:
            return web.Response(text="⏳ Bot 正在唤醒，请稍候...", status=503)
        return web.Response(text="✅ Bot 正常运行", status=200)

    async def on_startup(self, bot: Bot):
        webhook_url = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
        print(f"🔗 設定 Telegram webhook 為：{webhook_url}")
        await bot.delete_webhook(drop_pending_updates=True)
        await bot.set_webhook(webhook_url)
        lz_var_cold_start_flag = False  # 启动完成

    
    # send_media_by_doc_id 函数 
    async def send_media_by_doc_id(self, client, to_user_id, doc_id, client_type,msg_id=None):
        print(f"【send_media_by_doc_id】开始处理 doc_id={doc_id}，目标用户：{to_user_id}",flush=True)

        try:
            cursor = self.safe_execute(
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
            await self.send_media_via_bot(client, to_user_id, row, msg_id)
        else:
            await self.send_media_via_man(client, to_user_id, row, msg_id)

    # send_media_by_file_unique_id 函数
    async def send_media_by_file_unique_id(self,client, to_user_id, file_unique_id, client_type, msg_id):
        
        print(f"【1】开始处理 file_unique_id={file_unique_id}，目标用户：{to_user_id}",flush=True)
        try:
            if client_type == 'bot':
                # 机器人账号发送
                cursor = self.safe_execute(
                    "SELECT chat_id, message_id, doc_id, access_hash, file_reference, file_id, file_unique_id,file_type FROM file_records WHERE file_unique_id = %s AND bot_id = %s",
                    (file_unique_id,self.bot_id,)
                )
            else:
                cursor = self.safe_execute(
                    "SELECT chat_id, message_id, doc_id, access_hash, file_reference, file_id, file_unique_id,file_type FROM file_records WHERE file_unique_id = %s AND man_id = %s",
                    (file_unique_id,self.man_id)
                )
            
            row = cursor.fetchone()
            print(f"【2】本机没纪录,查询其他机器人: 结果：{row}",flush=True)

            if not row:

                ext_row = await self.fetch_file_by_source_id(file_unique_id)
                print(f"【3】扩展查询结果：{ext_row}",flush=True)
                if ext_row:
                    # print(f"【send_media_by_file_unique_id】在 file_extension 中找到对应记录，尝试从 Bot 获取文件",flush=True)
                    # 如果在 file_extension 中找到对应记录，尝试从 Bot 获取文件
                    bot_row = await self.receive_file_from_bot(ext_row)
                    
                    max_retries = 3
                    delay = 2  # 每次重试的延迟时间（秒）

                    if not bot_row:
                        await client.send_message(to_user_id, f"未找到 file_unique_id={file_unique_id} 对应的文件。(182)")
                        return
                    else:
                        print(f"【4】回传的 BOT_ROW",flush=True)
                       
                        return "retrieved"

                        # chat_id, message_id, doc_id, access_hash, file_reference_hex, file_id, file_unique_id, file_type = row
                        # await client.send_message(to_user_id, f"未找到 file_unique_id={file_unique_id} 对应的文件。(192)")
                        # return
                        # return await self.send_media_by_file_unique_id(client, to_user_id, file_unique_id, client_type, msg_id)
                        # pass
                else:
                    await client.send_message(to_user_id, f"未找到 file_unique_id={file_unique_id} 对应的文件。(201)")
                    return
               
                
        
        except Exception as e:
            print(f"[194] Error: {e}")
            return
        
        print(f"【send_media_by_file_unique_id】查询结果：{client_type}",flush=True)
        if client_type == 'bot':
            # 机器人账号发送
            await self.send_media_via_bot(client, to_user_id, row, msg_id)
        else:

            await self.send_media_via_man(client, to_user_id, row, msg_id)

    async def extract_video_metadata_from_telethon(self,msg):
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
        file_name      = self.get_file_name(media)

        return doc_id, access_hash, file_reference, mime_type, file_size, file_name, file_type
       

    async def extract_video_metadata_from_aiogram(self,message):
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
        
        return file_id, file_unique_id, mime_type, file_type, file_size, file_name

    async def fetch_file_by_source_id(self, source_id: str):
        cursor = self.safe_execute("""
                SELECT f.file_type, f.file_id, f.bot, b.bot_id, b.bot_token, f.file_unique_id
                FROM file_extension f
                LEFT JOIN bot b ON f.bot = b.bot_name
                WHERE f.file_unique_id = %s
                LIMIT 0, 1
            """, (source_id,))
        row = cursor.fetchone()
        if not row:
            return None
        else:
            print(f"【fetch_file_by_source_id】找到对应记录：{row}",flush=True)
            return {
                "file_type": row[0],
                "file_id": row[1],
                "bot": row[2],
                "bot_id": row[3],
                "bot_token": row[4],
                "file_unique_id": row[5],
            }
    
    async def receive_file_from_bot(self, row):
        retSend = None
        bot_token = f"{row['bot_id']}:{row['bot_token']}"
    
        from aiogram import Bot
        # print(f"【receive_file_from_bot】开始处理 file_unique_id={row['file_unique_id']}，bot_id={row['bot_id']}",flush=True)
        mybot = Bot(token=bot_token)
        try:
            if row["file_type"] == "photo":
                retSend = await mybot.send_photo(chat_id=self.man_id, photo=row["file_id"])
            elif row["file_type"] == "video":
                retSend = await mybot.send_video(chat_id=self.man_id, video=row["file_id"])
            elif row["file_type"] == "document":
                retSend = await mybot.send_document(chat_id=self.man_id, document=row["file_id"])
        except Exception as e:
            await self.user_client.send_message(row["bot"], "/start")
            await self.user_client.send_message(row["bot"], "[~bot~]")
            print(f"❌ 目标 chat 不存在或无法访问: {e}")

        finally:
            await mybot.session.close()
            
            return retSend
            

        
        
    # send_media_via_man 函数 
    async def send_media_via_man(self, client, to_user_id, row, msg_id=None):
        # to_user_entity = await client.get_input_entity(to_user_id)
        chat_id, message_id, doc_id, access_hash, file_reference_hex, file_id, file_unique_id, file_type = row
        print(f"send_media_via_man",flush=True)
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
            print(f"准备发送文件：{input_doc.id}, {input_doc.access_hash}, {input_doc.file_reference.hex()}",flush=True)
            await client.send_file(to_user_id, input_doc, reply_to=msg_id)
        except Exception:
            # file_reference 过期时，重新从历史消息拉取
            try:
                msg = await client.get_messages(chat_id, ids=message_id)
                if not msg:
                    print(f"历史消息中未找到对应消息，可能已被删除。(286)",flush=True)
                else:
                    media = msg.document or msg.photo or msg.video
                    if not media:
                        print(f"历史消息中未找到对应媒体，可能已被删除。(290)",flush=True)
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



    # send_media_via_bot 函数
    async def send_media_via_bot(self, bot_client, to_user_id, row,msg_id=None):
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
    


    async def check_file_exists_by_unique_id(self, file_unique_id: str) -> bool:
        try:
            cursor = self.safe_execute(
                "SELECT 1 FROM file_records WHERE file_unique_id = %s AND bot_id = %s AND doc_id IS NOT NULL LIMIT 1",
                (file_unique_id,self.bot_id)
            )
            return cursor.fetchone() is not None if cursor else False
        except Exception as e:
            print(f"528 Error: {e}")
            return False

    async def keep_alive_ping(self, ):
        url = f"{WEBHOOK_HOST}{WEBHOOK_PATH}" if BOT_MODE == "webhook" else f"{WEBHOOK_HOST}/"
        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        print(f"🌐 Keep-alive ping {url} status {resp.status}")
            except Exception as e:
                print(f"⚠️ Keep-alive ping failed: {e}")
            await asyncio.sleep(300)  # 每 5 分鐘 ping 一次





# ================= BOT Text Private. 私聊 Message 文字处理：Aiogram：BOT账号 =================
    async def aiogram_handle_private_text(self, message: types.Message):
        print(f"【Aiogram】收到私聊文本：{message.text}，来自 {message.from_user.id}",flush=True)
        # 只处理“私聊里发来的文本”
        if message.chat.type != "private" or message.content_type != ContentType.TEXT:
            return
        text = message.text.strip()
        to_user_id = message.chat.id
        reply_to_message = message.message_id

        # 检查 text 的长度是否少于 40 个字符

        if len(text)<40 and self.file_unique_id_pattern.fullmatch(text):
            
            file_unique_id = text
            ret = await self.send_media_by_file_unique_id(self.bot_client, to_user_id, text, 'bot', reply_to_message)
            print(f">>>【Telethon】发送文件：{file_unique_id} 到 {to_user_id}，返回结果：{ret}",flush=True)
            if(ret=='retrieved'):
                print(f">>>>>【Telethon】已从 Bot 获取文件，准备发送到 {to_user_id}，file_unique_id={file_unique_id}",flush=True)
                async def delayed_resend():
                    for _ in range(6):  # 最多重试 6 次
                        try:
                            # 尝试发送文件
                            print(f"【Telethon】第 {_+1} 次尝试发送文件：{file_unique_id} 到 {to_user_id} {self.receive_file_unique_id}",flush=True)
                            if self.receive_file_unique_id == file_unique_id:
                                # 显示第几次
                                
                                
                                await self.send_media_by_file_unique_id(self.bot_client, to_user_id, text, 'bot', reply_to_message)
                                return
                            else:
                                await asyncio.sleep(0.5)
                        except Exception as e:
                            print(f"【Telethon】发送失败，重试中：{e}", flush=True)
                    await self.send_media_by_file_unique_id(self.bot_client, to_user_id, text, 'bot', reply_to_message)

                asyncio.create_task(delayed_resend())


        elif len(text)<40 and self.doc_id_pattern.fullmatch(text):
            await self.send_media_by_doc_id(self.bot_client, to_user_id, int(text), 'bot', reply_to_message)
        else:
            print("D480")
            await message.delete()

# ================= BOT TEXT Private. 私聊 Message 媒体处理：Aiogram：BOT账号 =================
    async def aiogram_handle_private_media(self, message: types.Message):
        TARGET_GROUP_ID = self.config.get('target_group_id')
        if message.chat.type != "private" or message.content_type not in {
            ContentType.PHOTO, ContentType.DOCUMENT, ContentType.VIDEO
        }:
            return

        print(f"【Aiogram】收到私聊媒体：{message.content_type}，来自 {message.from_user.id}",flush=True)
        # 只处理“私聊里发来的媒体”

        file_id, file_unique_id, mime_type, file_type, file_size, file_name = await self.extract_video_metadata_from_aiogram(message)

        

        # ⬇️ 检查是否已存在
        if await self.check_file_exists_by_unique_id(file_unique_id):
            print(f"已存在：{file_unique_id}，跳过转发",flush=True)

        else:
            ret = None
            # ⬇️ 发到群组
            if message.photo:
                ret = await self.bot_client.send_photo(TARGET_GROUP_ID, file_id)
            elif message.document:
                ret = await self.bot_client.send_document(TARGET_GROUP_ID, file_id)
            else:
                ret = await self.bot_client.send_video(TARGET_GROUP_ID, file_id)

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
            self.upsert_file_record({
                    'file_unique_id': file_unique_id,
                    'file_id'       : file_id,
                    'file_type'     : file_type,
                    'mime_type'     : mime_type,
                    'file_name'     : file_name,
                    'file_size'     : file_size,
                    'uploader_type' : 'bot',
                    'chat_id'       : chat_id,
                    'message_id'    : message_id,
                    'bot_id'       : self.bot_id
                })

        # print(f"{ret} 已发送到目标群组：{TARGET_GROUP_ID}")
   
        await message.delete()
        print("D555 aiogram_handle_private_media")



# ================= BOT Media Group. 群聊 Message 图片/文档/视频处理：Aiogram：BOT账号 =================
    async def aiogram_handle_group_media(self, message: types.Message):
        TARGET_GROUP_ID = self.config.get('target_group_id')
        # 只处理“指定群组里发来的媒体”
        if message.chat.id != TARGET_GROUP_ID or message.content_type not in {
            ContentType.PHOTO, ContentType.DOCUMENT, ContentType.VIDEO
        }:
            return

        print(f"【Aiogram】收到群聊媒体：{message.content_type}，来自 {message.from_user.id}",flush=True)

        
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

        self.receive_file_unique_id = file_unique_id

        try:
            # 检查是否已存在相同 file_unique_id 的记录
            cursor =self.safe_execute(
                "SELECT chat_id, message_id FROM file_records WHERE file_unique_id = %s AND bot_id = %s",
                (file_unique_id,self.bot_id)
            )
        except Exception as e:
            print(f"578 Error: {e}")
    
        row = cursor.fetchone()
        if row:
            existing_chat_id, existing_msg_id = row
            if not (existing_chat_id == chat_id and existing_msg_id == message_id):
                self.upsert_file_record({
                    'file_unique_id': file_unique_id,
                    'file_id'       : file_id,
                    'file_type'     : file_type,
                    'mime_type'     : mime_type,
                    'file_name'     : file_name,
                    'file_size'     : file_size,
                    'uploader_type' : 'bot',
                    'chat_id'       : chat_id,
                    'message_id'    : message_id,
                    'bot_id'        : self.bot_id
                })
                print(f"【Aiogram】删除重覆 {message_id} by file_unique_id",flush=True)
                await self.bot_client.delete_message(chat_id, message_id)
                print("D631")
            else:
                print(f"【Aiogram】新增 {message_id} by file_unique_idd",flush=True)
                self.upsert_file_record({
                    'chat_id'       : chat_id,
                    'message_id'    : message_id,
                    'file_unique_id': file_unique_id,
                    'file_id'       : file_id,
                    'file_type'     : file_type,
                    'mime_type'     : mime_type,
                    'file_name'     : file_name,
                    'file_size'     : file_size,
                    'uploader_type' : 'bot',
                    'bot_id'        : self.bot_id
                })
            return

        try:
            cursor = self.safe_execute(
                "SELECT id FROM file_records WHERE chat_id = %s AND message_id = %s",
                (chat_id, message_id)
            )
        except Exception as e:
            print(f"614 Error: {e}")

        if cursor.fetchone():
            self.upsert_file_record({
                'chat_id'       : chat_id,
                'message_id'    : message_id,
                'file_unique_id': file_unique_id,
                'file_id'       : file_id,
                'file_type'     : file_type,
                'mime_type'     : mime_type,
                'file_name'     : file_name,
                'file_size'     : file_size,
                'uploader_type' : 'bot',
                'bot_id'        : self.bot_id
            })
        else:
            print(f"【Aiogram】新增 {message_id} by chat_id+message_id",flush=True)
            self.upsert_file_record({
                'chat_id'       : chat_id,
                'message_id'    : message_id,
                'file_unique_id': file_unique_id,
                'file_id'       : file_id,
                'file_type'     : file_type,
                'mime_type'     : mime_type,
                'file_name'     : file_name,
                'file_size'     : file_size,
                'uploader_type' : 'bot',
                'bot_id'        : self.bot_id
            })



    # ================= Human Private Text  私聊 Message 文字处理：人类账号 =================
    async def handle_user_private_text(self,event):
        
        msg = event.message
        if not msg.is_private or msg.media or not msg.text:
            return

        to_user_id = msg.from_id

        print(f"【Telethon】{msg}",flush=True)
        
        # 获取发信人 ID
        try:
            sender = await event.get_sender()
            to_user_id = sender.id
        except Exception as e:
            print(f"⚠️ 获取 sender 失败：{e}")
            await msg.delete()
            print("D704")
            return

        # print(f"【Telethon】收到私聊文本：来自 {to_user_id}",flush=True)
        text = msg.text.strip()

        if text:
            try:
                match = re.search(r'\|_kick_\|\s*(.*?)\s*(bot)', text, re.IGNORECASE)
                if match:
                    botname = match.group(1) + match.group(2)
                    await self.user_client.send_message(botname, "/start")
                    await self.user_client.send_message(botname, "[~bot~]")
                    await msg.delete()
                    print("D717")
                    return
            except Exception as e:
                    print(f"Error kicking bot: {e} {botname}", flush=True)

        

        if len(text)<40 and self.file_unique_id_pattern.fullmatch(text):
            file_unique_id = text
            ret = await self.send_media_by_file_unique_id(self.user_client, to_user_id, file_unique_id, 'man', msg.id)
            print(f">>>【Telethon】发送文件：{file_unique_id} 到 {to_user_id}，返回结果：{ret}",flush=True)
            if(ret=='retrieved'):
                print(f">>>>>【Telethon】已从 Bot 获取文件，准备发送到 {to_user_id}，file_unique_id={file_unique_id}",flush=True)
                async def delayed_resend():
                    for _ in range(6):  # 最多重试 6 次
                        try:
                            # 尝试发送文件
                            print(f"【Telethon】第 {_+1} 次尝试发送文件：{file_unique_id} 到 {to_user_id} {self.receive_file_unique_id}",flush=True)
                            if self.receive_file_unique_id == file_unique_id:
                                # 显示第几次
                                
                                
                                await self.send_media_by_file_unique_id(self.user_client, to_user_id, file_unique_id, 'man', msg.id)
                                return
                            else:
                                await asyncio.sleep(0.5)
                        except Exception as e:
                            print(f"【Telethon】发送失败，重试中：{e}", flush=True)
                    await self.send_media_by_file_unique_id(self.user_client, to_user_id, file_unique_id, 'man', msg.id)

                asyncio.create_task(delayed_resend())

        elif len(text)<40 and self.doc_id_pattern.fullmatch(text):
            doc_id = int(text)
            await self.send_media_by_doc_id(self.user_client, to_user_id, doc_id, 'man', msg.id)
        
        else:
            await msg.delete()
            print("D755")




    # ================= Human Private Meddia 私聊 Media 媒体处理：人类账号 =================
    async def handle_user_private_media(self,event):
        TARGET_GROUP_ID = self.config.get('target_group_id')
        msg = event.message
        await self.process_private_media_msg(msg, event)
        return
    
        if not msg.is_private or not (msg.document or msg.photo or msg.video):
            # print(f"【Telethon】收到私聊媒体，但不处理：，来自 {event.message.from_id}",flush=True)
            return
        print(f"【Telethon】收到私聊媒体，来自 {event.message.from_id}",flush=True)
    
        print(f"{msg}",flush=True)
        print(f"{event.message.text}",flush=True)
        
        doc_id, access_hash, file_reference, mime_type, file_size, file_name, file_type = await self.extract_video_metadata_from_telethon(msg)  
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
                print(f"📌 获取实体：{destination_chat_id}", flush=True)
                entity = await self.user_client.get_entity(destination_chat_id)
                ret = await self.user_client.send_file(entity, msg.media)
            #     print(f"✅ 成功发送到 {destination_chat_id}，消息 ID：{ret.id}", flush=True)
            # except Exception as e:
            #     print(f"❌ 无法发送到 {destination_chat_id}：{e}", flush=True)


            # try:
            #     ret = await user_client.send_file(destination_chat_id, msg.media)
                print(f"【Telethon】已转发到目标群组：{destination_chat_id}，消息 ID：{ret.id}",flush=True)
                print(f"{ret}",flush=True)
            except ChatForwardsRestrictedError:
                print(f"⚠️ 该媒体来自受保护频道，无法转发，已跳过。msg.id = {msg.id}", flush=True)
                return  # ⚠️ 不处理，直接跳出
            except Exception as e:
                print(f"❌ 其他发送失败(429)：{e}", flush=True)
                return

        # 检查：TARGET_GROUP_ID 群组是否已有相同 doc_id
        try:
            cursor = self.safe_execute(
                "SELECT 1 FROM file_records WHERE doc_id = %s AND chat_id = %s AND file_unique_id IS NOT NULL",
                (doc_id, TARGET_GROUP_ID)
            )
        except Exception as e:
            print(f"272 Error: {e}")
            
        if cursor.fetchone():
            print(f"【Telethon】已存在 doc_id={doc_id} 的记录，跳过转发", flush=True)
            await event.delete()
            return

        # 转发到群组，并删除私聊
        try:
            # 这里直接发送 msg.media，如果受保护会被阻止
            print(f"⚠️ 【Telethon】准备发送到目标群组：{TARGET_GROUP_ID}", flush=True)
            ret = await self.user_client.send_file(TARGET_GROUP_ID, msg.media)
        except ChatForwardsRestrictedError:
            print(f"🚫 跳过：该媒体来自受保护频道 msg.id = {msg.id}", flush=True)
            return
        except Exception as e:
            print(f"❌ 其他错误：{e}", flush=True)
            return

        



        # 插入或更新 placeholder 记录 (message_id 自动留空，由群组回调补全)
        self.upsert_file_record({
            'chat_id'       : ret.chat_id,
            'message_id'    : ret.id,
            'doc_id'        : doc_id,
            'access_hash'   : access_hash,
            'file_reference': file_reference,
            'mime_type'     : mime_type,
            'file_type'     : file_type,
            'file_name'     : file_name,
            'file_size'     : file_size,
            'uploader_type' : 'user',
            'man_id'        : self.man_id
            
        })
        await event.delete()  

    async def process_private_media_msg(self,msg,event=None):
        TARGET_GROUP_ID = self.config.get('target_group_id')
        if not msg.is_private or not (msg.document or msg.photo or msg.video):  
            # await msg.delete()
            print("D865 process_private_media_msg")
            # print(f"【Telethon】收到私聊媒体，但不处理：，来自 {event.message.from_id}",flush=True)
            return
        
        if(event is None):
            print(f"【Telethon】来自私聊媒体回溯处理：{msg.media}，chat_id={msg.chat_id}", flush=True)
        else:
            print(f"【Telethon】收到私聊媒体，来自 {event.message.from_id}",flush=True)
            print(f"{event.message.text}",flush=True)
            caption        = event.message.text or ""
    
        doc_id, access_hash, file_reference, mime_type, file_size, file_name, file_type = await self.extract_video_metadata_from_telethon(msg)  
        
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
                print(f"📌 获取实体：{destination_chat_id}", flush=True)
                entity = await self.user_client.get_entity(destination_chat_id)
                ret = await self.user_client.send_file(entity, msg.media)
            #     print(f"✅ 成功发送到 {destination_chat_id}，消息 ID：{ret.id}", flush=True)
            # except Exception as e:
            #     print(f"❌ 无法发送到 {destination_chat_id}：{e}", flush=True)


            # try:
            #     ret = await user_client.send_file(destination_chat_id, msg.media)
                print(f"【Telethon】已转发到目标群组：{destination_chat_id}，消息 ID：{ret.id}",flush=True)
                print(f"{ret}",flush=True)
            except ChatForwardsRestrictedError:
                print(f"⚠️ 该媒体来自受保护频道，无法转发，已跳过。msg.id = {msg.id}", flush=True)
                return  # ⚠️ 不处理，直接跳出
            except Exception as e:
                print(f"❌ 其他发送失败(429)：{e}", flush=True)
                return

        # 检查：TARGET_GROUP_ID 群组是否已有相同 doc_id
        try:
            cursor = self.safe_execute(
                "SELECT 1 FROM file_records WHERE doc_id = %s AND chat_id = %s AND file_unique_id IS NOT NULL",
                (doc_id, TARGET_GROUP_ID)
            )
        except Exception as e:
            print(f"272 Error: {e}")
            
        if cursor.fetchone():
            print(f"【Telethon】已存在 doc_id={doc_id} 的记录，跳过转发", flush=True)
            # await event.delete()
            await msg.delete()
            print("D926")
            return

        # 转发到群组，并删除私聊
        try:
            # 这里直接发送 msg.media，如果受保护会被阻止
            print(f"⚠️ 【Telethon】准备发送到目标群组：{TARGET_GROUP_ID}", flush=True)
            ret = await self.user_client.send_file(TARGET_GROUP_ID, msg.media)
        except ChatForwardsRestrictedError:
            print(f"🚫 跳过：该媒体来自受保护频道 msg.id = {msg.id}", flush=True)
            return
        except Exception as e:
            print(f"❌ 其他错误：{e}", flush=True)
            return

        



        # 插入或更新 placeholder 记录 (message_id 自动留空，由群组回调补全)
        self.upsert_file_record({
            'chat_id'       : ret.chat_id,
            'message_id'    : ret.id,
            'doc_id'        : doc_id,
            'access_hash'   : access_hash,
            'file_reference': file_reference,
            'mime_type'     : mime_type,
            'file_type'     : file_type,
            'file_name'     : file_name,
            'file_size'     : file_size,
            'uploader_type' : 'user',
            'man_id'        : self.man_id
            
        })
        print("D952 process_private_media_msg")
        await msg.delete() 

            
    # ================= Human Group Media 3-1. 群组媒体处理：人类账号 =================
    async def handle_user_group_media(self,event):
        msg = event.message
        await self.process_group_media_msg(msg)

    async def process_group_media_msg(self,msg):
        
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
        file_name      = self.get_file_name(media)

        # —— 步骤 A：先按 doc_id 查库 —— 
        try:
            # 检查是否已存在相同 doc_id 的记录
            cursor= self.safe_execute(
                "SELECT chat_id, message_id FROM file_records WHERE doc_id = %s AND man_id = %s",
                (doc_id,self.man_id)
            )
        except Exception as e:
            print(f"[process_group_media_msg] doc_id 查库失败: {e}", flush=True)
    
        row = cursor.fetchone()
        if row:
            existing_chat_id, existing_msg_id = row
            if not (existing_chat_id == chat_id and existing_msg_id == message_id):
                print(f"【Telethon】在指定群组，收到群组媒体：来自 {msg.chat_id}",flush=True)
    
                # 重复上传到不同消息 → 更新并删除新消息
                self.upsert_file_record({
                    'doc_id'        : doc_id,
                    'access_hash'   : access_hash,
                    'file_reference': file_reference,
                    'mime_type'     : mime_type,
                    'file_type'     : file_type,
                    'file_name'     : file_name,
                    'file_size'     : file_size,
                    'uploader_type' : 'user',
                    'chat_id'       : chat_id,
                    'message_id'    : message_id,
                    'man_id'        : self.man_id
                })
                print("D1015")
                await msg.delete()
            else:
                # 同一条消息重复触发 → 仅更新，不删除
                self.upsert_file_record({
                    'chat_id'       : chat_id,
                    'message_id'    : message_id,
                    'access_hash'   : access_hash,
                    'file_reference': file_reference,
                    'mime_type'     : mime_type,
                    'file_type'     : file_type,
                    'file_name'     : file_name,
                    'file_size'     : file_size,
                    'uploader_type' : 'user',
                    'man_id'        : self.man_id
                })
            return

        # —— 步骤 B：若 A 中没找到，再按 (chat_id, message_id) 查库 ——
        try:
            self.safe_execute(
                "SELECT id FROM file_records WHERE chat_id = %s AND message_id = %s",
                (chat_id, message_id)
            )
        except Exception as e:
            print(f"372 Error: {e}")
        if cursor.fetchone():
            # 已存在同条消息 → 更新并保留
            self.upsert_file_record({
                'chat_id'       : chat_id,
                'message_id'    : message_id,
                'doc_id'        : doc_id,
                'access_hash'   : access_hash,
                'file_reference': file_reference,
                'mime_type'     : mime_type,
                'file_type'     : file_type,
                'file_name'     : file_name,
                'file_size'     : file_size,
                'uploader_type' : 'user',
                'man_id'        : self.man_id
            })
        else:
            # 全新媒体 → 插入并保留
            self.upsert_file_record({
                'chat_id'       : chat_id,
                'message_id'    : message_id,
                'doc_id'        : doc_id,
                'access_hash'   : access_hash,
                'file_reference': file_reference,
                'mime_type'     : mime_type,
                'file_type'     : file_type,
                'file_name'     : file_name,
                'file_size'     : file_size,
                'uploader_type' : 'user',
                'man_id'        : self.man_id
            })
        # B 分支保留消息，不删除