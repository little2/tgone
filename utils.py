import re
import asyncio


from aiogram import types, Bot

from aiogram.types import ContentType

import time
from aiohttp import web
from telethon.errors import ChatForwardsRestrictedError
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError, TelegramNotFound
)
from telethon.tl.types import InputDocument, DocumentAttributeVideo,DocumentAttributeAnimated

from tgone_mysql import MySQLPool

from config import  TARGET_GROUP_ID


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

    # def __init__(self, pool: aiomysql.Pool, bot_client, user_client, lz_var_start_time, config):
    def __init__(self, bot_client, user_client, lz_var_start_time, config):
        self.bot_client = bot_client
        self.user_client = user_client
        self.lz_var_start_time = lz_var_start_time

        self.file_unique_id_pattern = re.compile(r'^[A-Za-z0-9_-]{14,}$')
        self.doc_id_pattern = re.compile(r'^\d+$')
       
        self.man_username = None
        self.man_id = 0
        self.bot_username = None
        self.bot_id = 0
        self.config = config

        self.receive_file_unique_id = None

        self.cold_start = True
        self.webhook_host = config.get("webhook_host")
        self.webhook_path = config.get("webhook_path")
        self.bot_mode = config.get("bot_mode", "polling")

  


    async def set_file_vaild_state(self,file_unique_id: str, vaild_state: int = 1):
        sql = """
            UPDATE sora_content
            SET valid_state = %s, stage = 'pending'  
            WHERE source_id = %s;
        """

        await MySQLPool.execute(
            sql,
            [vaild_state, file_unique_id]
        )

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

    def map_sora_file_type(self, file_type: str) -> str:
        """
        将媒体类型映射为 sora_content.file_type 所需的一位字母:
        - video    -> 'v'
        - photo    -> 'p'
        - document -> 'd'

        其他类型（如 animation）若传进来，就先统一当作 'v' 处理，
        你也可以按需求改成 'a' 或直接 return None 跳过。
        """
        mapping = {
            "video": "v",
            "photo": "p",
            "document": "d",
            "animation": "n",
            "v": "v",
            "p": "p",
            "d": "d",
            "n":"n"
        }
        return mapping.get(file_type)


    async def upsert_sora_content(self, data: dict):
        """
        新增或更新 sora_content 记录，并回传该记录的 id。
        """
        if not data:
            raise ValueError("upsert_sora_content: data 不可为空")

        if "source_id" not in data or not data.get("source_id"):
            file_uid = data.get("file_unique_id")
            if file_uid:
                data["source_id"] = file_uid
            else:
                raise ValueError("upsert_sora_content: data 需要 source_id 或 file_unique_id")

        if "file_type" in data:
            file_type = data.get("file_type")
            if file_type:
                data["file_type"] = self.map_sora_file_type(file_type)

        allowed_cols = {
            "source_id",
            "file_type",
            "content",
            "content_seg",
            "file_size",
            "duration",
            "tag",
            "thumb_file_unique_id",
            "thumb_hash",
            "owner_user_id",
            "source_channel_message_id",
            "valid_state",
            "stage",
            "plan_update_timestamp",
            "file_password",
        }

        cols = [c for c in data.keys() if c in allowed_cols]
        if not cols:
            return None

        placeholders = ["%s"] * len(cols)
        update_cols = [c for c in cols if c not in ("id", "source_id")]
        update_clause = ",".join(f"{c}=VALUES({c})" for c in update_cols) or "source_id=source_id"

        sql = f"""
            INSERT INTO sora_content (
                {",".join(cols)}
            )
            VALUES (
                {",".join(placeholders)}
            )
            ON DUPLICATE KEY UPDATE
                {update_clause}
        """
        params = [data[c] for c in cols]

        await MySQLPool.execute(sql, params)

        row = await MySQLPool.fetchone(
            "SELECT id FROM sora_content WHERE source_id=%s LIMIT 1",
            (data["source_id"],),
        )
        return row["id"] if row else None


    async def upsert_file_record(self, fields: dict):
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
        await MySQLPool.execute(sql, values)


    async def upsert_file_extension(self, data: dict):
        """
        data = {
            'file_unique_id': "...",
            'file_id': "...",
            'file_type': "...",
            optional:
                'bot': "...",
                'user_id': 123,
        }
        """

        if not data:
            return None

        # 1) 自动补 bot 默认值
        if "bot" not in data or not data.get("bot"):
            data["bot"] = self.bot_username

        # 2) 自动补 user_id 缺省→NULL，不用填
        if "user_id" not in data:
            data["user_id"] = None

        # 3) 生成 UPSERT SQL
        cols = list(data.keys())
        placeholders = ["%s"] * len(cols)

        # create_time 只在第一次插入写入，不在 update 里覆盖
        update_cols = [
            f"{col}=VALUES({col})"
            for col in cols
            if col not in ("create_time",)
        ]

        sql = f"""
            INSERT INTO file_extension (
                {",".join(cols)}, create_time
            )
            VALUES (
                {",".join(placeholders)}, NOW()
            )
            ON DUPLICATE KEY UPDATE
                {",".join(update_cols)}
        """

        params = list(data.values())
        return await MySQLPool.execute(sql, params)


    async def upsert_media_content(self, data: dict):
        """
        根据 file_type 将媒体写入 animation / photo / document / video 对应的数据表。
        
        参数:
            file_type: 'animation' | 'photo' | 'document' | 'video'
            data: dict，键为字段名，至少要包含:
                - 所有表共同必备: file_unique_id
                - 各表 NOT NULL 字段，例如:
                  * document: file_size
                  * animation: file_size
                  * video: file_size
                  * photo: file_size, width, height
                其它字段如 caption、kc_id、kc_status 等为可选。
        
        说明:
            - create_time 只在首次 INSERT 时写入 NOW()
            - update_time 每次 UPDATE 时会更新为 NOW()
            - 未出现在 allowed_cols 里的字段会被忽略（避免 SQL 报错）
        """

        if "file_type" not in data:
            return None

        file_type = data.get("file_type")

        # 不同类型对应的表名与允许写入的字段
        table_map = {
            "document": {
                "table": "document",
                "cols": [
                    "file_unique_id",
                    "file_size",
                    "file_name",
                    "mime_type",
                    "caption",
                    "files_drive",
                    "file_password",
                    "kc_id",
                    "kc_status",
                ],
            },
            "animation": {
                "table": "animation",
                "cols": [
                    "file_unique_id",
                    "file_size",
                    "duration",
                    "width",
                    "height",
                    "file_name",
                    "mime_type",
                    "caption",
                    "tag_count",
                    "kind",
                    "credit",
                    "files_drive",
                    "root",
                    "kc_id",
                    "kc_status",
                ],
            },
            "photo": {
                "table": "photo",
                "cols": [
                    "file_unique_id",
                    "file_size",
                    "width",
                    "height",
                    "file_name",
                    "caption",
                    "root_unique_id",
                    "files_drive",
                    "hash",
                    "same_fuid",
                    "kc_id",
                    "kc_status",
                ],
            },
            "video": {
                "table": "video",
                "cols": [
                    "file_unique_id",
                    "file_size",
                    "duration",
                    "width",
                    "height",
                    "file_name",
                    "mime_type",
                    "caption",
                    "tag_count",
                    "kind",
                    "credit",
                    "files_drive",
                    "root",
                    "kc_id",
                    "kc_status",
                ],
            },
        }

        if file_type not in table_map:
            raise ValueError(f"unsupported file_type: {file_type}")

        meta = table_map[file_type]
        table_name = meta["table"]
        allowed_cols = meta["cols"]

        # 只保留表结构里允许的字段
        cols = [col for col in allowed_cols if col in data]

        if "file_unique_id" not in cols:
            raise ValueError("`data` 必须至少包含 file_unique_id")

        # INSERT 部分
        placeholders = ["%s"] * len(cols)
        insert_cols_sql = ",".join(cols + ["create_time"])
        values_sql = ",".join(placeholders + ["NOW()"])

        # UPDATE 部分: 不更新 file_unique_id、create_time
        update_cols = [
            col for col in cols
            if col not in ("file_unique_id", "create_time")
        ]
        update_clauses = [f"{col}=VALUES({col})" for col in update_cols]
        # 统一维护 update_time
        update_clauses.append("update_time = NOW()")

        sql = f"""
            INSERT INTO {table_name} (
                {insert_cols_sql}
            )
            VALUES (
                {values_sql}
            )
            ON DUPLICATE KEY UPDATE
                {",".join(update_clauses)}
        """

        params = [data[col] for col in cols]
        return await MySQLPool.execute(sql, params)


    async def upsert_media(self, data: dict):
        sora_id = await self.upsert_sora_content(data)
        await self.upsert_media_content(data)
        await self.upsert_file_extension(data)
        return sora_id
        


    async def heartbeat(self):
        while True:
            print("💓 Alive (Aiogram polling still running)")
            try:
                await MySQLPool.execute("SELECT 1")
                print("✅ MySQL 连接正常")
            except Exception as e:
                print(f"⚠️ MySQL 保活失败：{e}")
            await asyncio.sleep(600)



    async def health(self, request):
        uptime = time.time() - self.lz_var_start_time
        if self.cold_start or uptime < 10:
            return web.Response(text="⏳ Bot 正在唤醒，请稍候...", status=503)
        return web.Response(text="✅ Bot 正常运行", status=200)

    async def on_startup(self, bot: Bot):
        webhook_url = f"{self.webhook_host}{self.webhook_path}"
        print(f"🔗 設定 Telegram webhook 為：{webhook_url}")
        await bot.delete_webhook(drop_pending_updates=True)
        await bot.set_webhook(webhook_url)
        self.cold_start = False  # 启动完成

    
    # send_media_by_doc_id 函数 
    async def send_media_by_doc_id(self, client, to_user_id, doc_id, client_type,msg_id=None):
        print(f"【send_media_by_doc_id】开始处理 doc_id={doc_id}，目标用户：{to_user_id}",flush=True)

        try:
            sql="""
                SELECT chat_id, message_id, doc_id, access_hash, file_reference, file_id, file_unique_id,file_type 
                FROM file_records WHERE doc_id = %s
            """
            row = await MySQLPool.fetchone(sql, (doc_id,))
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
            await self.send_media_via_bot(client, to_user_id, row, reply_to_message_id=msg_id)
        else:
            await self.send_media_via_man(client, to_user_id, row, reply_to_message_id=msg_id)

    # send_media_by_file_unique_id 函数
    async def send_media_by_file_unique_id(self,client, to_user_id, file_unique_id, client_type, msg_id):
        
        print(f"【1】开始处理 file_unique_id={file_unique_id}，目标用户：{to_user_id}",flush=True)
        try:
            if client_type == 'bot':
                # 机器人账号发送

                sql = """
                    SELECT chat_id, message_id, doc_id, access_hash, file_reference, file_id, file_unique_id,file_type 
                    FROM file_records WHERE file_unique_id = %s AND bot_id = %s
                """
                row = await MySQLPool.fetchone(sql, (file_unique_id,self.bot_id,))
            else:
                
     
                sql = """
                    SELECT chat_id, message_id, doc_id, access_hash, file_reference, file_id, file_unique_id,file_type 
                    FROM file_records WHERE file_unique_id = %s AND man_id = %s
                    """
                row = await MySQLPool.fetchone(sql, (file_unique_id,self.man_id,))
            
          
            print(f"【2】本机查询纪录: 结果：{row}",flush=True)

            if not row: # if row = None

                ext_row = await self.fetch_file_by_source_id(file_unique_id)
                print(f"【3】扩展查询结果：{ext_row}",flush=True)
                if ext_row:
                    # print(f"【send_media_by_file_unique_id】在 file_extension 中找到对应记录，尝试从 Bot 获取文件",flush=True)
                    # 如果在 file_extension 中找到对应记录，尝试从 Bot 获取文件
                    bot_row = await self.receive_file_from_bot(ext_row)
                    
                    max_retries = 3
                    delay = 2  # 每次重试的延迟时间（秒）

                    if not bot_row: # 传送失败
                        print(f"263【4】从机器人获取文件失败，file_unique_id={file_unique_id}",flush=True)
                        await client.send_message(to_user_id, f"未找到 file_unique_id={file_unique_id} 对应的文件。(182)",reply_to_message_id=msg_id)
                        return
                    else:
                        print(f"【4】其他机器人已将资源传给人型机器人 {file_unique_id}",flush=True)
                       
                        return "retrieved"

                        # chat_id, message_id, doc_id, access_hash, file_reference_hex, file_id, file_unique_id, file_type = row
                        # await client.send_message(to_user_id, f"未找到 file_unique_id={file_unique_id} 对应的文件。(192)")
                        # return
                        # return await self.send_media_by_file_unique_id(client, to_user_id, file_unique_id, client_type, msg_id)
                        # pass
                else:
                    # row['file_type']
                    text = f"未找到 file_unique_id={file_unique_id} 对应的文件记录。(194)"
                    if isinstance(client, Bot):
                        await client.send_message(to_user_id, text, reply_to_message_id=msg_id)
                    else:
                        await client.send_message(to_user_id, text, reply_to=msg_id)

                    
                    # 完全没有
                    # 如果 file_unqiue_id 的开头不是 X_
                    if not file_unique_id.startswith('X_'):
                        await self.set_file_vaild_state(file_unique_id, vaild_state=4)                    
                    return
            else:
                await self.set_file_vaild_state(file_unique_id, vaild_state=9)     
               
                
        
        except Exception as e:
            print(f"[194] Error: {e}")
            return
        
        print(f"【send_media_by_file_unique_id】查询结果：{client_type}",flush=True)
        if client_type == 'bot':
            # 机器人账号发送
            await self.send_media_via_bot(client, to_user_id, row, reply_to_message_id=msg_id)
        else:
            await self.send_media_via_man(client, to_user_id, row, reply_to_message_id=msg_id)

    async def extract_video_metadata_from_telethon(self,msg):
        file_type = ''
        if msg.document:
            media = msg.document

            # 检查 attributes 判定是否属于视频
            is_video = any(isinstance(attr, DocumentAttributeVideo) for attr in media.attributes)

            if is_video:
                file_type = "video"      # document 但类型是 video
            else:
                file_type = "document"   # 普通 document 比如 zip、pdf


            
        elif msg.video:
            media = msg.video
            file_type = 'video'
        elif msg.photo:
            media = msg.photo
            file_type = 'photo'
        else:
            raise ValueError("message 不包含可识别的媒体: photo/document/video")

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
       
        elif message.animation:
            a = message.animation
            file_id = a.file_id
            file_unique_id = a.file_unique_id
            mime_type = a.mime_type or "video/mp4"
            file_type = "animation"
            file_size = a.file_size
            file_name = a.file_name
        elif message.video:
            v = message.video
            file_id = v.file_id
            file_unique_id = v.file_unique_id
            mime_type = v.mime_type or "video/mp4"
            file_type = "video"
            file_size = v.file_size
            file_name = getattr(v, "file_name", None)
        else:
            raise ValueError("message 不包含可识别的媒体: photo/document/video/animation")

       
        
        return file_id, file_unique_id, mime_type, file_type, file_size, file_name

    async def build_media_dict_from_aiogram(self, message):
        """
        根据 aiogram.Message 解析媒体信息，产生适用于 upsert_media_content 的 data dict。

        返回:
            (file_type, data_dict)

        file_type:
            'photo' | 'animation' | 'document' | 'video'

        data_dict:
            按照你 animation/photo/document/video 四张表的字段准备，
            至少包含 file_unique_id + file_size 等必填字段。
        """
        caption = message.caption or None

        # 1) Photo
        if message.photo:
            largest = message.photo[-1]
            file_type = "photo"
            data = {
                "file_type": "photo",
                "file_unique_id": largest.file_unique_id,
                "file_id": largest.file_id,
                "file_size": largest.file_size,
                "width": largest.width,
                "height": largest.height,
                "file_name": None,          # photo 表允许为 NULL
                "caption": caption,
                # 可视需求补充:
                # "root_unique_id": None,
                # "files_drive": None,
                # "hash": None,
                # "same_fuid": None,
                # "kc_id": None,
                # "kc_status": None,
            }
            return data

        # 2) Animation (Telegram 动图 / GIF MP4)
        if message.animation:
            a = message.animation
            file_type = "animation"
            data = {
                "file_type": "animation",
                "file_unique_id": a.file_unique_id,
                "file_id": a.file_id,
                "file_size": a.file_size,
                "duration": a.duration,
                "width": a.width,
                "height": a.height,
                "file_name": a.file_name,
                "mime_type": a.mime_type or "video/mp4",
                "caption": caption,
                # "tag_count": 0,
                # "kind": None,
                # "credit": 0,
                # "files_drive": None,
                # "root": None,
                # "kc_id": None,
                # "kc_status": None,
            }
            return data

        # 3) Document
        if message.document:
            d = message.document
            file_type = "document"
            data = {
                "file_type": "document",
                "file_unique_id": d.file_unique_id,
                "file_id": d.file_id,
                "file_size": d.file_size,
                "file_name": d.file_name,
                "mime_type": d.mime_type,
                "caption": caption,
                # "files_drive": None,
                # "file_password": None,
                # "kc_id": None,
                # "kc_status": None,
            }
            return data

        # 4) Video
        if message.video:
            v = message.video
            file_type = "video"
            data = {
                "file_type": "video",
                "file_unique_id": v.file_unique_id,
                "file_id": v.file_id,
                "file_size": v.file_size,
                "duration": v.duration,
                "width": v.width,
                "height": v.height,
                "file_name": getattr(v, "file_name", None),
                "mime_type": v.mime_type or "video/mp4",
                "caption": caption,
                # "tag_count": 0,
                # "kind": None,
                # "credit": 0,
                # "files_drive": None,
                # "root": None,
                # "kc_id": None,
                # "kc_status": None,
            }
            return data

        raise ValueError("message 不包含可识别的媒体: photo/document/video/animation")


    async def fetch_file_by_source_id(self, source_id: str):
        sql = """
                SELECT f.file_type, f.file_id, f.bot, b.bot_id, b.bot_token, f.file_unique_id
                FROM file_extension f
                LEFT JOIN bot b ON f.bot = b.bot_name
                WHERE f.file_unique_id = %s
                LIMIT 0, 1
            """
        row = await MySQLPool.fetchone(sql, (source_id,))
       
        if not row:
            return None
        else:
            print(f"【fetch_file_by_source_id】找到对应记录：{row}",flush=True)
            return {
                "file_type": row["file_type"],
                "file_id": row["file_id"],
                "bot": row["bot"],
                "bot_id": row["bot_id"],
                "bot_token": row["bot_token"],
                "file_unique_id": row["file_unique_id"],
            }
    
    async def receive_file_from_bot(self, row):
        retSend = None
        bot_token = f"{row['bot_id']}:{row['bot_token']}"
    
        from aiogram import Bot
        print(f"4️⃣【receive_file_from_bot】开始处理 file_unique_id={row['file_unique_id']}，bot_id={row['bot_id']}",flush=True)
        mybot = Bot(token=bot_token)
        try:
            print(f"4️⃣【receive_file_from_bot】准备让机器人{row['bot_id']}发送文件file_unique_id={row['file_unique_id']}给{self.man_id}",flush=True)
            if row["file_type"] == "photo":
                # await mybot.send_photo(chat_id=7496113118, photo=row["file_id"])
                retSend = await mybot.send_photo(chat_id=self.man_id, photo=row["file_id"])
            elif row["file_type"] == "video":
                retSend = await mybot.send_video(chat_id=self.man_id, video=row["file_id"])

            elif row["file_type"] == "document":
                retSend = await mybot.send_document(chat_id=self.man_id, document=row["file_id"])
            elif row["file_type"] == "animation":
                retSend = await mybot.send_animation(chat_id=self.man_id, animation=row["file_id"])

            print(f"4️⃣{row['file_unique_id']}【receive_file_from_bot】文件已发送到人型机器人，file_unique_id={row['file_unique_id']}",flush=True)
            print(f"\n4️⃣retSend=>{retSend}\n",flush=True)
        except TelegramForbiddenError as e:
        # 私聊未 /start、被拉黑、群权限不足等
            print(f"4️⃣{row['file_unique_id']} 发送被拒绝（Forbidden）: {e}", flush=True)
        except TelegramNotFound:
            print(f"4️⃣{row['file_unique_id']} chat not found: {self.man_id}. 可能原因：ID 错、bot 未入群、或用户未对该 bot /start", flush=True)
            # 机器人根本不认识这个 chat（不在群里/用户未 start/ID 错）
            await self.user_client.send_message(row["bot"], "/start")
            await self.user_client.send_message(row["bot"], "[~bot~]")
            
        except TelegramBadRequest as e:
            # 这里能准确看到 “chat not found”“message thread not found”等具体文本
            await self.user_client.send_message(row["bot"], "/start")
            await self.user_client.send_message(row["bot"], "[~bot~]")           
            print(f"4️⃣{row['file_unique_id']} 发送失败（BadRequest）: {e}", flush=True)
        except Exception as e:
            # 不要在所有异常里就发 /start；只在你需要唤醒对话时再做
            print(f"4️⃣{row['file_unique_id']} ❌ 发送失败: {e}", flush=True)
        finally:
            print(f"4️⃣{row['file_unique_id']} 正常结束")
            await mybot.session.close()
            return retSend
             
    # send_media_via_man 函数 
    async def send_media_via_man(self, client, to_user_id, row, reply_to_message_id=None):
        # to_user_entity = await client.get_input_entity(to_user_id)
        

        chat_id        = row["chat_id"]
        message_id     = row["message_id"]
        doc_id         = row["doc_id"]
        access_hash    = row["access_hash"]
        file_reference_hex = row["file_reference"]
        file_id        = row["file_id"]
        file_unique_id = row["file_unique_id"]
        file_type      = row["file_type"]

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
            await client.send_file(to_user_id, input_doc, reply_to=reply_to_message_id)
        except Exception:
            # file_reference 过期时，重新从历史消息拉取
            try:
                msg = await client.get_messages(chat_id, ids=message_id)
                if not msg:
                    print(f"历史消息中未找到对应消息，可能已被删除。(286)",flush=True)
                    
                    row = {'file_type': file_type,
                           'file_id': file_id}
                    # 将媒体以bot再次寄送给人型机器人，以重新获取 file_reference
                    await self.send_media_via_bot(
                        self.bot_client, 
                        self.man_id,
                        row
                    )
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
            

                    await client.send_file(to_user_id, new_input, reply_to=reply_to_message_id)
            except Exception as e:
                print(f"发送文件时出错：{e}",flush=True)
                await client.send_message(to_user_id, f"发送文件时出错：{e}")

    # send_media_via_bot 函数
    async def send_media_via_bot(self, bot_client, to_user_id, row, reply_to_message_id=None):
        """
        bot_client: Aiogram Bot 实例
        row: (chat_id, message_id, doc_id, access_hash, file_reference_hex, file_id, file_unique_id)
        """
        

        file_type = row["file_type"]
        file_id   = row["file_id"]

        try:
            if file_type== "photo":
                # 照片（但不包括 GIF）
                await bot_client.send_photo(to_user_id, file_id, reply_to_message_id=reply_to_message_id)
        
            elif file_type == "video":
                # 视频
                await bot_client.send_video(to_user_id, file_id, reply_to_message_id=reply_to_message_id)
            elif file_type == "document":
                # 其他一律当文件发
                await bot_client.send_document(to_user_id, file_id, reply_to_message_id=reply_to_message_id)
            elif file_type == "animation":
                # 动图
                await bot_client.send_animation(to_user_id, file_id, reply_to_message_id=reply_to_message_id)
        except Exception as e:
            await bot_client.send_message(to_user_id, f"⚠️ 发送文件失败：{e}")
    
    async def check_file_exists_by_unique_id(self, file_unique_id: str, chat_id: int) -> bool:
        sql = """
            SELECT 1
            FROM file_records
            WHERE file_unique_id = %s
              AND bot_id = %s
              AND chat_id = %s 
              AND doc_id IS NOT NULL
            LIMIT 1
        """
        try:
            row = await MySQLPool.fetchone(sql, (file_unique_id, self.bot_id, chat_id))
            return row is not None
        except Exception as e:
            print(f"528 Error: {e}")
            return False




# ================= BOT Text Private. 私聊 Message 文字处理：Aiogram：BOT账号 =================
    async def aiogram_handle_private_text(self, message: types.Message):
        print(f"【Aiogram】收到私聊文本：{message.text}，来自 {message.chat.first_name}",flush=True)
        # 只处理“私聊里发来的文本”``
        if message.chat.type != "private" or message.content_type != ContentType.TEXT:
            return
        text = message.text.strip()
        to_user_id = message.chat.id
        reply_to_message = message.message_id

        # 检查 text 的长度是否少于 40 个字符

        if len(text)<40 and self.file_unique_id_pattern.fullmatch(text):
            
            file_unique_id = text
            ret = await self.send_media_by_file_unique_id(self.bot_client, to_user_id, text, 'bot', reply_to_message)
            
            if(ret=='retrieved'):
               
                print(f">>>>>【Telethon】已从 Bot 获取文件，准备发送到 {to_user_id}，file_unique_id={file_unique_id}",flush=True)
                async def delayed_resend():
                    for _ in range(6):  # 最多重试 6 次
                        try:
                            # 尝试发送文件(机器人)
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
            else:
                print(f">>>>>【Aiogram】文件已发送到 {to_user_id}，file_unique_id={file_unique_id}",flush=True)


        elif len(text)<40 and self.doc_id_pattern.fullmatch(text):
            await self.send_media_by_doc_id(self.bot_client, to_user_id, int(text), 'bot', reply_to_message)
        else:
            print("D480")
            await message.delete()

# ================= BOT TEXT Private. 私聊 Message 媒体处理：Aiogram：BOT账号 =================
    async def aiogram_handle_private_media(self, message: types.Message):
        
        # 若不是私信 且 不包括媒體，則跳過
        if message.chat.type != "private" or message.content_type not in {
            ContentType.PHOTO, ContentType.DOCUMENT, ContentType.VIDEO, ContentType.ANIMATION
        }:
            return



        print(f"【Aiogram】收到私聊媒体：{message.content_type}，来自 user_id = {message.from_user.id}",flush=True)
        # 只处理“私聊里发来的媒体”

        

        file_id, file_unique_id, mime_type, file_type, file_size, file_name = await self.extract_video_metadata_from_aiogram(message)

        

        # ⬇️ 检查是否對應的是否已存在  (doc_id IS NOT NULL AND bot_id, chat_id, file_unique_id) )
        if await self.check_file_exists_by_unique_id(file_unique_id, TARGET_GROUP_ID):
            print(f"已存在：{file_unique_id}，跳过转发",flush=True)

        else:
            print(f"{TARGET_GROUP_ID} {self.bot_id} | {message.from_user.id} {self.man_id}",flush=True)
            if TARGET_GROUP_ID == self.bot_id and message.from_user.id == self.man_id:

                sql = """
                    SELECT * 
                    FROM file_records 
                    WHERE file_unique_id IS NULL
                      AND man_id = %s
                      AND chat_id = %s
                      AND file_size = %s
                      AND mime_type = %s
                    LIMIT 1
                
                """
                row = await MySQLPool.fetchone(sql, (self.man_id, TARGET_GROUP_ID, file_size, mime_type))
                if row:  
                    await self.upsert_file_record({
                        'chat_id'       : row['chat_id'],
                        'message_id'    : row['message_id'],
                        'mime_type'     : mime_type,
                        'file_type'     : file_type,
                        'file_name'     : file_name,
                        'file_size'     : file_size,
                        'uploader_type' : 'bot',
                        'bot_id'        : self.bot_id,
                        'file_unique_id': file_unique_id,
                        'file_id'       : file_id
                        
                    })
            else:

                ret = None
                # ⬇️ 发到群组
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
                else:  # msg.video
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
                        'bot_id'       : self.bot_id
                    })



                # 新增：写入 photo 表/ document 表/ video 表/ animation 表
                data = await self.build_media_dict_from_aiogram(ret)
                await self.upsert_media(data)




        # print(f"{ret} 已发送到目标群组：{TARGET_GROUP_ID}")
   
        await message.delete()
        print("D555 aiogram_handle_private_media")

# ================= BOT Media Group. 群聊 Message 图片/文档/视频处理：Aiogram：BOT账号 =================
    async def aiogram_handle_group_media(self, message: types.Message):
        TARGET_GROUP_ID = self.config.get('target_group_id')
        # 只处理“指定群组里发来的媒体”
        if message.chat.id != TARGET_GROUP_ID or message.content_type not in {
            ContentType.PHOTO, ContentType.DOCUMENT, ContentType.VIDEO, ContentType.ANIMATION
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

        elif msg.animation:
            file_unique_id = msg.animation.file_unique_id
            file_id = msg.animation.file_id
            file_type = 'animation'
            mime_type = msg.animation.mime_type
            file_size = msg.animation.file_size
            file_name = msg.animation.file_name

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


            sql = '''
                SELECT chat_id, message_id,file_reference FROM file_records 
                WHERE file_unique_id = %s AND bot_id = %s
                '''
            row = await MySQLPool.fetchone(sql, (file_unique_id,self.bot_id))

        except Exception as e:
            print(f"578 Error: {e}")
    

        if row:
            
            existing_chat_id = row["chat_id"]
            existing_msg_id  = row["message_id"]
            file_reference   = row["file_reference"]   # 对应 SELECT 的字段
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


                # 新增：写入 photo 表/ document 表/ video 表/ animation 表
                data = await self.build_media_dict_from_aiogram(message)
                await self.upsert_media(data)


                if file_reference != None:
                    print(f"【Aiogram】删除重覆 {message_id} by file_unique_id",flush=True)
                    await self.bot_client.delete_message(chat_id, message_id)
                print("D631")
            else:
                print(f"【Aiogram】新增 {message_id} by file_unique_idd",flush=True)
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

        try:
            
            sql = """
                SELECT id FROM file_records WHERE chat_id = %s AND message_id = %s
                """
            row = await MySQLPool.fetchone(sql, (chat_id, message_id))
        except Exception as e:
            print(f"614 Error: {e}")

        if row:
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
            print(f"【Aiogram】新增 {message_id} by chat_id+message_id",flush=True)
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
            



        # 新增：写入 photo 表/ document 表/ video 表/ animation 表
        data = await self.build_media_dict_from_aiogram(message)
        await self.upsert_media(data)

    # ================= Human Private Text  私聊 Message 文字处理：人类账号 =================
    async def handle_user_private_text(self,event):
        
        msg = event.message
        if not msg.is_private or msg.media or not msg.text:
            return

        to_user_id = msg.from_id

        print(f"【Telethon】收到msg",flush=True)
        
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
            print(f">>>【Telethon】将文件：{file_unique_id} 回覆给 {to_user_id}，返回结果：{ret}",flush=True)
            if(ret=='retrieved'):
                print(f">>>>>【Telethon】已从 Bot 获取文件{file_unique_id}，准备回覆给 {to_user_id}",flush=True)
                async def delayed_resend():
                    for _ in range(6):  # 最多重试 6 次
                        try:
                            # 尝试发送文件 (人型机器人)
                            print(f"【Telethon】第 {_+1} 次尝试回覆文件：{file_unique_id} 给 {to_user_id} {self.receive_file_unique_id}",flush=True)
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
            print(f"{msg.text}")
            await msg.delete()
            print("D755")

    # ================= Human Private Meddia 私聊 Media 媒体处理：人类账号 =================
    async def handle_user_private_media(self,event):
        
        msg = event.message
        await self.process_private_media_msg(msg, event)
        return
    
    async def process_private_media_msg(self, msg, event=None):
        print("PPMM-receive")
        TARGET_GROUP_ID = self.config.get('target_group_id')

        # 若不是私聊,則不處理
        if not msg.is_private:
            print("PPMM-871 process_private_media_msg - not private")
            return

        # 若不包括媒体,也不處理
        if not (msg.document or msg.photo or msg.video or getattr(msg, 'media', None)):
            # print("PPMM-876 process_private_media_msg - no media content")
            # print(f"msg {msg}")
            return

        doc_id, access_hash, file_reference, mime_type, file_size, file_name, file_type = await self.extract_video_metadata_from_telethon(msg)  
        # print(f"doc_id={doc_id}, access_hash={access_hash}, file_reference={file_reference}, mime_type={mime_type}, file_size={file_size}, file_name={file_name}, file_type={file_type}",flush=True)
        caption = ""
        if(event is None):
            print(f"PPMM-{doc_id}-【Telethon】来自私聊媒体回溯处理：{msg.media} {file_type}，chat_id={msg.chat_id}", flush=True)
            caption        = msg.message or ""
            
        else:
            print(f"PPMM-{doc_id}-【Telethon】收到私聊媒体，来自 {event.peer_id.user_id} doc_id = {doc_id} {file_type}",flush=True)
            caption        = event.message.text or ""
            
        # print(f"caption={caption}",flush=True)
            

        
        if caption !='':
            print(f"PPMM")
            match = re.search(r'\|_forward_\|(@[a-zA-Z0-9_]+|-?\d+)', caption, re.IGNORECASE)
            if match:
                print(f"PPMM-【Telethon】匹配到的转发模式：{match}",flush=True)
                captured_str = match.group(1).strip()  # 捕获到的字符串
                print(f"PPMM-【Telethon】捕获到的字符串：{captured_str}",flush=True)

                if captured_str.startswith('-100') and captured_str[4:].isdigit():
                    destination_chat_id = int(captured_str)  # 正确做法，保留 -100
                elif captured_str.isdigit():
                    print(f"PPMM-【Telethon】捕获到的字符串是数字：{captured_str}",flush=True)
                    destination_chat_id = int(captured_str)
                else:
                    print(f"PPMM-【Telethon】捕获到的字符串不是数字：{captured_str}",flush=True)
                    destination_chat_id = str(captured_str)
                
                try:
                    print(f"PPMM-📌 获取实体：{destination_chat_id}", flush=True)
                    entity = await self.user_client.get_entity(destination_chat_id)
                    ret = await self.user_client.send_file(entity, msg.media)
                #     print(f"✅ 成功发送到 {destination_chat_id}，消息 ID：{ret.id}", flush=True)
                # except Exception as e:
                #     print(f"❌ 无法发送到 {destination_chat_id}：{e}", flush=True)


                # try:
                #     ret = await user_client.send_file(destination_chat_id, msg.media)
                    print(f"PPMM-【Telethon】已转发到目标群组：{destination_chat_id}，消息 ID：{ret.id}",flush=True)
                    # print(f"{ret}",flush=True)
                except ChatForwardsRestrictedError:
                    print(f"PPMM-⚠️ 该媒体来自受保护频道，无法转发，已跳过。msg.id = {msg.id}", flush=True)
                    return  # ⚠️ 不处理，直接跳出
                except Exception as e:
                    print(f"PPMM-❌ 其他发送失败(429)：{e}", flush=True)
                    return

        # 检查：TARGET_GROUP_ID 群组是否已有相同 doc_id
        try:
            print(f"PPMM-Check Exists")
     
            sql = """
                SELECT file_unique_id FROM file_records WHERE doc_id = %s AND chat_id = %s AND file_unique_id IS NOT NULL
                """
            row = await MySQLPool.fetchone(sql, (doc_id, TARGET_GROUP_ID))
        except Exception as e:
            print(f"272 Error: {e}")
            
       
        if row:
            print(f"PPMM-{doc_id}-【Telethon】已存在 doc_id={doc_id} fuid = {row} 的记录，跳过转发", flush=True)
            # await event.delete()
            await msg.delete()
            print("PPMM")
            return

        # 转发到群组，并删除私聊
        try:
            # 这里直接发送 msg.media，如果受保护会被阻止
            print(f"PPMM-{doc_id}-👉 【Telethon】准备发送到目标群组/機器人：{TARGET_GROUP_ID}", flush=True)
            ret = await self.user_client.send_file(TARGET_GROUP_ID, msg.media)
            # print(f"ret={ret}", flush=True)
        except ChatForwardsRestrictedError:
            print(f"🚫 跳过：该媒体来自受保护频道 msg.id = {msg.id}", flush=True)
            return
        except Exception as e:
            if "The chat is restricted and cannot be used in that request" in str(e):
                print(f"PPMM-⚠️ 這個群應該炸了", flush=True)
                return  # ⚠️ 不处理，直接跳出
            else:
                print(f"❌ 其他错误：{e} TARGET_GROUP_ID={TARGET_GROUP_ID}", flush=True)
            return

        



        # 插入或更新 placeholder 记录 (message_id 自动留空，由群组回调补全)
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
        print("PPMM- process_private_media_msg")



        await msg.delete() 
            
    # ================= Human Group Media 3-1. 群组媒体处理：人类账号 =================
    async def handle_user_group_media(self,event):
        msg = event.message
        await self.process_group_media_msg(msg)

    async def process_group_media_msg(self,msg):
        
        if not (msg.document or msg.photo or msg.video or msg.animation):
            return
        file_type = ''
        if msg.photo:
            media = msg.photo
            file_type = "photo"
        elif msg.document:
            media = msg.document
            attrs = media.attributes or []

            # 先判断是不是 video
            if any(isinstance(a, DocumentAttributeVideo) for a in attrs):
                file_type = "video"
            # 再判断是不是 gif / animation
            elif any(isinstance(a, DocumentAttributeAnimated) for a in attrs):
                file_type = "animation"
            else:
                file_type = "document"

        else:
            # 理论上不会进到这里（前面已经 return 过非 photo/document）
            return   

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

            sql = '''
                SELECT chat_id, message_id FROM file_records WHERE doc_id = %s AND man_id = %s
                '''
            row = await MySQLPool.fetchone(sql, (doc_id,self.man_id))

        except Exception as e:
            print(f"[process_group_media_msg] doc_id 查库失败: {e}", flush=True)
    
        
        if row:
            
            existing_chat_id = row["chat_id"]
            existing_msg_id  = row["message_id"]
            if not (existing_chat_id == chat_id and existing_msg_id == message_id):
                print(f"【Telethon】在指定群组，收到群组媒体：来自 {msg.chat_id}",flush=True)
    
                # 重复上传到不同消息 → 更新并删除新消息
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
                print("D1015")
                await msg.delete()
            else:
                # 同一条消息重复触发 → 仅更新，不删除
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

        # —— 步骤 B：若 A 中没找到，再按 (chat_id, message_id) 查库 ——
        try:
           
            sql = '''
                SELECT id FROM file_records WHERE chat_id = %s AND message_id = %s
                '''
            row = await  MySQLPool.fetchone(sql, (chat_id, message_id))
        except Exception as e:
            print(f"372 Error: {e}")
      
        if row:
            # 已存在同条消息 → 更新并保留
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
            # 全新媒体 → 插入并保留
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
        # B 分支保留消息，不删除