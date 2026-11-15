import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import userbot


def test_main_skips_aiogram_when_bot_token_is_missing(monkeypatch):
    config = {"bot_token": ""}
    manager = SimpleNamespace(load_config=Mock(return_value=config))
    health_runner = SimpleNamespace(cleanup=AsyncMock())
    aiogram_operator = Mock(side_effect=AssertionError("不应建立 AiogramBotOperator"))
    telethon_runner = AsyncMock()

    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.setattr(userbot, "UserAccountManager", Mock(return_value=manager))
    monkeypatch.setattr(userbot, "configure_mysql_pool", Mock())
    monkeypatch.setattr(
        userbot,
        "_start_health_server",
        AsyncMock(return_value=(health_runner, "http://127.0.0.1:10000")),
    )
    monkeypatch.setattr(userbot, "AiogramBotOperator", aiogram_operator)
    monkeypatch.setattr(userbot, "run_telethon_bot", telethon_runner)

    asyncio.run(userbot.main())

    aiogram_operator.assert_not_called()
    telethon_runner.assert_awaited_once_with(config, configure_mysql=False)
    health_runner.cleanup.assert_awaited_once()
