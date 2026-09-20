"""已登录 Telegram 使用者账号的人型机器人操作。"""

import asyncio
import hashlib
import io
import json
import os
import random
import re
from urllib.parse import unquote
import time
import unicodedata
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from telethon import TelegramClient, events
from telethon.errors import (
    ChatForwardsRestrictedError,
    InviteRequestSentError,
    UserAlreadyParticipantError,
    UsernameNotModifiedError,
)
from telethon.sessions import StringSession
from telethon.tl.functions.account import (
    SetPrivacyRequest,
    UpdateProfileRequest,
    UpdateUsernameRequest,
)
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.types import (
    Message,
    InputMessagesFilterVideo,
    InputPrivacyKeyForwards,
    InputPrivacyKeyPhoneCall,
    InputPrivacyKeyPhoneNumber,
    InputPrivacyKeyStatusTimestamp,
    InputPrivacyValueDisallowAll,
    MessageEntityBlockquote,
    MessageEntityHashtag,
    KeyboardButtonCopy,
    PeerChannel,
)

from telethon import utils
from aiogram import Bot
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup

from tgone_mysql import MySQLPool


class HumanBotOperator:
    """执行需要已登录使用者身份的 Telegram 操作。"""

    MONITOR_FORWARD_CHAT_ID = 5334310434
    BJD_CODE_BOT_ID = 8915213940
    PROTECTED_MEDIA_TRANSFER_TIMEOUT_SECONDS = 5 * 60
    CAPTCHA_SELECTION_TIMEOUT_SECONDS = 30
    _captcha_selection_waiters: dict[str, asyncio.Future[str]] = {}

    DEFAULT_TIMEZONE = ZoneInfo("Asia/Shanghai")
    TIME_PERIODS = (
        (5, 11, "morning"),
        (11, 14, "noon"),
        (14, 18, "afternoon"),
        (18, 22, "evening"),
        (22, 5, "late_night"),
    )



    _EMOJI_RANGES = (
        (0x00A9, 0x00A9),
        (0x00AE, 0x00AE),
        (0x203C, 0x203C),
        (0x2049, 0x2049),
        (0x2122, 0x2122),
        (0x2139, 0x2139),
        (0x2194, 0x21FF),
        (0x2300, 0x23FF),
        (0x25AA, 0x25AB),
        (0x25B6, 0x25B6),
        (0x25C0, 0x25C0),
        (0x25FB, 0x27BF),
        (0x2934, 0x2935),
        (0x2B05, 0x2B07),
        (0x2B1B, 0x2B1C),
        (0x2B50, 0x2B50),
        (0x2B55, 0x2B55),
        (0x3030, 0x3030),
        (0x303D, 0x303D),
        (0x3297, 0x3297),
        (0x3299, 0x3299),
        (0x1F000, 0x1FAFF),
    )

    def __init__(
        self,
        client: TelegramClient,
        taobao_bot_username: str | None = None,
    ) -> None:
        self.show_response = False
        self.client = client
        self.taobao_bot_username = (
            str(taobao_bot_username or "").strip().removeprefix("@") or None
        )
        self._next_message_id_by_chat: dict[int, int] = {}
        self.time_greetings = {
            "morning": [
                "早", "早啊", "早上好", "早安",  "早","古德猫宁","聊天就能加分","看看","没性欲了","早上好","开始爬楼","美好的早晨","好看的还是多"
                
            ],
            "noon": [
                "中午好", "午安",  "群友们好", "666", "好看爱看","看看","我要信誉分","多聊","好看🥰","爬楼啦","几千条"
                
            ],
            "afternoon": [
                "下午好", "下午好", "大佬们好","Hi","剩下的全靠点赞","聊天就能加分","看看","需要信誉分","没性欲了","多发言","太牛了","不错啊","牛逼","好看的还是多"
                
            ],
            "evening": [
                "晚上好",  "群友们好", "来色色了",  "刷刷分了", "晚安", "大佬们好","可以阿","唉","剩下的全靠点赞","服了","需要信誉","就是","9494","还是说少了啊","真不赖"
                
            ],
            "late_night": [
                "晚安", "群友们好",   "大佬好", "好看爱看","666","为了信誉分","积分一直涨，就是信誉分不涨了","新的一天","消息太多了","几千条"
            ]
        }

    @classmethod
    async def login_with_session(
        cls,
        session_string: str,
        api_id: int,
        api_hash: str,
        taobao_bot_username: str | None = None,
    ) -> "HumanBotOperator":
        """使用 Telethon StringSession 登录并返回操作实例。"""
        session_string = (session_string or "").strip()
        api_hash = (api_hash or "").strip()
        if not session_string:
            raise ValueError("session_string 不可为空")
        if not api_id:
            raise ValueError("api_id 不可为空")
        if not api_hash:
            raise ValueError("api_hash 不可为空")

        client = TelegramClient(
            StringSession(session_string),
            int(api_id),
            api_hash,
        )
        try:
            await client.connect()
            if not await client.is_user_authorized():
                raise RuntimeError("StringSession 尚未获得 Telegram 用户授权")
            else:
                me = await client.get_me()
                print(f"已成功使用 StringSession 登录 Telegram 用户。id = {me.id} {me.first_name}", flush=True)
        except Exception:
            await client.disconnect()
            raise

        return cls(client, taobao_bot_username=taobao_bot_username)

    @classmethod
    async def login_with_bot_token(
        cls,
        bot_token: str,
        api_id: int,
        api_hash: str,
        taobao_bot_username: str | None = None,
    ) -> "HumanBotOperator":
        """使用 Bot Token 登录，并返回与用户账号相同的操作接口。"""
        bot_token = (bot_token or "").strip()
        api_hash = (api_hash or "").strip()
        if not bot_token or not api_id or not api_hash:
            raise ValueError("bot_token、api_id、api_hash 均不可为空")

        client = TelegramClient(StringSession(), int(api_id), api_hash)
        try:
            await client.start(bot_token=bot_token)
        except Exception:
            await client.disconnect()
            raise
        return cls(client, taobao_bot_username=taobao_bot_username)

    @classmethod
    async def run_chat_script(
        cls,
        script_json: str | dict[str, Any],
        chat_id: int | str,
        message_thread_id: int | None = None,
        account_configs: dict[str, dict[str, Any]] | None = None,
        chat_invite_link: str | None = None,
        fast_mode: bool = False,
    ) -> dict[str, Any]:
        """解析 JSON、登录参与账号，并向参数指定的群组执行聊天脚本。"""
        payload, start_at = cls._validate_chat_script(script_json)
        participants = {
            participant["actor_id"]: participant
            for participant in payload["participants"]
        }
        if isinstance(chat_id, bool) or not isinstance(chat_id, (int, str)):
            raise ValueError("chat_id 必须是整数或可解析的群组标识")
        if isinstance(chat_id, str) and not chat_id.strip():
            raise ValueError("chat_id 不可为空")
        if message_thread_id is not None and (
            isinstance(message_thread_id, bool)
            or not isinstance(message_thread_id, int)
        ):
            raise ValueError("message_thread_id 必须是整数或 null")
        if not isinstance(fast_mode, bool):
            raise TypeError("fast_mode 必须是 bool")
        chat_invite_link = (chat_invite_link or "").strip() or None

        operator_by_actor: dict[str, HumanBotOperator] = {}
        account_label_by_actor: dict[str, str] = {}
        opened_operators: list[HumanBotOperator] = []

        try:
            if account_configs:
                normalized_configs = {
                    str(sender_id): config
                    for sender_id, config in account_configs.items()
                }
                operator_by_sender: dict[str, HumanBotOperator] = {}
                for participant in participants.values():
                    sender_id = str(participant["sender_id"])
                    operator = operator_by_sender.get(sender_id)
                    if operator is None:
                        credentials = normalized_configs.get(sender_id)
                        if credentials is None:
                            raise RuntimeError(
                                f"account_configs 找不到 sender_id={sender_id}"
                            )
                        operator = await cls._login_script_account(
                            participant["sender_type"],
                            credentials,
                        )
                        operator_by_sender[sender_id] = operator
                        opened_operators.append(operator)
                    operator_by_actor[participant["actor_id"]] = operator
                    account_label_by_actor[participant["actor_id"]] = sender_id
            else:
                participant_list = list(participants.values())
                non_user_actors = [
                    participant["actor_id"]
                    for participant in participant_list
                    if participant["sender_type"] != "user"
                ]
                if non_user_actors:
                    raise ValueError(
                        "未传入 account_configs 时只能自动分配用户 StringSession；"
                        f"以下 actor 是 bot：{', '.join(non_user_actors)}"
                    )

                database_accounts = await cls._load_script_accounts(
                    len(participant_list)
                )
                for participant, credentials in zip(
                    participant_list,
                    database_accounts,
                ):
                    operator = await cls._login_script_account(
                        "user",
                        credentials,
                    )
                    operator_by_actor[participant["actor_id"]] = operator
                    account_label_by_actor[participant["actor_id"]] = str(
                        credentials.get("bot_id") or "unknown"
                    )
                    opened_operators.append(operator)

            chat_entities: dict[str, Any] = {}
            for actor_id, operator in operator_by_actor.items():
                try:
                    chat_entities[actor_id] = await operator._resolve_input_entity(
                        chat_id
                    )
                except ValueError as resolve_error:
                    if chat_invite_link is not None:
                        await operator.join_chat(chat_invite_link)
                        try:
                            chat_entities[actor_id] = (
                                await operator._resolve_input_entity(chat_id)
                            )
                            continue
                        except ValueError:
                            pass

                    account_label = account_label_by_actor[actor_id]
                    invite_hint = (
                        "请传入 chat_invite_link，让程序先加入私有群。"
                        if chat_invite_link is None
                        else "该邀请链接可能无效、需要管理员审批，或与 chat_id 不匹配。"
                    )
                    raise ValueError(
                        f"actor={actor_id} 使用的账号={account_label} 无法访问 "
                        f"chat_id={chat_id}。请确认该账号已经加入目标群；{invite_hint}"
                    ) from resolve_error
            sent_messages: dict[str, Any] = {}
            send_errors: dict[str, BaseException] = {}
            sent_events = {
                message["message_id"]: asyncio.Event()
                for message in payload["messages"]
            }

            async def send_script_message(message: dict[str, Any]) -> None:
                message_id = message["message_id"]
                try:
                    scheduled_at = start_at + timedelta(
                        seconds=float(message["after_start"])
                    )
                    typing_duration = float(message["typing_duration"])
                    if not fast_mode:
                        typing_at = scheduled_at - timedelta(seconds=typing_duration)
                        await cls._sleep_until(typing_at)

                    reply_to = message_thread_id
                    reply_message_id = message.get("reply_to")
                    if reply_message_id is not None:
                        await sent_events[reply_message_id].wait()
                        if reply_message_id in send_errors:
                            raise RuntimeError(
                                f"回复目标 {reply_message_id} 发送失败"
                            ) from send_errors[reply_message_id]
                        reply_to = sent_messages[reply_message_id].id

                    actor_id = message["actor_id"]
                    operator = operator_by_actor[actor_id]
                    chat_entity = chat_entities[actor_id]
                    content = message["content"]
                    parse_mode = {
                        None: None,
                        "HTML": "html",
                        "MarkdownV2": "md",
                    }[content.get("parse_mode")]

                    async def send_now() -> Any:
                        return await operator.client.send_message(
                            chat_entity,
                            content["text"],
                            parse_mode=parse_mode,
                            reply_to=reply_to,
                        )

                    if fast_mode:
                        telegram_message = await send_now()
                    elif typing_duration > 0:
                        async with operator.client.action(chat_entity, "typing"):
                            await cls._sleep_until(scheduled_at)
                            telegram_message = await send_now()
                    else:
                        await cls._sleep_until(scheduled_at)
                        telegram_message = await send_now()

                    sent_messages[message_id] = telegram_message
                    print(
                        f"[脚本发言] {message_id} actor={message['actor_id']} "
                        f"telegram_message_id={telegram_message.id}",
                        flush=True,
                    )
                except BaseException as exc:
                    send_errors[message_id] = exc
                    raise
                finally:
                    sent_events[message_id].set()

            if fast_mode:
                try:
                    for message in payload["messages"]:
                        await send_script_message(message)
                except BaseException as exc:
                    if isinstance(exc, asyncio.CancelledError):
                        raise
                    raise RuntimeError(f"聊天脚本执行失败：{exc}") from exc
            else:
                tasks = [
                    asyncio.create_task(send_script_message(message))
                    for message in payload["messages"]
                ]
                try:
                    await asyncio.gather(*tasks)
                except BaseException as exc:
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
                    if isinstance(exc, asyncio.CancelledError):
                        raise
                    raise RuntimeError(f"聊天脚本执行失败：{exc}") from exc

            return {
                "script_id": payload["script"]["script_id"],
                "messages_sent": len(sent_messages),
                "telegram_message_ids": {
                    message_id: message.id
                    for message_id, message in sent_messages.items()
                },
            }
        finally:
            if opened_operators:
                await asyncio.gather(
                    *(operator.disconnect() for operator in opened_operators),
                    return_exceptions=True,
                )

    @staticmethod
    def _validate_chat_script(
        script_json: str | dict[str, Any],
    ) -> tuple[dict[str, Any], datetime]:
        """验证自动群聊 JSON，并返回脚本及带时区的开始时间。"""
        if isinstance(script_json, str):
            try:
                payload = json.loads(script_json)
            except json.JSONDecodeError as exc:
                raise ValueError("script_json 不是合法 JSON") from exc
        elif isinstance(script_json, dict):
            payload = script_json
        else:
            raise TypeError("script_json 必须是 JSON 字符串或 dict")

        if not isinstance(payload, dict):
            raise ValueError("JSON 顶层必须是 object")
        if payload.get("version") != "1.0":
            raise ValueError("仅支持 version=1.0")
        script = payload.get("script")
        participants = payload.get("participants")
        messages = payload.get("messages")
        if (
            not isinstance(script, dict)
            or not isinstance(script.get("script_id"), str)
            or not script["script_id"].strip()
        ):
            raise ValueError("script.script_id 不可为空")
        if not isinstance(script.get("title"), str):
            raise ValueError("script.title 必须是字符串")
        if not isinstance(participants, list) or not participants:
            raise ValueError("participants 必须是非空数组")
        if not isinstance(messages, list):
            raise ValueError("messages 必须是数组")

        try:
            start_at = datetime.fromisoformat(str(script["start_at"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("script.start_at 必须是 ISO 8601 时间") from exc
        if start_at.tzinfo is None or start_at.utcoffset() is None:
            raise ValueError("script.start_at 必须包含时区偏移")

        actor_ids = set()
        for participant in participants:
            if not isinstance(participant, dict):
                raise ValueError("participants 每一项必须是 object")
            actor_id = participant.get("actor_id")
            if (
                not isinstance(actor_id, str)
                or not actor_id.strip()
                or actor_id in actor_ids
            ):
                raise ValueError("participants.actor_id 不可为空或重复")
            actor_ids.add(actor_id)
            if not isinstance(participant.get("name"), str):
                raise ValueError(f"{actor_id}.name 必须是字符串")
            if participant.get("sender_type") not in {"user", "bot"}:
                raise ValueError("sender_type 只能是 user 或 bot")
            sender_id = participant.get("sender_id")
            if (
                isinstance(sender_id, bool)
                or not isinstance(sender_id, (int, str))
                or (isinstance(sender_id, str) and not sender_id.strip())
            ):
                raise ValueError("participants.sender_id 不可为空")

        message_ids: dict[str, float] = {}
        previous_after_start = -1.0
        for message in messages:
            if not isinstance(message, dict):
                raise ValueError("messages 每一项必须是 object")
            message_id = message.get("message_id")
            if (
                not isinstance(message_id, str)
                or not message_id.strip()
                or message_id in message_ids
            ):
                raise ValueError("messages.message_id 不可为空或重复")
            if message.get("actor_id") not in actor_ids:
                raise ValueError(f"{message_id}.actor_id 不存在")

            after_start = message.get("after_start")
            typing_duration = message.get("typing_duration")
            if (
                isinstance(after_start, bool)
                or not isinstance(after_start, (int, float))
                or after_start < 0
            ):
                raise ValueError(f"{message_id}.after_start 必须是非负数")
            if after_start < previous_after_start:
                raise ValueError("messages 必须按 after_start 从小到大排列")
            if (
                isinstance(typing_duration, bool)
                or not isinstance(typing_duration, (int, float))
                or typing_duration < 0
            ):
                raise ValueError(f"{message_id}.typing_duration 必须是非负数")

            reply_to = message.get("reply_to")
            if reply_to is not None and not isinstance(reply_to, str):
                raise ValueError(f"{message_id}.reply_to 必须是字符串或 null")
            if reply_to is not None and (
                reply_to not in message_ids
                or message_ids[reply_to] >= float(after_start)
            ):
                raise ValueError(f"{message_id}.reply_to 必须引用时间更早的消息")

            content = message.get("content")
            if not isinstance(content, dict) or not isinstance(content.get("text"), str):
                raise ValueError(f"{message_id}.content.text 必须是字符串")
            if content.get("parse_mode") not in {None, "HTML", "MarkdownV2"}:
                raise ValueError(f"{message_id}.content.parse_mode 不受支持")

            message_ids[message_id] = float(after_start)
            previous_after_start = float(after_start)

        return payload, start_at

    @classmethod
    async def _login_script_account(
        cls,
        sender_type: str,
        credentials: dict[str, Any],
    ) -> "HumanBotOperator":
        """使用脚本账号资料登录用户或 Bot。"""
        api_id = int(credentials.get("api_id") or os.getenv("API_ID", 0))
        api_hash = str(credentials.get("api_hash") or os.getenv("API_HASH", ""))
        if sender_type == "user":
            session_string = str(
                credentials.get("session_string")
                or credentials.get("bot_token")
                or ""
            )
            return await cls.login_with_session(session_string, api_id, api_hash)

        bot_token = str(credentials.get("bot_token") or "").strip()
        bot_id = credentials.get("bot_id")
        if bot_token and ":" not in bot_token and bot_id:
            bot_token = f"{bot_id}:{bot_token}"
        return await cls.login_with_bot_token(bot_token, api_id, api_hash)

    @staticmethod
    async def _load_script_accounts(count: int) -> list[dict[str, Any]]:
        """按参与者数量加载可用的用户 StringSession。"""
        if count <= 0:
            return []

        rows = await MySQLPool.fetchall(
            "SELECT `bot_id`, `bot_token` AS `session_string`, `api_id`, "
            "`api_hash` FROM `bot` WHERE `bot_id` = `user_id` "
            "AND `bot_token` IS NOT NULL AND `bot_token` != '' "
            "AND `work_status` IN ('used', 'free') "
            "ORDER BY `check_timestamp` ASC, `bot_id` ASC LIMIT %s",
            (count,),
            error_tag="human_bot_operator.load_script_accounts",
        )
        if len(rows) < count:
            raise RuntimeError(
                f"可用 StringSession 数量不足：需要 {count} 个，数据库只有 {len(rows)} 个"
            )
        return rows

    @staticmethod
    async def _load_script_account(sender_id: str) -> dict[str, Any]:
        """根据 sender_id 从 bot 表加载登录凭据。"""
        normalized_sender_id = sender_id.strip()
        if re.fullmatch(r"\d+", normalized_sender_id):
            row = await MySQLPool.fetchone(
                "SELECT `bot_id`, `bot_token`, `api_id`, `api_hash` FROM `bot` "
                "WHERE `bot_id` = %s OR `user_id` = %s LIMIT 1",
                (int(normalized_sender_id), int(normalized_sender_id)),
                error_tag="human_bot_operator.load_script_account_by_id",
            )
        else:
            account_name = normalized_sender_id.removeprefix("@")
            row = await MySQLPool.fetchone(
                "SELECT `bot_id`, `bot_token`, `api_id`, `api_hash` FROM `bot` "
                "WHERE `bot_name` = %s OR `bot_root` = %s OR `phone` = %s LIMIT 1",
                (account_name, account_name, normalized_sender_id),
                error_tag="human_bot_operator.load_script_account_by_name",
            )
        if not row:
            raise RuntimeError(f"找不到 sender_id={sender_id} 的账号登录资料")
        return row

    @staticmethod
    async def _sleep_until(target_time: datetime) -> None:
        delay = (target_time - datetime.now(target_time.tzinfo)).total_seconds()
        if delay > 0:
            await asyncio.sleep(delay)

    async def routine_insert(self):
        
        for i in range(4909, 4899, -1):  # 从 4900 往下降到 4800
            await self._insert_sora_code(
                code = f"item_{i}",
                source_chat_id=None,
                source_message_id=None, 
            )

    async def tracking_message_range(
        self,
        chat: Any,
        start_message_id: int = 0,
        end_message_id: int = 0,
    ) -> int:
        """按 ID 从小到大打印指定群组内包含起止边界的消息。"""
        if chat is None or (isinstance(chat, str) and not chat.strip()):
            raise ValueError("chat 不可为空")

        if isinstance(chat, str):
            chat = chat.strip()
            if re.fullmatch(r"-?\d+", chat):
                chat = int(chat)

        entity = await self.client.get_entity(chat)
        source_chat_id = await self.client.get_peer_id(entity)

        start_message_id = int(start_message_id)
        end_message_id = int(end_message_id)

        

        if start_message_id <= 0:
            
            start_message_id = await self._get_resume_message_id(source_chat_id)

        if end_message_id <= 0:
            end_message_id = start_message_id + 10000

        if start_message_id > end_message_id:
            raise ValueError("start_message_id 不可大于 end_message_id")

        printed_count = 0
        last_scanned_message_id: int | None = None
        async for message in self.client.iter_messages(
            entity,
            min_id=max(start_message_id - 1, 0),
            max_id=end_message_id + 1,
            reverse=True,
        ):
            last_scanned_message_id = message.id
            message_text = message.raw_text or ""
            code = self._extract_consecutive_emojis(message_text, count=8)
            if code is None:
                continue

            await self._insert_sora_code(
                code,
                source_chat_id=getattr(message, "chat_id", None),
                source_message_id=message.id,
            )

            message_text = message.raw_text or "[非文字消息]"
            print(
                f"[历史消息] message_id={message.id} {message_text}",
                
                flush=True,
            )
            printed_count += 1

        if last_scanned_message_id is not None:
            self._next_message_id_by_chat[source_chat_id] = (
                last_scanned_message_id + 1
            )
            await self._upsert_extra_log(
                source_chat_id,
                self._next_message_id_by_chat[source_chat_id],
            )

        return printed_count



    async def send_random_message(
        self,
        chat_id: Any,
        hour=None,
        messages: set[str] | None = None,
    ) -> str | None:
        """随机选择候选群组及一句话发送，并返回发送内容。"""
        chat_candidates = (
            list(chat_id)
            if isinstance(chat_id, (list, tuple, set, frozenset))
            else [chat_id]
        )
        normalized_candidates = []
        for candidate in chat_candidates:
            if candidate is None or candidate is False:
                return
            if isinstance(candidate, str):
                candidate = candidate.strip()
                if not candidate:
                    continue
                if re.fullmatch(r"-?\d+", candidate):
                    candidate = int(candidate)
            if candidate == 0:
                return
            normalized_candidates.append(candidate)

        if not normalized_candidates:
            print("没有可发送消息的有效群组。", flush=True)
            return None

        selected_chat_id = random.choice(normalized_candidates)

        chat_target = await self._resolve_input_entity(selected_chat_id)

        period = self.get_time_period(hour)
        greetings = self.time_greetings[period]
        weights = [random.uniform(0.8, 1.2) for _ in greetings]  # 模拟偏好但保持浮动
        


        selected_message = random.choices(greetings, weights=weights, k=1)[0]
        await self.client.send_message(chat_target, selected_message)
        print(
            f"已向群组 {selected_chat_id} 发送随机消息：{selected_message}",
            flush=True,
        )
        return selected_message

    async def send_first_video_to_bot(
        self,
        source_chat: Any,
        target_bot: Any,
        timeout: float = 60,
        search_limit: int | None = 1000,
    ) -> Any | None:
        """将来源群最近的一条视频发给机器人，并打印机器人的下一条回应。"""
        if source_chat is None or (
            isinstance(source_chat, str) and not source_chat.strip()
        ):
            raise ValueError("source_chat 不可为空")
        if target_bot is None or (
            isinstance(target_bot, str) and not target_bot.strip()
        ):
            raise ValueError("target_bot 不可为空")
        if timeout <= 0:
            raise ValueError("timeout 必须大于 0")
        if search_limit is not None and (
            isinstance(search_limit, bool)
            or not isinstance(search_limit, int)
            or search_limit <= 0
        ):
            raise ValueError("search_limit 必须是大于 0 的整数或 None")

        source_entity = await self._resolve_source_chat(source_chat)
        videos = await self.client.get_messages(
            source_entity,
            limit=1,
            filter=InputMessagesFilterVideo(),
        )
        video_message = videos[0] if videos else None
        if video_message is None:
            async for message in self.client.iter_messages(
                source_entity,
                limit=search_limit,
            ):
                if self._message_contains_video(message):
                    video_message = message
                    break

        if video_message is None:
            searched_range = "全部" if search_limit is None else f"最近 {search_limit} 条"
            print(
                f"指定群组 {source_chat} 的{searched_range}消息中没有找到视频", flush=True
            )
            return

        target_entity = await self._resolve_input_entity(target_bot)
        try:
            async with self.client.conversation(
                target_entity,
                timeout=timeout,
            ) as conversation:
                sent_message = await conversation.send_file(
                    video_message.media,
                    caption=video_message.raw_text or None,
                )
                await self.client.delete_messages(
                    source_entity,
                    [video_message.id],
                    revoke=True,
                )
                print(
                    f"已删除来源群组 {source_chat} 中的媒体消息，"
                    f"message_id={video_message.id}",
                    flush=True,
                )
                response = await conversation.get_response(sent_message)

                response_content = await self._format_bot_response(response)
                print(
                    f"[机器人回应] bot={target_bot} message_id={response.id}\n"
                    f"{response_content}",
                    flush=True,
                )

                completion_button = await self._find_bot_button(
                    response,
                    {"✅ 完成上傳", "✅ 完成上传"},
                )
                if completion_button is not None:
                    next_response = await self._click_button_and_wait(
                        conversation=conversation,
                        response=response,
                        edit_reference=sent_message,
                        button=completion_button,
                        button_text="✅ 完成上傳",
                        timeout=timeout,
                    )
                    if next_response is not None:
                        emoji_code = self._extract_consecutive_emojis(
                            next_response.raw_text or "",
                            count=8,
                        )
                        if emoji_code is not None:
                            print(f"[连续 8 个 Emoji] {emoji_code}", flush=True)
                            chat_target = await self._resolve_input_entity(-1004335920222)
                            await self.client.send_message(chat_target, emoji_code)


                        response = next_response
                        response_content = await self._format_bot_response(response)
                        print(
                            f"[机器人点击后回应] bot={target_bot} "
                            f"message_id={response.id}\n{response_content}",
                            flush=True,
                        )

                final_button = await self._find_bot_button(response, {"✅ 完成"})
                if final_button is not None:
                    next_response = await self._click_button_and_wait(
                        conversation=conversation,
                        response=response,
                        edit_reference=sent_message,
                        button=final_button,
                        button_text="✅ 完成",
                        timeout=timeout,
                    )
                    if next_response is not None:
                        response = next_response
                        response_content = await self._format_bot_response(response)
                        print(
                            f"[机器人完成后回应] bot={target_bot} "
                            f"message_id={response.id}\n{response_content}",
                            flush=True,
                        )

        except asyncio.TimeoutError as exc:
            raise TimeoutError(
                f"❗️ 等待机器人 {target_bot} 回应超过 {timeout} 秒"
            ) from exc

        return response

    @staticmethod
    async def _click_button_and_wait(
        *,
        conversation: Any,
        response: Any,
        edit_reference: Any,
        button: Any,
        button_text: str,
        timeout: float,
    ) -> Any:
        """点击按钮并等待机器人发送新消息或编辑已有消息。"""
        response_task = asyncio.ensure_future(
            conversation.get_response(response, timeout=timeout)
        )
        edit_task = asyncio.ensure_future(
            conversation.get_edit(edit_reference, timeout=timeout)
        )
        wait_tasks = {response_task, edit_task}

        try:
            # 先让两个等待器完成注册，避免机器人快速响应造成竞态。
            await asyncio.sleep(1)
            click = getattr(button, "click", None)
            if not callable(click):
                raise RuntimeError(f"按钮 {button_text} 不支持点击")
            click_result = await click()
            print(f"已点击机器人按钮：{button_text}", flush=True)
            click_result_content = HumanBotOperator._format_button_click_result(
                click_result
            )
            if click_result_content:
                print(f"[按钮回调] {click_result_content}", flush=True)

            done, pending = await asyncio.wait(
                wait_tasks,
                return_when=asyncio.FIRST_COMPLETED,
            )
            for completed_task in done:
                if not completed_task.cancelled() and completed_task.exception() is None:
                    return completed_task.result()

            errors = [
                completed_task.exception()
                for completed_task in done
                if not completed_task.cancelled()
            ]
            if errors and all(isinstance(error, TimeoutError) for error in errors):
                print(
                    f"点击 {button_text} 后 {timeout} 秒内没有收到新消息或消息编辑。",
                    flush=True,
                )
                return None
            if errors:
                raise errors[0]
            return None
        finally:
            for wait_task in wait_tasks:
                if not wait_task.done():
                    wait_task.cancel()
            await asyncio.gather(*wait_tasks, return_exceptions=True)

    @staticmethod
    def _format_button_click_result(click_result: Any) -> str | None:
        """格式化 Telegram 按钮点击返回的 callback answer。"""
        if click_result is None:
            return None

        details = [f"type={type(click_result).__name__}"]
        for attribute in ("message", "alert", "url", "cache_time"):
            value = getattr(click_result, attribute, None)
            if value not in (None, "", False, 0):
                details.append(f"{attribute}={value}")
        return ", ".join(details)

    @staticmethod
    async def _find_bot_button(
        response: Any,
        target_texts: set[str],
    ) -> Any | None:
        """查找机器人回应中符合任一候选文字的第一个按钮。"""
        if not isinstance(target_texts, set) or not target_texts:
            raise ValueError("target_texts 必须是非空的 set[str]")
        if not all(isinstance(text, str) and text.strip() for text in target_texts):
            raise ValueError("target_texts 只能包含非空字符串")

        get_buttons = getattr(response, "get_buttons", None)
        buttons = await get_buttons() if callable(get_buttons) else None
        if not buttons:
            return None

        normalized_targets = {
            unicodedata.normalize("NFC", text.strip())
            for text in target_texts
        }
        for row in buttons:
            for button in row:
                button_text = unicodedata.normalize(
                    "NFC",
                    str(getattr(button, "text", "") or "").strip(),
                )
                if button_text in normalized_targets:
                    return button

        return None

    @staticmethod
    async def _format_bot_response(response: Any) -> str:
        """格式化机器人回应中的文字、媒体和按钮资料。"""
        content_lines = [response.raw_text or "[无文字内容]"]

        media = getattr(response, "media", None)
        if media is not None:
            content_lines.append(f"[媒体类型] {type(media).__name__}")

        media_types = []
        for attribute, label in (
            ("photo", "图片"),
            ("video", "视频"),
            ("video_note", "圆形视频"),
            ("gif", "GIF"),
            ("audio", "音频"),
            ("voice", "语音"),
            ("sticker", "贴纸"),
            ("document", "文件"),
        ):
            if getattr(response, attribute, None) is not None:
                media_types.append(label)
        if media_types:
            content_lines.append(f"[媒体] {', '.join(dict.fromkeys(media_types))}")

        get_buttons = getattr(response, "get_buttons", None)
        buttons = await get_buttons() if callable(get_buttons) else None
        if buttons:
            content_lines.append("[按钮]")
            for row_number, row in enumerate(buttons, start=1):
                formatted_buttons = []
                for button in row:
                    original_button = getattr(button, "button", button)
                    details = [str(getattr(button, "text", "") or "[无文字]")]

                    url = getattr(button, "url", None) or getattr(
                        original_button, "url", None
                    )
                    if url:
                        details.append(f"url={url}")

                    data = getattr(button, "data", None)
                    if data is None:
                        data = getattr(original_button, "data", None)
                    if data is not None:
                        data_hex = data.hex() if isinstance(data, bytes) else str(data)
                        details.append(f"callback_data={data_hex}")

                    inline_query = getattr(button, "inline_query", None) or getattr(
                        original_button, "query", None
                    )
                    if inline_query is not None:
                        details.append(f"inline_query={inline_query}")

                    formatted_buttons.append(" | ".join(details))
                content_lines.append(
                    f"  第 {row_number} 行: " + " || ".join(formatted_buttons)
                )

        return "\n".join(content_lines)

    @staticmethod
    def _message_contains_video(message: Any) -> bool:
        """识别普通视频、圆形视频、GIF 以及 video/* 类型文件。"""
        if (
            getattr(message, "video", None) is not None
            or getattr(message, "video_note", None) is not None
            or getattr(message, "gif", None) is not None
        ):
            return True

        document = getattr(message, "document", None)
        mime_type = str(getattr(document, "mime_type", "") or "").lower()
        return mime_type.startswith("video/")


    @classmethod
    def get_time_period(cls, hour: int | None = None) -> str:
        """返回上海时区当前时段，或判断指定的 0–23 整点小时。"""
        if hour is None:
            hour = datetime.now(cls.DEFAULT_TIMEZONE).hour
        elif isinstance(hour, bool) or not isinstance(hour, int):
            raise TypeError("hour 必须是 0 到 23 的整数或 None")

        if not 0 <= hour <= 23:
            raise ValueError("hour 必须介于 0 和 23 之间")

        for start_hour, end_hour, period in cls.TIME_PERIODS:
            if start_hour <= hour < end_hour:
                return period
        return "late_night"

    @staticmethod
    async def get_secret(secret_id: int) -> dict[str, Any] | None:
        """根据主键 ID 取得一笔完整的 sora_code 记录。"""
        if isinstance(secret_id, bool) or not isinstance(secret_id, int):
            raise TypeError("secret_id 必须是整数")
        if secret_id <= 0:
            raise ValueError("secret_id 必须大于 0")

        return await MySQLPool.fetchone(
            "SELECT `id`, `code`, `code_hash`, `pack_id`, `bot_id`, "
            "`valid_state`, `created_ts`, `source_chat_id`, "
            "`source_message_id`, `extract_status` FROM `sora_code` "
            "WHERE `id` = %s LIMIT 1",
            (secret_id,),
            error_tag="human_bot_operator.get_secret",
        )

    async def extract(
        self,
        secret_id: int|None = None,
        code: str | None = None,
        bot_id: int | None = None,
        timeout: float = 60,
        ask_like: bool = False
    ) -> Any:
        """发送指定密文，并逐条监听机器人回应直到出现终止内容。"""
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
            raise TypeError("timeout 必须是数字")
        if timeout <= 0:
            raise ValueError("timeout 必须大于 0")
        
        if code is not None and bot_id is not None:
            try:
                target_bot = await self._resolve_input_entity(bot_id)
            except Exception as e:
                print(f"Failed to resolve target bot with bot_id={bot_id}: {e}", flush=True)
                # raise RuntimeError(f"Failed to resolve target bot with bot_id={bot_id}: {e}") from e

            pass
        else:    
            record = None
            if secret_id is None:
                # 只从最新 30 笔待提取记录中随机选择，避免 ORDER BY RAND() 全表扫描。
                rows = await MySQLPool.fetchall(
                    "SELECT * FROM `sora_code` "
                    "WHERE `extract_status` = 0 ORDER BY `id` DESC LIMIT 30",
                    error_tag="human_bot_operator.extract.get_random_secret_id",
                )
                if not rows:
                    raise LookupError("找不到 extract_status = 0 的 sora_code 记录")
                record = random.choice(rows)
                secret_id = int(record["id"])
            else:
                record = await self.get_secret(secret_id)

            if record is None:
                raise LookupError(f"找不到 sora_code.id={secret_id} 的记录")

            code = str(record.get("code") or "").strip()
            if not code:
                raise ValueError(f"sora_code.id={secret_id} 的 code 为空")

            target_bot = await self._resolve_input_entity(record.get("bot_id"))

        
        response_queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()
        new_message_event = events.NewMessage(
            chats=target_bot,
            from_users=target_bot,
            incoming=True,
        )
        edited_message_event = events.MessageEdited(
            chats=target_bot,
            from_users=target_bot,
            incoming=True,
        )

        async def capture_response(event: Any) -> None:
            await response_queue.put((type(event).__name__, event.message))

        self.client.add_event_handler(capture_response, new_message_event)
        self.client.add_event_handler(capture_response, edited_message_event)
        response_count = 0
        awaiting_file_response = False
        clicked_preview_message_id = None
        last_processed_media = None
        media_idle_deadline = None
        try:
            send_code = code
            # print(f"{target_bot}")
            if target_bot.user_id == 8791594127:
                send_code = f"/start {send_code}"

            sent_message = await self.client.send_message(target_bot, send_code)
            # print(
            #     f"已发送密文：code={send_code} "
            #     f"message_id={sent_message.id}，开始监听机器人回应。",
            #     flush=True,
            # )

            while True:
                wait_timeout = float(timeout)
                if media_idle_deadline is not None:
                    idle_remaining = media_idle_deadline - asyncio.get_running_loop().time()
                    if idle_remaining <= 0:
                        try:
                            update_type, response = response_queue.get_nowait()
                        except asyncio.QueueEmpty:
                            # print("媒体已全部处理，静默等待结束。", flush=True)
                            return last_processed_media
                    else:
                        wait_timeout = min(wait_timeout, idle_remaining)
                        update_type = response = None
                else:
                    update_type = response = None

                if response is None:
                    try:
                        update_type, response = await asyncio.wait_for(
                            response_queue.get(),
                            timeout=wait_timeout,
                        )
                    except asyncio.TimeoutError as exc:
                        if media_idle_deadline is not None:
                            try:
                                update_type, response = response_queue.get_nowait()
                            except asyncio.QueueEmpty:
                                # print("媒体已全部处理，静默等待结束。", flush=True)
                                return last_processed_media
                        else: 
                            print(f"❗️ 等待机器人 {target_bot} 的终止回应超过 {timeout} 秒", flush=True)
                            return False
                            # raise TimeoutError(
                            #     f"等待机器人 {target_bot} 的终止回应超过 "
                            #     f"{timeout} 秒"
                            # ) from exc

                response_count += 1
                response_message = self._get_response_text(response)
                media = getattr(response, "media", None)
                get_buttons = getattr(response, "get_buttons", None)
                buttons = (
                    await get_buttons()
                    if callable(get_buttons)
                    else getattr(response, "buttons", None)
                ) or []

                # 合并按钮文字检查，避免重复遍历同一组按钮。
                button_texts = {
                    str(getattr(button, "text", "") or "")
                    for button in self._iter_buttons(buttons)
                }
                has_complaint_button = any("🚩 投诉" in text for text in button_texts)
                has_get_file_button = any("📥 获取文件" in text for text in button_texts)
                has_continue_button = any("继续发送" in text for text in button_texts)
                
                # self.show_response = True
                if self.show_response:
                    response_content = await self._format_bot_response(response)
                    print(
                        f"[密文提取回应 #{response_count}] update={update_type} "
                        f"code={code} bot={target_bot} "
                        f"message_id={response.id} "
                        f"chat_id={getattr(response, 'chat_id', None)} "
                        f"sender_id={getattr(response, 'sender_id', None)} "
                        f"date={getattr(response, 'date', None)}\n"
                        f"{response_content}",
                        flush=True,
                    )


                    stringify = getattr(response, "stringify", None)
                    if callable(stringify):
                        print(f"[回应原始资料]\n{stringify()}", flush=True)

                if ask_like:
                    # 如果信息的文字包括: "文件组发送完成"
                    if "文件组发送完成" in response_message:
                        # 如果按钮组的按钮, 存在文字 👍 且不包括 [✓] 则点击这个按钮
                        for button in self._iter_buttons(buttons):
                            if "👍" in (getattr(button, "text", "") or "") and "[✓]" not in (getattr(button, "text", "") or ""):
                                # print(f"找到点赞按钮，data={getattr(button, 'data', None)}", flush=True)
                                await button.click()
                                '''
                                KeyboardButtonCallback(
                                    text='👍 · 2',
                                    data=b'delivered-upvote:167981@JHr8UY',
                                    requires_password=False,
                                    style=None
                                ),
                                '''                

                if secret_id:
                    if "该文件组的查看次数已用完" in response_message or "已用完" in response_message:
                        await self._mark_extract_status(secret_id, 11)
                        print("⚠️ 该文件组的查看次数已用完", flush=True)
                        return response
                    if "该文件组当前不可用" in response_message or "該檔案組目前不可用" in response_message:
                        await self._mark_extract_status(secret_id, 12)
                        print("⚠️ 该文件组当前不可用", flush=True)
                        return response
                    if "该文件组仅可查看一次" in response_message or "可查看一次" in response_message:
                        await self._mark_extract_status(secret_id, 13)
                        print("⚠️ 该文件组仅可查看一次", flush=True)
                        return response                    
                    if "信譽等級不足" in response_message:
                        # await self._mark_extract_status(secret_id, 11)
                        print("⚠️ 信譽等級不足，取得此檔案組需要至少 Lv3。", flush=True)
                        return response

                


                if (
                    awaiting_file_response
                    and response.id == clicked_preview_message_id
                ):
                    print(
                        "获取文件按钮所在消息已更新，继续等待机器人发送文件。",
                        flush=True,
                    )
                    continue

                # 代表收到商品预览消息
                if media is not None and (has_get_file_button or has_complaint_button):
                    print("收到商品预览消息，准备处理。", flush=True)
                    '''
                    photo=Photo(
                        id=5834687383876603877,
                        access_hash=7636275838754602338,
                        file_reference=b'\x01\x00\x00T\x8cj\xa6\xd5WcH\xf8\xc9\xd0\\\x82mG\xca\xd12%\x92A\x9d',
                        date=datetime.datetime(2026, 9, 7, 8, 45, 8, tzinfo=datetime.timezone.utc),
                    '''

                    # 如果图片存在，且图片的 access_hash 是 7636275838754602338 则 return False
                    if hasattr(media, "photo") and getattr(media.photo, "access_hash", None) == 7636275838754602338:
                        print(f"没有权限")
                        return False

                    # 得到预览图。
                    if hasattr(media, "photo"):
                        await self._forward_media_with_json_caption(
                            target=self.taobao_bot_username,
                            message=response,
                            file_code=code,
                        )

                    if has_complaint_button:
                        return True


                    if has_get_file_button:
                        # 不要再往下
                        return
                        await asyncio.sleep(1)  # Yield control to the event loop
                        callback_result = await response.click(
                            text=lambda button_text: (
                                "📥 获取文件" in str(button_text or "")
                            )
                        )
                        if callback_result is None:
                            raise RuntimeError(
                                f"message_id={response.id} 的获取文件按钮点击失败"
                            )
                        awaiting_file_response = True
                        clicked_preview_message_id = response.id
                        print(
                            f"已点击 message_id={response.id} 的「📥 获取文件」按钮，"
                            "继续等待机器人回覆。",
                            flush=True,
                        )
                        continue
                   

                if media is None and has_continue_button:
                    callback_result = await response.click(
                        text=lambda button_text: (
                            "继续发送" in str(button_text or "")
                        )
                    )
                    if callback_result is None:
                        raise RuntimeError(
                            f"message_id={response.id} 的继续发送按钮点击失败"
                        )
                    awaiting_file_response = True
                    media_idle_deadline = None
                    print(
                        f"已点击 message_id={response.id} 的「继续发送」按钮，"
                        "继续等待机器人发送文件。",
                        flush=True,
                    )
                    continue

                if awaiting_file_response and media is None:
                    print("已收到中间回应，继续等待机器人发送文件。", flush=True)
                    continue

                # 打印收到的媒体消息信息,还有caption, 按钮, 文字内容
                if self.show_response:
                    print(
                        f"收到媒体消息 message_id={response.id}，"
                        f"media={media}, "
                        f"caption={response_message}",
                        f"buttons={getattr(response, 'buttons', None)}",
                        f"text={getattr(response, 'text', None)}",
                        flush=True,
                    )

                if media is None:
                    # 如果 消息是纯文字，则打印出来
                    text = getattr(response, "text", None)
                    #如果 text 中包括字串 "验证码"
                    if isinstance(text, str) and "请先完成当前验证码" in text:
                        print("‼️ 收到包含验证码的文字回应，继续等待媒体。", flush=True)
                        return False
                    elif isinstance(text, str) and "获取文件组过" in text:
                        print("⚠️ 收到提示：获取文件组过于频繁，继续等待媒体。", flush=True)
                        return False
                    elif isinstance(text, str) and "文件组发送完成" in text:
                       pass
                    elif text:
                        print(f"收到文字回应:{text}，继续等待媒体。", flush=True)

                    continue

                # 如果收到的媒体消息是图片，且 caption 的字串包括 "只数清晰的大图案"
                is_photo = getattr(response, "photo", None) is not None
                if is_photo and "只数清晰的大图案" in response_message:
                    print("❗️ 收到符合条件的图片媒体消息(验证码)。", flush=True)
                   
                    await self.handle_captcha(response)
                    continue    #这条消息不算有效媒体，忽略它


                # 机器人直接发送媒体，或点击按钮后发送实际文件。
                purchase_bot = await self._resolve_input_entity(
                    f"@{self.taobao_bot_username}"
                )
                
                await self._send_pack_item_media(
                    purchase_bot,
                    response,
                    code,
                )
                last_processed_media = response
                awaiting_file_response = False
                clicked_preview_message_id = None
                idle_seconds = random.uniform(2, 3)
                media_idle_deadline = (
                    asyncio.get_running_loop().time() + idle_seconds
                )
                # print(
                #     f"媒体 message_id={response.id} 已处理；"
                #     f"继续等待 {idle_seconds:.1f} 秒接收后续媒体。",
                #     flush=True,
                # )
                continue
        finally:
            self.client.remove_event_handler(
                capture_response,
                new_message_event,
            )
            self.client.remove_event_handler(
                capture_response,
                edited_message_event,
            )

    async def handle_captcha(self, response: Any, user_id: int | None = None) -> None:
        """处理验证码响应。"""
        # print("处理验证码...", flush=True)
        if user_id is None:
            user_id = 7485812665  # 默认用户 ID
        user_id = int(user_id)

        bot_token = (os.getenv("BOT_TOKEN") or "").strip()
        if not bot_token:
            print("⚠️ 未配置 BOT_TOKEN，无法转发验证码图片到指定用户。", flush=True)
            return

        try:
            media_buffer = io.BytesIO()
            downloaded = await asyncio.wait_for(
                self.client.download_media(response, file=media_buffer),
                timeout=self.PROTECTED_MEDIA_TRANSFER_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            print(
                f"❗️ 验证码图片下载超时，user_id={user_id}，message_id={getattr(response, 'id', 'unknown')}",
                flush=True,
            )
            return
        except Exception as exc:
            print(
                f"❗️ 验证码图片下载失败，user_id={user_id}：{exc}",
                flush=True,
            )
            return

        if downloaded is None or media_buffer.tell() == 0:
            print(f"❗️ 验证码图片为空，未转发给 user_id={user_id}", flush=True)
            return

        file_name = getattr(getattr(response, "file", None), "name", None)
        if not file_name:
            extension = getattr(getattr(response, "file", None), "ext", None) or ".jpg"
            file_name = f"captcha_{getattr(response, 'id', 'captcha')}{extension}"
        media_buffer.name = file_name
        media_buffer.seek(0)
        media_file = BufferedInputFile(media_buffer.getvalue(), filename=file_name)

        caption = str(getattr(response, "raw_text", "") or "").strip() or None
        bot = Bot(token=bot_token)
        selection_future = None
        task_id = None
        

        try:
            if getattr(response, "photo", None) is not None:
                task_id = str(getattr(response, "id", "captcha"))
                selection_future = asyncio.get_running_loop().create_future()
                self._captcha_selection_waiters[task_id] = selection_future

                keyboard = [
                    [
                        InlineKeyboardButton(text="1", callback_data=f"ca:{task_id}:1"),
                        InlineKeyboardButton(text="2", callback_data=f"ca:{task_id}:2"),
                        InlineKeyboardButton(text="3", callback_data=f"ca:{task_id}:3"),
                        InlineKeyboardButton(text="4", callback_data=f"ca:{task_id}:4"),
                    ],
                    [
                        InlineKeyboardButton(text="5", callback_data=f"ca:{task_id}:5"),
                        InlineKeyboardButton(text="6", callback_data=f"ca:{task_id}:6"),
                        InlineKeyboardButton(text="7", callback_data=f"ca:{task_id}:7"),
                        InlineKeyboardButton(text="8", callback_data=f"ca:{task_id}:8"),
                    ],
                ]

                sent_message = await bot.send_photo(
                    chat_id=user_id,
                    photo=media_file,
                    caption=caption,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
                )
                # print(
                #     f"验证码按钮等待中：task_id={task_id} "
                #     f"message_id={sent_message.message_id}",
                #     flush=True,
                # )
            elif getattr(response, "document", None) is not None:
                await bot.send_document(
                    chat_id=user_id,
                    document=media_file,
                    caption=caption,
                )
            else:
                await bot.send_document(
                    chat_id=user_id,
                    document=media_file,
                    caption=caption,
                )
            print(f"✅ 已将验证码图片转发给用户 {user_id}", flush=True)
            if selection_future is not None:
                try:
                    selected = await asyncio.wait_for(
                        selection_future,
                        timeout=self.CAPTCHA_SELECTION_TIMEOUT_SECONDS,
                    )
                    # print(
                    #     f"验证码按钮选择结果：user_id={user_id} "
                    #     f"task_id={task_id} selected={selected}",
                    #     flush=True,
                    # )

                    try:
                        click_result = await response.click(
                            text=lambda button_text: str(button_text or "").strip() == str(selected)
                        )
                        '''
                        click_result=BotCallbackAnswer(cache_time=0, alert=False, has_url=False, native_ui=True, message='验证成功。', url=None)
                        '''
                        if click_result and click_result.message == '验证成功。':
                            print(f"✅ 验证码验证成功：user_id={user_id} task_id={task_id}", flush=True)
                        else:
                            print(f"❌ 验证码验证失败：user_id={user_id} task_id={task_id}", flush=True)
                
                    except Exception as exc:
                        print(
                            f"❌ 点击验证码原始按钮失败：selected={selected} error={exc}",
                            flush=True,
                        )

                except asyncio.TimeoutError:
                    print(
                        f"等待验证码按钮选择超时：user_id={user_id} task_id={task_id}",
                        flush=True,
                    )
                # 超时后也要移除等待器 并 删除验证码消息
                if task_id is not None:
                    waiter = self._captcha_selection_waiters.get(task_id)
                    if waiter is selection_future:
                        self._captcha_selection_waiters.pop(task_id, None)
                try:
                    await bot.delete_message(chat_id=user_id, message_id=sent_message.message_id)
                except Exception as exc:
                    if "not found" not in str(exc).lower() and "message to delete" not in str(exc).lower():
                        # print(f"删除验证码消息失败：{exc}", flush=True)
                        pass
        except Exception as exc:
            print(f"❗️ 发送验证码到 user_id={user_id} 失败：{exc}", flush=True)
        finally:
            if task_id is not None:
                waiter = self._captcha_selection_waiters.get(task_id)
                if waiter is selection_future:
                    self._captcha_selection_waiters.pop(task_id, None)
            await bot.session.close()

    @classmethod
    async def handle_captcha_callback(cls, callback_query: Any) -> bool:
        """处理验证码按钮选择，并唤醒等待中的 handle_captcha。"""
        data = str(getattr(callback_query, "data", "") or "")
        if not data.startswith("ca:"):
            return False

        parts = data.split(":", 2)
        if len(parts) != 3:
            print(f"收到无效验证码按钮资料：data={data}", flush=True)
            return True

        _, task_id, selected = parts
        from_user = getattr(callback_query, "from_user", None)
        message = getattr(callback_query, "message", None)
        user_id = getattr(from_user, "id", None)
        message_id = getattr(message, "message_id", None)
        
        # print(
        #     f"验证码按钮已选择：user_id={user_id} "
        #     f"message_id={message_id} task_id={task_id} selected={selected}",
        #     flush=True,
        # )

        waiter = cls._captcha_selection_waiters.get(task_id)
        if waiter is not None and not waiter.done():
            waiter.set_result(selected)

        answer = getattr(callback_query, "answer", None)
        if callable(answer):
            try:
                await answer(f"已选择 {selected}")
            except Exception as exc:
                print(f"回应验证码按钮选择失败：{exc}", flush=True)
            # 无论是否成功回应，都删除这个信息和等待器
            cls._captcha_selection_waiters.pop(task_id, None)
            try:
                await message.delete()
            except Exception as exc:
                pass
                # print(f"删除验证码消息失败：{exc}", flush=True)
        return True


    @staticmethod
    def _get_response_text(response: Any) -> str:
        """取得 Telegram 回应的纯文字。"""
        return str(
            getattr(response, "message", None)
            or getattr(response, "raw_text", None)
            or ""
        ).strip()

    @staticmethod
    def _iter_buttons(buttons: Any):
        """展开 Telethon 的二维按钮列表，并兼容单层按钮列表。"""
        for item in buttons or []:
            if isinstance(item, (list, tuple)):
                yield from item
            else:
                yield item

    @classmethod
    def _build_extract_caption_by_bot(cls, message: Any, file_code: str | None = None) -> str:
        """根据不同的机器人提取描述、8 Emoji 文件码与标签并生成 JSON。"""
        # print(f"{message.chat_id}")
        # print(f"{message.sender_id}")
        # print(f"{message.peer_id}")
        # print(f"{message.peer_id.user_id}")
        from_id = message.chat_id
        json_dict = dict()
        if from_id == cls.BJD_CODE_BOT_ID:  # 示例 bot_id
            json_dict =  cls._build_extract_caption_bjd(message, file_code=file_code)
        elif from_id == 8791594127:  # 另一个示例 bot_id
            json_dict = cls._build_extract_caption_fz(message)

        if not json_dict:
            json_dict = {
                "table": "pack",
                "description": "",
                "file_code": None,
                "tags": [],
            }

        return json.dumps(json_dict, ensure_ascii=False)

    @classmethod
    def _build_extract_caption_fz2(cls, message: Any) -> str:
        """从 posterre_bot 风格的消息中提取 description、hashtags 与 file_code。"""
        text = str(getattr(message, "text", "") or "").strip()
        entities = list(getattr(message, "entities", []) or [])
        description = ""
        tags: list[str] = []

        blockquote_offset = None
        for entity in entities:
            if isinstance(entity, MessageEntityBlockquote):
                blockquote_offset = entity.offset
                break

        if blockquote_offset is not None:
            description = text[: blockquote_offset].strip()
        else:
            hashtag_offsets = [
                entity.offset
                for entity in entities
                if isinstance(entity, MessageEntityHashtag)
            ]
            if hashtag_offsets:
                description = text[: min(hashtag_offsets)].strip()
            else:
                description = text

        description = re.sub(r"\s+", " ", description).strip()

        tag = []
        for entity in entities:
            if isinstance(entity, MessageEntityHashtag):
                
                tag = utils.get_inner_text(
                    message.message,
                    entity
                )
                tags.append(tag)

        print(f"\n\ntags=>{tags}\n\n")

        file_code = None
        reply_markup = getattr(message, "reply_markup", None)
        rows = getattr(reply_markup, "rows", []) or []
        for row in rows:
            buttons = getattr(row, "buttons", []) or []
            for button in buttons:
                copy_text = getattr(button, "copy_text", None)
                if not copy_text:
                    continue
                match = re.search(r"[?&]start=([A-Za-z0-9_:-]+)", str(copy_text))
                if match is not None:
                    file_code = match.group(1)
                    break
            if file_code is not None:
                break

        

        return json.dumps(
            {
                "table": "pack",
                "description": description,
                "file_code": f"{file_code}",
                "tags": tags,
            },
            ensure_ascii=False,
        )



    @classmethod
    def _slice_utf16(cls, text: str, start: int = 0, end: int | None = None) -> str:
        """
        按 Telegram Entity 的 UTF-16 offset / length 截取字符串。
        """
        raw = text.encode("utf-16-le")

        start_byte = start * 2
        end_byte = None if end is None else end * 2

        return raw[start_byte:end_byte].decode("utf-16-le")


    @classmethod
    def _extract_file_code(cls,message: Message) -> str | None:
        """
        从 KeyboardButtonCopy.copy_text 中提取：
            ?start=item_4903

        返回：
            item_4903
        """
        reply_markup = message.reply_markup
        if not reply_markup:
            return None

        for row in getattr(reply_markup, "rows", []) or []:
            for button in getattr(row, "buttons", []) or []:

                if not isinstance(button, KeyboardButtonCopy):
                    continue

                copy_text = button.copy_text or ""

                match = re.search(
                    r"[?&]start=([^&#\s\]\)]+)",
                    copy_text
                )

                if match:
                    return unquote(match.group(1))

        return None


    @classmethod
    def _build_extract_caption_fz(cls,message: Message) -> dict:
        """
        根据 Telegram Message Entity 结构解析资源信息。

        规则：
        1. 第一个 MessageEntityBlockquote 之前 = description
        2. Blockquote 后方的 MessageEntityHashtag = hashtags
        3. KeyboardButtonCopy.copy_text 中 URL 的 start= = file_code
        """

        text = message.message or ""
        entities = message.entities or []

        # --------------------------------------------------
        # 1. 找 Blockquote
        # --------------------------------------------------

        blockquote = min(
            (
                entity
                for entity in entities
                if isinstance(entity, MessageEntityBlockquote)
            ),
            key=lambda entity: entity.offset,
            default=None,
        )

        # --------------------------------------------------
        # 2. description
        # --------------------------------------------------

        if blockquote:
            description = cls._slice_utf16(
                text,
                0,
                blockquote.offset
            ).strip()
        else:
            # 没有 Blockquote 时，
            # 可以视整个 caption 为 description
            description = text.strip()

        # --------------------------------------------------
        # 3. hashtags
        # --------------------------------------------------

        hashtags = []

        # 只接受 Blockquote 后面的 hashtag
        hashtag_min_offset = (
            blockquote.offset + blockquote.length
            if blockquote
            else 0
        )

        for entity, entity_text in message.get_entities_text(
            MessageEntityHashtag
        ):
            if entity.offset < hashtag_min_offset:
                continue

            tag = entity_text.removeprefix("#").strip()

            if tag:
                hashtags.append(tag)

        # --------------------------------------------------
        # 4. file_code
        # --------------------------------------------------

        file_code = cls._extract_file_code(message)

        payload = {
            "table": "pack",
            "description": description,
            "tags": hashtags,
            "file_code": f"{file_code}",
        }

        return payload


    @classmethod
    def _build_extract_caption_bjd(cls, message: Any, file_code: str | None = None) -> dict:
        """从机器人回应提取描述、8 Emoji 文件码与标签并生成 dict"""
        
        message_text = cls._get_response_text(message)
        description = message_text.partition("📦 所含文件")[0].strip()


        if file_code is None:
            file_code = None
            file_code_match = re.search(
                r"^🔑\s*文件码\s*[：:]\s*(.+)$",
                message_text,
                flags=re.MULTILINE,
            )
            if file_code_match is not None:
                file_code = cls._extract_consecutive_emojis(
                    file_code_match.group(1).strip(),
                    count=8,
                )

        tags = []
        tags_match = re.search(
            r"^🏷️?\s*标签\s*[：:]\s*(.*)$",
            message_text,
            flags=re.MULTILINE,
        )
        if tags_match is not None:
            tags = [
                tag.strip()
                for tag in re.split(r"[,，]", tags_match.group(1))
                if tag.strip()
            ]

        return {
            "table": "pack",
            "description": description,
            "file_code": file_code,
            "tags": tags,
        }

    @staticmethod
    def _parse_json_caption(caption: Any) -> dict | None:
        """尝试将 caption 解析成 JSON object；无效时返回 None。"""
        if caption is None:
            return None
        caption_text = str(caption).strip()
        if not caption_text:
            return None
        try:
            payload = json.loads(caption_text)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _get_media_size_bytes(media: Any) -> int | None:
        """安全获取 media 的大小，兼容 MessageMediaPhoto / MessageMediaDocument 等对象。"""
        if media is None:
            return None

        direct_size = getattr(media, "size", None)
        if isinstance(direct_size, (int, float)):
            return int(direct_size)

        photo = getattr(media, "photo", None)
        if photo is not None:
            photo_sizes = getattr(photo, "sizes", None) or []
            if photo_sizes:
                candidate_sizes = [
                    int(getattr(item, "size", 0) or 0)
                    for item in photo_sizes
                    if getattr(item, "size", None) is not None
                ]
                if candidate_sizes:
                    return max(candidate_sizes)

        document = getattr(media, "document", None)
        if document is not None:
            doc_size = getattr(document, "size", None)
            if doc_size is not None:
                return int(doc_size)

        return None

    async def _forward_media_with_json_caption(
        self,
        target: Any,
        message: Any,
        *,
        caption: str | None = None,
        file_code: str | None = None,
        fallback_caption: str | None = None,
    ) -> Any:
        """将带 JSON caption 的媒体发给目标 bot；受保护媒体时回落到下载重传。"""
        if target is None:
            if self.taobao_bot_username is None:
                raise RuntimeError("taobao_bot_username 未配置")
            target = f"@{self.taobao_bot_username}"

        if isinstance(target, str):
            target_name = target.strip().removeprefix("@")
            try:
                resolved_target = await self._resolve_input_entity(target)
            except Exception as exc:
                print(
                    f"@{target_name} Failed to resolve purchase bot entity: {exc}",
                    flush=True,
                )
                raise
        else:
            resolved_target = target
            target_name = getattr(target, "username", None) or self.taobao_bot_username

        media = getattr(message, "media", None)
        if media is None:
            raise ValueError("媒体消息不包含可发送的 media")

        if caption is None:
            caption = self._build_extract_caption_by_bot(message, file_code=file_code)
            print(f"使用的 caption: {caption}", flush=True)

        last_exc: Exception | None = None
        for attempt in range(1, 4):
            try:
                sent_message = await self.client.send_file(
                    resolved_target,
                    media,
                    caption=caption,
                )
                if self.show_response:
                    print(
                        f"已使用 send_file 发送媒体给 @{target_name}，caption={caption}",
                        flush=True,
                    )
                return sent_message
            except Exception as exc:
                last_exc = exc
                message_text = str(exc)
                is_transient_transport_error = (
                    "Server closed the connection" in message_text
                    or "0 bytes read" in message_text
                    or "Connection reset" in message_text
                    or "Connection closed" in message_text
                    or "ConnectionError" in type(exc).__name__
                )

                if attempt < 3 and is_transient_transport_error:
                    delay = 2 ** (attempt - 1)
                    print(
                        f"⚠️ send_file 遇到 Telegram 连接中断，尝试重试 {attempt + 1}/3（{delay}s）: {exc}",
                        flush=True,
                    )
                    await asyncio.sleep(delay)
                    continue

                if self.show_response:
                    print(
                        f"直接 send_file 失败：{exc}；改用下载后重新上传。",
                        flush=True,
                    )
                try:
                    media_size_bytes = self._get_media_size_bytes(media)
                    if media_size_bytes is not None:
                        # 如果媒体大于20MB,则放弃下载，避免后续重试造成资源浪费。
                        if media_size_bytes > 20 * 1024 * 1024:
                            print(
                                f"媒体过大（>{20}MB），放弃下载。",
                                flush=True,
                            )
                            if file_code is not None:
                                await self._mark_extract_status_by_file_code(file_code, 13)
                            else:
                                print("⚠️ secret_id 为空，无法更新 extract_status。", flush=True)
                            return None
                        print(f"尝试重新发送媒体。size = {media_size_bytes} vs {20 * 1024 * 1024}", flush=True)
                    else:
                        print("尝试重新发送媒体（无法读取 size，按可重传流程继续）。", flush=True)
                except Exception as exc:
                    print(f"重新发送媒体前的检查失败: {exc}", flush=True)

                sent_message = await self._resend_protected_message(
                    resolved_target,
                    message,
                    caption=caption,
                )
                if self.show_response and sent_message:
                    print(
                        f"重新发送媒体成功: @{target_name}",
                        flush=True,
                    )
                return sent_message

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("send_file 失败但未返回可用结果")

    async def _send_pack_item_media(
        self,
        target: Any,
        message: Any,
        file_code: str,
    ) -> Any:
        """优先直接发送 pack_item 媒体，失败时下载后重新上传。"""
        caption = json.dumps(
            {
                "table": "pack_item",
                "file_code": file_code,
            },
            ensure_ascii=False,
        )

        print(f"准备发送 pack_item 媒体，caption={caption}")
        return await self._forward_media_with_json_caption(
            target,
            message,
            caption=caption,
            file_code=file_code,
        )

    async def _resend_protected_message(
        self,
        target: Any,
        message: Any,
        caption: str | None = None,
    ) -> Any:
        """下载并重新上传受保护媒体，且不会无限等待。"""
        media_buffer = io.BytesIO()
        downloaded = None
        message_id = getattr(message, "id", "unknown")
        timeout = self.PROTECTED_MEDIA_TRANSFER_TIMEOUT_SECONDS
        if self.show_response:
            print(
                f"开始下载受保护媒体 message_id={message_id}（超时 {timeout} 秒）",
                flush=True,
            )
        try:
            downloaded = await asyncio.wait_for(
                self.client.download_media(message, file=media_buffer),
                timeout=timeout,
            )
        except TimeoutError as exc:
            print(
                f" ❗️ 受保护媒体 message_id={message_id} 已下载超时（{timeout} 秒）{exc}",
                flush=True,
            )
            return False
        except Exception as exc:
            print(
                f" ❗️ 受保护媒体 message_id={message_id} 已下载失败: {exc}",
                flush=True,
            )
            return False

        if downloaded is None or media_buffer.tell() == 0:
            print(f" ❗️ 受保护媒体 message_id={message_id} 下载失败或为空", flush=True)
            return False

        print(
            f" ✅ 受保护媒体 message_id={message_id} 下载成功: {downloaded}，大小={media_buffer.tell()} 字节",
            flush=True,
        )

        message_file = getattr(message, "file", None)
        file_name = getattr(message_file, "name", None)
        if not file_name:
            extension = getattr(message_file, "ext", None) or ".jpg"
            file_name = f"sora_{getattr(message, 'id', 'media')}{extension}"
        media_buffer.name = file_name
        media_buffer.seek(0)
        if caption is None:
            caption = self._build_extract_caption_by_bot(message)
        if self.show_response:
            print(
                f" ✅ 下载完成，开始重新上传 message_id={message_id}（超时 {timeout} 秒）",
                flush=True,
            )
        try:
            return await asyncio.wait_for(
                self.client.send_file(
                    target,
                    media_buffer,
                    caption=caption,
                ),
                timeout=(timeout*2),
            )
        except TimeoutError as exc:
            print(
                f" ❗️ 受保护媒体 message_id={message_id} 重新上传超时（{(timeout*2)} 秒）{exc}",
                flush=True,
            )
            return False
        except Exception as exc:
            print(
                f" ❗️ 受保护媒体 message_id={message_id} 重新上传失败: {exc}",
                flush=True,
            )
            return False
        

    async def _mark_extract_status(self, secret_id: int, status: int ) -> None:
        """将 sora_code 的 extract_status 更新为指定状态。"""
        await MySQLPool.execute(
            "UPDATE `sora_code` SET `extract_status` = %s WHERE `id` = %s",
            (status, secret_id),
            error_tag="human_bot_operator.mark_extract_status",
        )

    async def _mark_extract_status_by_file_code(self, file_code: str, status: int ) -> None:
        """将 sora_code 的 extract_status 更新为指定状态。"""
        await MySQLPool.execute(
            "UPDATE `sora_code` SET `extract_status` = %s WHERE `file_code` = %s",
            (status, file_code),
            error_tag="human_bot_operator.mark_extract_status_by_file_code",
        )

    async def _get_resume_message_id(self, source_chat_id: int) -> int:
        """优先从实例缓存读取游标，否则从 sora_code 的最大消息 ID 续扫。"""
        cached_message_id = self._next_message_id_by_chat.get(source_chat_id)
        if cached_message_id is not None:
            return cached_message_id

        extra_log_row = await MySQLPool.fetchone(
            "SELECT `message_id` FROM `extra_log` WHERE `chat_id` = %s LIMIT 1",
            (source_chat_id,),
            error_tag="human_bot_operator.get_extra_log_cursor",
        )
        if extra_log_row is not None:
            next_message_id = int(extra_log_row.get("message_id") or 0)
            self._next_message_id_by_chat[source_chat_id] = next_message_id
            return next_message_id

        row = await MySQLPool.fetchone(
            "SELECT MAX(`source_message_id`) AS `max_source_message_id` "
            "FROM `sora_code` WHERE `source_chat_id` = %s",
            (source_chat_id,),
            error_tag="human_bot_operator.get_sora_code_cursor",
        )
        max_source_message_id = int((row or {}).get("max_source_message_id") or 0)
        next_message_id = (
            max_source_message_id + 1 if max_source_message_id > 0 else 0
        )
        self._next_message_id_by_chat[source_chat_id] = next_message_id
        return next_message_id

    async def _upsert_extra_log(
        self,
        source_chat_id: int,
        next_message_id: int,
    ) -> None:
        """将群组的下一条扫描游标写入 extra_log。"""
        await MySQLPool.execute(
            "INSERT INTO `extra_log` (`chat_id`, `message_id`, `create_ts`) "
            "VALUES (%s, %s, %s) "
            "ON DUPLICATE KEY UPDATE "
            "`message_id` = VALUES(`message_id`), "
            "`create_ts` = VALUES(`create_ts`)",
            (
                source_chat_id,
                next_message_id,
                int(time.time()),
            ),
            error_tag="human_bot_operator.upsert_extra_log",
            raise_on_error=True,
        )

    async def monitor_chat(
        self,
        chat: Any,
        forward_to: Any = MONITOR_FORWARD_CHAT_ID,
    ) -> None:
        """持续监控一个或多个群组，并将符合条件的新消息打印到终端。"""
        chat_values = list(chat) if isinstance(chat, (list, tuple, set)) else [chat]
        if not chat_values:
            raise ValueError("chat 不可为空")

        normalized_chats = []
        for chat_value in chat_values:
            if chat_value is None or (
                isinstance(chat_value, str) and not chat_value.strip()
            ):
                raise ValueError("chat 不可包含空值")
            if isinstance(chat_value, str):
                chat_value = chat_value.strip()
                if re.fullmatch(r"-?\d+", chat_value):
                    chat_value = int(chat_value)
            normalized_chats.append(chat_value)

        entities = [
            await self.client.get_entity(chat_value)
            for chat_value in normalized_chats
        ]
        forward_target = await self._resolve_input_entity(forward_to)
        new_message_event = events.NewMessage(chats=entities)

        async def print_message(event: events.NewMessage.Event) -> None:
            message_text = event.raw_text or ""
            if not self._contains_consecutive_emojis(message_text, minimum=8):
                return

            print(
                f"[群消息] chat_id={event.chat_id} "
                f"sender_id={event.sender_id} message_id={event.id}\n"
                f"{message_text}",
                flush=True,
            )
            try:
                await self.client.forward_messages(
                    forward_target,
                    event.message,
                )
            except Exception as exc:
                print(
                    f"消息转发到 {forward_to} 失败：{exc}",
                    flush=True,
                )

        self.client.add_event_handler(print_message, new_message_event)
        monitored_names = ", ".join(
            str(getattr(entity, "title", chat_value))
            for entity, chat_value in zip(entities, normalized_chats)
        )
        print(f"开始监控群组：{monitored_names}", flush=True)
        try:
            await self.client.run_until_disconnected()
        finally:
            self.client.remove_event_handler(print_message, new_message_event)

    async def _resolve_input_entity(self, entity_like: Any) -> Any:
        """解析并缓存转发目标所需的 InputPeer 与 access_hash。"""
        normalized_entity = entity_like
        if isinstance(normalized_entity, str):
            normalized_entity = normalized_entity.strip()
            if re.fullmatch(r"-?\d+", normalized_entity):
                normalized_entity = int(normalized_entity)

        try:
            return await self.client.get_input_entity(normalized_entity)
        except ValueError:
            # 数字 ID 只能在当前 Session 已见过该实体时解析；加载对话可刷新缓存。
            dialogs = await self.client.get_dialogs()

        if isinstance(normalized_entity, int):
            for dialog in dialogs:
                try:
                    dialog_peer_id = await self.client.get_peer_id(dialog.entity)
                except (TypeError, ValueError):
                    continue
                if dialog_peer_id == normalized_entity:
                    return await self.client.get_input_entity(dialog.entity)

        try:
            return await self.client.get_input_entity(normalized_entity)
        except ValueError as exc:
            raise ValueError(
                f"无法解析目标 {entity_like}；当前账号可能尚未加入该私有群，"
                "或 Session 中没有该群的 access_hash。公开群可改传 @username。"
            ) from exc

    async def _resolve_source_chat(self, source_chat: Any) -> Any:
        """解析消息来源；正数 ID 失败时再按频道/超级群原始 ID 尝试。"""
        normalized_source = source_chat
        if isinstance(normalized_source, str):
            normalized_source = normalized_source.strip()
            if re.fullmatch(r"\d+", normalized_source):
                normalized_source = int(normalized_source)

        try:
            return await self._resolve_input_entity(normalized_source)
        except ValueError as direct_error:
            if isinstance(normalized_source, int) and normalized_source > 0:
                try:
                    return await self._resolve_input_entity(
                        PeerChannel(normalized_source)
                    )
                except ValueError:
                    pass

            raise ValueError(
                f"无法解析来源群组 {source_chat}。如果这是私有用户，请传入 @username "
                "或先让当前账号与对方建立对话；如果这是频道/超级群，也可以传入 "
                "Bot API 格式的 -100... chat_id"
            ) from direct_error

    async def disconnect(self) -> None:
        """断开当前 Telegram 用户客户端连接。"""
        await self.client.disconnect()

    async def join_chat(self, invite_link: str) -> Any:
        """通过完整邀请链接、+邀请码或裸邀请码加入频道或群组。"""
        invite_hash = self._extract_invite_hash(invite_link)
        try:
            return await self.client(ImportChatInviteRequest(invite_hash))
        except InviteRequestSentError:
            print("入群申请已成功提交，正在等待管理员批准。", flush=True)
            return None
        except UserAlreadyParticipantError:
            print("当前账号已经加入该群组或频道。", flush=True)
            return None

    @staticmethod
    def _extract_invite_hash(invite_link: str) -> str:
        """从 Telegram 私有邀请链接中提取邀请哈希。"""
        value = (invite_link or "").strip()
        if not value:
            # raise ValueError("invite_link 不可为空")
            print(f"invite_link 为空，无法提取邀请哈希。", flush=True)
            return ""

        if "://" in value:
            parsed = urlparse(value)
            if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() not in {
                "t.me",
                "www.t.me",
            }:
                raise ValueError("invite_link 必须是 t.me 邀请链接")

            path = parsed.path.strip("/")
            if path.startswith("+"):
                value = path[1:]
            elif path.startswith("joinchat/"):
                value = path.removeprefix("joinchat/")
            else:
                raise ValueError("不是有效的 Telegram 私有邀请链接")
        else:
            value = value.removeprefix("+")

        if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
            raise ValueError("Telegram 邀请码格式无效")

        return value

    @classmethod
    def _contains_consecutive_emojis(cls, text: str, minimum: int = 8) -> bool:
        """判断文字中是否包含指定数量的连续 Emoji。"""
        return cls._extract_consecutive_emojis(text, count=minimum) is not None

    @classmethod
    def _extract_consecutive_emojis(cls, text: str, count: int = 8) -> str | None:
        """提取第一段连续 Emoji 的前 ``count`` 个符号。"""
        if count <= 0:
            raise ValueError("count 必须大于 0")

        consecutive = 0
        sequence_start = 0
        index = 0
        while index < len(text):
            emoji_end = cls._consume_emoji(text, index)
            if emoji_end is None:
                consecutive = 0
                index += 1
                continue

            if consecutive == 0:
                sequence_start = index
            consecutive += 1
            if consecutive >= count:
                return text[sequence_start:emoji_end]
            index = emoji_end

        return None

    async def _insert_sora_code(
        self,
        code: str,
        *,
        source_chat_id: int | None,
        source_message_id: int | None,
    ) -> None:
        """将 Emoji 密文及其 Unicode NFC SHA-256 写入 sora_code。"""
        normalized_code = unicodedata.normalize("NFC", code)
        code_hash = hashlib.sha256(normalized_code.encode("utf-8")).digest()
        await MySQLPool.execute(
            "INSERT INTO `sora_code` "
            "(`code`, `code_hash`, `bot_id`, `created_ts`, "
            "`source_chat_id`, `source_message_id`, `extract_status`) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE "
            "`code` = VALUES(`code`), "
            "`source_chat_id` = VALUES(`source_chat_id`), "
            "`source_message_id` = VALUES(`source_message_id`)",
            (
                code,
                code_hash,
                self.BJD_CODE_BOT_ID,
                int(time.time()),
                source_chat_id,
                source_message_id,
                0,
            ),
            error_tag="human_bot_operator.insert_sora_code",
            raise_on_error=True,
        )

    @classmethod
    def _consume_emoji(cls, text: str, index: int) -> int | None:
        """读取一个 Emoji（包括旗帜、肤色与 ZWJ 组合），返回结束位置。"""
        if index >= len(text):
            return None

        # 数字、#、* 加组合键帽符号组成一个 Emoji。
        if text[index] in "#*0123456789":
            end = index + 1
            if end < len(text) and ord(text[end]) == 0xFE0F:
                end += 1
            return end + 1 if end < len(text) and ord(text[end]) == 0x20E3 else None

        codepoint = ord(text[index])
        if 0x1F1E6 <= codepoint <= 0x1F1FF:
            next_index = index + 1
            if next_index < len(text) and 0x1F1E6 <= ord(text[next_index]) <= 0x1F1FF:
                return next_index + 1
            return None

        if not cls._is_emoji_base(codepoint):
            return None

        end = cls._consume_emoji_suffix(text, index + 1)
        while end < len(text) and ord(text[end]) == 0x200D:
            next_base = end + 1
            if next_base >= len(text) or not cls._is_emoji_base(ord(text[next_base])):
                break
            end = cls._consume_emoji_suffix(text, next_base + 1)
        return end

    @classmethod
    def _is_emoji_base(cls, codepoint: int) -> bool:
        if 0x1F3FB <= codepoint <= 0x1F3FF:
            return False
        return any(start <= codepoint <= end for start, end in cls._EMOJI_RANGES)

    @staticmethod
    def _consume_emoji_suffix(text: str, index: int) -> int:
        if index < len(text) and ord(text[index]) == 0xFE0F:
            index += 1
        if index < len(text) and 0x1F3FB <= ord(text[index]) <= 0x1F3FF:
            index += 1
        return index

    async def update_profile(
        self,
        first_name: str | None = None,
        last_name: str | None = None,
        random_name: bool = False,
    ) -> None:
        """按需更新姓名、清空用户名，并将电话和在线状态设为 Nobody。"""
        if random_name:
            name_row = await MySQLPool.fetchone(
                "SELECT `first_name`, `last_name` FROM `user` Where `first_name` IS NOT NULL "
                "ORDER BY RAND() LIMIT 1",
                error_tag="human_bot_operator.update_profile.random_name",
            )
            if name_row is None:
                raise LookupError("user 表中没有可供随机选择的姓名")

            first_name = name_row.get("first_name")
            last_name = name_row.get("last_name")

            print(f"随机选择的姓名: {first_name} {last_name}", flush=True)

        if first_name is not None or last_name is not None:
            try:
                await self.client(
                    UpdateProfileRequest(
                        first_name=first_name,
                        last_name=last_name,
                    )
                )
            except Exception as exc:
                print(f"用户姓名更新失败：{exc}", flush=True)
                raise

            print("用户姓名已成功更新。", flush=True)

        try:
            await self.client(UpdateUsernameRequest(""))
        except UsernameNotModifiedError:
            print("用户名已经为空，无需修改。", flush=True)
        except Exception as exc:
            print(f"用户名清空失败：{exc}", flush=True)
            raise
        else:
            print("用户名已成功清空。", flush=True)

        privacy_settings = (
            ("Phone number", InputPrivacyKeyPhoneNumber()),
            ("Last seen & online", InputPrivacyKeyStatusTimestamp()),
            ("Forwarded messages", InputPrivacyKeyForwards()),
            ("Calls", InputPrivacyKeyPhoneCall()),
        )
        for setting_name, privacy_key in privacy_settings:
            try:
                await self.client(
                    SetPrivacyRequest(
                        key=privacy_key,
                        rules=[InputPrivacyValueDisallowAll()],
                    )
                )
            except Exception as exc:
                print(f"{setting_name} 隐私设置失败：{exc}", flush=True)
                raise

            print(f"{setting_name} 已设置为 Nobody。", flush=True)
