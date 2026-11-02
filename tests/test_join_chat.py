from unittest.mock import AsyncMock

import pytest
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest

from human_bot_operator import HumanBotOperator


def _operator_with_client():
    operator = object.__new__(HumanBotOperator)
    operator.client = AsyncMock()
    operator.client.return_value = "joined"
    return operator


@pytest.mark.asyncio
async def test_join_chat_supports_public_tme_link():
    operator = _operator_with_client()
    entity = object()
    operator.client.get_entity.return_value = entity

    result = await operator.join_chat("https://t.me/BJDADJB")

    assert result == "joined"
    operator.client.get_entity.assert_awaited_once_with("@BJDADJB")
    request = operator.client.await_args.args[0]
    assert isinstance(request, JoinChannelRequest)
    assert request.channel is entity


@pytest.mark.asyncio
async def test_join_chat_keeps_private_invite_support():
    operator = _operator_with_client()

    result = await operator.join_chat("https://t.me/+LmR0F1WpnFQ0Y2Ix")

    assert result == "joined"
    operator.client.get_entity.assert_not_awaited()
    request = operator.client.await_args.args[0]
    assert isinstance(request, ImportChatInviteRequest)
    assert request.hash == "LmR0F1WpnFQ0Y2Ix"
