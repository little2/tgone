import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, call

import pytest

from ai_bot import AIBot


@pytest.mark.parametrize(
    ("replies", "attempts", "waits"),
    [
        ([[SimpleNamespace(text="🎉 签到成功")]], 1, 0),
        ([[SimpleNamespace(text="今天已签到，请明天再来")]], 1, 0),
        ([[], [SimpleNamespace(message="今天已签到")]], 2, 1),
        ([[], [SimpleNamespace(message="签到成功")]], 2, 1),
        ([[], [], []], 3, 2),
        ([[], [], [SimpleNamespace(text="签到成功")]], 3, 2),
    ],
)
def test_gaoren_check_in_retries_until_success(monkeypatch, replies, attempts, waits):
    sleep = AsyncMock()
    monkeypatch.setattr(asyncio, "sleep", sleep)
    operator = SimpleNamespace(
        _resolve_input_entity=AsyncMock(return_value="target"),
        update_bio=AsyncMock(),
        capture_bot_messages=AsyncMock(side_effect=[[object()], *replies]),
    )

    asyncio.run(AIBot.gaoren1231211_bot(operator))

    assert operator.capture_bot_messages.await_args_list == [
        call("target", "/start ref_7154552172"),
        *[call("target", "📅 签到")] * attempts,
    ]
    assert sleep.await_args_list == [call(15), *[call(10)] * waits]


@pytest.mark.parametrize(
    ("question", "answer"),
    [
        ("2 * 3 = ?", "6"),
        ("10 + 5 = ?", "15"),
        ("9 - 12 = ?", "-3"),
        ("−4.9 − −1.2 = ?", "-3.7"),
        (
            "🤖 **人机验证**\\\n\\\n"
            "请点击下方**马赛克**查看算式，然后选出正确答案：\\\n\\\n"
            "44 − 9 = ?\\\n\\\n"
            "👆 *点一下上面的马赛克，公式才会显示出来*\\\n"
            "👇 *算完点下面的按钮选答案*",
            "35",
        ),
        ("8 ÷ 2 = ?", "4"),
        ("3 × 7 = ?", "21"),
        ("🔢 签到验证\n\n请在60秒内点击正确答案：\n\n**4.9 - 1.2 = ?**", "3.7"),
        ("0.1 + 0.2 = ?", "0.3"),
        ("1.2 × 3 = ?", "3.6"),
        ("7.5 ÷ 2.5 = ?", "3"),
        ("5 / 2 = ?", "2.5"),
        ("1.2 - 4.9 = ?", "-3.7"),
        ("-0.0 * 2 = ?", "0"),
    ],
)
def test_calculate_verification_answer(question, answer):
    assert AIBot._calculate_verification_answer(question) == answer


def test_calculate_verification_answer_uses_last_expression():
    text = "旧题：1 + 1 = ?\n请回答最后一题：\n2 * 3 = ?"

    assert AIBot._calculate_verification_answer(text) == "6"


def test_calculate_verification_answer_rejects_unknown_text():
    with pytest.raises(ValueError, match="找不到"):
        AIBot._calculate_verification_answer("请选择正确答案")


def test_calculate_verification_answer_rejects_division_by_zero():
    with pytest.raises(ValueError, match="不能除以零"):
        AIBot._calculate_verification_answer("1.2 / 0 = ?")


def test_xhgsgk_bot_clicks_calculated_check_in_answer():
    challenge = SimpleNamespace(
        id=88,
        text="🔢 签到验证\n\n请在60秒内点击正确答案：\n\n2 * 3 = ?",
    )
    operator = SimpleNamespace(
        _resolve_input_entity=AsyncMock(return_value="target"),
        join_chat=AsyncMock(),
        capture_bot_messages=AsyncMock(
            side_effect=[[], [challenge], [SimpleNamespace(text="签到成功")]]
        ),
    )

    asyncio.run(AIBot.xhgsgk_bot(operator))

    assert operator.capture_bot_messages.await_args_list == [
        call("target", "/start yoQyA2fgRxrxkgR"),
        call("target", "/qd"),
        call("target", click_button_title="6", message_id=88),
    ]


def test_xhgsgk_bot_handles_empty_reply_after_clicking_16(monkeypatch):
    registration_board = SimpleNamespace(id=100, text="请完成注册")
    wrong_answer = SimpleNamespace(message="答案错误")
    challenge = SimpleNamespace(id=200, text="2 * 3 = ?")
    replies = [[registration_board]]
    for number in range(1, 16):
        replies.extend(
            ([wrong_answer], [SimpleNamespace(id=100 + number, text="请完成注册")])
        )
    replies.extend(([], [challenge], [SimpleNamespace(text="签到成功")]))

    operator = SimpleNamespace(
        _resolve_input_entity=AsyncMock(return_value="target"),
        join_chat=AsyncMock(),
        capture_bot_messages=AsyncMock(side_effect=replies),
    )
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())

    asyncio.run(AIBot.xhgsgk_bot(operator))

    assert call("target", click_button_title="16", message_id=115) in (
        operator.capture_bot_messages.await_args_list
    )
    assert operator.capture_bot_messages.await_args_list[-2:] == [
        call("target", "/qd"),
        call("target", click_button_title="6", message_id=200),
    ]
