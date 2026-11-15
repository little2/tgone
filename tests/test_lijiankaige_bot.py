import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, call

from lijiankaige_bot import AIBot


def make_operator(replies):
    return SimpleNamespace(
        _resolve_input_entity=AsyncMock(return_value="target"),
        capture_bot_messages=AsyncMock(side_effect=replies),
        send_random_message=AsyncMock(),
    )


def test_check_in_clicks_last_board():
    op = make_operator([[object()], [SimpleNamespace(id=1), SimpleNamespace(id=2)], []])
    asyncio.run(AIBot.check_in(op, 123))

    op._resolve_input_entity.assert_awaited_once_with("@lijiankaige_bot")
    assert op.capture_bot_messages.await_args_list == [
        call("target", "/start OQPiuIKr"),
        call("target", "📅 每日签到"),
        call("target", click_button_title="💎", message_id=2),
    ]
    op.send_random_message.assert_not_awaited()


def test_check_in_sends_random_message_when_start_has_no_reply():
    op = make_operator([[]])
    asyncio.run(AIBot.check_in(op, 123))

    op.capture_bot_messages.assert_awaited_once_with("target", "/start OQPiuIKr")
    op.send_random_message.assert_awaited_once_with(chat_id=[123])


def test_check_in_stops_when_check_in_has_no_reply():
    op = make_operator([[object()], []])
    asyncio.run(AIBot.check_in(op, 123))

    assert op.capture_bot_messages.await_count == 2
    op.send_random_message.assert_not_awaited()
