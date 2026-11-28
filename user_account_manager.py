"""Telegram 使用者帳號的新增、確認與管理。"""

import json
import os
import asyncio
import random
import re
import time
from datetime import datetime, timedelta, timezone

import qrcode
from getpass import getpass

import telethon
from app_timezone import APP_TIMEZONE
from html import escape
from typing import Any
from device_lists import WHITELIST, BLACKLIST

from telethon import TelegramClient, utils
from telethon.sessions import StringSession
from telethon.tl.functions.account import GetAuthorizationsRequest, ResetAuthorizationRequest, UpdateUsernameRequest
from telethon.errors import (
    AuthKeyUnregisteredError,
    FloodWaitError,
    PeerFloodError,
    PeerIdInvalidError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    RPCError,
    SessionPasswordNeededError,
    UserAlreadyParticipantError,
)
from telethon.tl.functions.contacts import ImportContactsRequest
from telethon.tl.functions.messages import CreateForumTopicRequest, ImportChatInviteRequest
from telethon.tl.types import InputPhoneContact, MessageActionTopicCreate
from telethon.tl.types.account import Authorizations
# shared_config 會在 import 時讀取 SETTING_URL，因此必須先載入環境變數。

from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent / ".env"

load_dotenv(dotenv_path=env_path)

from shared_config import SharedConfig  # noqa: E402
from tgone_mysql import MySQLPool  # noqa: E402


class UserAccountManager:
    """負責 Telegram 使用者帳號的新增、登入確認與資料管理。"""

    TGSOURCE_CHAT_ID = 777000
    ACCOUNT_TOPIC_CHAT_ID = -1004237132658
    ACCOUNT_TOPIC_INVITE_HASH = "WpOjlBIAcIcyZGVh"

    async def create_account_topic(
        self,
        user_client: TelegramClient,
        first_name: str | None,
        last_name: str | None,
        user_id: int,
    ) -> int:
        """加入帳號管理群組、建立主題並回傳主題 ID。"""
        join_result = None
        try:
            join_result = await user_client(
                ImportChatInviteRequest(self.ACCOUNT_TOPIC_INVITE_HASH)
            )
        except UserAlreadyParticipantError:
            pass

        group = None
        joined_updates = getattr(join_result, "updates", join_result)
        for chat in getattr(joined_updates, "chats", ()):
            if utils.get_peer_id(chat) == self.ACCOUNT_TOPIC_CHAT_ID:
                group = chat
                break

        if group is None:
            async for dialog in user_client.iter_dialogs():
                if dialog.id == self.ACCOUNT_TOPIC_CHAT_ID:
                    group = dialog.entity
                    break

        if group is None:
            raise RuntimeError(
                f"加入群組後仍找不到 chat_id={self.ACCOUNT_TOPIC_CHAT_ID}"
            )

        topic_title = " ".join(
            name.strip() for name in (first_name, last_name) if name and name.strip()
        )
        topic_title = (topic_title or str(user_id))[:128]
        result = await user_client(
            CreateForumTopicRequest(peer=group, title=topic_title)
        )

        for update in getattr(result, "updates", ()):
            message = getattr(update, "message", None)
            if isinstance(getattr(message, "action", None), MessageActionTopicCreate):
                return int(message.id)

        raise RuntimeError("Telegram 已建立主題，但回應中沒有主題 ID")

    async def check_active_sessions(self, user_client: TelegramClient) -> str:
        """检查当前账号的会话，按现有规则清理并发送报告。"""
        print("\n 列出当前帐号所有 active sessions", flush=True)
        auths = await user_client(GetAuthorizationsRequest())
        if not isinstance(auths, Authorizations):
            raise TypeError("Telegram 返回的会话列表格式不正确")
        device_model_str = ""
        for a in auths.authorizations:
            if a.date_created is None:
                print(f"❌ 会话 {a.hash} 缺少创建时间，无法检查", flush=True)
                continue
            date_created = a.date_created
            if a.hash == 0:
                print(f"✅ 保留本身 id={a.hash}  device={a.device_model}  platform={a.platform}  ip={a.ip}  date={date_created.astimezone(APP_TIMEZONE)}")
                device_model_str += "✅ (本身)" + a.device_model + "\n"
                continue
            elif a.device_model not in WHITELIST:
                try:
                    seven_days_ago = datetime.now(APP_TIMEZONE) - timedelta(days=7)
                    if date_created >= seven_days_ago:
                        print(f"❗️ 最近七天内创建的会话 id={a.hash}  device_model={a.device_model}  platform={a.platform}  ip={a.ip}  date={date_created.astimezone(APP_TIMEZONE)}")
                        device_model_str += "❗️ (七天新增)" + a.device_model + "\n"
                    elif a.device_model in BLACKLIST:
                        await user_client(ResetAuthorizationRequest(hash=a.hash))
                        print(f"❌ 已删除 id={a.hash}  device_model={a.device_model}  platform={a.platform}  ip={a.ip}  date={date_created.astimezone(APP_TIMEZONE)} (已删除)")
                        device_model_str += "❌ (黑名单)" + a.device_model + "\n"
                    elif a.hash == -212406687192506612 or a.hash == -6894703599540223408:
                        await user_client(ResetAuthorizationRequest(hash=a.hash))
                        print(f"❌ 已删除 id={a.hash}  device_model={a.device_model}  platform={a.platform}  ip={a.ip}  date={date_created.astimezone(APP_TIMEZONE)} (已删除)")
                        device_model_str += "❌ (特殊)" + a.device_model + "\n"
                    else:
                        print(f"⚠️ 建議删除 id={a.hash}  device_model={a.device_model}  platform={a.platform}  ip={a.ip}  date={date_created.astimezone(APP_TIMEZONE)}")
                        device_model_str += "⚠️ (建議删除)" + a.device_model + "\n"
                except Exception as e:
                    print(f"❌ 删除 {a.hash} 失败: {e}")
            else:
                print(f"✅ 保留 id={a.hash}  device_model={a.device_model}  platform={a.platform}  ip={a.ip}  date={date_created.astimezone(APP_TIMEZONE)}")
                device_model_str += "✅ (白名单)" + a.device_model + "\n"

        await user_client.send_message(
            SharedConfig.get("key_man_id"),
            f"\ndevice_model=\n{device_model_str}",
            parse_mode="HTML",
        )
        return device_model_str

    def load_config(self) -> dict[str, Any]:
        """合併遠端設定與 CONFIGURATION，後者有較高優先權。"""
        SharedConfig.load()

        try:
            configuration = json.loads(os.getenv("CONFIGURATION", "") or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError("CONFIGURATION 不是有效的 JSON") from exc

        if not isinstance(configuration, dict):
            raise ValueError("CONFIGURATION 必須是 JSON object")


        config = SharedConfig.get_all()

        configuration.update(config)
        return configuration


    async def get_all_bots(self) -> list[dict[str, Any]]:
        """登入 MySQL 並回傳 `bot` 資料表的所有資料。"""
        sql = """
            SELECT *
            FROM `bot`
            WHERE bot_id = user_id
                AND bot_token IS NOT NULL
                AND work_status IN ('used', 'free')
                AND check_timestamp <= UNIX_TIMESTAMP() - 3600
            ORDER BY check_timestamp ASC
        """
        return await MySQLPool.fetchall(
            sql,
            error_tag="userbot.get_all_bots",
        )


    async def get_bot(self, phone_number: str) -> dict[str, Any] | None:
        """根據電話號碼取得 `bot` 資料表中對應的完整 row。"""
        phone_number = (phone_number or "").strip()
        if not phone_number:
            raise ValueError("phone_number 不可為空")

        return await MySQLPool.fetchone(
            "SELECT * FROM `bot` WHERE `phone` = %s LIMIT 1",
            (phone_number,),
            error_tag="userbot.get_bot",
        )



    async def tg_qrcode_login(
        self,
        user_client: TelegramClient,
        pw2fa: str | None
    ):
        stage = "initializing"

        try:
            print(f"Telethon version: {telethon.__version__}")

            if not await user_client.is_user_authorized():
                qr = await user_client.qr_login()

                while True:
                    code = qrcode.QRCode(border=2)
                    code.add_data(qr.url)
                    code.make(fit=True)
                    code.print_ascii(invert=True)

                    print("請使用 Telegram 掃描 QR Code")

                    try:
                        result =await qr.wait()
                        return result
                        

                    except asyncio.TimeoutError:
                        print("QR Code 已過期，重新產生...")
                        await qr.recreate()
                    
                       
                    except SessionPasswordNeededError:
                        try:
                            await user_client.sign_in(password=pw2fa)
                        except Exception:
                            password = getpass("請輸入兩步驗證密碼：")
                            return await user_client.sign_in(password=password)
                        break



                    

            

            # Implement QR code login logic here
            # For example, you might generate a QR code and wait for the user to scan it

        except RPCError as e:
            print(f"❌ RPCError during QR code login at stage: {stage}")
            return e













    async def tg_login(
        self,
        user_client: TelegramClient,
        phone_number: str,
        pw2fa: str | None
    ):
        stage = "initializing"

        try:
            print(f"Telethon version: {telethon.__version__}")

            if not user_client.is_connected():
                await user_client.connect()

            if await user_client.is_user_authorized():
                return await user_client.get_me()

            stage = "send_code_request"

            sent_code = await user_client.send_code_request(
                phone_number
            )

            phone_code_hash = sent_code.phone_code_hash
            requested_at = time.monotonic()

            print(f"Code type: {sent_code.type}")
            print(f"Next type: {sent_code.next_type}")
            print(f"Timeout: {sent_code.timeout}")
            print(f"Hash received: {bool(phone_code_hash)}")

            stage = "sign_in"

            code = (
                await asyncio.to_thread(
                    input, "Please enter verification code: "
                )
            ).strip()

            print(f"Code length: {len(code)}")
            print(f"Code is ASCII digits: "
                f"{code.isascii() and code.isdigit()}")
            print(
                f"Elapsed: "
                f"{time.monotonic() - requested_at:.2f}s"
            )

            try:
                return await user_client.sign_in(
                    phone=phone_number,
                    code=code,
                    phone_code_hash=phone_code_hash,
                )

            except SessionPasswordNeededError:
                stage = "2FA"

                password = pw2fa or await asyncio.to_thread(
                    getpass, "Please enter 2FA password: "
                )

                return await user_client.sign_in(
                    password=password
                )

        except PhoneCodeInvalidError as e:
            print("❌ PHONE_CODE_INVALID")
            print(f"Stage: {stage}")
            return e

        except PhoneCodeExpiredError as e:
            print("❌ PHONE_CODE_EXPIRED")
            print(f"Stage: {stage}")
            return e

        except RPCError as e:
            print(f"❌ Stage: {stage}")
            print(f"Error type: {type(e).__name__}")
            print(f"Error: {e}")
            return e



    async def tg_login_old(
        self,
        user_client: TelegramClient,
        phone_number: str,
        pw2fa: str | None,
    ):
        try:
            # Send verification code and start the login process
            print("Sending verification code to the specified phone number...", flush=True)
            await user_client.send_code_request(phone_number)

            # User inputs the received verification code
            code = input('Please enter the code you received(a): ')
            # Use phone number and verification code to log in
            return await user_client.sign_in(phone=phone_number, password=pw2fa, code=code)

        except SessionPasswordNeededError:
            # Handle two-factor authentication
            print("Two-factor authentication password is required", flush=True)
            return await user_client.sign_in(password=pw2fa)

        except RPCError as e:
            # Capture RPC error and display detailed error message
            print(f"Failed to send verification request, error: {e}", flush=True)
            return e

    async def login_bot(
        self,
        bot_info: dict[str, Any],
        pw2fa: str | None = None,
        login_method: str = "phone",
    ) -> tuple[TelegramClient | None, int, dict[str, Any]]:
        """使用指定 bot 資料內的 StringSession 登入 Telegram。"""

        status_code = 1
        phone_number = bot_info.get("phone")
        session_string = bot_info.get("bot_token")
        bot_title = bot_info.get("bot_title")
        config = self.load_config()
        if pw2fa is None:
            pw2fa = config.get("default_pw2fa", None)
        api_id = bot_info.get('api_id', int(config.get("api_id", os.getenv("API_ID", 0) or 0)))
        api_hash = bot_info.get('api_hash', config.get("api_hash", os.getenv("API_HASH", "")))

        if not session_string:
            session_name = phone_number.replace('+', '').replace(' ', '') + '_' + str(api_id) # 确保电话号码格式正确
        else:
            session_name = StringSession(str(session_string).strip())
            

        #     bot_info['check_status'] =  "bot_info 的 bot_token 為空"
        #     return None, 0, bot_info


        if not api_id or not api_hash:
            bot_info['check_status'] =  "缺少 API_ID 或 API_HASH"
            return None, 0, bot_info



        try:
            # print(f"正在使用 session={session_name} 连接 Telegram...", flush=True)
            user_client = TelegramClient(
                session_name, api_id, str(api_hash)
            )
            await user_client.connect()
        except Exception as exc:
            bot_info['check_status'] =  (f"bot_token 不是有效的 Telethon StringSession，"
                        f"bot_id= {bot_info.get('bot_id')} ，api={api_id} 錯誤={exc}")


            # return (
            #     None,
            #     0,
            #     bot_info,
            # )

        if not await user_client.is_user_authorized():

            phone_number = bot_info.get('phone')
            if not phone_number:
                bot_name = str(bot_info.get('bot_name') or '')
                if bot_name.startswith("p_"):
                    phone_number = "+" + bot_name[2:]

            phone_number = str(phone_number or "").strip()
            if not re.fullmatch(r"\+[1-9]\d{6,14}", phone_number):
                await user_client.disconnect()
                bot_info['check_status'] =  (
                    f"bot_id= {bot_info.get('bot_id')} 缺少有效 phone ( {phone_number} )，"
                    "格式必須是 + 加國碼與電話號碼"
                )
                return (
                    None,
                    0,
                    bot_info,
                )

            print(f"❗️ User is not authorized, starting the login process...  {bot_title}  {phone_number} ,bot_id= {bot_info.get('bot_id')} ", flush=True)
            print(f"\n{bot_info.get('api_url')}\n",flush=True)
            if login_method == 'qrcode':
                result = await self.tg_qrcode_login(user_client,  pw2fa)
                print("使用 QR code 登录", flush=True)


            else:
                print("使用电话登录", flush=True)
                result = await self.tg_login(user_client, phone_number, pw2fa)

            if isinstance(result, FloodWaitError):
                await user_client.disconnect()
                bot_info['check_status'] = (
                    f"Telegram 限制發送驗證碼，需等待 {result.seconds} 秒後再試"
                )
                return None, 0, bot_info
            elif "has been banned from" in str(result):
                print(f"❌ 该用户已被封禁。{bot_info.get('bot_title')}", flush=True)
                bot_info['check_status'] = "該用戶已被封禁"
                return None, 4, bot_info
            elif "The phone code entered was invalid" in str(result):
                print("❌ The phone code entered was invalid。", flush=True)
                bot_info['check_status'] =  "The phone code entered was invalid"
                return None, 0, bot_info
            elif "can no longer be used" in str(result):
                '''
                Failed to send verification request, error: The authorization key (session file) was used under two different IP addresses simultaneously, and can no longer be used. Use the same session exclusively, or use different sessions (caused by SendCodeRequest)
                '''
                print(f"❌ {result}", flush=True)
                bot_info['check_status'] =  "two different IP addresses simultaneously"

                await user_client.disconnect()
                if isinstance(session_name, str):
                    session_path = Path(user_client.session.filename)
                    session_path.unlink(missing_ok=True)

                new_bot_info  = {
                    "phone": phone_number,
                    "api_url": bot_info.get('api_url'),
                }
                return await self.login_bot(bot_info=new_bot_info, pw2fa=pw2fa)


                # return None, 0, bot_info            
            elif result:
                stringsession = StringSession.save(user_client.session)
                print("\n✅ 以下是你的 StringSession（可写入 .env）\n")
                print("USER_SESSION_STRING=" + stringsession)
                bot_info['bot_token'] = stringsession
                bot_info['check_status'] = "new stringsession"
                return user_client, status_code,  bot_info


            else:
                await user_client.disconnect()
                bot_info['check_status'] = (
                    "bot_token 不是已授權的 Telethon StringSession，"
                    f"bot_id={bot_info.get('bot_id')} {bot_info.get('phone')}"
                )
                return (
                    None,
                    0,
                    bot_info,
                )
        else:
            print(f"✅ 已登入 {bot_info.get('bot_title')}，bot_id={bot_info.get('bot_id')}，phone={bot_info.get('phone')}", flush=True)
            
            print(f"\n{bot_info.get('api_url')}\n")

            bot_info['check_status'] = "已登入"

            bot_info['bot_token'] = StringSession.save(user_client.session)
            return user_client, status_code,  bot_info
        return user_client, status_code,  bot_info


    async def forward_latest_group_messages(self, user_client, target_user_id, group_id, limit=5):
        """Forward the latest messages from the configured group to the target user."""
        if not group_id:
            print("未配置 self.TGSOURCE_CHAT_ID，跳过群组消息转发", flush=True)
            return

        try:
            warning_tag = ""
            group = await user_client.get_entity(int(group_id))
            messages = await user_client.get_messages(group, limit=limit)
            messages = list(reversed(messages))

            if not messages:
                print(f"指定群组 {group_id} 没有可转发的消息", flush=True)
                return

            catch_code_message
            target = await user_client.get_entity(int(target_user_id))
            for msg in messages:
                safe_text = escape(msg.text or "")
                received_at = msg.date
                if received_at is not None:
                    if received_at.tzinfo is None:
                        received_at = received_at.replace(tzinfo=timezone.utc)
                    received_at = received_at.astimezone(APP_TIMEZONE)
                    received_time = received_at.strftime("%Y-%m-%d %H:%M:%S%z")
                else:
                    received_time = "未知"

                match = re.search(
                    r"\*{0,2}Login code:\*{0,2}\s*(\d+)",
                    safe_text,
                    re.IGNORECASE,
                )

                # 如果 received_time 是三天的，则打印
                if received_at is not None:
                    now = datetime.now(APP_TIMEZONE)
                    three_days_ago = now - timedelta(days=3)
                    fifteen_days_ago = now - timedelta(days=15)
                    if received_at >= three_days_ago:
                        
                        await user_client.send_message(
                            target,
                            f"‼️ 三天前的消息:（id={msg.id}）{safe_text}"
                            f"\n收到时间：{received_time}（",
                            parse_mode="html",
                        )
                    elif received_at < fifteen_days_ago:
                        print(f"十五天前的消息:（id={msg.id}）{safe_text}", flush=True)
                        continue


                if "IMPORTANT. Request to reset password." in safe_text:
                    warning_tag = "‼️‼️  "
                    await user_client.send_message(
                        target,
                        f"‼️ ‼️ 捕获到重要消息:（id={msg.id}）{safe_text}"
                        f"\n收到时间：{received_time}（",
                        parse_mode="html",
                    )

                    try:
                        buttons = await msg.get_buttons() if hasattr(msg, "get_buttons") else None
                        if not buttons:
                            print("消息中没有按钮，无法点击 Cancel Reset Request", flush=True)
                            continue

                        clicked = False
                        for row in buttons:
                            for button in row:
                                button_text = str(getattr(button, "text", "") or "").strip()
                                if "Cancel Reset Request" in button_text:
                                    print(f"找到按钮：{button_text}，开始点击", flush=True)
                                    click_result = await msg.click(
                                        text=lambda text: "Cancel Reset Request" in str(text or "")
                                    )
                                    print(f"点击结果：{click_result}", flush=True)
                                    print(
                                        f"alert={getattr(click_result, 'alert', None)}",
                                        f"message={getattr(click_result, 'message', None)}",
                                        f"url={getattr(click_result, 'url', None)}",
                                        flush=True,
                                    )
                                    clicked = True
                                    break
                            if clicked:
                                break

                        if not clicked:
                            print("未找到名为 Cancel Reset Request 的按钮", flush=True)
                    except Exception as exc:
                        print(f"点击 Cancel Reset Request 失败：{exc}", flush=True)
                    

                elif match:
                    code = match.group(1)
                    print(
                        f"捕获到 login code: {code}，收到时间：{received_time}（",
                        flush=True,
                    )

                    fullwidth_code = code.translate(
                        str.maketrans("0123456789", "０１２３４５６７８９")
                    )
                    catch_code_message += f"捕获到 code:（id={msg.id}）{fullwidth_code} at {received_time} \n"
            if catch_code_message:
                await user_client.send_message(
                    target,
                    catch_code_message,
                    parse_mode="html",
                )

        except Exception as exc:
            print(
                f"❌ 转发群组 {group_id} 的最后消息失败：{exc}",
                flush=True,
            )


    async def product_user_name(self):
        for attempt in range(5):
            # 以辅音和元音交替组成 3 至 4 个音节，避免难读的字母堆叠。
            english_name = "".join(
                random.choice("bdfhklmnprstv") + random.choice("aeiou")
                for _ in range(random.randint(3, 4))
            )
            digit_count = random.randint(2, 8)
            number_suffix = str(random.randint(10 ** (digit_count - 1), 10 ** digit_count - 1))
            username = f"{english_name}{number_suffix}"
            try:
                await self.client(UpdateUsernameRequest(username))
            except UsernameOccupiedError:
                if attempt == 4:
                    print("⚠️ 连续 5 次生成的用户名均已被占用。", flush=True)
                    raise
            except UsernameNotModifiedError:
                print(f"用户名已是 @{username}，无需修改。", flush=True)
                break
            except Exception as exc:
                print(f"⚠️ 用户名更新失败：{exc}", flush=True)
                raise
            else:
                print(f"✅ 用户名已更新为 @{username}。", flush=True)
                break


    async def check_userbot(
        self,
        bot_info: dict[str, Any],
        pw2fa: str | None = None,
        login_method: str = "phone",
    ) -> None:
        TARGET_USER_ID = SharedConfig.get("key_man_id")

        work_status = bot_info.get("work_status","free")
        user_client, status_code, new_bot_info = await self.login_bot(bot_info, pw2fa, login_method)

        config = self.load_config()
        default_pw2fa = config.get("default_pw2fa", None)
        if new_bot_info and new_bot_info.get("api_id") is None:
            new_bot_info["api_id"] = int(config.get("api_id", os.getenv("API_ID", 0) or 0))
        if new_bot_info and new_bot_info.get("api_hash") is None:
            new_bot_info["api_hash"] = config.get("api_hash", os.getenv("API_HASH", ""))


        if status_code != 1 or user_client is None:
            print(f"❌登入失敗: {new_bot_info.get('check_status')}", flush=True)
            if status_code == 4:
                work_status = "ban"

        else:
            try:
                me = await user_client.get_me()
                new_bot_info['bot_id'] = me.id
                new_bot_info['bot_name'] = me.username
                new_bot_info['user_id'] = me.id
                new_bot_info['bot_root'] = me.username
                new_bot_info['bot_title'] = me.first_name+" "+(me.last_name or "")


                try:

                    # 构造一个要导入的联系人
                    contact = InputPhoneContact(
                        client_id=0,
                        phone="+447447471403",
                        first_name="Vampire",
                        last_name=""
                    )




                    try:
                        result = await user_client(ImportContactsRequest([contact]))
                    except Exception as e:
                        
                        if "FROZEN_METHOD_INVALID" in str(e) or " frozen accounts" in str(e):
                            new_bot_info["work_status"] = 'frozen'
                            work_status = "frozen"
                            print(f"❌ 🧊 账号冻结: {e}")
                        else:
                            print(f"❌ 更新失败(ImportContactsRequest): {e}")
                        

                    if bot_info.get('topic_id') is None:
                        try:
                            new_bot_info['topic_id'] = await self.create_account_topic(
                                user_client,
                                me.first_name,
                                me.last_name,
                                me.id,
                            )
                            print(
                                f"✅ 已建立帳號主題，topic_id={new_bot_info['topic_id']}",
                                flush=True,
                            )
                        except Exception as exc:
                            warning = f"建立帳號主題失敗：{exc}"
                            new_bot_info['check_status'] = warning
                            print(f"❌ {warning}", flush=True)



                    target_user_id = int(TARGET_USER_ID)
                    target = await user_client.get_entity(target_user_id)
                    await user_client.send_message(
                        target,
                        f"<blockquote>{datetime.now(APP_TIMEZONE)}</blockquote>"
                        f"[RESET] 你好, 我是 <code>{me.id}</code> - "
                        f"{me.first_name} {me.last_name or ''} +{me.phone} "
                        f"\nrestricted={me.restricted}\nscam={me.scam}\nfake={me.fake}",
                        parse_mode="HTML",
                    )
                    # await self.forward_latest_group_messages(
                    #     user_client,
                    #     TARGET_USER_ID,
                    #     self.TGSOURCE_CHAT_ID,
                    # )
                except PeerFloodError as exc:
                    warning = f"Telegram 限制發送通知（PeerFloodError）：{exc}"
                    print(f"⚠️ {warning}", flush=True)
                    new_bot_info["check_status"] = warning
                except (PeerIdInvalidError, ValueError, TypeError) as exc:
                    peer_type = "bot" if getattr(me, "bot", False) else "user"
                    warning = (
                        f"通知發送失敗：登入類型={peer_type}，"
                        f"target_user_id={TARGET_USER_ID}，錯誤={exc}"
                    )
                    print(f"⚠️ {warning}", flush=True)
                    new_bot_info["check_status"] = warning
                    if peer_type == "user":
                        new_bot_info["work_status"] = 'frozen'


                # 1. 列出当前帐号所有 active sessions
                auths = await user_client(GetAuthorizationsRequest())

                device_model_str = ""
                for a in auths.authorizations:
                    
                    if a.hash == 0:
                        
                        print(f"✅ 保留本身 id={a.hash}  device={a.device_model}  platform={a.platform}  ip={a.ip}  date={a.date_created.astimezone(APP_TIMEZONE)}")
                        device_model_str += "✅ 保留本身 "+a.device_model + "\n"
                        continue  # 跳过主会话
                    elif a.device_model not in WHITELIST:
                        try:
                            # 如果 a.date_created 在七天之内的
                            seven_days_ago = datetime.now(APP_TIMEZONE) - timedelta(days=7)
                            if a.date_created >= seven_days_ago:
                                print(f"❗️ 最近七天内创建的会话 id={a.hash}  device_model={a.device_model}  platform={a.platform}  ip={a.ip}  date={a.date_created.astimezone(APP_TIMEZONE)}")
                                device_model_str += "❗️ 最近七天内创建的会话 "+a.device_model + "\n"

                            elif a.device_model in BLACKLIST:
                                print(f"❌ 已删除 id={a.hash}  device_model={a.device_model}  platform={a.platform}  ip={a.ip}  date={a.date_created.astimezone(APP_TIMEZONE)} (已删除)")
                                device_model_str += "❌ 黑名单已删除 "+a.device_model + "\n"
                                await user_client(ResetAuthorizationRequest(hash=a.hash))
                            elif a.hash == -212406687192506612 or a.hash == -6894703599540223408:
                                print(f"❌ 已删除 id={a.hash}  device_model={a.device_model}  platform={a.platform}  ip={a.ip}  date={a.date_created.astimezone(APP_TIMEZONE)} (已删除)")
                                device_model_str += "❌ 特定会话已删除 "+a.device_model + "\n"
                                await user_client(ResetAuthorizationRequest(hash=a.hash))
                            else:
                                # await client(ResetAuthorizationRequest(hash=a.hash))
                                print(f"⚠️ 建議删除 id={a.hash}  device_model={a.device_model}  platform={a.platform}  ip={a.ip}  date={a.date_created.astimezone(APP_TIMEZONE)}")
                                device_model_str += "⚠️ 建議删除 "+a.device_model + "\n"
                                # ❗️ 建議删除 id=-2622773520313404250  device_model=Desktop  platform=  ip=  date=2026-05-08 15:57:28+00:00
                                # ❗️ 建議删除 id=985113455830527986  device_model=Desktop  platform=  ip=  date=2026-01-03 08:01:27+00:00
                                # ❗️ 建議删除 id=3145982375868211614  device_model=Desktop  platform=  ip=  date=2026-05-08 15:55:32+00:00
                        except Exception as e:
                            print(f"❌ 删除 {a.hash} 失败: {e}")
                    else:
                        print(f"✅ 保留 id={a.hash}  device_model={a.device_model}  platform={a.platform}  ip={a.ip}  date={a.date_created.astimezone(APP_TIMEZONE)}")
                        device_model_str += "✅ 白名单保留 "+a.device_model + "\n"

                await user_client.send_message(
                    target,
                    f"[RESET] 你好, 我是 <code>{me.id}</code> - "
                    f"{me.first_name} {me.last_name or ''} +{me.phone} "
                    f"\nrestricted={me.restricted}\nscam={me.scam}\nfake={me.fake}"
                    f"\n<b>device_model:</b>\n{device_model_str}",
                    parse_mode="HTML",
                )

                await self.forward_latest_group_messages(
                    user_client,
                    TARGET_USER_ID,
                    self.TGSOURCE_CHAT_ID,
                )


                if pw2fa:
                    try:

                        if default_pw2fa and default_pw2fa != pw2fa:

                            await user_client.edit_2fa(
                                current_password=pw2fa,  # 直接传入旧密码
                                new_password=default_pw2fa,      # 设置的新密码
                                hint="HINT"
                            )
                            print("✅ 2FA 密码已更新")
                        else:
                            print(f"ℹ️ 2FA 密码未更新，使用默认密码或未提供新密码")

                    except Exception as e:
                        print(f"❌ 更新失败(edit_2fa): {e}")
                        if "FROZEN_METHOD_INVALID" in str(e):
                            print("❌ 旧密码无效，请检查 PW2FA 是否正确。")
                            new_bot_info['work_status']  = "frozen"
                            work_status = "frozen"

                username = None
                if new_bot_info['bot_name'] is None:
                    try:

                       

                        new_username = None
                        for attempt in range(5):
                            # 以辅音和元音交替组成 3 至 4 个音节，避免难读的字母堆叠。
                            english_name = "".join(
                                random.choice("bdfhklmnprstv") + random.choice("aeiou")
                                for _ in range(random.randint(3, 4))
                            )
                            digit_count = random.randint(2, 8)
                            number_suffix = str(random.randint(10 ** (digit_count - 1), 10 ** digit_count - 1))
                            new_username = f"{english_name}{number_suffix}"
                        new_bot_info['bot_name'] = new_username

                        
                        # phone_number2 = new_bot_info.get('phone').replace('+', 'p_').replace(' ', '')  # 确保电话号码格式正确
                        await user_client(UpdateUsernameRequest(new_username))  # 设置空字符串即为移除
                        # new_bot_info['bot_name'] = phone_number2
                        print("✅ 用户名已成功变更。")
                    except Exception as e:
                        print(f"❌ 用户名变更失败：{e}")


                print(
                    f"✅ Telegram 登入成功：資料列 id={bot_info.get('bot_id')} {bot_info.get('bot_title')}，"
                    f"user_id={getattr(me, 'id', None)}，"
                    f"username={getattr(me, 'username', None)}"
                )
            except AuthKeyUnregisteredError:
                work_status = "free"
                new_bot_info["check_status"] = (
                    "Telethon StringSession 的 auth key 已被 Telegram 註銷，需要重新登入"
                )
                print(
                    f"登入 session 已失效：bot_id= {new_bot_info.get('bot_id')} ",
                    flush=True,
                )
            except Exception as e:
                print(f"❌ 登入失败: {e}")

            finally:
                await user_client.disconnect()

        new_bot_info['check_timestamp'] = int(time.time())



        if(new_bot_info.get("bot_id") is not None):

            await MySQLPool.execute(
                "INSERT INTO `bot` "
                "(`bot_id`, `bot_token`, `bot_name`, `bot_root`, `user_id`, `bot_title`, `phone`, "
                "`api_id`, `api_hash`, `topic_id`, `work_status`, `check_timestamp`, `check_status`, `api_url`) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE "
                "`bot_token` = VALUES(`bot_token`), "
                "`bot_name` = VALUES(`bot_name`), "
                "`bot_root` = VALUES(`bot_root`), "
                "`user_id` = VALUES(`user_id`), "
                "`bot_title` = VALUES(`bot_title`), "
                "`phone` = VALUES(`phone`), "
                "`api_id` = VALUES(`api_id`), "
                "`api_hash` = VALUES(`api_hash`), "
                "`topic_id` = VALUES(`topic_id`), "
                "`check_timestamp` = VALUES(`check_timestamp`), "
                "`check_status` = VALUES(`check_status`), "
                "`work_status` = VALUES(`work_status`)",
                (
                    new_bot_info["bot_id"],
                    new_bot_info.get("bot_token", ""),
                    new_bot_info.get("bot_name"),
                    new_bot_info.get("bot_root"),
                    new_bot_info.get("user_id"),
                    new_bot_info.get("bot_title", ""),
                    new_bot_info.get("phone"),
                    new_bot_info.get("api_id"),
                    new_bot_info.get("api_hash"),
                    new_bot_info.get("topic_id"),
                    work_status,
                    new_bot_info["check_timestamp"],
                    new_bot_info.get("check_status", ""),
                    new_bot_info.get("api_url", ""),
                ),
                error_tag="userbot.upsert_check_timestamp",
                raise_on_error=True,
            )

    async def check_all_userbot(self, config: dict[str, Any] | None = None) -> None:

        bots = await self.get_all_bots()
        if not bots:
            raise RuntimeError("bot 資料表沒有任何資料")

        for bot in bots:
            await self.check_userbot(bot)
            await asyncio.sleep(5)  # 避免過於頻繁的請求
            print("\n" + "=" * 50 + "\n", flush=True)
        # bot_info = bots[0]
        # await self.check_userbot(bot_info)

    async def rec_new_account(
        self,
        phone_number: str,
        pw2fa: str | None = None,
        api_url: str = "",
        login_method: str = "phone",
    ) -> None:
        """建立並確認一個新的 Telegram 使用者帳號。"""
        phone_number = (phone_number or "").strip()
        if not phone_number:
            raise ValueError("phone_number 不可為空")

        bot_info  = {
            "phone": phone_number,
            "api_url": api_url,
        }
        print(f"開始登入 {phone_number} ...", flush=True)
        await self.check_userbot(bot_info, pw2fa=pw2fa, login_method=login_method)

    async def check_phone(self, phone_number: str) -> None:
        """依電話號碼載入並確認既有 Telegram 使用者帳號。"""
        bot_info = await self.get_bot(phone_number)
        if not bot_info:
            raise RuntimeError(f"找不到電話號碼 {phone_number} 的帳號資料")
        await self.check_userbot(bot_info)
