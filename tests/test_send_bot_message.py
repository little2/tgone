import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from human_bot_operator import HumanBotOperator
from tgone_mysql import MySQLPool


@pytest.mark.parametrize('bot_ids,operator_key', [({0: '8064370365'}, 0), ({8064370365}, 8064370365)])
def test_send_as_selected_account_and_record(monkeypatch, bot_ids, operator_key):
    row = {'id': 5, 'bot_id': 8064370365, 'text': '早安☀️', 'parse_mode': 'html', 'leadtime': 7}
    fetch = AsyncMock(return_value=row)
    update = AsyncMock(return_value=True)
    send = AsyncMock(return_value=SimpleNamespace(id=123))
    wrong_send = AsyncMock()
    monkeypatch.setattr(MySQLPool, 'fetchone', fetch)
    monkeypatch.setattr(MySQLPool, 'execute', update)
    monkeypatch.setattr('human_bot_operator.time.time', lambda: 1794042000)
    operators = {operator_key: SimpleNamespace(client=SimpleNamespace(send_message=send), _resolve_input_entity=AsyncMock(return_value="resolved_chat")),
                 99: SimpleNamespace(client=SimpleNamespace(send_message=wrong_send))}
    assert asyncio.run(HumanBotOperator.send_bot_message(operators, bot_ids)) == 7
    send.assert_awaited_once_with('resolved_chat', '早安☀️', parse_mode='html')
    wrong_send.assert_not_awaited()
    assert update.await_args.args[1] == (1794042000, -1003999277542, 123, 5)
    assert '`act_send_timestamp` IS NULL' in fetch.await_args.args[0]
    assert 'LIMIT 1' in fetch.await_args.args[0]


@pytest.mark.parametrize('row', [None, {'id': 1, 'bot_id': 8064370365, 'text': '早'}])
def test_missing_row_or_operator_does_not_record(monkeypatch, row):
    monkeypatch.setattr(MySQLPool, 'fetchone', AsyncMock(return_value=row))
    update = AsyncMock()
    monkeypatch.setattr(MySQLPool, 'execute', update)
    assert asyncio.run(HumanBotOperator.send_bot_message({}, {0: 8064370365})) == 0
    update.assert_not_awaited()


def test_send_failure_does_not_mark_sent(monkeypatch):
    monkeypatch.setattr(MySQLPool, 'fetchone', AsyncMock(return_value={'id': 1, 'bot_id': 42, 'text': '早'}))
    update = AsyncMock()
    monkeypatch.setattr(MySQLPool, 'execute', update)
    op = SimpleNamespace(client=SimpleNamespace(send_message=AsyncMock(side_effect=RuntimeError('send failed'))), _resolve_input_entity=AsyncMock(return_value='resolved_chat'))
    with pytest.raises(RuntimeError, match='send failed'):
        asyncio.run(HumanBotOperator.send_bot_message({0: op}, {0: 42}))
    update.assert_not_awaited()


def test_empty_ids_skip_database(monkeypatch):
    fetch = AsyncMock()
    monkeypatch.setattr(MySQLPool, 'fetchone', fetch)
    assert asyncio.run(HumanBotOperator.send_bot_message({}, {})) == 0
    fetch.assert_not_awaited()


def test_record_failure_reports_sent_message_without_resending(monkeypatch, capsys):
    monkeypatch.setattr(MySQLPool, 'fetchone', AsyncMock(return_value={'id': 1, 'bot_id': 42, 'text': '早'}))
    monkeypatch.setattr(MySQLPool, 'execute', AsyncMock(side_effect=RuntimeError('database down')))
    send = AsyncMock(return_value=SimpleNamespace(id=123))
    op = SimpleNamespace(client=SimpleNamespace(send_message=send), _resolve_input_entity=AsyncMock(return_value="resolved_chat"))
    assert asyncio.run(HumanBotOperator.send_bot_message({0: op}, {0: 42})) == 0
    send.assert_awaited_once()
    assert 'Telegram 消息 ID=123' in capsys.readouterr().out


def test_missing_entity_keeps_message_pending(monkeypatch, capsys):
    monkeypatch.setattr(MySQLPool, 'fetchone', AsyncMock(return_value={'id': 1, 'bot_id': 42, 'text': '早'}))
    update = AsyncMock()
    monkeypatch.setattr(MySQLPool, 'execute', update)
    send = AsyncMock()
    op = SimpleNamespace(client=SimpleNamespace(send_message=send),
                         _resolve_input_entity=AsyncMock(side_effect=ValueError('not joined')))
    assert asyncio.run(HumanBotOperator.send_bot_message({0: op}, {0: 42})) == 0
    send.assert_not_awaited()
    update.assert_not_awaited()
    assert '保留为未发送' in capsys.readouterr().out


def test_refresh_dialogs_before_sending(monkeypatch):
    from telethon.tl.types import InputPeerChannel
    entity = SimpleNamespace(id=3999277542)
    resolved = InputPeerChannel(3999277542, 123456)
    client = SimpleNamespace(
        get_input_entity=AsyncMock(side_effect=[ValueError('cache missing'), resolved]),
        get_dialogs=AsyncMock(return_value=[SimpleNamespace(entity=entity)]),
        get_peer_id=AsyncMock(return_value=-1003999277542),
        send_message=AsyncMock(return_value=SimpleNamespace(id=123)),
    )
    op = object.__new__(HumanBotOperator)
    op.client = client
    monkeypatch.setattr(MySQLPool, 'fetchone', AsyncMock(return_value={
        'id': 1, 'bot_id': 42, 'text': '早', 'leadtime': 5,
    }))
    monkeypatch.setattr(MySQLPool, 'execute', AsyncMock(return_value=True))
    assert asyncio.run(HumanBotOperator.send_bot_message({0: op}, {0: 42})) == 5
    client.get_dialogs.assert_awaited_once()
    client.send_message.assert_awaited_once_with(resolved, '早', parse_mode='html')
