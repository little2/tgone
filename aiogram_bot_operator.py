"""Aiogram Bot 轮询、媒体解析与数据库写入。"""

import asyncio
import hashlib
import json
import os
import re
import unicodedata
from datetime import datetime
from urllib.parse import quote

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

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
        self.connected_event = asyncio.Event()
        self.media_forward_queue: asyncio.Queue[
            tuple[Message, int | str, str, bool]
        ] = (
            asyncio.Queue()
        )
        configured_channel_id = str(
            config.get("media_forward_channel_id")
            or os.getenv("MEDIA_FORWARD_CHANNEL_ID", "")
        ).strip()
        if configured_channel_id.isdigit():
            configured_channel_id = f"-100{configured_channel_id}"
        self.media_forward_channel_id: int | str = (
            int(configured_channel_id)
            if configured_channel_id.lstrip("-").isdigit()
            else configured_channel_id
        )

        store_channel_id = str(
            config.get("store_channel_id")
            or os.getenv("STORE_CHANNEL_ID", "")
        ).strip()
        if store_channel_id.isdigit():
            store_channel_id = f"-100{store_channel_id}"
        self.store_channel_id: int | str = (
            int(store_channel_id)
            if store_channel_id.lstrip("-").isdigit()
            else store_channel_id
        )

        self.taobao_bot_username = (
            (taobao_bot_username or config.get("taobao_bot_username") or "")
            .strip()
            .removeprefix("@")
            or "taobao67bot"
        )

    async def print_bot_message(self, message: Message) -> None:
        """打印 Aiogram Bot 收到的消息摘要与完整内容。"""
        media_info = self.get_message_media_info(message)
        # print(f"media_info=>{message.caption}\n")
        caption_payload = (
            self.parse_json_caption(message.caption)
            if media_info is not None
            else None
        )

        # print(f"\ncaption_payload=>{caption_payload}\n")
        # line 75 只有在私信时才会继续
        if message.chat.type != "private":
            return

        process_result = None
        if caption_payload is not None and "table" in caption_payload:
            if caption_payload["table"] == "pack":
                pack_id = await self.upsert_pack_from_media_message(message)
                process_result = (
                    f"已写入 sora_pack.id={pack_id}，"
                    "并更新对应 sora_code.extract_status=2"
                )
                # pack 媒体转到存储频道。
                self.media_forward_queue.put_nowait(
                    (
                        message,
                        self.store_channel_id,
                        self._build_forward_caption(caption_payload),
                        True,
                    )
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

                # 从table sora_pack 查出 sora_pack.id = item_result['pack_id] 的record, 令 caption_payload 更新为最新的 description 和 tags
                pack_record = await self.get_pack_by_id(item_result['pack_id'])
                if pack_record:
                    caption_payload['description'] = pack_record.get('description', '')
                    caption_payload['tags'] = pack_record.get('tags', [])

                print(f"Updated caption_payload: {caption_payload}")

                # pack_item 媒体转到媒体转发频道。
                self.media_forward_queue.put_nowait(
                    (
                        message,
                        self.media_forward_channel_id,
                        self._build_forward_caption(caption_payload),
                        False,
                    )
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
        # print(message.model_dump_json(indent=2, exclude_none=True), flush=True)

    async def handle_callback_query(self, callback_query: CallbackQuery) -> None:
        """处理 Bot 收到的按钮回调。"""
        handled = await HumanBotOperator.handle_captcha_callback(callback_query)
        if handled:
            return


    def _build_forward_caption(self, payload: dict) -> str:
        """将媒体 JSON caption 转为频道展示用的三行文本。"""
        description = payload.get("description", "")
        description_line = (
            re.sub(r"\s+", " ", description).strip()
            if isinstance(description, str)
            else ""
        )
        file_code = str(payload.get("file_code") or "").strip()
        tags = payload.get("tags", [])
        if isinstance(tags, str):
            tags = re.split(r"[,，]", tags)
        tag_line = " ".join(
            f"#{tag.removeprefix('#').strip()}"
            for tag in tags
            if isinstance(tag, str) and tag.removeprefix("#").strip()
        )
        lines = [description_line, file_code]
        if tag_line:
            lines.append(tag_line)
        return "\n".join(lines)

    async def _send_file(
        self,
        destination_chat_id: int | str,
        message: Message,
        caption: str,
        include_portal_button: bool = False,
    ) -> None:
        """以原媒体 file_id 重发文件，并使用指定 caption。"""
        reply_markup = None
        if include_portal_button:
            payload = self.parse_json_caption(message.caption) or {}
            file_code = str(payload.get("file_code") or "").strip()
            if file_code:
                reply_markup = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="🧊传送门1",
                                url=(
                                    "https://t.me/di5k31bot?text="
                                    f"{quote(file_code, safe='')}"
                                ),
                            )
                        ]
                    ]
                )
        if message.photo:
            await self.bot.send_photo(
                chat_id=destination_chat_id,
                photo=message.photo[-1].file_id,
                caption=caption,
                reply_markup=reply_markup,
            )
        elif message.video:
            await self.bot.send_video(
                chat_id=destination_chat_id,
                video=message.video.file_id,
                caption=caption,
                reply_markup=reply_markup,
            )
        elif message.animation:
            await self.bot.send_animation(
                chat_id=destination_chat_id,
                animation=message.animation.file_id,
                caption=caption,
                reply_markup=reply_markup,
            )
        elif message.document:
            await self.bot.send_document(
                chat_id=destination_chat_id,
                document=message.document.file_id,
                caption=caption,
                reply_markup=reply_markup,
            )
        elif message.audio:
            await self.bot.send_audio(
                chat_id=destination_chat_id,
                audio=message.audio.file_id,
                caption=caption,
                reply_markup=reply_markup,
            )
        elif message.voice:
            await self.bot.send_voice(
                chat_id=destination_chat_id,
                voice=message.voice.file_id,
                caption=caption,
                reply_markup=reply_markup,
            )
        else:
            raise ValueError("不支持以带 caption 的方式重发此媒体类型")

    async def _forward_media_worker(self) -> None:
        """依照接收顺序在背景重发媒体到指定频道。"""
        while True:
            (
                source_message,
                destination_chat_id,
                caption,
                include_portal_button,
            ) = await self.media_forward_queue.get()
            try:
                await self._send_file(
                    destination_chat_id,
                    source_message,
                    caption,
                    include_portal_button,
                )
                # print(
                #     f"媒体 message_id={message_id} 已传到频道 "
                #     f"{self.media_forward_channel_id}",
                #     flush=True,
                # )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                print(
                    f"媒体 message_id={source_message.message_id} 传送失败：{exc}",
                    flush=True,
                )
            finally:
                self.media_forward_queue.task_done()


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

    async def get_pack_by_id(self, pack_id: int) -> dict | None:
        """根据 pack_id 从数据库中获取 sora_pack 记录，并归一化返回字段。"""
        if isinstance(pack_id, bool) or not isinstance(pack_id, int):
            raise TypeError("pack_id 必须是整数")
        if pack_id <= 0:
            raise ValueError("pack_id 必须大于 0")

        row = await MySQLPool.fetchone(
            "SELECT `id`, `pack_type`, `pack_content`, `tag`, `thumb_file_unique_id`, "
            "`owner_user_id`, `channel_chat_id`, `channel_message_id`, `created_ts`, "
            "`updated_ts` FROM `sora_pack` WHERE `id` = %s LIMIT 1",
            (pack_id,),
            error_tag="aiogram_bot_operator.get_pack_by_id",
        )
        if row is None:
            return None

        description = row.get("pack_content")
        if description is None:
            description = ""
        elif not isinstance(description, str):
            description = str(description)

        raw_tags = row.get("tag")
        tags: list[str] = []
        if isinstance(raw_tags, str):
            tags = [
                token.strip().removeprefix("#")
                for token in re.split(r"[,，]", raw_tags)
                if token and token.strip()
            ]
        elif isinstance(raw_tags, (list, tuple, set)):
            tags = [
                str(token).strip().removeprefix("#")
                for token in raw_tags
                if str(token).strip()
            ]

        normalized_row = dict(row)
        normalized_row["description"] = description.strip()
        normalized_row["tags"] = tags
        return normalized_row


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
            print("pack caption 的 file_code 为空或无效", flush=True)
            return None
            # raise ValueError("pack caption 的 file_code 不可为空")
        if isinstance(tags, str):
            tags = [tag.strip() for tag in tags.replace("，", ",").split(",")]
        if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
            raise ValueError("pack caption 的 tags 必须是字符串数组")

        normalized_code = unicodedata.normalize("NFC", file_code.strip())
        # extracted_code = HumanBotOperator._extract_consecutive_emojis(
        #     normalized_code,
        #     count=8,
        # )

        # if extracted_code is None:
        #     raise ValueError("pack caption 的 file_code 必须包含连续 8 个 Emoji")


        normalized_tags = [tag.strip() for tag in tags if tag.strip()]
        tag_value = ", ".join(normalized_tags)
        if len(tag_value) > 500:
            raise ValueError("pack caption 的 tags 总长度不可超过 500")
        return {
            "description": description.strip(),
            "file_code": file_code,
            "tag": tag_value or None,
        }


    async def upsert_pack_from_media_message(self, message: Message) -> int | None:
        """处理 Aiogram 收到的 table=pack 图片私信，并关联 sora_code。"""
        if message.chat.type != "private" or not message.photo:
            return None

        pack_data = self.parse_pack_caption(message.caption)
        # print(f"{pack_data}")
        if pack_data is None:
            return None

        thumb_file_unique_id = message.photo[-1].file_unique_id
        now_ts = int(datetime.now().timestamp())
        sender_id = getattr(message.from_user, "id", None)

        async def transaction(cur):
            await cur.execute(
                "SELECT `pack_id` FROM `sora_code` "
                "WHERE `code` = %s  LIMIT 1 FOR UPDATE",
                (pack_data["file_code"]),
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
                "WHERE `code` = %s ",
                (
                    pack_id,
                    pack_data["file_code"]
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
                (HumanBotOperator.BJD_CODE_BOT_ID, code_hash),
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
                        HumanBotOperator.BJD_CODE_BOT_ID,
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


    async def _check_channel_admin_permissions(self, bot_id: int) -> None:
        """检查 Bot 是否拥有两个媒体频道的管理员权限。"""
        channels = (
            ("store_channel_id", self.store_channel_id),
            ("media_forward_channel_id", self.media_forward_channel_id),
        )
        for setting_name, channel_id in channels:
            if not channel_id:
                print(f"⚠️ {setting_name} 未配置，跳过管理员权限检查。", flush=True)
                continue
            try:
                member = await self.bot.get_chat_member(
                    chat_id=channel_id,
                    user_id=bot_id,
                )
            except Exception as exc:
                print(
                    f"❌ 无法检查 {setting_name}={channel_id} 的管理员权限：{exc}",
                    flush=True,
                )
                continue

            status = getattr(member.status, "value", member.status)
            if status in {"administrator", "creator", "owner"}:
                print(
                    f"✅ Bot 是 {setting_name}={channel_id} 的管理员。",
                    flush=True,
                )
            else:
                print(
                    f"❌ Bot 不是 {setting_name}={channel_id} 的管理员 "
                    f"（当前身份：{status}）。",
                    flush=True,
                )

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
        dispatcher.callback_query.register(self.handle_callback_query)
        media_forward_worker = None

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
            await self._check_channel_admin_permissions(bot_info.id)
            self.connected_event.set()
            print(
                f"Aiogram Bot 已启动：id={bot_info.id} "
                f"username=@{self.taobao_bot_username}",
                flush=True,
            )
            media_forward_worker = asyncio.create_task(
                self._forward_media_worker(),
                name="aiogram-media-forward-worker",
            )
            await dispatcher.start_polling(bot)
        finally:
            if media_forward_worker is not None:
                media_forward_worker.cancel()
                await asyncio.gather(
                    media_forward_worker,
                    return_exceptions=True,
                )
            await bot.session.close()
