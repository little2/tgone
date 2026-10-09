"""moving_message_range 按 caption 分组、以 album 发送到 POOL_CHANNEL 的行为测试。"""

from types import SimpleNamespace

import pytest

from human_bot_operator import HumanBotOperator


class FakeMedia:
    """最小化的 media 替身，便于断言发送内容。"""

    def __init__(self, label):
        self.label = label

    def __repr__(self):
        return f"FakeMedia({self.label})"


class FakeClient:
    def __init__(self, messages):
        self.messages = messages
        self.sent = []

    async def get_entity(self, chat):
        return chat

    async def get_peer_id(self, entity):
        return entity

    async def get_input_entity(self, entity):
        return entity

    async def iter_messages(self, entity, **kwargs):
        for message in self.messages:
            yield message

    async def send_file(self, entity, file, caption=None):
        self.sent.append({"entity": entity, "file": file, "caption": caption})
        return SimpleNamespace(id=len(self.sent))


def make_message(message_id, caption, media=True):
    return SimpleNamespace(
        id=message_id,
        raw_text=caption,
        media=FakeMedia(message_id) if media else None,
    )


def build_operator(messages):
    operator = HumanBotOperator(client=FakeClient(messages))

    async def fake_upsert(source_chat_id, next_message_id):
        return None

    # 测试不碰数据库
    operator._upsert_extra_log = fake_upsert
    return operator


async def run_range(operator):
    return await operator.moving_message_range(
        chat=-1001234567890,
        start_message_id=1,
        end_message_id=len(operator.client.messages) + 1,
    )


def test_resolve_pool_channel_priority(monkeypatch):
    monkeypatch.delenv("POOL_CHANNEL", raising=False)
    monkeypatch.delenv("CONFIGURATION", raising=False)

    operator = build_operator([])
    assert operator._resolve_pool_channel() is None

    # 环境变量：纯数字自动补 -100 前缀
    monkeypatch.setenv("POOL_CHANNEL", "12345")
    assert operator._resolve_pool_channel() == -10012345

    # CONFIGURATION.pool_channel 优先于环境变量
    monkeypatch.setenv("CONFIGURATION", '{"pool_channel": "-100999"}')
    assert operator._resolve_pool_channel() == -100999

    # 类常量优先级最高
    monkeypatch.setattr(HumanBotOperator, "POOL_CHANNEL", "@pool_channel")
    assert operator._resolve_pool_channel() == "@pool_channel"


@pytest.mark.asyncio
async def test_same_caption_is_queued_and_flushed_on_change(monkeypatch):
    monkeypatch.setenv("POOL_CHANNEL", "12345")
    monkeypatch.delenv("CONFIGURATION", raising=False)
    messages = [
        make_message(1, "同一段说明"),
        make_message(2, "纯文字消息", media=False),
        make_message(3, "同一段说明"),
        make_message(4, "另一段说明"),
    ]
    operator = build_operator(messages)

    printed = await run_range(operator)

    assert printed == 4
    # caption 变化时，把之前 queue 里的媒体用 album 发出
    assert len(operator.client.sent) == 1
    sent = operator.client.sent[0]
    # 发送目标是 POOL_CHANNEL（"12345" → -10012345），不是来源群
    assert sent["entity"] == -10012345
    assert sent["caption"] == "同一段说明"
    assert isinstance(sent["file"], list)
    assert [item.label for item in sent["file"]] == [1, 3]
    # 新 caption 的媒体留在 queue 中等待下一次分组
    assert operator._pool_last_caption == "另一段说明"
    assert [message.id for message in operator._pool_media_queue] == [4]


@pytest.mark.asyncio
async def test_queue_flushes_after_album_max_size(monkeypatch):
    monkeypatch.setenv("POOL_CHANNEL", "12345")
    monkeypatch.delenv("CONFIGURATION", raising=False)
    messages = [make_message(i, "同一 caption") for i in range(1, 12)]
    operator = build_operator(messages)

    await run_range(operator)

    # 攒满 10 条立刻以 album 发出
    assert len(operator.client.sent) == 1
    assert len(operator.client.sent[0]["file"]) == 10
    assert operator.client.sent[0]["caption"] == "同一 caption"
    assert [message.id for message in operator._pool_media_queue] == [11]


@pytest.mark.asyncio
async def test_single_media_is_not_sent_as_album(monkeypatch):
    monkeypatch.setenv("POOL_CHANNEL", "12345")
    monkeypatch.delenv("CONFIGURATION", raising=False)
    messages = [make_message(1, "caption A"), make_message(2, "caption B")]
    operator = build_operator(messages)

    await run_range(operator)

    assert len(operator.client.sent) == 1
    sent = operator.client.sent[0]
    assert not isinstance(sent["file"], list)
    assert sent["file"].label == 1
    assert sent["caption"] == "caption A"
    assert [message.id for message in operator._pool_media_queue] == [2]


@pytest.mark.asyncio
async def test_missing_pool_channel_warns_and_skips(monkeypatch, capsys):
    monkeypatch.delenv("POOL_CHANNEL", raising=False)
    monkeypatch.delenv("CONFIGURATION", raising=False)
    messages = [make_message(1, "caption A"), make_message(2, "caption B")]
    operator = build_operator(messages)

    printed = await run_range(operator)

    assert printed == 2
    assert operator.client.sent == []
    assert "POOL_CHANNEL 未配置" in capsys.readouterr().out
    # 未配置时丢弃旧队列，新 caption 的媒体仍在 queue 中
    assert [message.id for message in operator._pool_media_queue] == [2]


@pytest.mark.asyncio
async def test_send_failure_is_logged_and_scan_continues(monkeypatch, capsys):
    monkeypatch.setenv("POOL_CHANNEL", "12345")
    monkeypatch.delenv("CONFIGURATION", raising=False)
    messages = [make_message(1, "caption A"), make_message(2, "caption B")]
    operator = build_operator(messages)

    async def failing_send(entity, file, caption=None):
        raise RuntimeError("boom")

    operator.client.send_file = failing_send

    printed = await run_range(operator)

    assert printed == 2
    assert "发送 album 失败" in capsys.readouterr().out
    assert [message.id for message in operator._pool_media_queue] == [2]
