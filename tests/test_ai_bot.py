import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, call

import pytest

from ai_bot import AIBot


@pytest.mark.parametrize(
    ("question", "answer"),
    [
        ("2 * 3 = ?", "6"),
        ("10 + 5 = ?", "15"),
        ("9 - 12 = ?", "-3"),
        ("8 ÷ 2 = ?", "4"),
        ("3 × 7 = ?", "21"),
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
        call("target", "/start 9uiZrIA2lj3qGSK"),
        call("target", "/qd"),
        call("target", click_button_title="6", message_id=88),
    ]
