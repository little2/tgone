

import os
import aiohttp
import asyncio
import time
from dotenv import load_dotenv
from telethon.sessions import StringSession
from telethon import TelegramClient, events
from datetime import datetime
# Aiogram 相关
from aiogram import F, Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import ContentType
from aiogram.filters import Command
from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from utils import MediaUtils
from telethon.tl.functions.contacts import ImportContactsRequest
from telethon.tl.types import InputPhoneContact

from tgone_config import API_ID, API_HASH, BOT_TOKEN, SWITCHBOT_USERNAME, TARGET_GROUP_ID, TARGET_GROUP_ID_FROM_BOT, PHONE_NUMBER,  BOT_MODE, WEBHOOK_HOST, WEBHOOK_PATH, SESSION_STRING,KEY_USER_PHONE,KEY_USER_ID, config

from telethon.errors.common import TypeNotFoundError
import traceback

lz_var_start_time = time.time()

if TARGET_GROUP_ID == 0:
    TARGET_GROUP_ID = 0 # bot

if TARGET_GROUP_ID_FROM_BOT == 0:
    
    TARGET_GROUP_ID_FROM_BOT = 0 # userbot
   



async def _fetch_and_consume(session: aiohttp.ClientSession, url: str):
    """
    并发读取网页内容：
    - 加一个时间戳参数，避免缓存
    - 真正把内容 read() 回来，让对方服务器感觉有人在看页面
    """
    try:
        params = {"t": int(datetime.now().timestamp())}
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            content = await resp.read()  # 真实读取内容
            length = len(content)
            # print(f"🌐 keep-alive fetch => {url} status={resp.status} bytes={length}", flush=True)
    except asyncio.TimeoutError:
        print(f"⚠️ keep-alive fetch timeout => {url} (10s)", flush=True)
    except Exception as e:
        print(f"⚠️ keep-alive fetch failed => {url}: {type(e).__name__}: {e}", flush=True)



async def ping_keepalive_task():
    """
    每 4 分钟并发访问一轮 URL，读取完整内容。
    """
    ping_urls = [
        "https://tgone-da0b.onrender.com",  # TGOND  park
        "https://lz-qjap.onrender.com",     # 上传 luzai02bot
        "https://lz-v2p3.onrender.com",     # LZ-No1    
        "https://twork-vdoh.onrender.com",  # TGtworkONE freebsd666bot
        "https://twork-f1im.onrender.com",  # News  news05251
        "https://lz-9bfp.onrender.com",     # 菊次郎 stcxp1069
        "https://lz-rhxh.onrender.com",     # 红包 stoverepmaria
        "https://lz-6q45.onrender.com",     # 布施 yaoqiang648
        "https://tgone-ah13.onrender.com",  # Rely
        "https://hb-lp3a.onrender.com",     # HB  
        "https://lz-upload.onrender.com",   # LZ-No2
        "https://lz-pbtb.onrender.com"      # LZ-1002
    ]

    timeout = aiohttp.ClientTimeout(total=10)
    headers = {
        # 用正常浏览器 UA，更像「真人访问」
        "User-Agent": "Mozilla/5.0 (keep-alive-bot) Chrome/120.0"
    }

    while True:
        try:
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                tasks = [
                    _fetch_and_consume(session, url)
                    for url in ping_urls
                ]
                # 并发执行所有请求
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # 只在需要时检查异常（这里仅打印，有需求可加统计）
                for url, r in zip(ping_urls, results):
                    if isinstance(r, Exception):
                        print(f"⚠️ task error for {url}: {r}", flush=True)

        except Exception as outer:
            print(f"🔥 keep-alive loop outer error: {outer}", flush=True)

        # 间隔 50 秒
        try:
            await user_client.catch_up()
            user_client.iter_dialogs(limit=1)
        except Exception as e:
            print("⚠️ catch_up() 失败，准备重连:", e, flush=True)
            try:
                await user_client.disconnect()
            except Exception:
                pass
            await user_client.connect()
            await user_client.catch_up()
        await asyncio.sleep(50)



async def keep_alive_ping():
    url = f"{WEBHOOK_HOST}{WEBHOOK_PATH}" if BOT_MODE == "webhook" else f"{WEBHOOK_HOST}/"
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    print(f"🌐 Keep-alive ping {url} status {resp.status}")
                    await user_client.catch_up()
                    user_client.iter_dialogs(limit=1)
        except Exception as e:
            print(f"⚠️ Keep-alive ping failed: {e}")

        try:
            print(f"[CATCH] 触发重连 + catch_up()", flush=True)        
            await user_client.catch_up()
            print("[CATCH] catch_up() 执行完成。", flush=True)
        except Exception as e:
            err = f"[CATCH] 执行 catch_up() 失败: {e!r}"
            print(err, flush=True)
        
        try:
            user_client.iter_dialogs(limit=1)
        except Exception as e:
            print(f"[WD] keep_updates_warm 出错: {e}", flush=True)
        return


        await asyncio.sleep(120)  # 每 5 分鐘 ping 一次

async def on_startup(bot: Bot):
    webhook_url = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
    print(f"🔗 設定 Telegram webhook 為：{webhook_url}")
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(webhook_url)
    cold_start = False  # 启动完成

async def on_startup_poll(bot: Bot):
   
    print(f"🔗 設定 Telegram webhook 為空")
    await bot.delete_webhook(drop_pending_updates=True)
    # await bot.set_webhook(None)
   

# ================= 7. 初始化 Telethon 客户端 =================

if SESSION_STRING:
    user_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    print("【Telethon】使用 StringSession 登录。",flush=True)
else:
    exit("❌ 请在环境变量中设置 USER_SESSION_STRING 以使用 StringSession 登录。")


bot_client = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()

media_utils = MediaUtils(bot_client, user_client, lz_var_start_time, config)



async def join(invite_hash):
    from telethon.tl.functions.messages import ImportChatInviteRequest
    try:
        await user_client(ImportChatInviteRequest(invite_hash))
        print("已成功加入群组",flush=True)
    except Exception as e:
        if 'InviteRequestSentError' in str(e):
            print("加入请求已发送，等待审批",flush=True)
        else:
            print(f"失败-加入群组: {invite_hash} {e}", flush=True)



from telethon import events
from telethon.tl.types import InputPhoneContact
from telethon.tl.functions.contacts import ImportContactsRequest

from telethon.tl.types import InputPhoneContact, MessageMediaContact
from telethon.tl.functions.contacts import ImportContactsRequest

@user_client.on(
    events.NewMessage(
        incoming=True,
        func=lambda e: e.is_private and (
            getattr(e.message, "contact", None) is not None
            or isinstance(getattr(e.message, "media", None), MessageMediaContact)
        )
    )
)
async def on_contact_card(event):
    # 1) 兼容两种结构：message.contact / message.media(MessageMediaContact)
    c = getattr(event.message, "contact", None)
    if c is None and isinstance(getattr(event.message, "media", None), MessageMediaContact):
        c = event.message.media

    if c is None:
        # 理论上不该发生，但兜底避免崩溃
        return

    phone = getattr(c, "phone_number", None)
    if not phone:
        await event.reply("❌ 名片没有手机号，无法加入联系人")
        return

    first_name = getattr(c, "first_name", "") or "Unknown"
    last_name  = getattr(c, "last_name", "") or ""
    card_uid   = getattr(c, "user_id", None)  # 可能为 None

    contact = InputPhoneContact(
        client_id=card_uid or 0,
        phone=phone,
        first_name=first_name,
        last_name=last_name,
    )

    try:
        result = await user_client(ImportContactsRequest([contact]))
    except Exception as e:
        await event.reply(f"❌ 导入联系人失败：{type(e).__name__}: {e}")
        return

    imported_uid = result.imported[0].user_id if getattr(result, "imported", None) else None
    users = getattr(result, "users", None) or []

    if imported_uid:
        await event.reply(f"✅ 已加入联系人：user_id={imported_uid}")
    elif users:
        await event.reply(f"✅ 已处理名片（可能已存在联系人）：user_id={users[0].id}")
    else:
        await event.reply("⚠️ 已请求导入，但没有返回用户信息（可能隐私限制或已存在）")



# ================= H1. 私聊 Message 文字处理：人类账号 =================
# @user_client.on(events.NewMessage(incoming=True))
@user_client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private and not e.message.media))
async def handle_user_private_text(event):
    text = event.raw_text.strip()
    parts = text.split(maxsplit=1)
    if text.startswith("/join"):
        invite_hash = parts[1]
        # 执行加入群组
        await join(invite_hash)
    if text.startswith("/hello"):
        hello_param = parts[1]
        # 执行加入群组
        await event.reply(f"已处理 join 指令：{hello_param}")
    else:    
        await media_utils.handle_user_private_text(event)
    return


    

# async def handle_user_private_text(event):
#     await media_utils.handle_user_private_text(event)
#     return



# ================= H2-1. 私聊 Media 媒体处理：人类账号 =================

@user_client.on(
    events.NewMessage(
        incoming=True,
        func=lambda e: e.is_private
        and e.message.media is not None
        and not getattr(e.message, "contact", None)
        and not isinstance(getattr(e.message, "media", None), MessageMediaContact)
    )
)
async def handle_user_private_media(event):
    await media_utils.handle_user_private_media(event)
    return

# ================= H3-1. 群组媒体处理：人类账号 =================
@user_client.on(events.NewMessage(chats=TARGET_GROUP_ID, incoming=True))
async def handle_user_group_media(event):
    await media_utils.handle_user_group_media(event)
    return

# ================= B1P. 私聊 Message 文字处理：Aiogram：BOT账号 =================
@dp.message(F.chat.type == "private", F.content_type.in_({ContentType.TEXT}))
async def aiogram_handle_private_text(message: types.Message):
    await media_utils.aiogram_handle_private_text(message)
    return

# ================= B2P. 私聊 Message 媒体处理：Aiogram：BOT账号 =================
@dp.message(F.chat.type == "private", F.content_type.in_({ContentType.PHOTO, ContentType.DOCUMENT, ContentType.VIDEO, ContentType.ANIMATION}))
async def aiogram_handle_private_media(message: types.Message):
    await media_utils.aiogram_handle_private_media(message)
    return

# ================= B3G. 群聊 Message 图片/文档/视频处理：Aiogram：BOT账号 =================
@dp.message(F.chat.id == TARGET_GROUP_ID, F.content_type.in_({ContentType.PHOTO, ContentType.DOCUMENT, ContentType.VIDEO, ContentType.ANIMATION}))
async def aiogram_handle_group_media(message: types.Message):
    await media_utils.aiogram_handle_group_media(message)
    return
   
async def say_hello():
     # 构造一个要导入的联系人
    contact = InputPhoneContact(
        client_id=0, 
        phone=KEY_USER_PHONE, 
        first_name="KeyMan", 
        last_name=""
    )
    result = await user_client(ImportContactsRequest([contact]))
    # print("导入结果:", result)
    target = await user_client.get_entity(KEY_USER_ID)     # 7550420493

    me = await user_client.get_me()
    await user_client.send_message(target, f"[TGONE] <code>{me.id}</code> - {me.first_name} {me.last_name or ''} {me.phone or ''}。我在执行TGONE任务！",parse_mode='html') 

    try:
        switch_ret=await user_client.send_message(SWITCHBOT_USERNAME, f"/start",parse_mode='html')
        print(f"✅ 已向 @{SWITCHBOT_USERNAME} 发送启动消息。{switch_ret}", flush=True)
    except Exception as e:
        print(f"⚠️ 向 @{SWITCHBOT_USERNAME} 发送消息失败（可能未关联或未启动）：{e}", flush=True)
        pass

async def run_telethon():
    
    await user_client.start(PHONE_NUMBER)
    print("【Telethon】人类账号 已启动。", flush=True)
    await say_hello()

    await media_utils.set_bot_info()
    print(f'你的用户名: {media_utils.man_username} / {media_utils.bot_username}', flush=True)
    print(f'你的ID (target_group_id_from_bot): {media_utils.man_id} / (target_group_id) {media_utils.bot_id}', flush=True)
    await user_client.send_message(media_utils.bot_username, '/start')
    # await user_client.run_until_disconnected()
    await run_client_forever(user_client)

async def run_client_forever(client):
    while True:
        try:
            print("[INFO] starting telethon client", flush=True)
            await client.run_until_disconnected()
        except TypeNotFoundError as e:
            print(f"[ERROR] Telethon TypeNotFoundError: {e}", flush=True)
            traceback.print_exc()
            await asyncio.sleep(3)
        except Exception as e:
            print(f"[ERROR] unexpected telethon crash: {e}", flush=True)
            traceback.print_exc()
            await asyncio.sleep(5)

async def run_aiogram_polling():
    print("【Aiogram】Bot（纯 Bot-API） 已启动，监听私聊＋群组媒体。", flush=True)
    me = await bot_client.get_me()
    TARGET_GROUP_ID = me.id
    await dp.start_polling(bot_client)   

# ================= 14. 启动两个客户端 =================
async def main():
# 10.1 Telethon “人类账号” 登录
    # await media_utils.ensure_database_tables()
    asyncio.create_task(media_utils.heartbeat())
    asyncio.create_task(ping_keepalive_task())
    if BOT_MODE == "webhook":
        asyncio.create_task(run_telethon())
        dp.startup.register(on_startup)
        print("🚀 啟動 Webhook 模式")

        app = web.Application()
        app.router.add_get("/", media_utils.health)  # ✅ 健康检查路由

        SimpleRequestHandler(dispatcher=dp, bot=bot_client).register(app, path=WEBHOOK_PATH)
        setup_application(app, dp, bot=bot_client)

        asyncio.create_task(keep_alive_ping())
        
        # ✅ Render 环境用 PORT，否则本地用 8080
        port = int(os.environ.get("PORT", 8080))
        await web._run_app(app, host="0.0.0.0", port=port)
    else:
        dp.startup.register(on_startup_poll)
        print("🚀 啟動 Polling 模式")
        t = asyncio.create_task(run_telethon())
        await run_aiogram_polling()
        t.cancel()

if __name__ == "__main__":
    asyncio.run(main())

