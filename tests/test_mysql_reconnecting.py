import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, call

import aiomysql
import pytest

from tgone_mysql import MySQLPool, reconnecting


@pytest.mark.parametrize("code", [2006, 2013])
def test_disconnect_retries_ten_times_with_increasing_delays(monkeypatch, code):
    sleep = AsyncMock()
    monkeypatch.setattr("tgone_mysql.asyncio.sleep", sleep)
    pool = SimpleNamespace(_rebuild_pool=AsyncMock())
    query = AsyncMock(side_effect=aiomysql.OperationalError(code, "disconnected"))

    with pytest.raises(aiomysql.OperationalError):
        asyncio.run(reconnecting(query)(pool, "SELECT 1"))

    assert query.await_count == 11
    assert pool._rebuild_pool.await_count == 10
    assert sleep.await_args_list == [call(i) for i in range(1, 11)]


def test_retry_returns_result_after_recovery(monkeypatch):
    sleep = AsyncMock()
    monkeypatch.setattr("tgone_mysql.asyncio.sleep", sleep)
    pool = SimpleNamespace(_rebuild_pool=AsyncMock())
    query = AsyncMock(side_effect=[aiomysql.OperationalError(2013, "lost"), {"id": 1}])

    assert asyncio.run(reconnecting(query)(pool)) == {"id": 1}
    assert query.await_count == 2
    sleep.assert_awaited_once_with(1)


def test_failed_rebuild_remains_in_retry_budget(monkeypatch):
    sleep = AsyncMock()
    monkeypatch.setattr("tgone_mysql.asyncio.sleep", sleep)
    pool = SimpleNamespace(_rebuild_pool=AsyncMock(
        side_effect=aiomysql.OperationalError(2003, "cannot connect")
    ))
    query = AsyncMock(side_effect=aiomysql.OperationalError(2013, "lost"))

    with pytest.raises(aiomysql.OperationalError) as exc:
        asyncio.run(reconnecting(query)(pool))

    assert exc.value.args[0] == 2003
    assert query.await_count == 1
    assert pool._rebuild_pool.await_count == 10
    assert sleep.await_args_list == [call(i) for i in range(1, 11)]


def test_other_sql_errors_are_not_retried(monkeypatch):
    sleep = AsyncMock()
    monkeypatch.setattr("tgone_mysql.asyncio.sleep", sleep)
    pool = SimpleNamespace(_rebuild_pool=AsyncMock())
    query = AsyncMock(side_effect=aiomysql.OperationalError(1054, "unknown column"))

    with pytest.raises(aiomysql.OperationalError):
        asyncio.run(reconnecting(query)(pool))

    query.assert_awaited_once()
    pool._rebuild_pool.assert_not_awaited()
    sleep.assert_not_awaited()


def test_rebuild_initializes_without_acquiring_lock_again(monkeypatch):
    class Pool(MySQLPool):
        _pool = None
        _lock = asyncio.Lock()

    async def initialize():
        assert Pool._lock.locked()

    initialize_mock = AsyncMock(side_effect=initialize)
    monkeypatch.setattr(Pool, "_init_pool_locked", initialize_mock)

    async def run():
        await asyncio.wait_for(Pool._rebuild_pool(), timeout=1)

    asyncio.run(run())
    initialize_mock.assert_awaited_once()
    assert not Pool._lock.locked()
