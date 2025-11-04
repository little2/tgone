import re
import asyncio
import aiohttp
from typing import Union, Literal, Optional
from aiogram import types, Bot
from telethon import events
from aiogram.types import ContentType
from telethon.tl.types import InputDocument, MessageMediaDocument, PeerUser
import time
from aiohttp import web
from telethon.errors import ChatForwardsRestrictedError
from aiogram.exceptions import (
    TelegramNetworkError, TelegramRetryAfter, TelegramBadRequest,
    TelegramForbiddenError, TelegramNotFound
)
import aiomysql

class MediaUtils:
    def __init__(self, *, pool: aiomysql.Pool, bot_client: Bot, user_client, lz_var_start_time, config):
        self.pool = pool
        self.bot_client = bot_client
        self.user_client = user_client
        self.lz_var_start_time = lz_var_start_time

        self.file_unique_id_pattern = re.compile(r'^[A-Za-z0-9_-]{14,}$')
        self.doc_id_pattern = re.compile(r'^\d+$')
        self.bot_id = 0
        self.man_username = None
        self.man_id = 0
        self.bot_username = None
        self.config = config

        self.receive_file_unique_id = None

    # -------------------- 通用 DB Helper --------------------
    async def db_exec(self, sql: str, params: Optional[list | tuple] = None, *, fetch: Literal['one','all',None] = None):
        """Execute SQL via aiomysql pool.
        fetch=None → no fetch; 'one' → fetchone; 'all' → fetchall
        Returns fetched rows when requested, otherwise affected rows.
        """
        await self.ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                try:
                    await cur.execute(sql, params or ())
                    if fetch == 'one':
                        return await cur.fetchone()
                    if fetch == 'all':
                        return await cur.fetchall()
                    return cur.rowcount
                except Exception as e:
                    print(f"❌ 数据库执行出错: {e}\nSQL: {sql}\nParams: {params}")
                    return None

    async def ensure_pool(self):
        if self.pool is None or self.pool.closed:
            raise RuntimeError("MySQL pool is not initialized")

    # -------------------- 业务方法 --------------------
    async def set_file_vaild_state(self, file_unique_id: str, vaild_state: int = 1):
        sql = """
            UPDATE sora_content
            SET valid_state = %s, stage = 'pending'
            WHERE source_id = %s
        """
        await self.db_exec(sql, [vaild_state, file_unique_id])

    async def set_bot_info(self):
        man_info = await self.user_client.get_me()
        self.man_id = man_info.id
        self.man_username = man_info.username

        bot_info = await self.bot_client.get_me()
        self.bot_id = bot_info.id
        self.bot_username = bot_info.username

    def get_file_name(self, media):
        from telethon.tl.types import DocumentAttributeFilename
        for attr in getattr(media, 'attributes', []):
            if isinstance(attr, DocumentAttributeFilename):
                return attr.file_name
        return None

    async def upsert_file_record(self, fields: dict):
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
        await self.db_exec(sql, values)

    async def heartbeat(self):
        while True:
            print("💓 Alive (Aiogram polling still running)")
            try:
                await self.ensure_pool()
                async with self.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute("SELECT 1")
                        await cur.fetchone()
                print("✅ MySQL 连接正常")
            except Exception as e:
                print(f"⚠️ MySQL 保活失败：{e}")
            await asyncio.sleep(600)

    # -------------------- 发送逻辑 --------------------
    async def send_media_by_doc_id(self, client, to_user_id, doc_id, client_type, msg_id=None):
        print(f"【send_media_by_doc_id】开始处理 doc_id={doc_id}，目标用户：{to_user_id}", flush=True)
        row = await self.db_exec(
            "SELECT chat_id, message_id, doc_id, access_hash, file_reference, file_id, file_unique_id, file_type "
            "FROM file_records WHERE doc_id = %s",
            (doc_id,), fetch='one')
        if not row:
            if client_type == 'man':
                try:
                    to_user_entity = await client.get_input_entity(to_user_id)
                    await client.send_message(to_user_entity, f"未找到 doc_id={doc_id} 对应的文件。(176)")
                except Exception as e:
                    print(f"获取用户实体失败: {e}")
                    await client.send_message('me', f"无法获取用户实体: {to_user_id}")
            else:
                await client.send_message(to_user_id, f"未找到 doc_id={doc_id} 对应的文件。(181)")
            return

        if client_type == 'bot':
            await self.send_media_via_bot(client, to_user_id, row, reply_to_message_id=msg_id)
        else:
            await self.send_media_via_man(client, to_user_id, row, reply_to_message_id=msg_id)

    async def send_media_by_file_unique_id(self, client, to_user_id, file_unique_id, client_type, msg_id):
        print(f"【1】开始处理 file_unique_id={file_unique_id}，目标用户：{to_user_id}", flush=True)
        if client_type == 'bot':
            row = await self.db_exec(
                "SELECT chat_id, message_id, doc_id, access_hash, file_reference, file_id, file_unique_id, file_type "
                "FROM file_records WHERE file_unique_id = %s AND bot_id = %s",
                (file_unique_id, self.bot_id), fetch='one')
        else:
            row = await self.db_exec(
                "SELECT chat_id, message_id, doc_id, access_hash, file_reference, file_id, file_unique_id, file_type "
                "FROM file_records WHERE file_unique_id = %s AND man_id = %s",
                (file_unique_id, self.man_id), fetch='one')

        print(f"【2】本机查询纪录: 结果：{row}", flush=True)
        if not row:
            ext_row = await self.fetch_file_by_source_id(file_unique_id)
            print(f"【3】扩展查询结果：{ext_row}", flush=True)
            if ext_row:
                bot_row = await self.receive_file_from_bot(ext_row)
                if not bot_row:
                    await client.send_message(to_user_id, f"未找到 file_unique_id={file_unique_id} 对应的文件。(182)", reply_to=msg_id)
                    return
                else:
                    print(f"【4】其他机器人已将资源传给人型机器人 {file_unique_id}", flush=True)
                    return "retrieved"
            else:
                await client.send_message(to_user_id, f"未找到 file_unique_id={file_unique_id} 对应的文件。(201)", reply_to=msg_id)
                await self.set_file_vaild_state(file_unique_id, vaild_state=4)
                return
        else:
            await self.set_file_vaild_state(file_unique_id, vaild_state=9)

        print(f"【send_media_by_file_unique_id】查询结果：{client_type}", flush=True)
        if client_type == 'bot':
            await self.send_media_via_bot(client, to_user_id, row, reply_to_message_id=msg_id)
        else:
            await self.send_media_via_man(client, to_user_id, row, reply_to_message_id=msg_id)

    async def extract_video_metadata_from_telethon(self, msg):
        file_type = ''
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

    async def extract_video_metadata_from_aiogram(self, message):
        if message.photo:
            largest = message.photo[-1]
            file_id = largest.file_id
            file_unique_id = largest.file_unique_id
            mime_type = 'image/jpeg'
            file_type = 'photo'
            file_size = largest.file_size
            file_name = None
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
        row = await self.db_exec(
            """
            SELECT f.file_type, f.file_id, f.bot, b.bot_id, b.bot_token, f.file_unique_id
            FROM file_extension f
            LEFT JOIN bot b ON f.bot = b.bot_name
            WHERE f.file_unique_id = %s
            LIMIT 0, 1
            """,
            (source_id,), fetch='one')
        if not row:
            return None
        else:
            print(f"【fetch_file_by_source_id】找到对应记录：{row}", flush=True)
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
        print(f"4️⃣【receive_file_from_bot】开始处理 file_unique_id={row['file_unique_id']}，bot_id={row['bot_id']}", flush=True)
        mybot = Bot(token=bot_token)
        try:
            print(f"4️⃣【receive_file_from_bot】准备让机器人{row['bot_id']}发送文件file_unique_id={row['file_unique_id']}给{self.man_id}", flush=True)
            if row["file_type"] == "photo":
                retSend = await mybot.send_photo(chat_id=self.man_id, photo=row["file_id"])
            elif row["file_type"] == "video":
                retSend = await mybot.send_video(chat_id=self.man_id, video=row["file_id"])
            elif row["file_type"] == "document":
                retSend = await mybot.send_document(chat_id=self.man_id, document=row["file_id"])
            elif row["file_type"] == "animation":
                retSend = await mybot.send_animation(chat_id=self.man_id, animation=row["file_id"])
            print(f"4️⃣{row['file_unique_id']}【receive_file_from_bot】文件已发送到人型机器人", flush=True)
        except TelegramForbiddenError as e:
            print(f"4️⃣{row['file_unique_id']} 发送被拒绝（Forbidden）: {e}", flush=True)
        except TelegramNotFound:
            print(f"4️⃣{row['file_unique_id']} chat not found: {self.man_id}", flush=True)
            await self.user_client.send_message(row["bot"], "/start")
            await self.user_client.send_message(row["bot"], "[~bot~]")
        except TelegramBadRequest as e:
            await self.user_client.send_message(row["bot"], "/start")
            await self.user_client.send_message(row["bot"], "[~bot~]")
            print(f"4️⃣{row['file_unique_id']} 发送失败（BadRequest）: {e}", flush=True)
        except Exception as e:
            print(f"4️⃣{row['file_unique_id']} ❌ 发送失败: {e}", flush=True)
        finally:
            await mybot.session.close()
            return retSend

    async def send_media_via_man(self, client, to_user_id, row, reply_to_message_id=None):
        chat_id, message_id, doc_id, access_hash, file_reference_hex, file_id, file_unique_id, file_type = row
        try:
            file_reference = bytes.fromhex(file_reference_hex)
        except Exception:
            import base64
            try:
                file_reference = base64.b64decode(file_reference_hex)
            except Exception:
                await client.send_message(to_user_id, "文件引用格式异常，无法发送。")
                return

        input_doc = InputDocument(id=doc_id, access_hash=access_hash, file_reference=file_reference)
        try:
            await client.send_file(to_user_id, input_doc, reply_to=reply_to_message_id)
        except Exception:
            try:
                msg = await client.get_messages(chat_id, ids=message_id)
                if not msg:
                    await client.send_message(to_user_id, "历史消息中未找到对应媒体，可能已被删除。")
                    return
                media = msg.document or msg.photo or msg.video
                if not media:
                    await client.send_message(to_user_id, "历史消息中未找到对应媒体，可能已被删除。")
                    return
                if msg.document:
                    new_input = InputDocument(id=msg.document.id, access_hash=msg.document.access_hash, file_reference=msg.document.file_reference)
                elif msg.photo:
                    new_input = msg.photo
                else:
                    await client.send_message(to_user_id, "暂不支持此媒体类型。")
                    return
                await client.send_file(to_user_id, new_input, reply_to=reply_to_message_id)
            except Exception as e:
                await client.send_message(to_user_id, f"发送文件时出错：{e}")

    async def send_media_via_bot(self, bot_client, to_user_id, row, reply_to_message_id=None):
        chat_id, message_id, doc_id, access_hash, file_reference_hex, file_id, file_unique_id, file_type = row
        try:
            if file_type == "photo":
                await bot_client.send_photo(to_user_id, file_id, reply_to_message_id=reply_to_message_id)
            elif file_type == "video":
                await bot_client.send_video(to_user_id, file_id, reply_to_message_id=reply_to_message_id)
            elif file_type == "document":
                await bot_client.send_document(to_user_id, file_id, reply_to_message_id=reply_to_message_id)
            elif file_type == "animation":
                await bot_client.send_animation(to_user_id, file_id, reply_to_message_id=reply_to_message_id)
        except Exception as e:
            await bot_client.send_message(to_user_id, f"⚠️ 发送文件失败：{e}")

    async def check_file_exists_by_unique_id(self, file_unique_id: str) -> bool:
        row = await self.db_exec(
            "SELECT 1 FROM file_records WHERE file_unique_id = %s AND bot_id = %s AND doc_id IS NOT NULL LIMIT 1",
            (file_unique_id, self.bot_id), fetch='one')
        return row is not None

    # ================= BOT Text Private =================
    async def aiogram_handle_private_text(self, message: types.Message):
        print(f"【Aiogram】收到私聊文本：{message.text}，来自 {message.chat.first_name}", flush=True)
        if message.chat.type != "private" or message.content_type != ContentType.TEXT:
            return
        text = message.text.strip()
        to_user_id = message.chat.id
        reply_to_message = message.message_id

        if len(text) < 40 and self.file_unique_id_pattern.fullmatch(text):
            file_unique_id = text
            ret = await self.send_media_by_file_unique_id(self.bot_client, to_user_id, text, 'bot', reply_to_message)
            if ret == 'retrieved':
                async def delayed_resend():
                    for _ in range(6):
                        try:
                            if self.receive_file_unique_id == file_unique_id:
                                await self.send_media_by_file_unique_id(self.bot_client, to_user_id, text, 'bot', reply_to_message)
                                return
                            else:
                                await asyncio.sleep(0.5)
                        except Exception as e:
                            print(f"【Telethon】发送失败，重试中：{e}", flush=True)
                    await self.send_media_by_file_unique_id(self.bot_client, to_user_id, text, 'bot', reply_to_message)
                asyncio.create_task(delayed_resend())
            else:
                print(f">>>>>【Aiogram】文件已发送到 {to_user_id}，file_unique_id={file_unique_id}", flush=True)
        elif len(text) < 40 and self.doc_id_pattern.fullmatch(text):
            await self.send_media_by_doc_id(self.bot_client, to_user_id, int(text), 'bot', reply_to_message)
        else:
            print("D480")
            await message.delete()

    # ================= BOT Media Private =================
    async def aiogram_handle_private_media(self, message: types.Message):
        TARGET_GROUP_ID = self.config.get('target_group_id')
        if message.chat.type != "private" or message.content_type not in {ContentType.PHOTO, ContentType.DOCUMENT, ContentType.VIDEO, ContentType.ANIMATION}:
            return
        print(f"【Aiogram】收到私聊媒体：{message.content_type}，来自 {message.from_user.id}", flush=True)
        file_id, file_unique_id, mime_type, file_type, file_size, file_name = await self.extract_video_metadata_from_aiogram(message)

        if await self.check_file_exists_by_unique_id(file_unique_id):
            print(f"已存在：{file_unique_id}，跳过转发", flush=True)
        else:
            if message.photo:
                ret = await self.bot_client.send_photo(TARGET_GROUP_ID, file_id)
            elif message.document:
                ret = await self.bot_client.send_document(TARGET_GROUP_ID, file_id)
            elif message.animation:
                ret = await self.bot_client.send_animation(TARGET_GROUP_ID, file_id)
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
            elif ret.animation:
                file_unique_id = ret.animation.file_unique_id
                file_id = ret.animation.file_id
                file_type = 'animation'
                mime_type = ret.animation.mime_type
                file_size = ret.animation.file_size
                file_name = ret.animation.file_name
            else:  # video
                file_unique_id = ret.video.file_unique_id
                file_id = ret.video.file_id
                file_type = 'video'
                mime_type = ret.video.mime_type or 'video/mp4'
                file_size = ret.video.file_size
                file_name = getattr(ret.video, 'file_name', None)

            chat_id = ret.chat.id
            message_id = ret.message_id
            await self.upsert_file_record({
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
        await message.delete()
        print("D555 aiogram_handle_private_media")

    # ================= BOT Media Group =================
    async def aiogram_handle_group_media(self, message: types.Message):
        TARGET_GROUP_ID = self.config.get('target_group_id')
        if message.chat.id != TARGET_GROUP_ID or message.content_type not in {ContentType.PHOTO, ContentType.DOCUMENT, ContentType.VIDEO, ContentType.ANIMATION}:
            return
        print(f"【Aiogram】收到群聊媒体：{message.content_type}，来自 {message.from_user.id}", flush=True)

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
        elif msg.animation:
            file_unique_id = msg.animation.file_unique_id
            file_id = msg.animation.file_id
            file_type = 'animation'
            mime_type = msg.animation.mime_type
            file_size = msg.animation.file_size
            file_name = msg.animation.file_name
        else:
            file_unique_id = msg.video.file_unique_id
            file_id = msg.video.file_id
            file_type = 'video'
            mime_type = msg.video.mime_type or 'video/mp4'
            file_size = msg.video.file_size
            file_name = getattr(msg.video, 'file_name', None)

        chat_id = msg.chat.id
        message_id = msg.message_id
        self.receive_file_unique_id = file_unique_id

        row = await self.db_exec(
            "SELECT chat_id, message_id, file_reference FROM file_records WHERE file_unique_id = %s AND bot_id = %s",
            (file_unique_id, self.bot_id), fetch='one')
        if row:
            existing_chat_id, existing_msg_id, file_reference = row
            if not (existing_chat_id == chat_id and existing_msg_id == message_id):
                await self.upsert_file_record({
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
                if file_reference is not None:
                    await self.bot_client.delete_message(chat_id, message_id)
            else:
                await self.upsert_file_record({
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

        # B: 按 chat_id + message_id
        row2 = await self.db_exec(
            "SELECT id FROM file_records WHERE chat_id = %s AND message_id = %s",
            (chat_id, message_id), fetch='one')
        if row2:
            await self.upsert_file_record({
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
            await self.upsert_file_record({
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

    # ================= Human Private Text =================
    async def handle_user_private_text(self, event):
        msg = event.message
        if not msg.is_private or msg.media or not msg.text:
            return
        to_user_id = msg.from_id
        print(f"【Telethon】收到msg", flush=True)
        try:
            sender = await event.get_sender()
            to_user_id = sender.id
        except Exception as e:
            print(f"⚠️ 获取 sender 失败：{e}")
            await msg.delete()
            return
        text = msg.text.strip()

        if text:
            try:
                match = re.search(r'\|_kick_\|\s*(.*?)\s*(bot)', text, re.IGNORECASE)
                if match:
                    botname = match.group(1) + match.group(2)
                    await self.user_client.send_message(botname, "/start")
                    await self.user_client.send_message(botname, "[~bot~]")
                    await msg.delete()
                    return
            except Exception as e:
                print(f"Error kicking bot: {e} {botname}", flush=True)

        if len(text) < 40 and self.file_unique_id_pattern.fullmatch(text):
            file_unique_id = text
            ret = await self.send_media_by_file_unique_id(self.user_client, to_user_id, file_unique_id, 'man', msg.id)
            if ret == 'retrieved':
                async def delayed_resend():
                    for _ in range(6):
                        try:
                            if self.receive_file_unique_id == file_unique_id:
                                await self.send_media_by_file_unique_id(self.user_client, to_user_id, file_unique_id, 'man', msg.id)
                                return
                            else:
                                await asyncio.sleep(0.5)
                        except Exception as e:
                            print(f"【Telethon】发送失败，重试中：{e}", flush=True)
                    await self.send_media_by_file_unique_id(self.user_client, to_user_id, file_unique_id, 'man', msg.id)
                asyncio.create_task(delayed_resend())
        elif len(text) < 40 and self.doc_id_pattern.fullmatch(text):
            doc_id = int(text)
            await self.send_media_by_doc_id(self.user_client, to_user_id, doc_id, 'man', msg.id)
        else:
            await msg.delete()

    # ================= Human Private Media =================
    async def handle_user_private_media(self, event):
        msg = event.message
        await self.process_private_media_msg(msg, event)
        return

    async def process_private_media_msg(self, msg, event=None):
        TARGET_GROUP_ID = self.config.get('target_group_id')
        if not msg.is_private:
            return
        if not (msg.document or msg.photo or msg.video or getattr(msg, 'media', None)):
            return

        doc_id, access_hash, file_reference, mime_type, file_size, file_name, file_type = await self.extract_video_metadata_from_telethon(msg)
        caption = msg.message or (event.message.text if event else "") or ""

        if caption:
            match = re.search(r'\|_forward_\|(@[a-zA-Z0-9_]+|-?\d+)', caption, re.IGNORECASE)
            if match:
                captured_str = match.group(1).strip()
                if captured_str.startswith('-100') and captured_str[4:].isdigit():
                    destination_chat_id = int(captured_str)
                elif captured_str.isdigit():
                    destination_chat_id = int(captured_str)
                else:
                    destination_chat_id = str(captured_str)
                try:
                    entity = await self.user_client.get_entity(destination_chat_id)
                    ret = await self.user_client.send_file(entity, msg.media)
                except ChatForwardsRestrictedError:
                    print(f"⚠️ 该媒体来自受保护频道，无法转发，已跳过。msg.id = {msg.id}", flush=True)
                    return
                except Exception as e:
                    print(f"❌ 其他发送失败(429)：{e}", flush=True)
                    return

        row = await self.db_exec(
            "SELECT file_unique_id FROM file_records WHERE doc_id = %s AND chat_id = %s AND file_unique_id IS NOT NULL",
            (doc_id, TARGET_GROUP_ID), fetch='one')
        if row:
            await msg.delete()
            return

        try:
            ret = await self.user_client.send_file(TARGET_GROUP_ID, msg.media)
        except ChatForwardsRestrictedError:
            print(f"🚫 跳过：该媒体来自受保护频道 msg.id = {msg.id}", flush=True)
            return
        except Exception as e:
            print(f"❌ 其他错误：{e} TARGET_GROUP_ID={TARGET_GROUP_ID}", flush=True)
            return

        await self.upsert_file_record({
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
        await msg.delete()

    # ================= Human Group Media =================
    async def handle_user_group_media(self, event):
        msg = event.message
        await self.process_group_media_msg(msg)

    async def process_group_media_msg(self, msg):
        if not (msg.document or msg.photo or msg.video or msg.animation):
            return
        if msg.animation:
            media = msg.animation; file_type = 'animation'
        elif msg.document:
            media = msg.document; file_type = 'document'
        elif msg.video:
            media = msg.video; file_type = 'video'
        else:
            media = msg.photo; file_type = 'photo'

        chat_id    = msg.chat_id
        message_id = msg.id
        doc_id     = media.id
        access_hash    = media.access_hash
        file_reference = media.file_reference.hex()
        mime_type  = getattr(media, 'mime_type', 'image/jpeg' if file_type == 'photo' else None)
        file_size  = getattr(media, 'size', None)
        file_name  = self.get_file_name(media)

        row = await self.db_exec("SELECT chat_id, message_id FROM file_records WHERE doc_id = %s AND man_id = %s", (doc_id, self.man_id), fetch='one')
        if row:
            existing_chat_id, existing_msg_id = row
            if not (existing_chat_id == chat_id and existing_msg_id == message_id):
                await self.upsert_file_record({
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
                await msg.delete()
            else:
                await self.upsert_file_record({
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

        row2 = await self.db_exec("SELECT id FROM file_records WHERE chat_id = %s AND message_id = %s", (chat_id, message_id), fetch='one')
        if row2:
            await self.upsert_file_record({
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
            await self.upsert_file_record({
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
