import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from telethon.errors import FloodWaitError, ServerError

import human_bot_operator as module


class LoginOperator(module.HumanBotOperator):
    def __init__(self, client, **kwargs):
        self.client = client


@pytest.fixture
def clients(monkeypatch, tmp_path):
    monkeypatch.setattr(module, "__file__", str(tmp_path / "operator.py"))
    created = []

    def create(*args):
        client = SimpleNamespace(start=AsyncMock(), disconnect=AsyncMock())
        created.append(client)
        return client

    factory = Mock(side_effect=create)
    monkeypatch.setattr(module, "TelegramClient", factory)
    return factory, created


@pytest.mark.asyncio
async def test_bot_login_reuses_session_path(clients):
    factory, created = clients
    await LoginOperator.login_with_bot_token("123:secret", 1, "hash")
    await LoginOperator.login_with_bot_token("123:secret", 1, "hash")
    assert factory.call_args_list[0] == factory.call_args_list[1]
    path = factory.call_args.args[0]
    assert "secret" not in path
    assert "telethon_bot_sessions" in path
    await LoginOperator.login_with_bot_token("456:other", 1, "hash")
    assert factory.call_args.args[0] != path


@pytest.mark.asyncio
async def test_flood_wait_obeys_server_delay_before_retry(clients, monkeypatch):
    factory, created = clients
    create = factory.side_effect

    def flood_once(*args):
        client = create(*args)
        if len(created) == 1:
            client.start.side_effect = FloodWaitError(request=None, capture=1799)
        return client

    factory.side_effect = flood_once

    async def wait(seconds):
        assert seconds == 1799
        assert len(created) == 1
        created[0].disconnect.assert_awaited_once()

    sleep = AsyncMock(side_effect=wait)
    monkeypatch.setattr(module.asyncio, "sleep", sleep)
    operator = await LoginOperator.login_with_bot_token("123:secret", 1, "hash")
    assert operator.client is created[1]
    sleep.assert_awaited_once_with(1799)


@pytest.mark.asyncio
@pytest.mark.parametrize("during_wait", [False, True])
async def test_bot_login_cancellation_disconnects_without_retry(
    clients, monkeypatch, during_wait
):
    factory, created = clients
    create = factory.side_effect

    def cancel_login(*args):
        client = create(*args)
        client.start.side_effect = (
            FloodWaitError(request=None, capture=1799)
            if during_wait else asyncio.CancelledError()
        )
        return client

    factory.side_effect = cancel_login
    monkeypatch.setattr(
        module.asyncio, "sleep", AsyncMock(side_effect=asyncio.CancelledError())
    )
    with pytest.raises(asyncio.CancelledError):
        await LoginOperator.login_with_bot_token("123:secret", 1, "hash")
    assert len(created) == 1
    created[0].disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_server_errors_still_have_bounded_retries(clients, monkeypatch):
    factory, created = clients
    create = factory.side_effect

    def fail_login(*args):
        client = create(*args)
        client.start.side_effect = ServerError(request=None, message="unavailable")
        return client

    factory.side_effect = fail_login
    sleep = AsyncMock()
    monkeypatch.setattr(module.asyncio, "sleep", sleep)
    with pytest.raises(ServerError):
        await LoginOperator.login_with_bot_token("123:secret", 1, "hash")
    assert len(created) == LoginOperator.TELEGRAM_LOGIN_MAX_ATTEMPTS
    assert [call.args[0] for call in sleep.await_args_list] == [2, 4, 8]
    for client in created:
        client.disconnect.assert_awaited_once()
