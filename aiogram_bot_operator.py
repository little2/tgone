"""Aiogram Bot 轮询、媒体解析与数据库写入。"""

import asyncio
import hashlib
import json
import os
import unicodedata
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError
from aiogram.types import Message

from human_bot_operator import HumanBotOperator
from tgone_mysql import MySQLPool


class AiogramBotOperator:
    """管理 Aiogram Bot，并处理收到的 Pack 媒体消息。"""

    def __init__(
        self,
        config: dict,
        taobao_bot_username: str | None = None,
    ):
        self.config = config
        self.taobao_bot_username = (
            (taobao_bot_username or config.get("taobao_bot_username") or "")
            .strip()
            .removeprefix("@")
            or "taobao67bot"
        )

    async def print_bot_message(self, message: Message) -> None:
        """打印 Aiogram Bot 收到的消息摘要与完整内容。"""
        media_info = self.get_message_media_info(message)
        caption_payload = (
            self.parse_json_caption(message.caption)
            if media_info is not None
            else None
        )
        process_result = None
        if caption_payload is not None and "table" in caption_payload:
            if caption_payload["table"] == "pack":
                pack_id = await self.upsert_pack_from_media_message(message)
                process_result = (
                    f"已写入 sora_pack.id={pack_id}，"
                    "并更新对应 sora_code.extract_status=2"
                )
            elif caption_payload["table"] == "pack_item":
                item_result = await self.upsert_pack_item_from_media_message(
                    message,
                    caption_payload,
                    media_info,
                )
                process_result = (
                    f"已写入 sora_pack.id={item_result['pack_id']}，"
                    f"sora_pack_item.id={item_result['item_id']}"
                )

        sender = message.from_user
        # print(
        #     "[Bot 收到消息] "
        #     f"message_id={message.message_id} "
        #     f"chat_id={message.chat.id} "
        #     f"chat_type={message.chat.type} "
        #     f"sender_id={getattr(sender, 'id', None)} "
        #     f"username={getattr(sender, 'username', None)} "
        #     f"date={message.date}",
        #     flush=True,
        # )
        print(message.model_dump_json(indent=2, exclude_none=True), flush=True)
        if process_result is not None:
            print(process_result, flush=True)


    def parse_json_caption(self, caption: str | None) -> dict | None:
        """caption 是 JSON object 时返回 dict，否则返回 None。"""
        if not caption or not caption.strip():
            return None
        try:
            payload = json.loads(caption)
        except (json.JSONDecodeError, TypeError):
            return None
        return payload if isinstance(payload, dict) else None


    def get_message_media_info(self, message: Message) -> dict | None:
        """取得 Aiogram 消息中主要媒体及缩略图的文件资料。"""
        if message.photo:
            media = message.photo[-1]
            thumbnail = message.photo[0]
            return {
                "file_unique_id": media.file_unique_id,
                "file_type": "photo",
                "thumb_file_id": thumbnail.file_id,
                "thumb_file_unique_id": thumbnail.file_unique_id,
            }

        for file_type in (
            "video",
            "animation",
            "document",
            "audio",
            "voice",
            "video_note",
            "sticker",
        ):
            media = getattr(message, file_type, None)
            if media is None:
                continue
            thumbnail = getattr(media, "thumbnail", None) or getattr(
                media,
                "thumb",
                None,
            )
            return {
                "file_unique_id": media.file_unique_id,
                "file_type": file_type,
                "thumb_file_id": getattr(thumbnail, "file_id", None),
                "thumb_file_unique_id": getattr(
                    thumbnail,
                    "file_unique_id",
                    None,
                ),
            }
        return None


    def parse_pack_caption(self, caption: str | None) -> dict | None:
        """解析 table=pack 的 JSON caption；其他 caption 返回 None。"""
        payload = self.parse_json_caption(caption)
        if payload is None or payload.get("table") != "pack":
            return None

        description = payload.get("description")
        file_code = payload.get("file_code")
        tags = payload.get("tags", [])
        if not isinstance(description, str):
            raise ValueError("pack caption 的 description 必须是字符串")
        if not isinstance(file_code, str) or not file_code.strip():
            raise ValueError("pack caption 的 file_code 不可为空")
        if isinstance(tags, str):
            tags = [tag.strip() for tag in tags.replace("，", ",").split(",")]
        if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
            raise ValueError("pack caption 的 tags 必须是字符串数组")

        normalized_code = unicodedata.normalize("NFC", file_code.strip())
        extracted_code = HumanBotOperator._extract_consecutive_emojis(
            normalized_code,
            count=8,
        )
        if extracted_code is None:
            raise ValueError("pack caption 的 file_code 必须包含连续 8 个 Emoji")

        normalized_tags = [tag.strip() for tag in tags if tag.strip()]
        tag_value = ", ".join(normalized_tags)
        if len(tag_value) > 500:
            raise ValueError("pack caption 的 tags 总长度不可超过 500")
        return {
            "description": description.strip(),
            "file_code": extracted_code,
            "tag": tag_value or None,
        }


    async def upsert_pack_from_media_message(self, message: Message) -> int | None:
        """处理 Aiogram 收到的 table=pack 图片私信，并关联 sora_code。"""
        if message.chat.type != "private" or not message.photo:
            return None

        pack_data = self.parse_pack_caption(message.caption)
        if pack_data is None:
            return None

        thumb_file_unique_id = message.photo[-1].file_unique_id
        now_ts = int(datetime.now().timestamp())
        sender_id = getattr(message.from_user, "id", None)

        async def transaction(cur):
            await cur.execute(
                "SELECT `pack_id` FROM `sora_code` "
                "WHERE `code` = %s AND `bot_id` = %s LIMIT 1 FOR UPDATE",
                (pack_data["file_code"], HumanBotOperator.SORA_CODE_BOT_ID),
            )
            code_row = await cur.fetchone()
            if code_row is None:
                raise LookupError(
                    f"找不到 file_code={pack_data['file_code']} 对应的 sora_code"
                )

            pack_id = code_row.get("pack_id")
            pack_exists = False
            if pack_id:
                await cur.execute(
                    "SELECT `id` FROM `sora_pack` WHERE `id` = %s LIMIT 1 FOR UPDATE",
                    (pack_id,),
                )
                pack_exists = await cur.fetchone() is not None

            pack_values = (
                1,
                pack_data["description"],
                pack_data["tag"],
                thumb_file_unique_id,
                sender_id,
                message.chat.id,
                message.message_id,
                now_ts,
                now_ts,
            )
            if pack_exists:
                await cur.execute(
                    "UPDATE `sora_pack` SET `pack_type` = %s, `pack_content` = %s, "
                    "`tag` = %s, `thumb_file_unique_id` = %s, `owner_user_id` = %s, "
                    "`channel_chat_id` = %s, `channel_message_id` = %s, "
                    "`created_ts` = %s, `updated_ts` = %s WHERE `id` = %s",
                    pack_values + (pack_id,),
                )
            else:
                await cur.execute(
                    "INSERT INTO `sora_pack` "
                    "(`pack_type`, `pack_content`, `tag`, `thumb_file_unique_id`, "
                    "`owner_user_id`, `channel_chat_id`, `channel_message_id`, "
                    "`created_ts`, `updated_ts`) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    pack_values,
                )
                pack_id = int(cur.lastrowid)

            await cur.execute(
                "UPDATE `sora_code` SET `pack_id` = %s, `extract_status` = 2 "
                "WHERE `code` = %s AND `bot_id` = %s",
                (
                    pack_id,
                    pack_data["file_code"],
                    HumanBotOperator.SORA_CODE_BOT_ID,
                ),
            )
            return int(pack_id)

        return await MySQLPool.transaction(transaction)


    async def upsert_pack_item_from_media_message(
        self,
        message: Message,
        caption_payload: dict | None = None,
        media_info: dict | None = None,
    ) -> dict[str, int]:
        """事务化写入 table=pack_item 的密文、私密 Pack 与媒体项目。"""
        if message.chat.type != "private":
            raise ValueError("pack_item 只接受 Bot 私聊媒体")
        if caption_payload is None:
            caption_payload = self.parse_json_caption(message.caption)
        if caption_payload is None or caption_payload.get("table") != "pack_item":
            raise ValueError("caption.table 必须是 pack_item")
        if media_info is None:
            media_info = self.get_message_media_info(message)
        if media_info is None:
            raise ValueError("pack_item 消息不包含支持的媒体")

        raw_code = caption_payload.get("file_code")
        if not isinstance(raw_code, str) or not raw_code.strip():
            raise ValueError("pack_item caption 的 file_code 不可为空")
        normalized_code = unicodedata.normalize("NFC", raw_code.strip())
        file_code = HumanBotOperator._extract_consecutive_emojis(
            normalized_code,
            count=8,
        )
        if file_code is None:
            raise ValueError("pack_item caption 的 file_code 必须包含连续 8 个 Emoji")

        code_hash = hashlib.sha256(file_code.encode("utf-8")).digest()
        now_ts = int(datetime.now().timestamp())
        sender_id = getattr(message.from_user, "id", None)

        async def transaction(cur):
            await cur.execute(
                "SELECT `id`, `pack_id` FROM `sora_code` "
                "WHERE `bot_id` = %s AND `code_hash` = %s LIMIT 1 FOR UPDATE",
                (HumanBotOperator.SORA_CODE_BOT_ID, code_hash),
            )
            code_row = await cur.fetchone()
            if code_row is None:
                await cur.execute(
                    "INSERT INTO `sora_code` "
                    "(`code`, `code_hash`, `pack_id`, `bot_id`, `valid_state`, "
                    "`created_ts`, `source_chat_id`, `source_message_id`, "
                    "`extract_status`) VALUES (%s, %s, NULL, %s, 1, %s, %s, %s, 3)",
                    (
                        file_code,
                        code_hash,
                        HumanBotOperator.SORA_CODE_BOT_ID,
                        now_ts,
                        message.chat.id,
                        message.message_id,
                    ),
                )
                code_id = int(cur.lastrowid)
                pack_id = None
            else:
                # sql: 令 extract_status = 3
                await cur.execute(
                    "UPDATE `sora_code` SET `extract_status` = 3 WHERE `id` = %s",
                    (code_row["id"],),
                )
                code_id = int(code_row["id"])
                pack_id = code_row.get("pack_id")

            pack_exists = False
            if pack_id:
                await cur.execute(
                    "SELECT `id` FROM `sora_pack` WHERE `id` = %s LIMIT 1 FOR UPDATE",
                    (pack_id,),
                )
                pack_exists = await cur.fetchone() is not None

            if pack_exists:
                await cur.execute(
                    "UPDATE `sora_pack` SET `pack_type` = 2, "
                    "`owner_user_id` = COALESCE(`owner_user_id`, %s), "
                    "`channel_chat_id` = %s, `channel_message_id` = %s, "
                    "`updated_ts` = %s WHERE `id` = %s",
                    (
                        sender_id,
                        message.chat.id,
                        message.message_id,
                        now_ts,
                        pack_id,
                    ),
                )
            else:
                await cur.execute(
                    "INSERT INTO `sora_pack` "
                    "(`pack_type`, `owner_user_id`, "
                    "`channel_chat_id`, `channel_message_id`, `created_ts`, `updated_ts`) "
                    "VALUES (2, %s, %s, %s, %s, %s)",
                    (
                        sender_id,
                        message.chat.id,
                        message.message_id,
                        now_ts,
                        now_ts,
                    ),
                )
                pack_id = int(cur.lastrowid)

            await cur.execute(
                "UPDATE `sora_code` SET `pack_id` = %s WHERE `id` = %s",
                (pack_id, code_id),
            )

            await cur.execute(
                "SELECT `id` FROM `sora_pack_item` "
                "WHERE `pack_id` = %s AND `file_unique_id` = %s "
                "LIMIT 1 FOR UPDATE",
                (pack_id, media_info["file_unique_id"]),
            )
            item_row = await cur.fetchone()
            if item_row is not None:
                item_id = int(item_row["id"])
                await cur.execute(
                    "UPDATE `sora_pack_item` SET `file_type` = %s, "
                    "`thumb_file_id` = %s, `thumb_file_unique_id` = %s, "
                    "`first_user_id` = COALESCE(`first_user_id`, %s), "
                    "`source_chat_id` = %s, `source_message_id` = %s "
                    "WHERE `id` = %s",
                    (
                        media_info["file_type"],
                        media_info["thumb_file_id"],
                        media_info["thumb_file_unique_id"],
                        sender_id,
                        message.chat.id,
                        message.message_id,
                        item_id,
                    ),
                )
            else:
                await cur.execute(
                    "SELECT COALESCE(MAX(`seq`), 0) + 1 AS `next_seq` "
                    "FROM `sora_pack_item` WHERE `pack_id` = %s",
                    (pack_id,),
                )
                seq_row = await cur.fetchone()
                next_seq = int((seq_row or {}).get("next_seq") or 1)
                await cur.execute(
                    "INSERT INTO `sora_pack_item` "
                    "(`pack_id`, `seq`, `file_unique_id`, `file_type`, "
                    "`thumb_file_id`, `thumb_file_unique_id`, `first_user_id`, "
                    "`source_chat_id`, `source_message_id`, `created_ts`) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        pack_id,
                        next_seq,
                        media_info["file_unique_id"],
                        media_info["file_type"],
                        media_info["thumb_file_id"],
                        media_info["thumb_file_unique_id"],
                        sender_id,
                        message.chat.id,
                        message.message_id,
                        now_ts,
                    ),
                )
                item_id = int(cur.lastrowid)

            return {"pack_id": int(pack_id), "item_id": item_id}

        return await MySQLPool.transaction(transaction)


    async def run(self) -> None:
        """使用 Aiogram 长轮询并打印 Bot 收到的所有消息。"""
       
        config = self.config
        bot_token = str(
            config.get("bot_token") or os.getenv("BOT_TOKEN", "")
        ).strip()
        if not bot_token:
            raise ValueError("缺少 Bot Token，请设置 BOT_TOKEN 或配置 bot_token")

        proxy_url = str(
            config.get("telegram_bot_proxy")
            or os.getenv("TELEGRAM_BOT_PROXY", "")
        ).strip()
        session = AiohttpSession(proxy=proxy_url or None)
        self.bot = Bot(token=bot_token, session=session)
        bot = self.bot
        dispatcher = Dispatcher()
        dispatcher.message.register(self.print_bot_message)

        try:
            print(
                "正在连接 Aiogram Bot..."
                + ("（使用 TELEGRAM_BOT_PROXY）" if proxy_url else "（直连）"),
                flush=True,
            )
            while True:
                try:
                    # 使用 me() 缓存 Bot 身份，避免 start_polling() 再请求一次 getMe。
                    bot_info = await asyncio.wait_for(bot.me(), timeout=15)
                    break
                except (asyncio.TimeoutError, TelegramNetworkError) as exc:
                    print(
                        f"Aiogram Bot 网络连接失败：{exc}；5 秒后重试。"
                        "可设置 TELEGRAM_BOT_PROXY。",
                        flush=True,
                    )
                    await asyncio.sleep(5)
            bot_username = str(getattr(bot_info, "username", "") or "").strip()
            bot_username = bot_username.removeprefix("@")
            if bot_username:
                self.taobao_bot_username = bot_username
                self.config["taobao_bot_username"] = bot_username
            print(
                f"Aiogram Bot 已启动：id={bot_info.id} "
                f"username=@{self.taobao_bot_username}",
                flush=True,
            )
            await dispatcher.start_polling(bot)
        finally:
            await bot.session.close()

