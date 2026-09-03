"""讀取 MySQL `bot` 資料表中的所有資料。"""

import json
import os
import asyncio
import re
import time
from datetime import timedelta, timezone
from html import escape
from typing import Any
from unittest import result

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.account import GetAuthorizationsRequest, ResetAuthorizationRequest, UpdateUsernameRequest
from telethon.errors import (
    AuthKeyDuplicatedError,
    AuthKeyUnregisteredError,
    FloodWaitError,
    PeerFloodError,
    PeerIdInvalidError,
    RPCError,
    SessionPasswordNeededError,
)
from telethon.tl.functions.contacts import ImportContactsRequest
from telethon.tl.types import InputPhoneContact
# shared_config 會在 import 時讀取 SETTING_URL，因此必須先載入環境變數。

from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent / ".env"

load_dotenv(dotenv_path=env_path)

from shared_config import SharedConfig  # noqa: E402
from tgone_mysql import MySQLPool  # noqa: E402

TGSOURCE_CHAT_ID = 777000               # Telegram 服务讯息


def load_config() -> dict[str, Any]:
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


async def get_all_bots() -> list[dict[str, Any]]:
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


async def get_bot(phone_number: str) -> dict[str, Any] | None:
    """根據電話號碼取得 `bot` 資料表中對應的完整 row。"""
    phone_number = (phone_number or "").strip()
    if not phone_number:
        raise ValueError("phone_number 不可為空")

    return await MySQLPool.fetchone(
        "SELECT * FROM `bot` WHERE `phone` = %s LIMIT 1",
        (phone_number,),
        error_tag="userbot.get_bot",
    )


async def tg_login(user_client, phone_number, pw2fa):
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
    bot_info: dict[str, Any], 
    pw2fa: str | None = None
) -> tuple[TelegramClient | None, int, dict[str, Any]]:
    """使用指定 bot 資料內的 StringSession 登入 Telegram。"""

    status_code = 1
    phone_number = bot_info.get("phone")
    session_string = bot_info.get("bot_token")
    config = load_config()
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
        
        print(f"User is not authorized, starting the login process...  {phone_number} ,bot_id= {bot_info.get('bot_id')} ", flush=True)
        result = await tg_login(user_client, phone_number, pw2fa)
       
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
        bot_info['check_status'] = "已登入"
        
        bot_info['bot_token'] = StringSession.save(user_client.session)
        return user_client, status_code,  bot_info
    return user_client, status_code,  bot_info


async def forward_latest_group_messages(user_client, target_user_id, group_id, limit=3):
    """Forward the latest messages from the configured group to the target user."""
    if not group_id:
        print("未配置 TGSOURCE_CHAT_ID，跳过群组消息转发", flush=True)
        return

    try:
        group = await user_client.get_entity(int(group_id))
        messages = await user_client.get_messages(group, limit=limit)
        messages = list(reversed(messages))

        if not messages:
            print(f"指定群组 {group_id} 没有可转发的消息", flush=True)
            return

        target = await user_client.get_entity(int(target_user_id))
        for msg in messages:
            safe_text = escape(msg.text or "")
            received_at = msg.date
            if received_at is not None:
                if received_at.tzinfo is None:
                    received_at = received_at.replace(tzinfo=timezone.utc)
                received_time = received_at.astimezone(
                    timezone(timedelta(hours=8))
                ).strftime("%Y-%m-%d %H:%M:%S")
            else:
                received_time = "未知"

            match = re.search(
                r"\*{0,2}Login code:\*{0,2}\s*(\d+)",
                safe_text,
                re.IGNORECASE,
            )

            if match:
                code = match.group(1)
                print(
                    f"捕获到 login code: {code}，收到时间：{received_time}（Asia/Taipei）",
                    flush=True,
                )

                fullwidth_code = code.translate(
                    str.maketrans("0123456789", "０１２３４５６７８９")
                )
                await user_client.send_message(
                    target,
                    f"捕获到 code:（id={msg.id}）{fullwidth_code}"
                    f"\n收到时间：{received_time}（Asia/Taipei）",
                    parse_mode="html",
                )

    except Exception as exc:
        print(
            f"转发群组 {group_id} 的最后消息失败：{exc}",
            flush=True,
        )


async def check_userbot(bot_info, pw2fa=None):
    TARGET_USER_ID = SharedConfig.get("key_man_id")

    work_status = bot_info.get("work_status","free")
    user_client, status_code, new_bot_info = await login_bot(bot_info, pw2fa)

    config = load_config()
    default_pw2fa = config.get("default_pw2fa", None)
    if new_bot_info and new_bot_info.get("api_id") is None:
        new_bot_info["api_id"] = int(config.get("api_id", os.getenv("API_ID", 0) or 0))
    if new_bot_info and new_bot_info.get("api_hash") is None:
        new_bot_info["api_hash"] = config.get("api_hash", os.getenv("API_HASH", ""))
        

    if status_code != 1 or user_client is None:
        print(f"登入失敗: {new_bot_info.get('check_status')}", flush=True)
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
                    print(f"❌ 更新失败: {e}")
                    if "FROZEN_METHOD_INVALID" in str(e):                       
                        new_bot_info["work_status"] = 'frozen'



                target_user_id = int(TARGET_USER_ID)
                target = await user_client.get_entity(target_user_id)
                await user_client.send_message(
                    target,
                    f"[RESET] 你好, 我是 <code>{me.id}</code> - "
                    f"{me.first_name} {me.last_name or ''} +{me.phone} "
                    f"\nrestricted={me.restricted}\nscam={me.scam}\nfake={me.fake}",
                    parse_mode="HTML",
                )
                await forward_latest_group_messages(
                    user_client,
                    TARGET_USER_ID,
                    TGSOURCE_CHAT_ID,
                )
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


            WHITELIST = {
                "Redmi Redmi K40",                       # PC 64bit Android
                "XiaomiM2012K11AC",     # XiaomiM2012K11AC
                "PC 64bit",     # PC 64bit
                "Oppo Find X7",
                "OPPOPHZ110",
                "MacBook Pro",
                "U36JC",
                "Desktop",
                "Xiaomi Mi 9 Lite",
                "XiaomiMi 9 Lite",
                "iPad mini (6th gen)"
            }

            # 1. 列出当前帐号所有 active sessions
            auths = await user_client(GetAuthorizationsRequest())
            
            for a in auths.authorizations:
                if a.hash == 0:
                    print(f"✅ 保留本身 id={a.hash}  device={a.device_model}  platform={a.platform}  ip={a.ip}  date={a.date_created}")
                    continue  # 跳过主会话
                elif a.device_model not in WHITELIST:
                    try:
                        if a.device_model == "Swift SFG14-71" or a.device_model == "Vivo Y28s 5G":
                            print(f"❌ 已删除 id={a.hash}  device_model={a.device_model}  platform={a.platform}  ip={a.ip}  date={a.date_created} (已删除)")
                            await user_client(ResetAuthorizationRequest(hash=a.hash))
                        elif a.hash == -212406687192506612 or a.hash == -6894703599540223408:
                            print(f"❌ 已删除 id={a.hash}  device_model={a.device_model}  platform={a.platform}  ip={a.ip}  date={a.date_created} (已删除)")
                            await user_client(ResetAuthorizationRequest(hash=a.hash))
                        else:
                            # await client(ResetAuthorizationRequest(hash=a.hash))
                            print(f"❗️ 建議删除 id={a.hash}  device_model={a.device_model}  platform={a.platform}  ip={a.ip}  date={a.date_created}")
                            # ❗️ 建議删除 id=-2622773520313404250  device_model=Desktop  platform=  ip=  date=2026-05-08 15:57:28+00:00
                            # ❗️ 建議删除 id=985113455830527986  device_model=Desktop  platform=  ip=  date=2026-01-03 08:01:27+00:00
                            # ❗️ 建議删除 id=3145982375868211614  device_model=Desktop  platform=  ip=  date=2026-05-08 15:55:32+00:00
                    except Exception as e:
                        print(f"删除 {a.hash} 失败: {e}")
                else:
                    print(f"✅ 保留 id={a.hash}  device_model={a.device_model}  platform={a.platform}  ip={a.ip}  date={a.date_created}")

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
                    print(f"❌ 更新失败: {e}")
                    if "FROZEN_METHOD_INVALID" in str(e):
                        print("❌ 旧密码无效，请检查 PW2FA 是否正确。")
                        new_bot_info['work_status']  = "frozen"

            username = None
            if new_bot_info['bot_name'] is None:
                try:
                    phone_number2 = new_bot_info.get('phone').replace('+', 'p_').replace(' ', '')  # 确保电话号码格式正确
                    await user_client(UpdateUsernameRequest(phone_number2))  # 设置空字符串即为移除
                    new_bot_info['bot_name'] = phone_number2
                    print("用户名已成功变更。")
                except Exception as e:
                    print(f"用户名变更失败：{e}") 
            

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
        finally:
            await user_client.disconnect()

    new_bot_info['check_timestamp'] = int(time.time())





    await MySQLPool.execute(
        "INSERT INTO `bot` "
        "(`bot_id`, `bot_token`, `bot_name`, `bot_root`, `user_id`, `bot_title`, `phone`, "
        "`api_id`, `api_hash`, `work_status`, `check_timestamp`, `check_status`, `api_url`) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
        "ON DUPLICATE KEY UPDATE "
        "`bot_token` = VALUES(`bot_token`), "
        "`bot_name` = VALUES(`bot_name`), "
        "`bot_root` = VALUES(`bot_root`), "
        "`user_id` = VALUES(`user_id`), "
        "`bot_title` = VALUES(`bot_title`), "
        "`phone` = VALUES(`phone`), "
        "`api_id` = VALUES(`api_id`), "
        "`api_hash` = VALUES(`api_hash`), "
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
            work_status,
            new_bot_info["check_timestamp"],
            new_bot_info.get("check_status", ""),
            new_bot_info.get("api_url", ""),
        ),
        error_tag="userbot.upsert_check_timestamp",
        raise_on_error=True,
    )

async def check_all_userbot(config: dict[str, Any] | None = None) -> None:
    
    bots = await get_all_bots()
    if not bots:
        raise RuntimeError("bot 資料表沒有任何資料")

    for bot in bots:
        await check_userbot(bot)
        await asyncio.sleep(3)  # 避免過於頻繁的請求
        print("\n" + "=" * 50 + "\n", flush=True)
    # bot_info = bots[0]
    # await check_userbot(bot_info)
    

async def rec_new_account():   
    pw2fa = "Aa123123"  # Replace with the actual password for two-factor authentication
    phone_number = "+62895376857784"  # Replace with the actual phone number for the new account
    api_url = ""

    bot_info  = {       
        "phone": phone_number,
        "api_url": api_url,       
    }
    print(f"開始登入 {phone_number} ...", flush=True)
    await check_userbot(bot_info, pw2fa)

async def check_phone():
  
    phone_number = "+6287888900688"  # Replace with the actual phone number for the new account

    bot_info = await get_bot(phone_number)
    if not bot_info:
        raise RuntimeError("bot 資料表沒有任何資料")
    await check_userbot(bot_info)    




async def main() -> None:
    config = load_config()
    MySQLPool.configure(
        host=config.get("db_host", os.getenv("MYSQL_DB_HOST", "localhost")),
        user=config.get("db_user", os.getenv("MYSQL_DB_USER", "")),
        password=config.get("db_password", os.getenv("MYSQL_DB_PASSWORD", "")),
        database=config.get("db_name", os.getenv("MYSQL_DB_NAME", "")),
        port=int(config.get("db_port", os.getenv("MYSQL_DB_PORT", 3306))),
    )
    try:
        await check_all_userbot(config)
        # await rec_new_account()  # Replace with the actual phone number
        # await check_phone()  # Replace with the actual phone number
    finally:
        await MySQLPool.close()


if __name__ == "__main__":
    asyncio.run(main())
