import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.users import GetFullUserRequest

from human_bot_operator import HumanBotOperator


def _operator_with_client():
    operator = object.__new__(HumanBotOperator)
    operator.client = AsyncMock()
    return operator


def test_update_bio_sends_profile_request():
    operator = _operator_with_client()
    updated_user = SimpleNamespace(id=123, username="tester")
    operator.client.side_effect = [
        updated_user,
        SimpleNamespace(full_user=SimpleNamespace(about="今天也要开心")),
    ]

    result = asyncio.run(operator.update_bio("今天也要开心"))

    update_request = operator.client.await_args_list[0].args[0]
    verify_request = operator.client.await_args_list[1].args[0]
    assert isinstance(update_request, UpdateProfileRequest)
    assert update_request.about == "今天也要开心"
    assert isinstance(verify_request, GetFullUserRequest)
    assert verify_request.id is updated_user
    assert result == "今天也要开心"


def test_update_bio_accepts_empty_string_to_clear_bio():
    operator = _operator_with_client()
    operator.client.side_effect = [
        SimpleNamespace(id=123, username=None),
        SimpleNamespace(full_user=SimpleNamespace(about=None)),
    ]

    result = asyncio.run(operator.update_bio(""))

    request = operator.client.await_args_list[0].args[0]
    assert request.about == ""
    assert result == ""


def test_update_bio_rejects_non_string_value():
    operator = _operator_with_client()

    with pytest.raises(TypeError, match="bio 必须是字符串"):
        asyncio.run(operator.update_bio(None))

    operator.client.assert_not_awaited()


def test_update_bio_raises_when_server_value_does_not_match():
    operator = _operator_with_client()
    operator.client.side_effect = [
        SimpleNamespace(id=123, username=None),
        SimpleNamespace(full_user=SimpleNamespace(about="旧简介")),
    ]

    with pytest.raises(RuntimeError, match="与设置值不一致"):
        asyncio.run(operator.update_bio("新简介"))
