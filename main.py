import tracemalloc
tracemalloc.start()

import os
import base64
import pymysql
import asyncio
import json
import time
from dotenv import load_dotenv
import aiohttp
from telethon.sessions import StringSession
from telethon import TelegramClient, events
from telethon.tl.types import InputDocument
from telethon import events

# Aiogram 相关
from aiogram import F, Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import ContentType
from aiohttp import web

from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

import re

from utils import MediaUtils

# ================= 1. 载入 .env 中的环境变量 =================
# 加载环境变量
if not os.getenv('GITHUB_ACTIONS'):
    # load_dotenv(dotenv_path='.25299903.warehouse.env', override=True)
   
    load_dotenv(dotenv_path='.24690454.queue.env')
    # load_dotenv(dotenv_path='.28817994.luzai.env')
    # load_dotenv(dotenv_path='.a25299903.warehouse.env')
    # print("✅ 成功加载 .env 文件", flush=True)

config = {}
# 嘗試載入 JSON 並合併參數
try:
    configuration_json = json.loads(os.getenv('CONFIGURATION', '') or '{}')
    if isinstance(configuration_json, dict):
        config.update(configuration_json)  # 將 JSON 鍵值對合併到 config 中
except Exception as e:
    print(f"⚠️ 無法解析 CONFIGURATION：{e}")

API_ID          = int(config.get('api_id', os.getenv('API_ID', 0)))
API_HASH        = config.get('api_hash', os.getenv('API_HASH', ''))
PHONE_NUMBER    = config.get('phone_number', os.getenv('PHONE_NUMBER', ''))
BOT_TOKEN       = config.get('bot_token', os.getenv('BOT_TOKEN', ''))
TARGET_GROUP_ID = int(config.get('target_group_id', os.getenv('TARGET_GROUP_ID', 0)))
MYSQL_HOST      = config.get('db_host', os.getenv('MYSQL_DB_HOST', 'localhost'))
MYSQL_USER      = config.get('db_user', os.getenv('MYSQL_DB_USER', ''))
MYSQL_PASSWORD  = config.get('db_password', os.getenv('MYSQL_DB_PASSWORD', ''))
MYSQL_DB        = config.get('db_name', os.getenv('MYSQL_DB_NAME', ''))
MYSQL_DB_PORT   = int(config.get('db_port', os.getenv('MYSQL_DB_PORT', 3306)))
SESSION_STRING  = os.getenv("USER_SESSION_STRING")
BOT_MODE        = os.getenv("BOT_MODE", "polling").lower()
WEBHOOK_SECRET  = os.getenv("WEBHOOK_SECRET", "")  
WEBHOOK_PATH    = os.getenv("WEBHOOK_PATH", "/")       
WEBHOOK_HOST    = os.getenv("WEBHOOK_HOST")  # 确保设置为你的域名或 IP                                   
USER_SESSION    = str(API_ID) + 'session_name'  # 确保与上传的会话文件名匹配

# ================= 2. 初始化 MySQL 连接 =================
mysql_config = {
    'host'      : MYSQL_HOST,
    'user'      : MYSQL_USER,
    'password'  : MYSQL_PASSWORD,
    'database'  : MYSQL_DB,
    "port"      : MYSQL_DB_PORT,
    'charset'   : 'utf8mb4',
    'autocommit': True
}
db = pymysql.connect(**mysql_config)
cursor = db.cursor()

lz_var_start_time = time.time()
lz_var_cold_start_flag = True

# file_unique_id 通常是 base64 编码短字串，长度 20~35，字母+数字组成
file_unique_id_pattern = re.compile(r'^[A-Za-z0-9_-]{12,64}$')
# doc_id 是整数，通常为 Telegram 64-bit ID
doc_id_pattern = re.compile(r'^\d{10,20}$')


async def heartbeat():
    while True:
        print("💓 Alive (Aiogram polling still running)")
        try:
            db.ping(reconnect=True)
            print("✅ MySQL 连接正常")
        except Exception as e:
            print(f"⚠️ MySQL 保活失败：{e}")
        await asyncio.sleep(600)

async def health(request):
    uptime = time.time() - lz_var_start_time
    if lz_var_cold_start_flag or uptime < 10:
        return web.Response(text="⏳ Bot 正在唤醒，请稍候...", status=503)
    return web.Response(text="✅ Bot 正常运行", status=200)


async def keep_alive_ping():
    url = f"{WEBHOOK_HOST}{WEBHOOK_PATH}" if BOT_MODE == "webhook" else f"{WEBHOOK_HOST}/"
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    print(f"🌐 Keep-alive ping {url} status {resp.status}")
        except Exception as e:
            print(f"⚠️ Keep-alive ping failed: {e}")
        await asyncio.sleep(300)  # 每 5 分鐘 ping 一次



async def on_startup(bot: Bot):
    webhook_url = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
    print(f"🔗 設定 Telegram webhook 為：{webhook_url}")
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(webhook_url)
    lz_var_cold_start_flag = False  # 启动完成





# ================= 7. 初始化 Telethon 客户端 =================

if SESSION_STRING:
    user_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    print("【Telethon】使用 StringSession 登录。",flush=True)
else:
    user_client = TelegramClient(USER_SESSION, API_ID, API_HASH)









# ================= H1. 私聊 Message 文字处理：人类账号 =================
@user_client.on(events.NewMessage(incoming=True))
async def handle_user_private_text(event):
    await media_utils.handle_user_private_text(event)
    return

# ================= H2-1. 私聊 Media 媒体处理：人类账号 =================
@user_client.on(events.NewMessage(incoming=True))
async def handle_user_private_media(event):
    await media_utils.handle_user_private_media(event)
    return

# ================= H3-1. 群组媒体处理：人类账号 =================
@user_client.on(events.NewMessage(chats=TARGET_GROUP_ID, incoming=True))
async def handle_user_group_media(event):
    await media_utils.handle_user_group_media(event)
    return

bot_client = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()

media_utils = MediaUtils(
    db=db,
    bot_client=bot_client,
    user_client=user_client,
    lz_var_start_time=lz_var_start_time,
    config=config,
)

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
   

# ================= 14. 启动两个客户端 =================
async def main():
# 10.1 Telethon “人类账号” 登录

    task_heartbeat = asyncio.create_task(heartbeat())

    await user_client.start(PHONE_NUMBER)
    print("【Telethon】人类账号 已启动。",flush=True)

    await media_utils.set_bot_info()


    print(f'你的用户名: {media_utils.man_username} / {media_utils.bot_username}',flush=True)
    print(f'你的ID: {media_utils.man_id} / {media_utils.bot_id}',flush=True)

    # 10.2 并行运行 Telethon 与 Aiogram
    task_telethon = asyncio.create_task(user_client.run_until_disconnected())

    if BOT_MODE == "webhook":
        dp.startup.register(on_startup)
        print("🚀 啟動 Webhook 模式")

        app = web.Application()
        app.router.add_get("/", health)  # ✅ 健康检查路由

        SimpleRequestHandler(dispatcher=dp, bot=bot_client).register(app, path=WEBHOOK_PATH)
        setup_application(app, dp, bot=bot_client)

        task_keep_alive = asyncio.create_task(keep_alive_ping())

        # ✅ Render 环境用 PORT，否则本地用 8080
        port = int(os.environ.get("PORT", 8080))
        await web._run_app(app, host="0.0.0.0", port=port)
    else:
        print("【Aiogram】Bot（纯 Bot-API） 已启动，监听私聊＋群组媒体。",flush=True)
        await dp.start_polling(bot_client)  # Aiogram 轮询

    

    # 理论上 Aiogram 轮询不会退出，若退出则让 Telethon 同样停止
    task_telethon.cancel()

if __name__ == "__main__":
    asyncio.run(main())

