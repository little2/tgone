

import os
import aiohttp
import asyncio
import time
from dotenv import load_dotenv
from telethon.sessions import StringSession
from telethon import TelegramClient, events

# Aiogram 相关
from aiogram import F, Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import ContentType
from aiogram.filters import Command
from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from utils import MediaUtils


from tgone_config import API_ID, API_HASH, BOT_TOKEN, TARGET_GROUP_ID, PHONE_NUMBER,  BOT_MODE, WEBHOOK_HOST, WEBHOOK_PATH, SESSION_STRING, config

lz_var_start_time = time.time()


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
@user_client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private and e.message.media is not None))
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
   

async def run_telethon():
    await user_client.start(PHONE_NUMBER)
    print("【Telethon】人类账号 已启动。", flush=True)
    await media_utils.set_bot_info()
    print(f'你的用户名: {media_utils.man_username} / {media_utils.bot_username}', flush=True)
    print(f'你的ID: {media_utils.man_id} / {media_utils.bot_id}', flush=True)
    await user_client.send_message(media_utils.bot_username, '/start')
    await user_client.run_until_disconnected()


async def run_aiogram_polling():
    print("【Aiogram】Bot（纯 Bot-API） 已启动，监听私聊＋群组媒体。", flush=True)
    await dp.start_polling(bot_client)   

# ================= 14. 启动两个客户端 =================
async def main():
# 10.1 Telethon “人类账号” 登录

    print("🔧 正在初始化数据库表...")
    await media_utils.ensure_database_tables()

    asyncio.create_task(media_utils.heartbeat())

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
        t = asyncio.create_task(run_telethon())
        await run_aiogram_polling()
        t.cancel()

if __name__ == "__main__":
    asyncio.run(main())

