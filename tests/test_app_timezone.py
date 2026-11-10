from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app_timezone import APP_TIMEZONE
from human_bot_operator import HumanBotOperator
from tgone_mysql import MySQLPool


@pytest.mark.parametrize("source", [
    "2026-11-09T16:30:00+00:00",
    "2026-11-09T11:30:00-05:00",
    "2026-11-10T00:30:00+08:00",
])
def test_script_start_time_converts_offset_without_changing_instant(source):
    payload = {
        "version": "1.0",
        "script": {"script_id": "timezone", "title": "test", "start_at": source},
        "participants": [{
            "actor_id": "1", "name": "test", "sender_type": "user", "sender_id": "1",
        }],
        "messages": [],
    }
    result, start_at = HumanBotOperator._validate_chat_script(payload)
    assert start_at.isoformat() == "2026-11-10T00:30:00+08:00"
    assert start_at.timestamp() == datetime.fromisoformat(source).timestamp()
    assert result["script"]["start_at"] == start_at.isoformat()
    assert HumanBotOperator.DEFAULT_TIMEZONE is APP_TIMEZONE
    assert start_at.utcoffset() == timedelta(hours=8)


@pytest.mark.asyncio
async def test_mysql_pool_sets_timezone_on_every_new_connection(monkeypatch):
    class Pool(MySQLPool):
        _pool = None
        _config = {"host": "example", "user": "test", "db": "test"}
        _cache_ready = True

    create = AsyncMock(return_value=SimpleNamespace())
    monkeypatch.setattr("tgone_mysql.aiomysql.create_pool", create)
    await Pool._init_pool_locked()
    assert create.call_args.kwargs["init_command"] == "SET time_zone = '+08:00'"
