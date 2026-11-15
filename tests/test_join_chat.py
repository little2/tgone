from unittest.mock import AsyncMock

import pytest
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.chatlists import (
    CheckChatlistInviteRequest,
    JoinChatlistInviteRequest,
)
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


@pytest.mark.asyncio
async def test_join_chat_supports_chatlist_invite():
    operator = _operator_with_client()
    peer_refs = [object(), object()]
    input_peers = [object(), object()]
    invite = type("Invite", (), {"peers": peer_refs})()
    operator.client.side_effect = [invite, "joined-list"]
    operator.client.get_input_entity.side_effect = input_peers

    result = await operator.join_chat("https://t.me/addlist/hv_WjtuvpvcyMmNl")

    assert result == "joined-list"
    check_request = operator.client.await_args_list[0].args[0]
    join_request = operator.client.await_args_list[1].args[0]
    assert isinstance(check_request, CheckChatlistInviteRequest)
    assert check_request.slug == "hv_WjtuvpvcyMmNl"
    assert isinstance(join_request, JoinChatlistInviteRequest)
    assert join_request.slug == "hv_WjtuvpvcyMmNl"
    assert join_request.peers == input_peers
    assert operator.client.get_input_entity.await_count == 2


@pytest.mark.asyncio
async def test_join_chat_skips_chatlist_when_nothing_is_missing():
    operator = _operator_with_client()
    invite = type("Invite", (), {"missing_peers": []})()
    operator.client.side_effect = [invite]

    result = await operator.join_chat("https://t.me/addlist/already_joined")

    assert result is invite
    assert operator.client.await_count == 1
    operator.client.get_input_entity.assert_not_awaited()
