import asyncio

import pytest

from human_bot_operator import HumanBotOperator


class FakeButton:
    def __init__(self, text, on_click=None):
        self.text = text
        self._on_click = on_click

    async def click(self):
        if self._on_click is not None:
            await self._on_click()
        return None


class FakeMessage:
    """最小化的 Telethon Message 替身，只提供擷取流程需要的属性。"""

    def __init__(self, message_id, text, rows=None):
        self.id = message_id
        self.message = text
        self.raw_text = text
        self.media = None
        self._rows = rows or []

    async def get_buttons(self):
        return self._rows


class FakeEvent:
    def __init__(self, message):
        self.message = message


def _build_operator(
    *,
    send_replies=None,
    auto_replies=None,
    click_replies=None,
    stored_messages=None,
    target="target-entity",
):
    """建立一個不連線的 HumanBotOperator，並記錄事件處理器與已發送訊息。

    send_replies:    呼叫 send_message 後機器人立即輸出的消息清單。
    auto_replies:    註冊事件後由機器人主動輸出的消息（模擬未發送觸發時）。
    click_replies:   點擊按鈕後機器人接著輸出的消息清單。
    stored_messages: 可透過 get_messages(ids=...) 取得的既有消息，
                     用於測試以 message_id 指定按鈕所在的消息。
    """
    operator = object.__new__(HumanBotOperator)
    operator.show_response = False

    handlers = []
    removed = []
    sent = []

    async def emit_event(event):
        seen = set()
        for callback, _handler_event in list(handlers):
            if id(callback) in seen:
                continue
            seen.add(id(callback))
            await callback(event)

    async def on_click():
        await emit_replies(click_replies)

    clicks = []

    def build_rows(titles, on_click_handler=None):
        buttons = []
        for title in titles:
            def make_click(label=title, handler=on_click_handler):
                async def _click():
                    clicks.append(label)
                    if handler is not None:
                        await handler()
                return _click

            buttons.append(FakeButton(title, on_click=make_click()))
        return [buttons] if buttons else []

    async def emit_replies(replies):
        for spec in replies or []:
            message = FakeMessage(
                spec["id"],
                spec["text"],
                build_rows(spec.get("buttons", []), on_click),
            )
            await emit_event(FakeEvent(message))

    stored = {}
    for spec in stored_messages or []:
        message = FakeMessage(spec["id"], spec["text"], [])
        mutation = spec.get("click_mutation")

        async def mutate(message=message, mutation=mutation):
            # 只改写消息内容、不推送任何事件，模拟「机器人编辑了但没推事件」。
            message.message = mutation["text"]
            message.raw_text = mutation["text"]
            message._rows = build_rows(mutation.get("buttons", []), on_click)

        message._rows = build_rows(
            spec.get("buttons", []),
            mutate if mutation is not None else on_click,
        )
        stored[spec["id"]] = message

    class FakeClient:
        def __init__(self):
            self._auto_scheduled = False

        async def send_message(self, target_entity, text):
            assert target_entity == target
            sent.append(text)
            await emit_replies(send_replies)
            return FakeMessage(1, text)

        async def get_messages(self, target_entity, ids=None):
            assert target_entity == target
            if isinstance(ids, (list, tuple)):
                return [stored.get(message_id) for message_id in ids]
            return stored.get(ids)

        def add_event_handler(self, callback, event):
            handlers.append((callback, event))
            if not self._auto_scheduled:
                self._auto_scheduled = True
                asyncio.ensure_future(emit_replies(auto_replies))

        def remove_event_handler(self, callback, event):
            removed.append((callback, event))
            for item in list(handlers):
                if item[0] is callback:
                    handlers.remove(item)

    operator.client = FakeClient()

    async def fake_resolve(entity_like):
        assert entity_like == "@targetbot"
        return target

    operator._resolve_input_entity = fake_resolve
    operator._fake_clicks = clicks
    return operator, handlers, removed, sent


@pytest.mark.asyncio
async def test_capture_bot_messages_sends_and_returns_bot_output():
    operator, handlers, removed, sent = _build_operator(
        send_replies=[{"id": 1001, "text": "機器人回應內容"}]
    )

    result = await operator.capture_bot_messages(
        "@targetbot", "/start", max_messages=1
    )

    assert [m.message for m in result] == ["機器人回應內容"]
    assert sent == ["/start"]
    # 事件處理器必須被移除，避免事件泄漏。
    assert removed and handlers == []


@pytest.mark.asyncio
async def test_capture_bot_messages_stops_on_keyword_and_returns_texts():
    operator, _handlers, _removed, _sent = _build_operator(
        send_replies=[{"id": 1001, "text": "第一段"}, {"id": 1002, "text": "處理完成"}]
    )

    result = await operator.capture_bot_messages(
        "@targetbot",
        "/start",
        stop_keywords={"完成"},
        return_texts=True,
        max_messages=2,
    )

    assert result == ["第一段", "處理完成"]


@pytest.mark.asyncio
async def test_capture_bot_messages_clicks_button_then_returns_output():
    operator, _handlers, _removed, _sent = _build_operator(
        send_replies=[{"id": 1001, "text": "首頁", "buttons": ["🏆 排行榜"]}],
        click_replies=[{"id": 1002, "text": "排行榜內容"}],
    )

    result = await operator.capture_bot_messages(
        "@targetbot", "/start", click_button_title="🏆 排行榜", max_messages=2
    )

    assert [m.message for m in result] == ["首頁", "排行榜內容"]


@pytest.mark.asyncio
async def test_capture_bot_messages_clicks_without_send_text():
    # 未提供 send_text，機器人主動輸出帶按鈕的消息。
    operator, _handlers, _removed, sent = _build_operator(
        auto_replies=[{"id": 3001, "text": "首頁", "buttons": ["排行榜"]}],
        click_replies=[{"id": 3002, "text": "排行榜內容"}],
    )

    result = await operator.capture_bot_messages(
        "@targetbot", click_button_title="排行榜", max_messages=2
    )

    assert [m.message for m in result] == ["首頁", "排行榜內容"]
    assert sent == []


@pytest.mark.asyncio
async def test_capture_bot_messages_without_actions_just_waits():
    operator, _handlers, _removed, sent = _build_operator()

    result = await operator.capture_bot_messages("@targetbot", timeout=0.05)

    assert result == []
    assert sent == []


@pytest.mark.asyncio
async def test_capture_bot_messages_rejects_invalid_arguments():
    operator, _handlers, _removed, _sent = _build_operator()

    with pytest.raises(ValueError):
        await operator.capture_bot_messages("@targetbot", "   ")
    with pytest.raises(ValueError):
        await operator.capture_bot_messages("@targetbot", click_button_title="  ")
    # message_id 必須與 click_button_title 搭配使用。
    with pytest.raises(ValueError):
        await operator.capture_bot_messages("@targetbot", message_id=8416)
    with pytest.raises(ValueError):
        await operator.capture_bot_messages(
            "@targetbot", click_button_title="排行榜", message_id=0
        )
    with pytest.raises(TypeError):
        await operator.capture_bot_messages(
            "@targetbot", click_button_title="排行榜", message_id="8416"
        )


@pytest.mark.asyncio
async def test_capture_bot_messages_clicks_button_by_message_id():
    # 以 message_id 指定既有消息，點擊其上符合文字的按鈕後回傳機器人反饋。
    operator, _handlers, _removed, sent = _build_operator(
        stored_messages=[
            {"id": 8416, "text": "首頁", "buttons": ["🏆 排行榜"]}
        ],
        click_replies=[{"id": 8417, "text": "排行榜內容"}],
    )

    result = await operator.capture_bot_messages(
        "@targetbot",
        click_button_title="🏆 排行榜",
        message_id=8416,
        max_messages=1,
    )

    assert [m.message for m in result] == ["排行榜內容"]
    assert sent == []


@pytest.mark.asyncio
async def test_capture_bot_messages_message_id_without_matching_button_returns_empty():
    # 指定的消息存在但沒有符合文字的按鈕時，不會點擊，等待逾時後回傳空清單。
    operator, _handlers, _removed, _sent = _build_operator(
        stored_messages=[{"id": 9001, "text": "首頁", "buttons": ["關於"]}],
    )

    result = await operator.capture_bot_messages(
        "@targetbot",
        click_button_title="排行榜",
        message_id=9001,
        timeout=0.05,
    )

    assert result == []


@pytest.mark.asyncio
async def test_capture_bot_messages_message_id_polls_when_no_event_arrives():
    # 機器人只改寫訊息內容、沒有推送事件時，靠輪詢仍要能捕捉到結果。
    operator, _handlers, _removed, _sent = _build_operator(
        stored_messages=[
            {
                "id": 5001,
                "text": "🏆 排行榜",
                "buttons": ["🆕 最新發布"],
                "click_mutation": {
                    "text": "🆕 最新發布內容",
                    "buttons": ["🔙 返回"],
                },
            }
        ],
    )

    result = await operator.capture_bot_messages(
        "@targetbot",
        click_button_title="🆕",
        message_id=5001,
        timeout=0.5,
        poll_interval=0.02,
        max_messages=1,
    )

    assert [m.message for m in result] == ["🆕 最新發布內容"]


@pytest.mark.asyncio
async def test_capture_bot_messages_message_id_no_change_returns_empty():
    # 內容完全沒變時不應重複回傳，逾時後回傳空清單。
    operator, _handlers, _removed, _sent = _build_operator(
        stored_messages=[{"id": 6001, "text": "首頁", "buttons": ["🏆 排行榜"]}],
    )

    result = await operator.capture_bot_messages(
        "@targetbot",
        click_button_title="🏆",
        message_id=6001,
        timeout=0.1,
        poll_interval=0.02,
        max_messages=1,
    )

    assert result == []


@pytest.mark.asyncio
async def test_capture_bot_messages_clicks_button_exactly_once():
    # 修正重複點擊：同一次擷取內按鈕只能被點一次。
    operator, _handlers, _removed, _sent = _build_operator(
        stored_messages=[{"id": 7001, "text": "首頁", "buttons": ["🏆 排行榜"]}],
    )

    await operator.capture_bot_messages(
        "@targetbot",
        click_button_title="🏆",
        message_id=7001,
        timeout=0.05,
        poll_interval=0.02,
        max_messages=1,
    )

    assert operator._fake_clicks == ["🏆 排行榜"]


@pytest.mark.asyncio
async def test_capture_bot_messages_rejects_invalid_poll_interval():
    operator, _handlers, _removed, _sent = _build_operator()

    with pytest.raises(ValueError):
        await operator.capture_bot_messages("@targetbot", poll_interval=0)
    with pytest.raises(TypeError):
        await operator.capture_bot_messages("@targetbot", poll_interval="2")

