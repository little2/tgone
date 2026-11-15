import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call

import pytest

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


def test_run_main_loop_waits_one_minute_before_next_run(monkeypatch):
    run_count = 0

    async def fake_main():
        nonlocal run_count
        run_count += 1
        if run_count == 2:
            raise asyncio.CancelledError

    sleep = AsyncMock()
    monkeypatch.setattr(userbot, "main", fake_main)
    monkeypatch.setattr(asyncio, "sleep", sleep)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(userbot.run_main_loop())

    assert run_count == 2
    sleep.assert_awaited_once_with(60)


def test_run_for_fetch_mode_repeats_only_in_patrol_mode(monkeypatch):
    main = AsyncMock()
    main_loop = AsyncMock()
    monkeypatch.setattr(userbot, "main", main)
    monkeypatch.setattr(userbot, "run_main_loop", main_loop)

    monkeypatch.setattr(userbot, "FETCH_MODE", "patrol")
    asyncio.run(userbot.run_for_fetch_mode())

    main_loop.assert_awaited_once_with(7000)
    main.assert_not_awaited()


def test_run_for_fetch_mode_runs_once_outside_ai_mode(monkeypatch):
    main = AsyncMock()
    main_loop = AsyncMock()
    monkeypatch.setattr(userbot, "main", main)
    monkeypatch.setattr(userbot, "run_main_loop", main_loop)
    monkeypatch.setattr(userbot, "FETCH_MODE", "render")

    asyncio.run(userbot.run_for_fetch_mode())

    main.assert_awaited_once_with()
    main_loop.assert_not_awaited()


def test_initialize_bbt_operator_sets_shared_operator(monkeypatch):
    bbt_operator = SimpleNamespace()
    login = AsyncMock(return_value=bbt_operator)
    set_bbt = AsyncMock()
    monkeypatch.setattr(userbot, "BBT_TOKEN", "token")
    monkeypatch.setattr(userbot, "API_ID", 123)
    monkeypatch.setattr(userbot, "API_HASH", "hash")
    monkeypatch.setattr(userbot.HumanBotOperator, "login_with_bot_token", login)
    monkeypatch.setattr(userbot.HumanBotOperator, "set_bbt_bot", set_bbt)

    result = asyncio.run(userbot._initialize_bbt_operator())

    assert result is bbt_operator
    login.assert_awaited_once_with(
        bot_token="token",
        api_id=123,
        api_hash="hash",
    )
    assert set_bbt.await_args_list == [call(None), call(bbt_operator)]
