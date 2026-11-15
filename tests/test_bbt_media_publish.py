import asyncio
import io
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import quote

from human_bot_operator import HumanBotOperator


def test_send_media_to_bbt_channel_includes_caption_and_two_buttons(monkeypatch):
    source_client = SimpleNamespace(download_media=AsyncMock())
    bbt_client = SimpleNamespace(
        get_me=AsyncMock(return_value=SimpleNamespace(username="want_bot")),
        send_file=AsyncMock(return_value="sent"),
    )
    monkeypatch.setattr(
        HumanBotOperator,
        "BBT_OPERATOR",
        SimpleNamespace(client=bbt_client),
    )
    monkeypatch.setattr(HumanBotOperator, "BJD_CODE_BOT_NAME", "@code_bot")
    media = object()
    message = SimpleNamespace(id=12, media=media)
    code = "🧟‍♀️🤪↖️🙍💊🌾🐡🤔"

    result = asyncio.run(
        HumanBotOperator._send_media_to_bbt_channel(
            source_client,
            message,
            "媒体说明",
            code,
        )
    )

    assert result == "sent"
    send_call = bbt_client.send_file.await_args
    assert send_call.args == (-1004482706977, media)
    assert send_call.kwargs["caption"] == "媒体说明"
    assert send_call.kwargs["parse_mode"] is None
    buttons = send_call.kwargs["buttons"][0]
    assert [button.text for button in buttons] == ["去获取", "我想要"]
    encoded_code = quote(code, safe="")
    assert buttons[0].url == f"https://t.me/code_bot?text={encoded_code}"
    assert buttons[1].url == f"https://t.me/want_bot?text={encoded_code}"
    source_client.download_media.assert_not_awaited()


def test_send_media_to_bbt_channel_downloads_when_media_reference_fails(monkeypatch):
    async def download_media(_message, *, file):
        assert isinstance(file, io.BytesIO)
        file.write(b"media-content")
        return file

    source_client = SimpleNamespace(download_media=AsyncMock(side_effect=download_media))
    bbt_client = SimpleNamespace(
        get_me=AsyncMock(return_value=SimpleNamespace(username="want_bot")),
        send_file=AsyncMock(
            side_effect=[RuntimeError("invalid file reference"), "uploaded"]
        ),
    )
    monkeypatch.setattr(
        HumanBotOperator,
        "BBT_OPERATOR",
        SimpleNamespace(client=bbt_client),
    )
    monkeypatch.setattr(HumanBotOperator, "BJD_CODE_BOT_NAME", "code_bot")
    message = SimpleNamespace(
        id=13,
        media=object(),
        file=SimpleNamespace(name="video.mp4", ext=".mp4"),
    )

    result = asyncio.run(
        HumanBotOperator._send_media_to_bbt_channel(
            source_client,
            message,
            "说明",
            "ABCDEFGH",
        )
    )

    assert result == "uploaded"
    source_client.download_media.assert_awaited_once()
    uploaded_file = bbt_client.send_file.await_args_list[1].args[1]
    assert isinstance(uploaded_file, io.BytesIO)
    assert uploaded_file.name == "video.mp4"
    assert uploaded_file.getvalue() == b"media-content"
