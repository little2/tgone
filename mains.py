import tracemalloc
tracemalloc.start()

import os
import base64
import asyncio
import json
import time
from dotenv import load_dotenv
import aiohttp
import aiomysql
from telethon.sessions import StringSession
from telethon import TelegramClient, events

# Aiogram 相关
from aiogram import F, Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import ContentType
from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

import re

from us import MediaUtils

# ================= 1. 载入 .env 中的环境变量 =================
# 加载环境变量
if not os.getenv('GITHUB_ACTIONS'):
    load_dotenv(dotenv_path='.24690454.queue.env')

config = {}
# 嘗試載入 JSON 並合併參數
try:
    configuration_json = json.loads(os.getenv('CONFIGURATION', '') or '{}')
    if isinstance(configuration_json, dict):
        config.update(configuration_json)
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
WEBHOOK_HOST    = os.getenv("WEBHOOK_HOST")
USER_SESSION    = str(API_ID) + 'session_name'

# ================= 2. 初始化 aiomysql 连接池 =================
mysql_pool: aiomysql.Pool | None = None

async def init_mysql_pool():
    global mysql_pool
    if mysql_pool and not mysql_pool.closed:
        return mysql_pool
    mysql_pool = await aiomysql.create_pool(
        host=MYSQL_HOST,
        port=MYSQL_DB_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        db=MYSQL_DB,
        charset='utf8mb4',
        autocommit=True,
        minsize=1,
        maxsize=10
    )
    print("✅ aiomysql pool 已建立")
    return mysql_pool

lz_var_start_time = time.time()
lz_var_cold_start_flag = True

# file_unique_id 通常是 base64 编码短字串，长度 20~35，字母+数字组成
file_unique_id_pattern = re.compile(r'^[A-Za-z0-9_-]{12,64}$')
# doc_id 是整数，通常为 Telegram 64-bit ID
doc_id_pattern = re.compile(r'^\d{10,20}$')


async def heartbeat():
    global mysql_pool
    while True:
        print("💓 Alive (Aiogram polling still running)")
        try:
            await init_mysql_pool()
            async with mysql_pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT 1")
                    await cur.fetchone()
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
        await asyncio.sleep(300)

async def on_startup(bot: Bot):
    webhook_url = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
    print(f"🔗 設定 Telegram webhook 為：{webhook_url}")
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(webhook_url)
    global lz_var_cold_start_flag
    lz_var_cold_start_flag = False  # 启动完成

# ================= 7. 初始化 Telethon 客户端 =================
if SESSION_STRING:
    user_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    print("【Telethon】使用 StringSession 登录。", flush=True)
else:
    user_client = TelegramClient(USER_SESSION, API_ID, API_HASH)

# Bot (Aiogram)
bot_client = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()

# media_utils 实例在 init_mysql_pool 之后创建（传入 pool）
media_utils: MediaUtils | None = None

# ================= H1/H2/H3. Telethon 处理 =================
@user_client.on(events.NewMessage(incoming=True))
async def handle_user_private_text(event):
    await media_utils.handle_user_private_text(event)
    return

#
'''
TODO
目前奇怪的点是在于 AQADnAtrGzk56FR- 传给人型机器人后，再转 file_unqiuee_id 就变成 AQADnAtrGzk56FR9
需要还原一下整个流程 
'''
#


@user_client.on(events.NewMessage(incoming=True))
async def handle_user_private_media(event):
    await media_utils.handle_user_private_media(event)
    return

@user_client.on(events.NewMessage(chats=TARGET_GROUP_ID, incoming=True))
async def handle_user_group_media(event):
    await media_utils.handle_user_group_media(event)
    return

# ================= Aiogram 处理 =================
@dp.message(F.chat.type == "private", F.content_type.in_({ContentType.TEXT}))
async def aiogram_handle_private_text(message: types.Message):
    await media_utils.aiogram_handle_private_text(message)
    return

@dp.message(F.chat.type == "private", F.content_type.in_({ContentType.PHOTO, ContentType.DOCUMENT, ContentType.VIDEO, ContentType.ANIMATION}))
async def aiogram_handle_private_media(message: types.Message):
    await media_utils.aiogram_handle_private_media(message)
    return

@dp.message(F.chat.id == TARGET_GROUP_ID, F.content_type.in_({ContentType.PHOTO, ContentType.DOCUMENT, ContentType.VIDEO, ContentType.ANIMATION}))
async def aiogram_handle_group_media(message: types.Message):
    await media_utils.aiogram_handle_group_media(message)
    return

# ================= 14. 启动两个客户端 =================
async def main():
    global media_utils

    # 2.1 init MySQL pool
    pool = await init_mysql_pool()

    # 10.1 Telethon “人类账号” 登录
    task_heartbeat = asyncio.create_task(heartbeat())

    await user_client.start(PHONE_NUMBER)
    print("【Telethon】人类账号 已启动。", flush=True)

    # 2.2 init MediaUtils（传入 pool 而非同步连接）
    media_utils = MediaUtils(
        pool=pool,
        bot_client=bot_client,
        user_client=user_client,
        lz_var_start_time=lz_var_start_time,
        config=config,
    )

    await media_utils.set_bot_info()

    print(f'你的用户名: {media_utils.man_username} / {media_utils.bot_username}', flush=True)
    print(f'你的ID: {media_utils.man_id} / {media_utils.bot_id}', flush=True)

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

        port = int(os.environ.get("PORT", 8080))
        await web._run_app(app, host="0.0.0.0", port=port)
    else:
        print("【Aiogram】Bot（纯 Bot-API） 已启动，监听私聊＋群组媒体。", flush=True)
        await dp.start_polling(bot_client)

    # 理论上 Aiogram 轮询不会退出，若退出则让 Telethon 同样停止
    task_telethon.cancel()

if __name__ == "__main__":
    asyncio.run(main())
