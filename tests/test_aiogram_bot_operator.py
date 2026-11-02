import asyncio
from types import SimpleNamespace

import pytest

from aiogram_bot_operator import AiogramBotOperator


@pytest.mark.asyncio
async def test_media_worker_survives_failure_notification_error(
    monkeypatch, capsys
):
    operator = object.__new__(AiogramBotOperator)
    operator.media_forward_queue = asyncio.Queue()

    async def fail_send(*_args):
        raise Exception("Telegram server says - Bad Request: chat not found")

    async def fail_in_thread(function, *args):
        assert function.__name__ == "_download_from_api"
        assert args == ({"text": "媒体传送失败"},)
        raise RuntimeError("通知服务不可用")

    operator._send_file = fail_send
    monkeypatch.setattr(asyncio, "to_thread", fail_in_thread)

    worker = asyncio.create_task(operator._forward_media_worker())
    await operator.media_forward_queue.put(
        (SimpleNamespace(message_id=123), -1001, "caption", False)
    )
    await asyncio.wait_for(operator.media_forward_queue.join(), timeout=1)

    assert not worker.done()
    assert "媒体传送失败通知发送失败：通知服务不可用" in capsys.readouterr().out

    worker.cancel()
    with pytest.raises(asyncio.CancelledError):
        await worker
