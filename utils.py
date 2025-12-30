import re
import asyncio


from aiogram import types, Bot

from aiogram.types import ContentType,Message

import time
from aiohttp import web
from telethon.errors import ChatForwardsRestrictedError,FileReferenceExpiredError
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError, TelegramNotFound
)
from telethon.tl.types import InputDocument, DocumentAttributeVideo,DocumentAttributeAnimated,InputPhoto


from tgone_mysql import MySQLPool, DBIntegrityError, DBOperationalError

from tgone_config import  TARGET_GROUP_ID, TARGET_GROUP_ID_FROM_BOT


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



class LoadingManager:
    def __init__(self):
        # key: file_unique_id
        # value: {
        #   "file_id": file_id,
        #   "chat_id": ...,
        #   "message_id": ...
        # }
        self._data = {}

    def set(self, file_unique_id: str, chat_id: int, message_id: int):
        """
        建立 loading 状态
        """
        self._data[file_unique_id] = {
            "file_id": None,
            "chat_id": chat_id,
            "message_id": message_id,
        }

    def pop(self, file_unique_id: str):
        """
        取出并移除 loading
        """
        return self._data.pop(file_unique_id, None)

    def get(self, file_unique_id: str):
        """
        只读取，不移除
        """
        return self._data.get(file_unique_id)

    def has_file_id(self, file_unique_id: str) -> bool:
        """
        检查 loading[file_id] 中是否有 file_id 且有值
        """
        info = self._data.get(file_unique_id)
        if not info:
            return False
        return bool(info.get("file_id"))

    def exists(self, file_unique_id: str) -> bool:
        """
        单纯判断 loading[file_unique_id] 是否存在
        """
        return file_unique_id in self._data

    def attach_file_id(self, file_unique_id: str, file_id: str) -> bool:
        """
        为已存在的 loading 绑定真实 file_id
        """
        info = self._data.get(file_unique_id)
        if not info:
            return False

        info["file_id"] = file_id
        return True


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

     
        self.loading_manager = LoadingManager()

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

    def map_sora_file_type(self, file_type: str, mode:str = 'short') -> str:
        """
        将媒体类型映射为 sora_content.file_type 所需的一位字母:
        - video    -> 'v'
        - photo    -> 'p'
        - document -> 'd'

        其他类型（如 animation）若传进来，就先统一当作 'v' 处理，
        你也可以按需求改成 'a' 或直接 return None 跳过。
        """
        if mode == 'short':
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
        else:
            mapping = {
                "video": "video",
                "photo": "photo",
                "document": "document",
                "animation": "animation",
                "v": "video",
                "p": "photo",
                "d": "document",
                "n":"animation"
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
            data["file_type"] = self.map_sora_file_type(data["file_type"],'short')

        data['valid_state'] = 9  # 标记为有效
        data['stage'] = "pending"  # 标记为有效

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

        allowed = {
            "file_id","file_unique_id","file_type","mime_type","file_size","file_name","uploader_type","created_at","updated_at","man_id","bot_id","chat_id", "message_id", "doc_id","id","doc_id","access_hash", "file_reference"
        }

        safe_fields = {k: v for k, v in fields.items() if k in allowed}

        if not safe_fields:
            return       

        cols = list(safe_fields.keys())
        placeholders = ["%s"] * len(cols)
        update_clauses = [f"{col}=VALUES({col})" for col in cols]
        sql = f"""
            INSERT INTO file_records ({','.join(cols)})
            VALUES ({','.join(placeholders)})
            ON DUPLICATE KEY UPDATE {','.join(update_clauses)}
        """
        values = list(safe_fields.values())
       
  
        try:
            await MySQLPool.execute(sql, values, raise_on_error=True)

        except DBIntegrityError as e:                
            raise
        except DBOperationalError as e:
            # 例如断线/超时等（具体是否会被 reconnect 吃掉取决于你的装饰器逻辑）
            raise

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

        if "file_type" in data:
            data["file_type"] = self.map_sora_file_type(data["file_type"],'full')


        allowed = {
            "id","file_type","file_id","file_unique_id","bot","user_id","create_time"
        }

        safe_fields = {k: v for k, v in data.items() if k in allowed}

        if not safe_fields:
            return       



        # 3) 生成 UPSERT SQL
        cols = list(safe_fields.keys())
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

        params = list(safe_fields.values())
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

        if file_type == 'v':
            file_type = 'video'
        elif file_type == 'p':
            file_type = 'photo'
        elif file_type == 'd':
            file_type = 'document'
        elif file_type == 'n':
            file_type = 'animation'

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
        data['caption'] = None
        data['kc_id']= sora_id
        data['kc_status']= 'pending'
        await self.upsert_media_content(data)
        await self.upsert_file_extension(data)
        return sora_id
    
    async def heartbeat(self):
        while True:
            print("💓 Alive (🤖 polling still running)")
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


    # ================= 数据库表初始化 =================
    async def ensure_database_tables(self):
        """确保所有必需的数据库表存在，若不存在则创建"""
        tables_sql = {
            "sora_content": """
            CREATE TABLE IF NOT EXISTS `sora_content` (
            `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT,
            `source_id` varchar(50) NOT NULL,
            `file_type` varchar(10) DEFAULT 'v',
            `content` text DEFAULT NULL,
            `content_seg` text DEFAULT NULL,
            `file_size` bigint(20) UNSIGNED DEFAULT NULL,
            `duration` int(10) UNSIGNED DEFAULT NULL,
            `tag` varchar(200) DEFAULT NULL,
            `thumb_file_unique_id` varchar(100) DEFAULT NULL,
            `thumb_hash` varchar(64) DEFAULT NULL,
            `owner_user_id` bigint(20) UNSIGNED DEFAULT NULL,
            `source_channel_message_id` bigint(20) UNSIGNED DEFAULT NULL,
            `valid_state` tinyint(3) UNSIGNED NOT NULL DEFAULT 1 COMMENT '1待验证 / 4失效 / 9有效 / 20 下架',
            `stage` enum('','salai','luguan','no_thumb','no_file','pending','updated','prepare') DEFAULT NULL,
            `plan_update_timestamp` int(13) UNSIGNED DEFAULT NULL,
            `file_password` varchar(150) DEFAULT NULL,
            PRIMARY KEY (`id`),
            UNIQUE KEY `source_id` (`source_id`),
            KEY `idx_file_size` (`file_size`),
            KEY `idx_duration` (`duration`),
            KEY `idx_source_id` (`source_id`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
            """,
            "file_records": """
            CREATE TABLE IF NOT EXISTS `file_records` (
            `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT,
            `chat_id` bigint(20) DEFAULT NULL COMMENT 'Telegram 的 chat ID',
            `message_id` bigint(20) DEFAULT NULL COMMENT 'Telegram 的 message ID，群组触发后补全',
            `doc_id` bigint(20) DEFAULT NULL COMMENT 'MTProto 媒体的 document.id / photo.id / video.id',
            `access_hash` bigint(20) DEFAULT NULL COMMENT 'MTProto 媒体的 access_hash',
            `file_reference` text DEFAULT NULL COMMENT 'MTProto 媒体的 file_reference（hex）',
            `file_id` varchar(255) DEFAULT NULL COMMENT 'Bot API 的 file_id',
            `file_unique_id` varchar(255) DEFAULT NULL COMMENT 'Bot API 的 file_unique_id',
            `file_type` varchar(10) DEFAULT NULL,
            `mime_type` varchar(100) DEFAULT NULL COMMENT '媒体的 MIME 类型（如 "image/jpeg" 或 "video/mp4"）',
            `file_name` varchar(255) DEFAULT NULL COMMENT '文件名（只有 document/video 才有，photo 通常无）',
            `file_size` bigint(20) UNSIGNED DEFAULT NULL COMMENT '媒体大小（字节数）',
            `uploader_type` enum('bot','user') DEFAULT 'user' COMMENT '标记此行由 bot 还是 user 上传',
            `created_at` timestamp NULL DEFAULT current_timestamp() COMMENT '创建时间',
            `updated_at` timestamp NULL DEFAULT current_timestamp() ON UPDATE current_timestamp() COMMENT '最近更新时间',
            `man_id` bigint(20) UNSIGNED DEFAULT NULL,
            `bot_id` bigint(20) UNSIGNED DEFAULT NULL,
            PRIMARY KEY (`id`),
            UNIQUE KEY `uniq_file_uid` (`file_unique_id`,`bot_id`) USING BTREE,
            KEY `doc_id` (`doc_id`,`man_id`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin COMMENT='Telegram 媒体索引表';
            """,
            "file_extension": """
            CREATE TABLE IF NOT EXISTS `file_extension` (
            `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT,
            `file_type` varchar(30) DEFAULT NULL,
            `file_unique_id` varchar(100) NOT NULL,
            `file_id` varchar(200) NOT NULL,
            `bot` varchar(50) DEFAULT NULL,
            `user_id` bigint(20) DEFAULT NULL,
            `create_time` datetime DEFAULT NULL,
            PRIMARY KEY (`id`),
            UNIQUE KEY `file_id` (`file_id`,`bot`),
            KEY `idx_file_unique_id` (`file_unique_id`),
            KEY `idx_file_id` (`file_id`),
            KEY `idx_bot` (`bot`),
            KEY `idx_uid_bid` (`file_unique_id`,`file_id`),
            KEY `idx_uid_bot` (`file_unique_id`,`bot`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
            """,
            "document": """
            CREATE TABLE IF NOT EXISTS `document` (
            `file_unique_id` varchar(100) NOT NULL,
            `file_size` int(12) UNSIGNED NOT NULL,
            `file_name` varchar(100) DEFAULT NULL,
            `mime_type` varchar(100) DEFAULT NULL,
            `caption` mediumtext DEFAULT NULL,
            `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `update_time` datetime DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
            `files_drive` varchar(100) DEFAULT NULL,
            `file_password` varchar(150) DEFAULT NULL,
            `kc_id` int(10) UNSIGNED DEFAULT NULL,
            `kc_status` enum('','pending','updated') DEFAULT NULL,
            PRIMARY KEY (`file_unique_id`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
            """,
            "photo": """
            CREATE TABLE IF NOT EXISTS `photo` (
            `file_unique_id` varchar(100) NOT NULL,
            `file_size` int(11) NOT NULL,
            `width` int(11) NOT NULL,
            `height` int(11) NOT NULL,
            `file_name` varchar(100) DEFAULT NULL,
            `caption` mediumtext DEFAULT NULL,
            `root_unique_id` varchar(100) DEFAULT NULL,
            `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `update_time` datetime DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
            `files_drive` varchar(100) DEFAULT NULL,
            `hash` varchar(64) DEFAULT NULL,
            `same_fuid` varchar(50) DEFAULT NULL,
            `kc_id` int(11) UNSIGNED DEFAULT NULL,
            `kc_status` varchar(10) DEFAULT NULL,
            PRIMARY KEY (`file_unique_id`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
            """,
            "video": """
            CREATE TABLE IF NOT EXISTS `video` (
            `file_unique_id` varchar(100) NOT NULL,
            `file_size` int(13) UNSIGNED NOT NULL,
            `duration` int(11) UNSIGNED DEFAULT NULL,
            `width` int(11) UNSIGNED DEFAULT NULL,
            `height` int(11) UNSIGNED DEFAULT NULL,
            `file_name` varchar(100) DEFAULT NULL,
            `mime_type` varchar(100) NOT NULL DEFAULT 'video/mp4',
            `caption` mediumtext DEFAULT NULL,
            `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `update_time` datetime DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
            `tag_count` int(11) DEFAULT 0,
            `kind` varchar(2) DEFAULT NULL,
            `credit` int(11) DEFAULT 0,
            `files_drive` varchar(100) DEFAULT NULL,
            `root` varchar(50) DEFAULT NULL,
            `kc_id` int(11) UNSIGNED DEFAULT NULL,
            `kc_status` enum('','pending','updated') DEFAULT NULL,
            PRIMARY KEY (`file_unique_id`),
            KEY `file_size` (`file_size`,`width`,`height`,`mime_type`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
            """,
            "animation": """
            CREATE TABLE IF NOT EXISTS `animation` (
            `file_unique_id` varchar(100) NOT NULL,
            `file_size` int(13) UNSIGNED NOT NULL,
            `duration` int(11) UNSIGNED DEFAULT NULL,
            `width` int(11) UNSIGNED DEFAULT NULL,
            `height` int(11) UNSIGNED DEFAULT NULL,
            `file_name` varchar(100) DEFAULT NULL,
            `mime_type` varchar(100) NOT NULL DEFAULT 'video/mp4',
            `caption` mediumtext DEFAULT NULL,
            `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `update_time` datetime DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
            `tag_count` int(11) DEFAULT 0,
            `kind` varchar(2) DEFAULT NULL,
            `credit` int(11) DEFAULT 0,
            `files_drive` varchar(100) DEFAULT NULL,
            `root` varchar(50) DEFAULT NULL,
            `kc_id` int(11) UNSIGNED DEFAULT NULL,
            `kc_status` enum('','pending','updated') DEFAULT NULL,
            PRIMARY KEY (`file_unique_id`),
            KEY `file_size` (`file_size`,`width`,`height`,`mime_type`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
            """,
            "bot": """
            CREATE TABLE IF NOT EXISTS `bot` (
            `bot_id` bigint(1) UNSIGNED NOT NULL,
            `bot_token` mediumtext NOT NULL,
            `bot_name` varchar(30) NOT NULL,
            `user_id` bigint(1) DEFAULT NULL,
            `bot_root` varchar(30) NOT NULL,
            `bot_title` varchar(30) NOT NULL,
            `work_status` enum('used','ban','free','frozen','') DEFAULT NULL,
            PRIMARY KEY (`bot_id`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
            """
        }

        for table_name, sql in tables_sql.items():
            try:
                await MySQLPool.execute(sql)
                print(f"✅ 确保表 `{table_name}` 存在")
            except Exception as e:
                print(f"❌ 创建表 `{table_name}` 失败: {e}")
                raise


    
    # send_media_by_doc_id 函数 
    async def send_media_by_doc_id(self, client, to_user_id, doc_id, client_type,msg_id=None):
        print(f"【send_media_by_doc_id】开始处理 doc_id={doc_id}，目标用户：{to_user_id}",flush=True)

        try:
            sql="""
                SELECT chat_id, message_id, doc_id, access_hash, file_reference, file_id, file_unique_id,file_type 
                FROM file_records WHERE doc_id = %s AND man_id = %s
            """
            row = await MySQLPool.fetchone(sql, (doc_id,self.man_id))
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
                await client.send_message(to_user_id, f"未找到 doc_id={doc_id} 对应的文件记录。(500)")
            return

        if client_type == 'bot':
            # 机器人账号发送
            await self.send_media_via_bot(client, to_user_id, row, reply_to_message_id=msg_id)
        else:
            await self.send_media_via_man(client, to_user_id, row, reply_to_message_id=msg_id)

    # send_media_by_file_unique_id 函数
    async def send_media_by_file_unique_id(self,client, to_user_id, file_unique_id, client_type, msg_id):
        ext_row = []
        print(f"👇-send_media_by_file_unique_id-",flush=True)
        print(f"【🚹】【1】[{file_unique_id}]开始处理 file_unique_id={file_unique_id}，先查询是否有该 file_unqiue_id 是否在库 , 目标用户：{to_user_id}",flush=True)
        try:
            
            sql = """
                SELECT chat_id, message_id, doc_id, access_hash, file_reference, file_id, file_unique_id,file_type 
                FROM file_records WHERE file_unique_id = %s AND bot_id = %s
                """
            
            row = await MySQLPool.fetchone(sql, (file_unique_id,self.bot_id,))
            print(f"【🚹】【2.C】[{file_unique_id}]查询结果：",flush=True)
            if not row: # if row = None
                
                ext_row = await self.fetch_file_by_source_id(file_unique_id)
                print(f"【🚹】【2-2】[{file_unique_id}]没有找到本地端的文档，需要查找扩展库",flush=True)
                
                if ext_row:
                    # print(f"【send_media_by_file_unique_id】在 file_extension 中找到对应记录，尝试从 Bot 获取文件",flush=True)
                    # 如果在 file_extension 中找到对应记录，尝试从 Bot 获取文件
                    print(f"【🚹】【2-3】[{file_unique_id}]扩展库有😄",flush=True)
                    bot_row = await self.receive_file_from_bot(ext_row)
                    
                    max_retries = 3
                    delay = 2  # 每次重试的延迟时间（秒）

                    if not bot_row: # 传送失败
                        print(f"【🤖】【4】从机器人获取文件失败，file_unique_id={file_unique_id}",flush=True)
                        text = f"未找到 file_unique_id={file_unique_id} 对应的文件记录。(181)"
                        if isinstance(client, Bot):
                            await client.send_message(to_user_id, text, reply_to_message_id=msg_id)
                        else:
                            await client.send_message(to_user_id, text, reply_to=msg_id)
                        
                        return
                    else:
                        return "retrieved"

                        # chat_id, message_id, doc_id, access_hash, file_reference_hex, file_id, file_unique_id, file_type = row
                        # await client.send_message(to_user_id, f"未找到 file_unique_id={file_unique_id} 对应的文件。(192)")
                        # return
                        # return await self.send_media_by_file_unique_id(client, to_user_id, file_unique_id, client_type, msg_id)
                        # pass
                else:
                    print(f"【🚹】【2-4】[{file_unique_id}]扩展库没有",flush=True)
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
                print(f"【🚹】【2-1】从本机可查询到",flush=True)
                await self.set_file_vaild_state(file_unique_id, vaild_state=9)   
                if row and row['doc_id'] is None:
                    print(f"【🚹】【3】发现 doc_id 为空，尝试发消息 这个媒体 给 {TARGET_GROUP_ID_FROM_BOT}",flush=True)
                    file_metadata = {
                        'file_type': row['file_type'],
                        'file_id': row['file_id'],
                        'file_unique_id': row['file_unique_id']
                    }
                    
                    await self.bot_send_file(file_metadata, TARGET_GROUP_ID_FROM_BOT)
                   
                    
               
                
        
        except Exception as e:
            if "Token is invalid" in str(e):
                print(f"[194] Bot Token 无效，请检查配置。")
                return
            print(f"[194] Error: {e}")
            return
        
        print(f"【🤖】【5】开始传送 {row['file_unique_id']} by {client_type}",flush=True)
        if client_type == 'bot':
            # 机器人账号发送
            await self.send_media_via_bot(client, to_user_id, row, reply_to_message_id=msg_id)
        else:
            await self.send_media_via_man(client, to_user_id, row, reply_to_message_id=msg_id)
        print(f"👆-send_media_by_file_unique_id-[{file_unique_id}]",flush=True)

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




    async def build_media_dict_from_telethon(self, msg):
        """
        dict 版 extract_video_metadata_from_telethon
        key 与原 tuple 输出语义完全一致：
        doc_id, access_hash, file_reference,
        mime_type, file_size, file_name, file_type
        """
        caption = (getattr(msg, "message", None) or getattr(msg, "raw_text", None) or None)
        # ================== Document / Video ==================
        if msg.document:
            media = msg.document

            # 判定是否为 video（document + video attribute）
            is_video = any(
                isinstance(attr, DocumentAttributeVideo)
                for attr in (media.attributes or [])
            )

            file_type = "video" if is_video else "document"

            return {
                "doc_id": media.id,
                "access_hash": media.access_hash,
                "file_reference": media.file_reference.hex(),
                "mime_type": media.mime_type,
                "file_size": media.size,
                "file_name": self.get_file_name(media),
                "file_type": file_type,
                "caption": caption,
            }

        # ================== Video（理论上不会先于 document，但保留语义） ==================
        if msg.video:
            media = msg.video

            return {
                "doc_id": media.id,
                "access_hash": media.access_hash,
                "file_reference": media.file_reference.hex(),
                "mime_type": media.mime_type or "video/mp4",
                "file_size": media.size,
                "file_name": self.get_file_name(media),
                "file_type": "video",
                "caption": caption,
            }

        # ================== Photo（结构与 document 不同，必须单独处理） ==================
        if msg.photo:
            p = msg.photo  # telethon.tl.types.Photo，本体才有 access_hash / file_reference
            
            # file_size：从 sizes 里取最大那个 size
            max_size = None
            sizes = getattr(p, "sizes", None) or []
            for s in sizes:
                sz = getattr(s, "size", None)
                if isinstance(sz, int):
                    max_size = sz if (max_size is None or sz > max_size) else max_size

            return {
                "doc_id": p.id,
                "access_hash": getattr(p, "access_hash", None),
                "file_reference": (p.file_reference.hex() if getattr(p, "file_reference", None) else None),
                "mime_type": "image/jpeg",
                "file_size": max_size,
                "file_name": None,
                "file_type": "photo",
                "caption": caption,
            }

        raise ValueError("message 不包含可识别的媒体: photo / document / video")




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

        process_header = f"--【🤖】{row['file_unique_id']} x "
    
        from aiogram import Bot
        print(f"{process_header}开始处理 file_unique_id={row['file_unique_id']}，bot_id={row['bot_id']}",flush=True)
        mybot = Bot(token=bot_token)
        try:
            print(f"{process_header}准备让机器人{row['bot_id']}发送文件file_unique_id={row['file_unique_id']} 给 【👦】{self.man_id}",flush=True)
            if row["file_type"] == "photo" or row["file_type"] == "p":
                # await mybot.send_photo(chat_id=7496113118, photo=row["file_id"])
                retSend = await mybot.send_photo(chat_id=self.man_id, photo=row["file_id"])
            elif row["file_type"] == "video" or row["file_type"] == "v":
                retSend = await mybot.send_video(chat_id=self.man_id, video=row["file_id"])

            elif row["file_type"] == "document" or row["file_type"] == "d":
                retSend = await mybot.send_document(chat_id=self.man_id, document=row["file_id"])
            elif row["file_type"] == "animation" or row["file_type"] == "n":
                retSend = await mybot.send_animation(chat_id=self.man_id, animation=row["file_id"])

            print(f"{process_header} 媒体已 私发 到👦，file_unique_id={row['file_unique_id']}",flush=True)
            # print(f"\n【🤖】4️⃣retSend=>{retSend}\n",flush=True)
        except TelegramForbiddenError as e:
        # 私聊未 /start、被拉黑、群权限不足等
            print(f"{process_header}发送被拒绝（Forbidden）: {e}", flush=True)
        except TelegramNotFound:
            print(f"{process_header} chat not found: {self.man_id}. 可能原因：ID 错、bot 未入群、或用户未对该 bot /start", flush=True)
            # 机器人根本不认识这个 chat（不在群里/用户未 start/ID 错）
            await self.user_client.send_message(row["bot"], "/start")
            await self.user_client.send_message(row["bot"], "[~bot~]")
            
        except TelegramBadRequest as e:
            # 这里能准确看到 “chat not found”“message thread not found”等具体文本
            await self.user_client.send_message(row["bot"], "/start")
            await self.user_client.send_message(row["bot"], "[~bot~]")           
            print(f"{process_header} 发送失败（BadRequest）: {e}", flush=True)
        except Exception as e:
            if "Unauthorized" in str(e):
                await self.user_client.send_message(row["bot"], "/start")
                await self.user_client.send_message(row["bot"], "[~bot~]") 
                print(f"{process_header} {e}", flush=True)
            else:
                # 不要在所有异常里就发 /start；只在你需要唤醒对话时再做
                print(f"{process_header} ❌ 发送失败: {e}", flush=True)
        finally:

            print(f"{process_header} 最终结束，回主流程看看 👦 有没有收到了")
            await mybot.session.close()
            return retSend
             
    # send_media_via_man 函数 
    async def send_media_via_man_old(self, client, to_user_id, row, reply_to_message_id=None):
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
            print(f"【👦】准备发送文件：{input_doc.id}, {input_doc.access_hash}, {input_doc.file_reference.hex()}",flush=True)
            await client.send_file(to_user_id, input_doc, reply_to=reply_to_message_id)
        except Exception:
            # file_reference 过期时，重新从历史消息拉取
            try:
                msg = await client.get_messages(chat_id, ids=message_id)
                if not msg:
                    print(f"【👦】历史消息中未找到对应消息，可能已被删除。(286)",flush=True)
                    sql = """
                        UPDATE file_records SET  access_hash = NULL, file_reference = NULL, doc_id = NULL
                        WHERE doc_id = %s and man_id = %s
                    """
                    await MySQLPool.execute(sql, (row["doc_id"], self.man_id))

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
                    print(f"【👦】重新获取文件引用：{media.id}, {media.access_hash}, {media.file_reference.hex()}",flush=True)
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
                    
                    
                    print(f"【👦】重新获取文件引用成功，准备发送。",flush=True)
            

                    await client.send_file(to_user_id, new_input, reply_to=reply_to_message_id)
            except Exception as e:
                print(f"【👦】发送文件时出错：{e}",flush=True)
                await client.send_message(to_user_id, f"【👦】发送文件时出错：{e}")

    async def send_media_via_man(self, client, to_user_id, row, reply_to_message_id=None):
        chat_id            = row.get("chat_id")
        message_id         = row.get("message_id")
        doc_id             = row.get("doc_id")
        access_hash        = row.get("access_hash")
        file_reference_hex = row.get("file_reference")
        file_type          = row.get("file_type")
        file_id            = row.get("file_id")
        file_unique_id     = row.get("file_unique_id")

        def _has_ref_fields() -> bool:
            return bool(doc_id) and bool(access_hash) and bool(file_reference_hex)

        async def _send_from_history():
            msg = await client.get_messages(chat_id, ids=message_id)
            if not msg:
                raise RuntimeError("history message not found (maybe deleted)")
            media = msg.document or msg.photo or msg.video
            if not media:
                raise RuntimeError("history message has no media")
            await client.send_file(to_user_id, media, reply_to=reply_to_message_id)

        async def _refresh_by_bot_and_retry():
            """
            第三兜底：历史消息没了 & 引用过期时，用 bot 的 file_id 重新投喂给 man，
            让系统获得新的 doc_id/access_hash/file_reference，再重试发送。
            """
            if not (file_id and file_type):
                raise RuntimeError("no file_id/file_type to refresh by bot")

            sql = """
                UPDATE file_records SET  access_hash = NULL, file_reference = NULL, doc_id = NULL
                WHERE file_unique_id = %s and man_id = %s
            """
            await MySQLPool.execute(sql, (file_unique_id, self.man_id))

            # 1) 先让 bot 发给 man（你旧版就是这么做的）
            await self.send_media_via_bot(self.bot_client, self.man_id, {
                "file_type": file_type,
                "file_id": file_id,
            })

            # 2) 关键：此时需要依赖你群组/私聊的回调把新的 ref 写回 file_records
            #    这里给一个简单轮询重查（最多等 3 秒）
            for _ in range(6):
                await asyncio.sleep(0.5)
                new_row = await MySQLPool.fetchone(
                    """
                    SELECT chat_id, message_id, doc_id, access_hash, file_reference, file_id, file_unique_id, file_type
                    FROM file_records
                    WHERE file_unique_id=%s AND man_id=%s
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (file_unique_id, self.man_id),
                )
                if new_row and new_row.get("file_reference") and new_row.get("doc_id"):
                    # 用刷新后的 row 再走一次 send_media_via_man（递归一次即可）
                    return await self.send_media_via_man(client, to_user_id, new_row, reply_to_message_id)

            raise RuntimeError("bot refresh sent, but file_records not updated in time")

        try:
            print(f"【👦】准备发送文件，file_type={file_type}, doc_id={doc_id}, access_hash={access_hash}",flush=True)
            # 优先走历史消息（最稳：可自动刷新引用）
            await _send_from_history()
            return

        except Exception:
            # 历史消息拿不到，再尝试 DB ref 直发
            
            pass

        try:
            print(f"【👦】尝试用 DB 引用发送文件，file_type={file_type}, doc_id={doc_id}, access_hash={access_hash}",flush=True)
            if file_type == "photo":
                if not _has_ref_fields():
                    return await _refresh_by_bot_and_retry()
                file_reference = bytes.fromhex(file_reference_hex)
                input_photo = InputPhoto(id=int(doc_id), access_hash=int(access_hash), file_reference=file_reference)
                await client.send_file(to_user_id, input_photo, reply_to=reply_to_message_id)
                return

            if file_type in ("document", "video"):
                if not _has_ref_fields():
                    return await _refresh_by_bot_and_retry()
                file_reference = bytes.fromhex(file_reference_hex)
                input_doc = InputDocument(id=int(doc_id), access_hash=int(access_hash), file_reference=file_reference)
                await client.send_file(to_user_id, input_doc, reply_to=reply_to_message_id)
                return

            # 其它类型统一走 bot 刷新
            print(f"【👦】未知文件类型，尝试用 bot 刷新，file_type={file_type}",flush=True)
            return await _refresh_by_bot_and_retry()

        except FileReferenceExpiredError:
            print(f"【👦】文件引用过期，尝试用 bot 刷新，file_type={file_type}",flush=True)
            # 引用过期：直接走 bot 刷新（不要再回拉历史了，历史前面已经失败过）
            return await _refresh_by_bot_and_retry()

        except Exception as e:
            print(f"【👦】发送文件时出错：{e}，尝试用 bot 刷新",flush=True)
            # 其它异常：最后也尝试 bot 刷新一次
            try:
                return await _refresh_by_bot_and_retry()
            except Exception as e2:
                raise RuntimeError(f"send_media_via_man failed: {e} | refresh fallback failed: {e2}") from e2

    # send_media_via_bot 函数
    async def send_media_via_bot(self, bot_client, to_user_id, row, reply_to_message_id=None):
        """
        bot_client: 🤖 Bot 实例
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
            
            print(f"【🤖】文件已发送到 {to_user_id}，file_id={file_id}",flush=True)
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
        print(f"【🤖】收到私聊文本：{message.text}，来自 {message.chat.first_name}",flush=True)
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
               
                print(f"正在等待扩展库的渲染【Telethon】已从 Bot 获取文件，准备发送到 {to_user_id}，file_unique_id={file_unique_id}",flush=True)
                async def delayed_resend(get_file_unique_id):
                    for _ in range(6):  # 最多重试 6 次
                        try:
                            # 尝试发送文件(机器人)
                            print(f"【Telethon】第 {_+1} 次检查是否收到渲染，并尝试发送文件：{get_file_unique_id} 到 {to_user_id} ",flush=True)
                            if self.loading_manager.has_file_id(get_file_unique_id):
                            
                                # 显示第几次
                                await self.send_media_by_file_unique_id(self.bot_client, to_user_id, get_file_unique_id, 'bot', reply_to_message)
                                return
                            else:
                                await asyncio.sleep(0.9)
                        except Exception as e:
                            print(f"【Telethon】发送失败，重试中：{e}", flush=True)
                    await self.send_media_by_file_unique_id(self.bot_client, to_user_id, get_file_unique_id, 'bot', reply_to_message)
                    print(f"【Telethon】最终尝试发送文件：{get_file_unique_id} 到 {to_user_id}，也有可能收不到",flush=True)

                asyncio.create_task(delayed_resend(file_unique_id))
            else:
                print(f">>>>>【🤖】文件已发送到 {to_user_id}，file_unique_id={file_unique_id}",flush=True)


        elif len(text)<40 and self.doc_id_pattern.fullmatch(text):
            await self.send_media_by_doc_id(self.bot_client, to_user_id, int(text), 'bot', reply_to_message)
        else:
            
            await message.delete()

# ================= BOT Media Private. 私聊 Message 媒体处理：Aiogram：BOT账号 =================
    async def aiogram_handle_private_media(self, message: types.Message):
        doc_id= None

        # 若不是私信 且 不包括媒體，則跳過
        if message.chat.type != "private" or message.content_type not in {
            ContentType.PHOTO, ContentType.DOCUMENT, ContentType.VIDEO, ContentType.ANIMATION
        }:
            return

        print(f"【🤖】收到私聊媒体：{message.content_type}，来自 user_id = {message.from_user.id}",flush=True)
        # 只处理“私聊里发来的媒体”


        metadata = await self.build_media_dict_from_aiogram(message)
        file_unique_id = metadata['file_unique_id']
        caption = metadata['caption']


        if message.from_user.id == self.man_id:
            doc_id = int(caption)
            
        if doc_id:
            sql = """
                SELECT * FROM file_records WHERE doc_id=%s AND man_id=%s
                """
            record =  await MySQLPool.fetchone(sql, (doc_id, self.man_id))
            print(f"【🤖】通过 doc_id={doc_id} 查询到的记录", flush=True)

        if doc_id is None or record is None:
            sql = """
                SELECT * FROM file_records WHERE file_unique_id=%s AND bot_id=%s
                """
            record =  await MySQLPool.fetchone(sql, (file_unique_id, self.bot_id))
            print(f"【🤖】通过 file_unique_id={file_unique_id} 查询到的记录", flush=True)

        if record:
             if record['doc_id'] is not None and record['file_unique_id'] is not None:
                print(f"【🤖】已存在：doc_id={doc_id}，file_unique_id={record['file_unique_id']}，跳过转发", flush=True)
                return   
             else:
                print(f"【🤖】记录存在但缺少 doc_id {record['doc_id']} 或 file_unique_id ( {record['file_unique_id']})，继续处理", flush=True)   
        else:
            print(f"【🤖】这个doc_id={doc_id}:file_unique_id={file_unique_id} 不存在最新的库中",flush=True)     

        if not record or (record and record['doc_id'] is None):
            print(f"【🤖】发送给 {TARGET_GROUP_ID_FROM_BOT} 以获取 doc_id ")
            file_metadata = await self.build_media_dict_from_aiogram(message)
            metadata =await self.bot_send_file(file_metadata, target_group_id = TARGET_GROUP_ID_FROM_BOT)
            metadata['bot_id'] = self.bot_id

            #删除 metadata 中的 chat_id 和 message_id，避免插入 file_records 时冲突
            if TARGET_GROUP_ID_FROM_BOT != TARGET_GROUP_ID:
                if 'chat_id' in metadata:
                    del metadata['chat_id']
                if 'message_id' in metadata:
                    del metadata['message_id']
        else:
            metadata = await self.build_media_dict_from_aiogram(message)
            metadata['bot_id'] = self.bot_id

        if record and record['id'] is not None:
            metadata['id'] = record['id']

        try:
            await self.upsert_media(metadata)
            await self.upsert_file_record(metadata)

            self.loading_manager.attach_file_id(metadata['file_unique_id'], metadata['file_id'])
            print(f"【👦】附加加载管理器，file_unique_id={metadata['file_unique_id']} file_id={metadata['file_id']}", flush=True)
            
        except Exception as e:
            code = e.args[0] if e.args else None
            msg = e.args[1] if len(e.args) > 1 else str(e)

            if code == 1062:
                # Duplicate entry
                # msg 里也有 key 名：for key 'uniq_file_uid'
                if 'uniq_file_uid' in msg:
                    sql = """
                        DELETE FROM file_records
                        WHERE file_unique_id = %s AND bot_id = %s
                        LIMIT 1
                    """
                    await MySQLPool.execute(sql, (metadata['file_unique_id'], metadata['bot_id']))
                    await self.upsert_file_record(metadata)



            



        await message.delete()
        print(f"【🤖】🔚吃掉媒体，结束流程 ")
       
   
    
    
    async def bot_send_file(self, meta_message, target_group_id):
        ret = None
        # ⬇️ 发到群组
        file_id = meta_message['file_id']
        file_unique_id = meta_message['file_unique_id']   

        if meta_message['file_type'] == "photo":
            ret = await self.bot_client.send_photo(target_group_id, file_id, caption=file_unique_id)
        elif meta_message['file_type'] == "document":
            ret = await self.bot_client.send_document(target_group_id, file_id, caption=file_unique_id)
        elif meta_message['file_type'] == "animation":
            ret = await self.bot_client.send_animation(target_group_id, file_id, caption=file_unique_id)
        else:
            ret = await self.bot_client.send_video(target_group_id, file_id, caption=file_unique_id)

        metadata = await self.build_media_dict_from_aiogram(ret)
        metadata['chat_id'] = ret.chat.id
        metadata['message_id'] = ret.message_id
        metadata['uploader_type'] = 'bot'
        return metadata

# ================= BOT Media Group. 群聊 Message 图片/文档/视频处理：Aiogram：BOT账号 =================
    async def aiogram_handle_group_media(self, message: types.Message):
        TARGET_GROUP_ID = self.config.get('target_group_id')
        row = None
        # 只处理“指定群组里发来的媒体”
        if message.chat.id != TARGET_GROUP_ID or message.content_type not in {
            ContentType.PHOTO, ContentType.DOCUMENT, ContentType.VIDEO, ContentType.ANIMATION
        }:
            return


        metadata = await self.build_media_dict_from_aiogram(message)
        chat_id = message.chat.id
        message_id = message.message_id

      
        print(f"【🤖】收到群聊媒体：{metadata['file_unique_id']}, 来自UID: {message.from_user.id}",flush=True)
        
       

        if metadata and metadata['caption']:
            caption = metadata['caption']
            if caption and caption.isdigit():
                doc_id = int(caption)
                sql = """
                    SELECT * FROM file_records WHERE doc_id=%s AND man_id=%s
                    """
                row =  await MySQLPool.fetchone(sql, (doc_id, self.man_id))
                print(f"【🤖】通过 doc_id={doc_id} 查询到的记录")

        if not row:
            try:
                # 检查是否已存在相同 file_unique_id 的记录

                sql = '''
                    SELECT * FROM file_records 
                    WHERE file_unique_id = %s AND bot_id = %s
                    '''
                row = await MySQLPool.fetchone(sql, (metadata['file_unique_id'], self.bot_id))

                if row:
                    if row['chat_id'] != chat_id and row['message_id'] != message_id:
                        await self.bot_client.delete_message(chat_id, message_id)

            except Exception as e:
                print(f"578 Error: {e}")
    
        if not row:
            sql = """
                SELECT * FROM file_records WHERE chat_id=%s AND message_id=%s
                """
            row =  await MySQLPool.fetchone(sql, (chat_id, message_id))

        metadata['bot_id'] = self.bot_id
        
        if row and row['id']:
            metadata['id'] = row['id']    

        try:
            await self.upsert_media(metadata)
            await self.upsert_file_record(metadata)
            
        except Exception as e:
            
            code = e.args[0] if e.args else None
            msg = e.args[1] if len(e.args) > 1 else str(e)

            if code == 1062:
                # Duplicate entry
                # msg 里也有 key 名：for key 'uniq_file_uid'
                if 'uniq_file_uid' in msg:
                    sql = """
                        DELETE FROM file_records
                        WHERE file_unique_id = %s AND bot_id = %s AND doc_id != %s
                        
                    """
                    await MySQLPool.execute(sql, (metadata['file_unique_id'], metadata['bot_id'], metadata.get('doc_id')))
                    await self.upsert_file_record(metadata)
                    print(f"AIOR-606 Error: {e}")

        #TODO: 如果都有要回到哪一个 chat_id, message_id, 是否直接回就好? (但懒得想) 12/21
        self.loading_manager.attach_file_id(metadata['file_unique_id'], metadata['file_id'])
        
        

    # ================= Human Private Text  私聊 Message 文字处理：人类账号 =================
    async def handle_user_private_text(self,event):
        _title = ''
        msg = event.message
        if not msg.is_private or msg.media or not msg.text:
            return

        to_user_id = msg.from_id

        
        
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

        if len(text)<40 and self.doc_id_pattern.fullmatch(text):
            _title = f"【👦】{msg.text} -"
            print(f"{_title}👇 (私聊) === 收到 doc_id- 请求 {msg.text}",flush=True)
            doc_id = int(text)
            await self.send_media_by_doc_id(self.user_client, to_user_id, doc_id, 'man', msg.id)


        elif len(text)<40 and self.file_unique_id_pattern.fullmatch(text):
            _title = f"【👦】{msg.text} -"
            print(f"{_title}👇 (私聊) ==== 收到 file_unqiue_id 请求- {msg.text}",flush=True)
            file_unique_id = text
            ret = await self.send_media_by_file_unique_id(self.user_client, to_user_id, file_unique_id, 'man', msg.id)
            
            if(ret=='retrieved'):
                print(f"{_title} 收到 retrieved , 已请 Bot 发送文件 {file_unique_id}，等待渲染成功，以回覆给 {to_user_id}",flush=True)
                async def delayed_resend(get_file_unique_id):
                    print(f".      背景检查 {get_file_unique_id}")
                    for _ in range(6):  # 最多重试 6 次
                        try:
                            # 尝试发送文件 (人型机器人)
                            
                            if self.loading_manager.has_file_id(get_file_unique_id):
                                # 显示第几次
                                print(f".      {_title}在 {_+1} 次检查 file_id 已渲染，并尝试回覆文件：{get_file_unique_id} 给 {to_user_id}",flush=True)
                                try:
                                    await self.send_media_by_file_unique_id(self.user_client, to_user_id, get_file_unique_id, 'man', msg.id)
                                except Exception as e:
                                    print(f"{_title}发送失败，重试中：{e}", flush=True)
                                return
                            else:
                                await asyncio.sleep(0.9)
                        except Exception as e:
                            print(f"{_title}发送失败，重试中：{e}", flush=True)
                    retsult_send_media_by_file_unique_id = await self.send_media_by_file_unique_id(self.user_client, to_user_id, get_file_unique_id, 'man', msg.id)
                    print(f"{_title}最后一试，可能没东西，尝试回覆文件：{get_file_unique_id} 给 {to_user_id} ret=>{retsult_send_media_by_file_unique_id}",flush=True)

                self.loading_manager.set(file_unique_id, chat_id=msg.chat_id, message_id=msg.id)
                asyncio.create_task(delayed_resend(file_unique_id))
            else:
                print(f"{_title}👆 直发，将文件：{file_unique_id} 回覆给 {to_user_id}，(send_media_via_) ",flush=True)
        else:
            await msg.delete()
            print(f"(私聊) 非请求=== 收到 text - {msg.text}",flush=True)
            

    # ================= Human Private Meddia 私聊 Media 媒体处理：人类账号 =================
    async def handle_user_private_media(self,event):
        
        msg = event.message
        await self.process_private_media_msg(msg, event)
        return
    
    async def process_private_media_msg(self, msg, event=None):
        
        TARGET_GROUP_ID = self.config.get('target_group_id')
        file_unique_id = None
        record = None
        upsert_data = {}

        # 若不是私聊,則不處理
        if not msg.is_private:
            print("【👦】-871 process_private_media_msg - not private")
            return

        # 若不包括媒体,也不處理
        if not (msg.document or msg.photo or msg.video or getattr(msg, 'media', None)):
            # print("PPMM-876 process_private_media_msg - no media content")
            # print(f"msg {msg}")
            return

        # doc_id, access_hash, file_reference, mime_type, file_size, file_name, file_type = await self.extract_video_metadata_from_telethon(msg)  
        # print(f"doc_id={doc_id}, access_hash={access_hash}, file_reference={file_reference}, mime_type={mime_type}, file_size={file_size}, file_name={file_name}, file_type={file_type}",flush=True)
        m = await self.build_media_dict_from_telethon(msg)

        doc_id         = m["doc_id"]
        access_hash    = m["access_hash"]
        file_reference = m["file_reference"]
        mime_type      = m["mime_type"]
        file_size      = m["file_size"]
        file_name      = m["file_name"]
        file_type      = m["file_type"]
        
        
        caption = ""
        if(event is None):
            print(f"【👦】👇 (私聊)-process_private_media_msg- {doc_id} -来自私聊媒体回溯处理：{msg.media} {file_type}，chat_id={msg.chat_id}", flush=True)
            caption        = msg.message or ""
            
        else:
            print(f"【👦】👇 (私聊)-process_private_media_msg- {doc_id} -收到私聊媒体，来自 {event.peer_id.user_id} doc_id = {doc_id} {file_type}",flush=True)
            caption        = event.message.text or ""
            
        # print(f"caption={caption}",flush=True)
            

        
        if caption !='':
            print(f"【👦】")
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
            elif event.peer_id.user_id == self.bot_id:
                file_unique_id = caption.strip()

        # 检查：TARGET_GROUP_ID 群组是否已有相同 doc_id

        if file_unique_id:
            print(f"【👦】私聊媒体带有 file_unique_id：{file_unique_id}", flush=True)
            sql = """
                SELECT * FROM file_records WHERE file_unique_id = %s AND bot_id = %s    
                """
            record = await MySQLPool.fetchone(sql, (file_unique_id, self.bot_id))
        
        if file_unique_id is None or record is None:    # 非机器人转发，或找不到记录
            try:
                
        
                sql = """
                    SELECT * FROM file_records WHERE doc_id = %s AND man_id = %s 
                    """
                record = await MySQLPool.fetchone(sql, (doc_id, self.man_id))
            except Exception as e:
                print(f"272 Error: {e}")
            
        if record:

            if record['doc_id'] is not None and record['file_unique_id'] is not None:
                print(f"【👦】确认已存在：doc_id={doc_id}，file_unique_id={record['file_unique_id']}，跳过转发", flush=True)
                return
            else:
                print(f"【👦】确认记录存在，但缺少 doc_id ({record['doc_id']}) 或 file_unique_id ({record['file_unique_id']}), 准备更新并转发到 {TARGET_GROUP_ID}", flush=True)
        else:
            print(f"【👦】1390:这个doc {doc_id} 不存在最新的库中，准备转发到 {TARGET_GROUP_ID}",flush=True)


        # 转发到群组，并删除私聊
        try:
            # 这里直接发送 msg.media，如果受保护会被阻止
            try:
                ret = await self.user_client.send_file(TARGET_GROUP_ID, msg.media, caption=str(doc_id))
                print(f"【👦】已转发到目标群组：{TARGET_GROUP_ID}，消息 ID：{ret.id}",flush=True)
            except ChatForwardsRestrictedError:
                print(f"【👦】🚫 跳过：该媒体来自受保护频道 msg.id = {msg.id}", flush=True)
                return  # ⚠️ 不处理，直接跳出
            except Exception as e:
                print(f"【👦】❌ 其他发送失败：{e}", flush=True)
                return
            
           
            # 插入或更新 placeholder 记录 (message_id 自动留空，由群组回调补全)
            upsert_data = {
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
            }

            if record and record['id']:
                upsert_data['id'] = record['id']
                print(f"【👦】更新记录 id={record['id']}")
                
            
            await self.upsert_file_record(upsert_data)

            
                
        except ChatForwardsRestrictedError:
            print(f"【👦】🚫 跳过：该媒体来自受保护频道 msg.id = {msg.id}", flush=True)
            
        except Exception as e:
            if "The chat is restricted and cannot be used in that request" in str(e):
                print(f"【👦】-⚠️ 這個群應該炸了", flush=True)
                
            else:
                print(f"【👦】❌ 其他错误：{e} TARGET_GROUP_ID={TARGET_GROUP_ID}", flush=True)
                '''
                有可能 doc_id+man 和 file_unique_id + bot 没有一对一对应关系
                所以需要再做处理, 等发生了再补
                '''
            return
                  
        print("【👦】👆 (私聊)-process_private_media_msg- 更新并传送给机器人，完成媒体接收流程")
        await msg.delete() 

    # ================= Human Group Media 3-1. 群组媒体处理：人类账号 =================
    async def handle_user_group_media(self,event):
        msg = event.message
        await self.process_group_media_msg(msg)

    async def process_group_media_msg(self,msg):
        
        if not (msg.document or msg.photo or msg.video or msg.animation):
            return
        file_type = ''
        row = None

        chat_id        = msg.chat_id
        message_id     = msg.id

        print(f"【👦】收到群组媒体，来自 chat_id={chat_id} message_id={message_id}, 检查库里有没有",flush=True)
        metadata = await self.build_media_dict_from_telethon(msg)

        # —— 步骤 A：先按 doc_id 查库 —— 
        if metadata["caption"] is not None:
            metadata["caption"] = metadata["caption"].strip()
            sql = '''
                SELECT * FROM file_records WHERE file_unique_id = %s AND bot_id = %s
                '''
            row = await MySQLPool.fetchone(sql, (metadata["caption"],self.bot_id))
            print(f"【👦】已经存 file_unique_id={metadata['caption']} 的记录", flush=True)

        if not row:
            try:
                # 检查是否已存在相同 doc_id 的记录
                sql = '''
                    SELECT * FROM file_records WHERE doc_id = %s AND man_id = %s
                    '''
                row = await MySQLPool.fetchone(sql, (metadata["doc_id"],self.man_id))
                print(f"【👦】通过 doc_id={metadata['doc_id']} 查询到的记录", flush=True)
                '''
                如何解决同步问题
                以及扩展名
                '''

            except Exception as e:
                print(f"[process_group_media_msg] doc_id 查库失败: {e}", flush=True)
    
        if not row:
            sql = '''
                SELECT * FROM file_records WHERE chat_id = %s AND message_id = %s
                '''
            row = await MySQLPool.fetchone(sql, (chat_id, message_id))
            print(f"【👦】通过 chat_id={chat_id} 和 message_id={message_id} 查询到的记录", flush=True)

        metadata['man_id'] = self.man_id

        if row and row['id']:
            metadata['id'] = row['id']   


        metadata['chat_id'] = chat_id
        metadata['message_id'] = message_id        

        try:
            print(f"【👦】- {metadata['doc_id']} - 更新记录", flush=True)
            await self.upsert_file_record(metadata)
           
        except Exception as e:
            print(f"AIOR-606 Error: {e}")        

        
        # B 分支保留消息，不删除