"""已登录 Telegram 使用者账号的人型机器人操作。"""

import asyncio
import code
import copy
import ctypes
import hashlib
import io
import json
import os
import random
import re
import uuid
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
from telethon.extensions import html as telethon_html
from aiogram import Bot

from captcha_bot_operator import CaptchaBotOperator
from tgone_mysql import MySQLPool


class HumanBotOperator:
	"""执行需要已登录使用者身份的 Telegram 操作。"""

	MONITOR_FORWARD_CHAT_ID = 5334310434
	BJD_CODE_BOT_ID = 8915213940
	FZ_CODE_BOT_ID = 8805711672

	
	REWARD_BOT_NAME = "zttower5bot"
	FREE_CHAT_ID = -1002093182221
	# 媒体汇聚频道：0 表示未配置（实际值按 _resolve_pool_channel 的顺序解析）
	POOL_CHANNEL: int | str = 0
	# Telegram album 一次最多 10 条
	ALBUM_MAX_SIZE = 10
	PROTECTED_MEDIA_TRANSFER_TIMEOUT_SECONDS = 5 * 60
	CAPTCHA_SELECTION_TIMEOUT_SECONDS = 30
	_bot_cache: dict[str, Bot] = {}

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
		# caption 相同的媒体先入队，凑成 album 后再发到 POOL_CHANNEL
		self._pool_last_caption: str | None = None
		self._pool_media_queue: list[Any] = []
		self._pool_channel_warned = False
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
				await operator.simulate_ctrl_press()
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
			if isinstance(actor_id, bool) or not isinstance(actor_id, (int, str)):
				raise ValueError("participants.actor_id 不可为空或重复")
			actor_id = str(actor_id).strip()
			if (
				not actor_id
				or actor_id in actor_ids
			):
				raise ValueError("participants.actor_id 不可为空或重复")
			participant["actor_id"] = actor_id
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
				isinstance(message_id, bool)
				or not isinstance(message_id, (int, str))
			):
				raise ValueError("messages.message_id 不可为空或重复")
			message_id = str(message_id).strip()
			if not message_id or message_id in message_ids:
				raise ValueError("messages.message_id 不可为空或重复")
			message["message_id"] = message_id
			message_actor_id = message.get("actor_id")
			if isinstance(message_actor_id, bool) or not isinstance(
				message_actor_id, (int, str)
			):
				raise ValueError(f"{message_id}.actor_id 不存在")
			message_actor_id = str(message_actor_id).strip()
			if message_actor_id not in actor_ids:
				raise ValueError(f"{message_id}.actor_id 不存在")
			message["actor_id"] = message_actor_id

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
			if reply_to is not None:
				if isinstance(reply_to, bool) or not isinstance(reply_to, (int, str)):
					raise ValueError(
						f"{message_id}.reply_to 必须是字符串、整数或 null"
					)
				reply_to = str(reply_to).strip()
				message["reply_to"] = reply_to
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
		
		for i in range(6573, 6260, -1):  # 从 6260 往下降到 2
			await self._insert_sora_code(
				code = f"item_{i}",
				source_chat_id=None,
				source_message_id=None, 
				bot_id=self.FZ_CODE_BOT_ID,
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

	async def moving_message_range(
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
			end_message_id = start_message_id + 20

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
			
			# print(
			# 	f"[历史消息] message={message}",
			# )

			# 如果是媒体信息：先比较 caption 和 last_caption 是否一致
			if getattr(message, "media", None) is not None:
				caption = (message.raw_text or "").strip()
				if (
					self._pool_last_caption is not None
					and caption == self._pool_last_caption
				):
					# 相同：先放到 queue 中，攒够一组 album 再发送
					self._pool_media_queue.append(message)
					if len(self._pool_media_queue) >= self.ALBUM_MAX_SIZE:
						await self._flush_pool_album()
				else:
					# 不相同：先把之前已经放在 queue 的媒体发送到 POOL_CHANNEL
					await self._flush_pool_album()
					self._pool_last_caption = caption
					self._pool_media_queue = [message]
			# print(
			# 	f"[历史消息] message_id={message.id} {message_text}",	
			# 	flush=True,
			# )
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



	def _resolve_pool_channel(self) -> int | str | None:
		"""解析 POOL_CHANNEL：类常量 → CONFIGURATION.pool_channel → 环境变量 POOL_CHANNEL。

		因为入口程序在 import 本模块之后才 load_dotenv，所以必须惰性读取。
		返回 None 表示未配置。
		"""
		raw: Any = self.POOL_CHANNEL
		if raw in (0, None, ""):
			try:
				payload = json.loads(os.getenv("CONFIGURATION", "") or "{}")
				if isinstance(payload, dict):
					raw = payload.get("pool_channel") or ""
			except Exception:
				raw = ""
		if raw in (0, None, ""):
			raw = os.getenv("POOL_CHANNEL", "")

		text = str(raw).strip()
		if not text:
			return None
		if re.fullmatch(r"-?\d+", text):
			value = int(text)
			if value == 0:
				return None
			if value > 0:
				# 与 aiogram_bot_operator 的约定一致：纯数字自动补 -100 前缀
				value = int(f"-100{value}")
			return value
		return text

	async def _flush_pool_album(self) -> None:
		"""把队列中的媒体以 album 形式发送到 POOL_CHANNEL。"""
		if not self._pool_media_queue:
			return

		target = self._resolve_pool_channel()
		if target is None:
			if not self._pool_channel_warned:
				print("⚠️ POOL_CHANNEL 未配置，跳过 album 发送。", flush=True)
				self._pool_channel_warned = True
			self._pool_media_queue.clear()
			return

		pending_messages = list(self._pool_media_queue)
		self._pool_media_queue.clear()
		caption = self._pool_last_caption or ""

		try:
			entity = await self._resolve_input_entity(target)
			if len(pending_messages) == 1:
				# 单条不构造 album，避免 SendMultiMedia 只带一项
				await self.client.send_file(
					entity,
					pending_messages[0].media,
					caption=caption,
				)
			else:
				await self.client.send_file(
					entity,
					[message.media for message in pending_messages],
					caption=caption,
				)

			print(
				f"[POOL] 已向 {target} 发送 {len(pending_messages)} 条媒体，"
				f"caption={caption}",
				flush=True,
			)
			sleep_time = random.randint(7, 15)
			print(f"==>Sleeping for {sleep_time} seconds before next operation.", flush=True)
			await asyncio.sleep(sleep_time)
		except Exception as exc:
			print(
				f"⚠️ [POOL] 发送 album 失败（{len(pending_messages)} 条，已丢弃）：{exc}",
				flush=True,
			)

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
			if click_result_content and HumanBotOperator.show_response:
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
	def _extract_wait_seconds_from_telegram_message(message: Any) -> int | None:
		"""从 Telegram 限流提示中解析等待秒数，兼容中文/英文格式。"""
		if message is None:
			return None

		text = str(message)
		patterns = (
			r"请在\s*(\d+)\s*秒后重试",
			r"预计\s*(\d+)\s*秒后恢复",
			r"A wait of (\d+) seconds is required",
			r"(\d+)\s*(?:秒|second|seconds|s)",
		)
		for pattern in patterns:
			match = re.search(pattern, text, re.IGNORECASE)
			if match is not None:
				return max(int(match.group(1)), 1)
		return None

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

					requires_password = getattr(button, "requires_password", None)
					if requires_password is None:
						requires_password = getattr(
							original_button, "requires_password", None
						)
					if requires_password:
						details.append("requires_password=True")

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

	@staticmethod
	async def get_code(code: str) -> dict[str, Any] | None:
		"""根据code 取得一笔完整的 sora_code 记录。"""
		if isinstance(code, bool) or not isinstance(code, str):
			raise TypeError("code 必须是文本")


		return await MySQLPool.fetchone(
			"SELECT `id`, `code`, `code_hash`, `pack_id`, `bot_id`, "
			"`valid_state`, `created_ts`, `source_chat_id`, "
			"`source_message_id`, `extract_status`, `desc_order_id` FROM `sora_code` "
			"WHERE `code` = %s LIMIT 1",
			(code,),
			error_tag="human_bot_operator.get_code",
		)

	async def fetch_list(self,page:int|None = None,desc_order_id:int|None = 0):
		'''
		首頁    /start
		排行榜
		最行發布
		
		放大鏡
		輸入最後一頁 （8035）
		出現列表        
		'''

		_qty = 0
		target_bot = await self._resolve_input_entity("@yunupan1bot")

		desc_order_id = int(desc_order_id)

		if desc_order_id <= 0:    
			# desc_order_id = await self._get_resume_message_id(source_chat_id='10001') or 0
			desc_order_id = await self._get_max_desc_order_id() or 0


		# 首頁    /start
		result = await self.capture_bot_messages(target_bot, "/start")
		if not result:
			print("⚠️ 沒有取得 /start 首頁訊息", flush=True)
			return
		menu_id = result[-1].id                      # 用最後一則，通常才是選單

		result2 = await self.capture_bot_messages(
			target_bot, click_button_title="🏆", message_id=menu_id
		)
		if not result2:
			print("⚠️ 排行榜點擊後沒有取得任何輸出", flush=True)
			return
		board_id = result2[-1].id
	   
	

		result_most_recent = await self.capture_bot_messages(
			target_bot, click_button_title="🆕", message_id=board_id
		)
		if not result_most_recent:
			print("⚠️ 點擊「🆕 最新發布」後沒有取得任何輸出", flush=True)
			return
		latest_id = result_most_recent[-1].id

		if result_most_recent and result_most_recent[-1].raw_text:
			caption_text = result_most_recent[-1].raw_text
			# 以 📦 来分割字串，再列出最后一个
			caption_text = caption_text.split("📦")[-1]
			

			result_detail = await self.capture_bot_messages(
				target_bot, click_button_title=caption_text, message_id=latest_id
			)
			if not result_detail:
				print(f"⚠️ 點擊「{caption_text}」後沒有取得任何輸出", flush=True)
				return

			get_buttons = getattr(result_detail[-1], "get_buttons", None)
			buttons = await get_buttons() if callable(get_buttons) else None
			if buttons:
				for row_number, row in enumerate(buttons, start=1):                
					for button in row:                   
						button_text = str(getattr(button, "text", "") or "[无文字]")
						# 使用正則式，如果 button_text 的組成是 數字/數字
						match = re.match(r"(\d+)/(\d+)", button_text)
						if match:
							_, max_item = map(int, match.groups())
							last_item = max_item - desc_order_id
							last_item = str(last_item)

							result_click_jump = await self.capture_bot_messages(
								target_bot, click_button_title=button_text, message_id=result_detail[-1].id
							)

							result_jump_to = await self.capture_bot_messages(target_bot, send_text=last_item)
							current_item = await self.parse_bot_response(result_jump_to[-1])
							latest_id = result_jump_to[-1].id
			
							while current_item != max_item:
								result_loop = await self.capture_bot_messages(
									target_bot, click_button_title="⬅️", message_id=latest_id
								)
									
								if not result_loop:
									print("⚠️ 點擊「⬅️」後沒有取得任何輸出", flush=True)
									return
								current_item =await self.parse_bot_response(result_loop[-1])
								latest_id = result_loop[-1].id

								# print("extracting...", flush=True)
								# await self.extract(ask_like=True, bot_id=HumanBotOperator.FZ_CODE_BOT_ID, extract_status=0)

								
								if _qty == 1:
									await self.tracking_message_range(chat=-1004335920222)
								elif _qty == 3:
									await self.tracking_message_range(chat=-1004372020134) 
								# elif _qty == 5:
								#   玉
								# 	await self.tracking_message_range(chat=-1004383041223)


								if _qty%5 == 0:
									await self.extract(ask_like=True, bot_id=HumanBotOperator.BJD_CODE_BOT_ID, extract_status=2)
								elif _qty%5 == 2 or _qty%5 == 3:
									await self.extract(ask_like=True, bot_id=HumanBotOperator.BJD_CODE_BOT_ID, extract_status=0)

								
								sleep_time = random.randint(3, 7)
								# await asyncio.sleep(sleep_time)
								await asyncio.sleep(sleep_time)

								_qty += 1
								if _qty >= 20:
									print("⚠️ 已達到最大嘗試次數，停止循環", flush=True)
									return



		
			


	async def parse_bot_response(
		self,
		message: Any
	) -> str:
		"""解析机器人回应，返回格式化后的文本内容。"""
		try:
			caption = message.raw_text
			code = self._extract_consecutive_emojis(message.raw_text, count=8)
			if code is None:
				pass
			else:
				
				caption = caption.replace(f"[{code}]", "")
				# caption = caption.strip()
				if self.show_response:
					print(f"Extracted code: {code}\n caption={caption}", flush=True)
			   
				


			get_buttons = getattr(message, "get_buttons", None)
			buttons = await get_buttons() if callable(get_buttons) else None
			if buttons:
				for row_number, row in enumerate(buttons, start=1):                
					for button in row:                   
						button_text = str(getattr(button, "text", "") or "[无文字]")
						# 使用正則式，如果 button_text 的組成是 數字/數字
						match = re.match(r"(\d+)/(\d+)", button_text)
						if match:
							current_item, max_item = map(int, match.groups())
							desc_order_id = max_item - current_item
							if self.show_response:
								print(f"Parsed pagination: current_item={current_item}, max_item={max_item}", flush=True)
							await self._insert_sora_code(
								code,
								source_chat_id=0,
								source_message_id=0,
								desc_order_id=desc_order_id
							)

							sora_code = await self.get_code(code)

							json_dict = {
								"table": "pack",
								"description": caption,
								"file_code": code,
								"tags": [],
							}

							if self.show_response:
								print(f"{sora_code} extract_status={sora_code.get('extract_status')}", flush=True)

							if sora_code and sora_code.get("extract_status") !=1 and sora_code.get("extract_status") !=2:
								if self.show_response:
									print(f"⚠️ 提取码 {code} 已存在，转发", flush=True)     
								await self._forward_media_with_json_caption(
									target=self.taobao_bot_username,
									message=message,
									file_code=code,
									caption=json.dumps(json_dict, ensure_ascii=False),
								)

							await self._upsert_extra_log(source_chat_id='10001',next_message_id=desc_order_id)
							return current_item
							




		   
		except Exception as e:
			print(f"⚠️ 无法解析机器人回应: {e}", flush=True)
			return ""
	   





		

	async def extract(
		self,
		secret_id: int|None = None,
		code: str | None = None,
		bot_id: int | None = None,
		timeout: float = 60,
		ask_like: bool = False,
		extract_status: int |None = None,
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
				print(f"⚠️ Failed to resolve target bot with bot_id={bot_id}: {e}", flush=True)
				# raise RuntimeError(f"Failed to resolve target bot with bot_id={bot_id}: {e}") from e

			pass
		else:    
			record = None
			if secret_id is None:
				# 只从最新 30 笔待提取记录中随机选择，避免 ORDER BY RAND() 全表扫描。
				# 如果 bot_id 有值，則增加 sql 的過濾條件，例如 "AND `bot_id` = {bot_id}"
				
				if extract_status is not None:
					bot_filter = f" `extract_status` = {extract_status}"
				else:
					bot_filter = " `extract_status` IN (0,2)"
				bot_filter += f" AND `bot_id` = {bot_id}" if bot_id is not None else ""
				rows = await MySQLPool.fetchall(
					"SELECT * FROM `sora_code` "
					f"WHERE {bot_filter} ORDER BY `id` DESC LIMIT 100",
					error_tag="human_bot_operator.extract.get_random_secret_id",
				)
				
				if not rows:
					print(f"未找到 extract_status = 0 的 sora_code 记录，{bot_id} / {extract_status} 等待 60 秒后重试...", flush=True)
					await asyncio.sleep(60)
					return None
				   
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
			if target_bot.user_id == self.FZ_CODE_BOT_ID:
				send_code = f"/start {send_code}"
				print(f"send_code={send_code}")

			try:
				sent_message = await asyncio.wait_for(
					self.client.send_message(target_bot, send_code),
					timeout=timeout,
				)
			except (TimeoutError, ConnectionError, OSError) as exc:
				print(
					f"⚠️ 发送密文给机器人 {target_bot} 失败或超过 {timeout} 秒"
					f"（可能是连线被服务器中断）：{exc}",
					flush=True,
				)
				if secret_id is not None:
					await self._mark_extract_status(secret_id, 14)
				return False
			print(
				f"已发送密文：code={send_code} "
				f"message_id={sent_message.id}，开始监听机器人回应。",
				flush=True,
			)

			
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
							if secret_id is not None:
								await self._mark_extract_status(secret_id, 14)
						   
							  
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
					elif "该文件组当前不可用" in response_message or "該檔案組目前不可用" in response_message:
						await self._mark_extract_status(secret_id, 12)
						print("⚠️ 该文件组当前不可用", flush=True)
						return response
					elif "资源不存在或已不可用。" in response_message:
						await self._mark_extract_status(secret_id, 12)
						print("⚠️ 资源不存在或已不可用。", flush=True)
						return response                    
					elif "该文件组仅可查看一次" in response_message or "可查看一次" in response_message:
						await self._mark_extract_status(secret_id, 13)
						print("⚠️ 该文件组仅可查看一次", flush=True)
						return response      
					elif "此资源已由作者下架" in response_message:
						await self._mark_extract_status(secret_id, 15)
						print("⚠️ 此资源已由作者下架", flush=True)
						return response   
					elif "此资源已下架" in response_message:
						await self._mark_extract_status(secret_id, 12)
						print("⚠️ 此资源已下架", flush=True)
						return response
					elif "资源已由管理员下架" in response_message:
						await self._mark_extract_status(secret_id, 12)
						print("⚠️ 资源已由管理员下架", flush=True)
						return response
				   


					
					elif "信譽等級不足" in response_message:
						# await self._mark_extract_status(secret_id, 11)
						print(f"⚠️ {response_message}", flush=True)
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
				   

					# 如果图片存在，且图片的 access_hash 是 7636275838754602338 则 return False
					if hasattr(media, "photo") and getattr(media.photo, "access_hash", None) == 7636275838754602338:
						print(f"没有权限")
						return False

					# 得到预览图。
					if hasattr(media, "photo"):
						if record['extract_status'] != 2 and record['extract_status'] != 1:
							await self._forward_media_with_json_caption(
								target=self.taobao_bot_username,
								message=response,
								file_code=code,
							)
						else:
							print(f"Record extract status is 2 or 1, skipping forward. {record['extract_status']}", flush=True)

						if has_complaint_button:
							await self._mark_extract_status(secret_id, 1)


					if has_complaint_button:
						return True


					if has_get_file_button:
						
						
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

				 
						# print(f"callback_result={callback_result}", flush=True)

						msg = getattr(callback_result, "message", None)
						if not isinstance(msg, str):
							msg = None
						if msg is not None:
							print(f"callback_result message: {msg}", flush=True)


							if "此目录及其下级内容仅限编辑员下载" in msg and secret_id:
								await self._mark_extract_status(secret_id, 16)
								print("⚠️ 此目录及其下级内容仅限编辑员下载", flush=True)
								return response

							if "今日公共文件组获取次数已用完" in msg:
								print(f"{msg}", flush=True)
								return response    

							if  (
								"操作过于频繁" in msg
								or "文件额度不足" in msg
								or ("请在" in msg and "秒后重试" in msg)
								or ("A wait of" in msg and "seconds is required" in msg)
							):
								print(f"触发频繁操作或文件额度不足: {msg}", flush=True)
								wait_seconds = HumanBotOperator._extract_wait_seconds_from_telegram_message(msg)
								if wait_seconds is not None:
									print(
										f"⚠️ 触发 Telegram 限流：{msg}，等待 {wait_seconds} 秒后继续。",
										flush=True,
									)
									await asyncio.sleep(wait_seconds + 1)      
								return response    
						# print(
						#     f"callback_result does not indicate frequent operation or insufficient file quota: {msg}",
						#     flush=True,
						# )
						# if callback_result and callback_result.message:
						#     print(f"点击获取文件按钮后的回调结果: {callback_result}", flush=True)
						#     if ("操作过于频繁" in callback_result.message) or ("文件额度不足" in callback_result.message):
						#         wait_time_match = re.search(r'(\d+)\s*秒', callback_result.message)
						#         if wait_time_match:
						#             wait_time = int(wait_time_match.group(1))
						#             print(f"⚠️ {callback_result.message} -- {wait_time} 秒后再试。", flush=True)
						#             await asyncio.sleep(wait_time + 2)


						#             callback_result = await response.click(
						#                 text=lambda button_text: (
						#                     "📥 获取文件" in str(button_text or "")
						#                 )
						#             )
							

								  

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

					print(f"callback_result(1387)={callback_result}", flush=True)
					''''
					callback_result=BotCallbackAnswer(cache_time=1, alert=True, has_url=False, native_ui=True, message='操作过于频繁，请 32 秒后再试。', url=None)
					如果收到 message 说明文字包括"操作过于频繁"，就直接按等待的秒数进行 sleep
					
					'''
					# if callback_result and callback_result.message:
					#     if ("操作过于频繁" in callback_result.message) or ("文件额度不足" in callback_result.message):
					#         wait_time_match = re.search(r'(\d+)\s*秒', callback_result.message)
					#         if wait_time_match:
					#             wait_time = int(wait_time_match.group(1))
					#             print(f"⚠️ {callback_result.message} -- {wait_time} 秒后再试。", flush=True)
					#             await asyncio.sleep(wait_time + 2)
					#             await response.click(
					#                 text=lambda button_text: (
					#                     "继续发送" in str(button_text or "")
					#                 )
					#             )
					#             print(f"已点击 message_id={response.id} 的「继续发送」按钮，继续等待机器人发送文件。", flush=True)
								
					if callback_result:
						# print(f"callback_result message: {getattr(callback_result, 'message', None)}, alert: {getattr(callback_result, 'alert', None)}", flush=True)

						msg = getattr(callback_result, "message", None)
						if not isinstance(msg, str):
							msg = None
						print(f"msg2={msg}",flush=True)
						if msg and (
							"操作过于频繁" in msg
							or "文件额度不足" in msg
							or ("请在" in msg and "秒后重试" in msg)
							or ("A wait of" in msg and "seconds is required" in msg)
						):
							print(f"Detected frequent operation or insufficient file quota: {msg}", flush=True)
							wait_seconds = HumanBotOperator._extract_wait_seconds_from_telegram_message(msg)
							if wait_seconds is not None:
								print(f"⚠️ {msg}，等待 {wait_seconds} 秒后继续。", flush=True)
								await asyncio.sleep(wait_seconds + 1)
								continue
							print(f"⚠️ 限流消息已识别，但未解析到等待秒数：{msg}", flush=True)
							await asyncio.sleep(5)
							continue
						# print(f"callback_result does not indicate frequent operation or insufficient file quota: {msg}", flush=True)
							# await response.click(
							#     text=lambda button_text: (
							#         "继续发送" in str(button_text or "")
							#     )
							# )
							# print(f"已点击 message_id={response.id} 的「继续发送」按钮，继续等待机器人发送文件。", flush=True)
													
					   



					if callback_result is None:
						raise RuntimeError(
							f"message_id={response.id} 的继续发送按钮点击失败"
						)
					awaiting_file_response = True
					media_idle_deadline = None
				 
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
						print(f"⚠️ {text}", flush=True)
						'''
						当收到信息时，则等待休息 N 秒，如下所示
						⚠️ 获取文件组过于频繁，请在 6 秒后重试。 提升信誉等级可提高每分钟获取额度。
						'''
						if "请在" in text and "秒后重试" in text:
							import re
							match = re.search(r"请在 (\d+) 秒后重试", text)
							if match:
								wait_seconds = int(match.group(1))+1
								print(f"等待 {wait_seconds} 秒后重试...", flush=True)
								await asyncio.sleep(wait_seconds)
						return False
					elif isinstance(text, str) and "文件组发送完成" in text:
					   pass
					elif text:
						print(f"收到文字回应:{text}，继续等待媒体。", flush=True)

					continue

				# 如果收到的媒体消息是图片，且 caption 的字串包括 "只数清晰的大图案" 或 "与上方物体相同"
				is_photo = getattr(response, "photo", None) is not None
				if is_photo and ("只数清晰的大图案" in response_message or "与上方物体相同" in response_message):
					print("❗️ 收到符合条件的图片媒体消息(验证码)。", flush=True)
					print(f"{self.FREE_CHAT_ID} {self.REWARD_BOT_NAME} 已处理。")

					result = await self.handle_captcha(
						response,
						user_id=self.FREE_CHAT_ID,
						reward_bot_name=self.REWARD_BOT_NAME,
					)
					if result is True:
						continue    # 验证成功，继续等待后续媒体

					print("⚠️ 验证码处理失败，不等待媒体，结束此轮处理。", flush=True)
					return False


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

	@staticmethod
	def _get_bot(token: str) -> Bot:
		"""复用单例 Bot 实例，避免每次处理验证码都重新初始化。"""
		token = (token or "").strip()
		if not token:
			raise ValueError("BOT_TOKEN 不可为空")
		bot = HumanBotOperator._bot_cache.get(token)
		if bot is None:
			bot = Bot(token=token)
			HumanBotOperator._bot_cache[token] = bot
		return bot

	async def handle_captcha(self, response: Any, user_id: int | None = None, reward_bot_name: str | None = None) -> bool:
		"""委托给独立的验证码处理器执行，并返回是否成功处理。"""
		captcha_operator = CaptchaBotOperator(client=self.client)
		return await captcha_operator.handle_captcha(
			response=response,
			user_id=user_id,
			reward_bot_name=reward_bot_name,
		)

	@classmethod
	async def handle_captcha_callback(cls, callback_query: Any) -> bool:
		"""委托给独立的验证码处理器处理按钮回调。"""
		return await CaptchaBotOperator.handle_captcha_callback(callback_query)


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
		elif from_id == cls.FZ_CODE_BOT_ID:  # 另一个示例 bot_id
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
		"""从 postfilebbot 风格的消息中提取 description、hashtags 与 file_code。"""
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
				match = re.search(r"[?&]start=([^&#\s\]\)]+)", str(copy_text))
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
	def _slice_entities(
		cls,
		entities: list[Any] | None,
		start: int = 0,
		end: int | None = None,
	) -> list[Any]:
		"""
		按 UTF-16 offset 范围裁切 message entities，并将 offset 对齐到新的起点（0）。
		与 end 边界重叠的 entity 会被裁短，完全落在范围外的 entity 会被剔除。
		"""
		sliced: list[Any] = []
		for entity in entities or []:
			entity_start = entity.offset
			entity_end = entity.offset + entity.length

			if entity_end <= start:
				continue
			if end is not None and entity_start >= end:
				continue

			clipped_start = max(entity_start, start)
			clipped_end = entity_end if end is None else min(entity_end, end)
			if clipped_end <= clipped_start:
				continue

			clipped_entity = copy.copy(entity)
			clipped_entity.offset = clipped_start - start
			clipped_entity.length = clipped_end - clipped_start
			sliced.append(clipped_entity)

		return sliced


	@classmethod
	def _build_html_description(
		cls,
		text: str,
		entities: list[Any] | None,
		start: int = 0,
		end: int | None = None,
	) -> str:
		"""
		按 UTF-16 offset 范围截取文字与对应 entities，并转换为 HTML 格式字符串。
		"""
		snippet = cls._slice_utf16(text, start, end)
		snippet_entities = cls._slice_entities(entities, start, end)
		return telethon_html.unparse(snippet, snippet_entities)


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
		1. 第一个 MessageEntityBlockquote 之前 + 第一个 MessageEntityBlockquote 内容 (包括引用本身) = description
		2. Blockquote 后方的 MessageEntityHashtag = hashtags
		3. KeyboardButtonCopy.copy_text 中 URL 的 start= = file_code
		"""

		# print(f"message={message}")

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

		description_end = (
			blockquote.offset + blockquote.length if blockquote else None
		)

		# 按 HTML 格式输出，保留原有的 MessageEntityBlockquote 等格式设定。
		description = cls._build_html_description(
			text,
			entities,
			0,
			description_end,
		).strip()

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

		max_caption_bytes = 1024
		encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
		if len(encoded) <= max_caption_bytes:
			return payload

		# 先裁掉 description 中的引用块内容；它通常是最容易让 caption 变长的部分。
		stripped_description = re.sub(
			r"(?is)<blockquote[^>]*>.*?</blockquote>|&lt;blockquote[^&]*&gt;.*?&lt;/blockquote&gt;",
			"",
			description,
		)
		stripped_description = re.sub(
			r"(?is)<blockquote[^>]*>|&lt;blockquote[^&]*&gt;|</blockquote>|&lt;/blockquote&gt;",
			"",
			stripped_description,
		)
		stripped_description = re.sub(r"<[^>]+>", "", stripped_description)
		stripped_description = re.sub(r"&lt;|&gt;|&amp;", lambda m: {"&lt;": "<", "&gt;": ">", "&amp;": "&"}[m.group(0)], stripped_description)
		stripped_description = re.sub(r"\s+", " ", stripped_description).strip()

		payload["description"] = stripped_description
		encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
		if len(encoded) <= max_caption_bytes:
			return payload

		payload["tags"] = (payload.get("tags") or [])[:5]
		payload["description"] = stripped_description[:180]
		encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
		if len(encoded) <= max_caption_bytes:
			return payload

		payload["tags"] = []
		payload["description"] = stripped_description[:120]
		return payload


	@classmethod
	def _build_extract_caption_bjd(cls, message: Any, file_code: str | None = None) -> dict:
		"""从机器人回应提取描述、8 Emoji 文件码与标签并生成 dict"""
		
		message_text = cls._get_response_text(message)
		description = message_text.partition("🔑 文件码")[0]


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
			# description 存的是纯文字，统一转成 Telegram 可用的 HTML（转义特殊字符），
			# 与 fz 来源保持一致，下游才能安全地以 parse_mode="HTML" 发送。
			"description": telethon_html.escape(description),
			"file_code": file_code,
			"tags": tags,
		}

	@staticmethod
	def _parse_json_caption(caption: Any) -> dict | None:
		"""尝试将 caption 解析成 JSON object；无效时返回 None。"""
		if caption is None:
			return None
		caption_text = str(caption)
		if not caption_text:
			return None
		try:
			payload = json.loads(caption_text)
		except (TypeError, ValueError, json.JSONDecodeError):
			return None
		return payload if isinstance(payload, dict) else None

	@staticmethod
	def _sanitize_telegram_caption(caption: str | None, *, max_bytes: int = 1024) -> str:
		"""确保 Telegram 媒体 caption 不超长，也不含 malformed HTML / 未闭合标签。"""
		if caption is None:
			return ""

		text = str(caption)
		if not text:
			return ""

		# Telegram 对 caption 中的 HTML 实体非常严格，任何未闭合的 blockquote 等标签都会被拒绝。
		# 先把这类标签清掉，再做长度裁剪，确保最终发送是安全文本。
		tag_stripped = re.sub(r"</?(?:blockquote|b|strong|i|em|u|s|code|pre|a|span|p|div|br)[^>]*>", "", text, flags=re.IGNORECASE)
		tag_stripped = re.sub(r"<[^>]+>", "", tag_stripped)
		text = tag_stripped.strip()

		if len(text.encode("utf-8")) <= max_bytes:
			return text

		payload = HumanBotOperator._parse_json_caption(text)
		if payload is not None:
			safe_payload = dict(payload)
			description = str(safe_payload.get("description") or "")
			file_code = safe_payload.get("file_code")
			tags = safe_payload.get("tags") or []

			if isinstance(tags, list):
				safe_payload["tags"] = [str(tag)[:32] for tag in tags[:10]]
			if description:
				truncated = re.sub(r"</?(?:blockquote|b|strong|i|em|u|s|code|pre|a|span|p|div|br)[^>]*>", "", description, flags=re.IGNORECASE)
				truncated = re.sub(r"<[^>]+>", "", truncated)
				safe_payload["description"] = truncated[:200]

			if file_code is not None:
				safe_payload["file_code"] = str(file_code)[:64]

			compact = json.dumps(safe_payload, ensure_ascii=False, separators=(",", ":"))
			if len(compact.encode("utf-8")) <= max_bytes:
				return compact

		if len(text.encode("utf-8")) > max_bytes:
			# Telegram 对 caption 的硬限制通常是 1024 bytes；保底裁剪。
			tail = "..."
			max_text_len = max_bytes - len(tail.encode("utf-8"))
			if max_text_len <= 0:
				return tail[:max_bytes]
			return text.encode("utf-8")[:max_text_len].decode("utf-8", errors="ignore") + tail

		return text

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
					f"⚠️ @{target_name} Failed to resolve purchase bot entity: {exc}",
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
			# print(f"使用的 caption: {caption}", flush=True)
		

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
					or "Cannot connect to host" in message_text
					or "ClientConnectorError" in message_text
					or "ClientConnectorError" in type(exc).__name__
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
					print(f"⚠️ 重新发送媒体前的检查失败: {exc}", flush=True)

				sent_message = await self._resend_protected_message(
					resolved_target,
					message,
					caption=caption,
				)
				if self.show_response and sent_message:
					print(
						f"重新发送媒体成功: @{target_name} {caption}",
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
		caption = self._sanitize_telegram_caption(caption)
		if self.show_response:
			print(
				f" ✅ 下载完成，开始重新上传 message_id={message_id}（超时 {timeout} 秒）",
				flush=True,
			)
			
		try:
			await asyncio.sleep(1)
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

			wait_match = re.search(r"A wait of (\d+) seconds is required", str(exc))
			if wait_match:
				wait_seconds = max(int(wait_match.group(1)) + 1, 1)
				print(
					f"检测到 Telegram 发送限流，等待 {wait_seconds} 秒后重试：{exc}",
					flush=True,
				)
				await asyncio.sleep((wait_seconds+5))
				return await self._resend_protected_message(
					target,
					message,
					caption=caption,
				)

			if "FloodWait" in type(exc).__name__ or "FloodWaitError" in str(type(exc)):
				wait_seconds = max(int(getattr(exc, "seconds", 0) or 0), 1)
				print(
					f"检测到 FloodWait，等待 {wait_seconds} 秒后重试：{exc}",
					flush=True,
				)
				await asyncio.sleep(wait_seconds)
				return await self._resend_protected_message(
					target,
					message,
					caption=caption,
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
			"UPDATE `sora_code` SET `extract_status` = %s WHERE `code` = %s",
			(status, file_code),
			error_tag="human_bot_operator.mark_extract_status_by_file_code",
		)

	async def _get_max_desc_order_id(self) -> int:
		"""获取指定源群组的最大描述消息 ID。"""
		row = await MySQLPool.fetchone(
			"SELECT MAX(`desc_order_id`) AS `max_desc_order_id` FROM `sora_code`",
			(),
			error_tag="human_bot_operator.get_max_desc_order_id",
		)
		max_desc_order_id = int((row or {}).get("max_desc_order_id") or 0)
		return max_desc_order_id

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

	async def capture_bot_messages(
		self,
		bot: Any,
		send_text: str | None = None,
		*,
		click_button_title: str | None = None,
		message_id: int | None = None,
		timeout: float = 10.0,
		idle_timeout: float | None = None,
		poll_interval: float = 2.0,
		stop_keywords: set[str] | None = None,
		max_messages: int | None = 1,
		include_edited: bool = True,
		return_texts: bool = False,
	) -> list[Any]:
		"""擷取指定机器人输出的消息，可先发送触发消息或点击按钮后再收集。

		参数（send_text、click_button_title 与 message_id 皆为非必填）：
			send_text:          发送给机器人的触发消息（如 "/start" 或密文）。
			click_button_title: 当机器人输出中出现名称符合此值的按钮时，点击
								该按钮一次，再继续收集之后收到的消息。
			message_id:         指定要点击按钮的既有消息 ID；必须与
								click_button_title 搭配使用。有值时不再依赖
								新消息触发的按钮，而是直接取得该 message_id
								的消息、点击其中文字符合 click_button_title
								的按钮，再回传机器人这次点击的反馈信息。
								点击后会同时「轮询」该消息（见 poll_interval），
								即使 Telegram 没有推送编辑事件，只要内容改变
								也一样会被回传。
			poll_interval:     message_id 路径下回读该消息、比对内容是否改变的
								间隔秒数（默认 2 秒）。仅在传入 message_id 时
								生效；不传 message_id 时不会产生额外请求。
		两者皆不填时（未指定 send_text、click_button_title 与 message_id），
		只会等待并回传该机器人在等待期间输出的消息。

		用法：
			await op.capture_bot_messages("@yunupan1bot", "/start")
			await op.capture_bot_messages(
				"@yunupan1bot", "/start", click_button_title="排行榜"
			)
			await op.capture_bot_messages(
				"@yunupan1bot", click_button_title="排行榜"
			)
			await op.capture_bot_messages(
				"@yunupan1bot",
				click_button_title="排行榜",
				message_id=8416,
			)

		流程：解析目标机器人 -> 注册消息事件 ->（可选）发送 send_text ->
		（可选）点击指定 message_id 中符合 click_button_title 的按钮，并记录
		该消息的内容指纹 -> 逐条收集该机器人的输出（事件与轮询两条来源）；
		遇到符合 click_button_title 的按钮则点击一次，
		直到整体超时、静默超时、命中停止关键字或达到收集上限；无论正常结束或
		异常，都会移除事件处理器，避免事件泄漏。
		"""
		if send_text is not None and (
			not isinstance(send_text, str) or not send_text.strip()
		):
			raise ValueError("send_text 必须是非空字符串或 None")
		if click_button_title is not None and (
			not isinstance(click_button_title, str)
			or not click_button_title.strip()
		):
			raise ValueError("click_button_title 必须是非空字符串或 None")
		if message_id is not None:
			if isinstance(message_id, bool) or not isinstance(message_id, int):
				raise TypeError("message_id 必须是整数或 None")
			if message_id <= 0:
				raise ValueError("message_id 必须大于 0")
			if click_button_title is None:
				raise ValueError(
					"message_id 必须与 click_button_title 搭配使用"
				)
		if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
			raise TypeError("timeout 必须是数字")
		if timeout <= 0:
			raise ValueError("timeout 必须大于 0")
		if idle_timeout is not None:
			if isinstance(idle_timeout, bool) or not isinstance(
				idle_timeout, (int, float)
			):
				raise TypeError("idle_timeout 必须是数字或 None")
			if idle_timeout <= 0:
				raise ValueError("idle_timeout 必须大于 0")
		if isinstance(poll_interval, bool) or not isinstance(
			poll_interval, (int, float)
		):
			raise TypeError("poll_interval 必须是数字")
		if poll_interval <= 0:
			raise ValueError("poll_interval 必须大于 0")
		if max_messages is not None:
			if isinstance(max_messages, bool) or not isinstance(max_messages, int):
				raise TypeError("max_messages 必须是整数或 None")
			if max_messages <= 0:
				raise ValueError("max_messages 必须大于 0")
		if stop_keywords is not None:
			stop_keywords = {str(keyword) for keyword in stop_keywords}

		target_bot = await self._resolve_input_entity(bot)

		response_queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()
		new_message_event = events.NewMessage(
			chats=target_bot,
			from_users=target_bot,
			incoming=True,
		)
		edited_message_event = (
			events.MessageEdited(
				chats=target_bot,
				from_users=target_bot,
				incoming=True,
			)
			if include_edited
			else None
		)

		async def capture_response(event: Any) -> None:
			# NewMessage.Event 与 MessageEdited.Event 的类名都是 "Event"，
			# 这里用 isinstance 明确标示来源，方便分辨是新消息还是编辑。
			update_type = (
				"EDITED" if isinstance(event, events.MessageEdited.Event) else "NEW"
			)
			await response_queue.put((update_type, event.message))

		self.client.add_event_handler(capture_response, new_message_event)
		if edited_message_event is not None:
			self.client.add_event_handler(capture_response, edited_message_event)

		captured_messages: list[Any] = []
		captured_texts: list[str] = []
		button_clicked = False
		# message_id 路径：记录被点击消息的内容指纹，稍后用轮询比对内容变化。
		poll_target_id: int | None = None
		poll_baseline: tuple[str, tuple[str, ...]] | None = None
		try:
			if send_text is not None:
				try:
					await asyncio.wait_for(
						self.client.send_message(target_bot, send_text),
						timeout=timeout,
					)
				except (TimeoutError, ConnectionError, OSError) as exc:
					print(
						f"⚠️ 发送触发消息给机器人 {bot} 失败：{exc}",
						flush=True,
					)
					return []

				print(f"已发送触发消息给机器人 {bot}：{send_text}", flush=True)

			if message_id is not None:
				# 指定既有消息 ID：直接取得该消息并点击其中的按钮，
				# 之后继续收集机器人对这次点击的反馈。
				try:
					target_message = await asyncio.wait_for(
						self.client.get_messages(target_bot, ids=message_id),
						timeout=timeout,
					)
				except (TimeoutError, ConnectionError, OSError) as exc:
					print(
						f"⚠️ 取得机器人 {bot} 的消息 message_id={message_id} "
						f"失败：{exc}",
						flush=True,
					)
					target_message = None

				if target_message is None:
					print(
						f"⚠️ 找不到机器人 {bot} 的消息 message_id={message_id}，"
						"无法点击按钮。",
						flush=True,
					)
				else:
					get_buttons = getattr(target_message, "get_buttons", None)
					message_buttons = (
						await get_buttons()
						if callable(get_buttons)
						else getattr(target_message, "buttons", None)
					)
					matched_button = self._find_button_by_title(
						message_buttons, click_button_title
					)
					if matched_button is None:
						print(
							f"⚠️ 消息 message_id={message_id} 中找不到文字为"
							f"“{click_button_title}”的按钮。",
							flush=True,
						)
					else:
						# 先记住点击前的内容指纹，之后才能判断机器人是否已修改。
						poll_target_id = message_id
						poll_baseline = await self._message_signature(
							target_message
						)

						click_result = await matched_button.click()
						click_result_content = HumanBotOperator._format_button_click_result(
							click_result
						)
						if click_result_content and self.show_response:
							print(f"[按钮回调] {click_result_content}", flush=True)

						button_clicked = True
						await asyncio.sleep(1)
						if self.show_response:
							print(
								f"🖱️ 已点击消息 message_id={message_id} 的按钮"
								f"“{click_button_title}”。",
								flush=True,
							)

			loop = asyncio.get_running_loop()
			overall_deadline = loop.time() + timeout
			idle_deadline = (
				overall_deadline + idle_timeout
				if idle_timeout is not None
				else None
			)
			while True:
				if max_messages is not None and len(captured_messages) >= max_messages:
					if self.show_response:
						print(
							f"⚠️ 已达到最大消息数 {max_messages}，结束擷取。",
							flush=True,
						)
					break

				polling = poll_target_id is not None
				deadlines = [overall_deadline]
				if idle_deadline is not None:
					deadlines.append(idle_deadline)
				next_deadline = min(deadlines)
				remaining = next_deadline - loop.time()
				# message_id 路径：把等待切成 poll_interval 小段，
				# 让「机器人以编辑回覆但没有推送事件」也能被回读发现。
				wait_timeout = min(remaining, poll_interval) if polling else remaining
				if wait_timeout <= 0:
					if idle_deadline is not None and next_deadline == idle_deadline:
						print(
							f"⏹️ 机器人 {bot} 已静默 {idle_timeout} 秒，结束擷取。",
							flush=True,
						)
					else:
						print(
							f"❗️ 等待机器人 {bot} 输出超过 {timeout} 秒，结束擷取。",
							flush=True,
						)
					break

				update_type: str | None = None
				response = None
				try:
					update_type, response = await asyncio.wait_for(
						response_queue.get(),
						timeout=wait_timeout,
					)
				except asyncio.TimeoutError:
					# 没等到事件：若启用轮询就回读被点击的消息比对内容指纹。
					if polling:
						polled = await self._poll_clicked_message(
							target_bot,
							poll_target_id,
							poll_baseline,
						)
						if polled is not None:
							update_type = "EDITED"
							response = polled
							poll_baseline = await self._message_signature(polled)
							if max_messages is None:
								# 已回读到一次变化，停止轮询以免重复回传。
								poll_target_id = None

				if response is None:
					# 这一轮既没有事件也没有变化，只有真的到期才结束。
					if loop.time() >= next_deadline:
						if idle_deadline is not None and idle_deadline <= loop.time():
							print(
								f"⏹️ 机器人 {bot} 已静默 {idle_timeout} 秒，结束擷取。",
								flush=True,
							)
						else:
							print(
								f"❗️ 等待机器人 {bot} 输出超过 {timeout} 秒，结束擷取。",
								flush=True,
							)
						break
					continue

				if idle_timeout is not None:
					idle_deadline = loop.time() + idle_timeout

				response_message = self._get_response_text(response)
				captured_messages.append(response)
				captured_texts.append(response_message)

				if self.show_response:
					response_content = await self._format_bot_response(response)
					print(
						f"[D擷取机器人输出 #{len(captured_messages)}] "
						f"update={update_type} bot={bot} "
						f"message_id={getattr(response, 'id', None)}\n"
						f"{response_content}",
						flush=True,
					)
				# else:
				#     print(
				#         f"[S擷取机器人输出 #{len(captured_messages)}] "
				#         f"message_id={getattr(response, 'id', None)} "
				#         f"{response_message}",
				#         flush=True,
				#     )

				if click_button_title is not None and not button_clicked:
					get_buttons = getattr(response, "get_buttons", None)
					message_buttons = (
						await get_buttons()
						if callable(get_buttons)
						else getattr(response, "buttons", None)
					)
					matched_button = self._find_button_by_title(
						message_buttons, click_button_title
					)
					if matched_button is not None:
						# 只点一次，并顺便记录 callback answer 的内容。
						click_result = await matched_button.click()
						click_result_content = HumanBotOperator._format_button_click_result(
							click_result
						)
						if click_result_content and self.show_response:
							print(f"[按钮回调] {click_result_content}", flush=True)

						button_clicked = True
						await asyncio.sleep(1)
						if self.show_response:
							print(
								f"🖱️ 已点击按钮“{click_button_title}”"
								f"（message_id={getattr(response, 'id', None)}）。",
								flush=True,
							)

				if stop_keywords and any(
					keyword in response_message for keyword in stop_keywords
				):
					print(
						f"✅ 命中停止关键字，结束擷取机器人 {bot} 输出。",
						flush=True,
					)
					break
		finally:
			self.client.remove_event_handler(capture_response, new_message_event)
			if edited_message_event is not None:
				self.client.remove_event_handler(
					capture_response, edited_message_event
				)

		if message_id is not None and not captured_messages:
			# 空结果诊断：回读该消息，判断机器人到底有没有改动内容。
			await self._report_clicked_message_state(
				bot,
				target_bot,
				poll_target_id if poll_target_id is not None else message_id,
				poll_baseline,
			)

		return captured_texts if return_texts else captured_messages

	@classmethod
	async def _message_signature(cls, message: Any) -> tuple[str, tuple[str, ...]]:
		"""取得消息文字与按钮文字的指纹，用来判断该消息内容是否改变。"""
		text = cls._get_response_text(message)
		button_texts: list[str] = []
		get_buttons = getattr(message, "get_buttons", None)
		try:
			rows = (
				await get_buttons()
				if callable(get_buttons)
				else getattr(message, "buttons", None)
			)
			for button in cls._iter_buttons(rows):
				button_text = str(getattr(button, "text", "") or "").strip()
				if button_text:
					button_texts.append(button_text)
		except Exception:
			# 指纹只用于辅助判断，取不到按钮时退回纯文字比对。
			button_texts = []
		return text, tuple(button_texts)

	async def _poll_clicked_message(
		self,
		entity: Any,
		message_id: int,
		baseline: tuple[str, tuple[str, ...]] | None,
	) -> Any | None:
		"""回读被点击的消息；内容指纹已改变则回传最新消息，否则回传 None。"""
		try:
			latest = await self.client.get_messages(entity, ids=message_id)
		except (TimeoutError, ConnectionError, OSError):
			return None

		if latest is None:
			return None

		signature = await self._message_signature(latest)
		if baseline is not None and signature == baseline:
			return None
		return latest

	async def _report_clicked_message_state(
		self,
		bot_label: Any,
		entity: Any,
		message_id: int,
		baseline: tuple[str, tuple[str, ...]] | None,
	) -> None:
		"""擷取为空时回读指定消息并打印诊断，判断机器人是否真的改过内容。"""
		try:
			latest = await self.client.get_messages(entity, ids=message_id)
		except (TimeoutError, ConnectionError, OSError) as exc:
			print(
				f"🔍 回读诊断：取得 message_id={message_id} 失败：{exc}",
				flush=True,
			)
			return

		if latest is None:
			print(
				f"🔍 回读诊断：找不到 message_id={message_id}。",
				flush=True,
			)
			return

		text, button_texts = await self._message_signature(latest)
		changed = baseline is not None and (text, button_texts) != baseline
		print(
			f"🔍 回读诊断：bot={bot_label} message_id={message_id} "
			f"内容是否有变化={'是' if changed else '否'}",
			flush=True,
		)
		print(f"   目前文字：{text or '[无文字内容]'}", flush=True)
		print(
			"   目前按钮："
			+ ("、".join(button_texts) if button_texts else "[无按钮]"),
			flush=True,
		)
		if not changed:
			print(
				"   结论：机器人没有修改这条消息，也没有推送新消息或编辑事件。",
				flush=True,
			)

	@staticmethod
	def _find_button_by_title(buttons: Any, title: str) -> Any:
		"""在按钮组中寻找文字等于 title 的按钮，找不到则回退到包含 title 者。"""
		target = str(title or "").strip()
		if not target:
			return None
		fallback = None
		for button in HumanBotOperator._iter_buttons(buttons):
			text = str(getattr(button, "text", "") or "").strip()
			if not text:
				continue
			if text == target:
				return button
			if fallback is None and target in text:
				fallback = button
		return fallback

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
					f"⚠️ 消息转发到 {forward_to} 失败：{exc}",
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

	async def simulate_ctrl_press(self) -> None:
		"""模拟按下 Ctrl 键，并阻止系统进入屏幕保护/睡眠。

		这是为了让 Windows 机器在脚本长时间后台运行时不因为空闲而触发
		屏保、休眠或熄屏。这里优先使用 Win32 API 直接防止系统进入 idle
		状态，并补上一次 Ctrl 键事件，以符合原先的设计意图。
		"""
		if os.name != "nt":
			return

		try:
			ES_CONTINUOUS = 0x80000000
			ES_SYSTEM_REQUIRED = 0x00000001
			ctypes.windll.kernel32.SetThreadExecutionState(
				ES_CONTINUOUS | ES_SYSTEM_REQUIRED
			)

			user32 = ctypes.windll.user32
			VK_CONTROL = 0x11
			KEYEVENTF_KEYUP = 0x0002
			user32.keybd_event(VK_CONTROL, 0, 0, 0)
			user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
		except Exception as exc:
			print(f"⚠️ simulate_ctrl_press 触发失败：{exc}", flush=True)

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
		bot_id: int | None = None,
		desc_order_id : int | None = None,
	) -> None:
		"""将 Emoji 密文及其 Unicode NFC SHA-256 写入 sora_code。"""
		normalized_code = unicodedata.normalize("NFC", code)
		code_hash_hex = hashlib.sha256(normalized_code.encode("utf-8")).hexdigest()
		if bot_id is None:
			bot_id = self.BJD_CODE_BOT_ID

		await MySQLPool.execute(
			"INSERT INTO `sora_code` "
			"(`code`, `code_hash`, `bot_id`, `created_ts`, "
			"`source_chat_id`, `source_message_id`, `desc_order_id`, `extract_status`) "
			"VALUES (%s, UNHEX(%s), %s, %s, %s, %s, %s, %s) "
			"ON DUPLICATE KEY UPDATE "
			"`code` = VALUES(`code`), "
			"`source_chat_id` = VALUES(`source_chat_id`), "
			"`source_message_id` = VALUES(`source_message_id`), "
			"`desc_order_id` = VALUES(`desc_order_id`)",
			(
				code,
				code_hash_hex,
				bot_id,
				int(time.time()),
				source_chat_id,
				source_message_id,
				desc_order_id,
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
				print(f"⚠️ 用户姓名更新失败：{exc}", flush=True)
				raise

			print(f"✅ 用户姓名已成功更新。", flush=True)

		try:
			await self.client(UpdateUsernameRequest(""))
		except UsernameNotModifiedError:
			print("用户名已经为空，无需修改。", flush=True)
		except Exception as exc:
			print(f"⚠️ 用户名清空失败：{exc}", flush=True)
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
				print(f"⚠️ {setting_name} 隐私设置失败：{exc}", flush=True)
				raise

			print(f"{setting_name} 已设置为 Nobody。", flush=True)
