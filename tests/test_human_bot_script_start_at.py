from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from human_bot_operator import HumanBotOperator


@pytest.mark.asyncio
@pytest.mark.parametrize("start_offset", [None, -60, 3600])
async def test_chat_script_normalizes_start_at_after_resolving_chat(monkeypatch, start_offset):
    resolved_at = None
    original_start_at = (
        None if start_offset is None else
        (datetime.now(HumanBotOperator.DEFAULT_TIMEZONE)
         + timedelta(seconds=start_offset)).isoformat()
    )

    class FakeClient:
        async def send_message(self, *args, **kwargs):
            return SimpleNamespace(id=1)

    class FakeOperator:
        client = FakeClient()

        async def join_chat(self, invite_link):
            return None

        async def simulate_ctrl_press(self):
            return None

        async def _resolve_input_entity(self, chat_id):
            nonlocal resolved_at
            resolved_at = datetime.now(HumanBotOperator.DEFAULT_TIMEZONE)
            return "chat"

        async def disconnect(self):
            return None

    operator = FakeOperator()

    async def fake_login(cls, sender_type, credentials):
        return operator

    async def skip_sleep(target_time):
        return None

    monkeypatch.setattr(
        HumanBotOperator,
        "_login_script_account",
        classmethod(fake_login),
    )
    monkeypatch.setattr(HumanBotOperator, "_sleep_until", staticmethod(skip_sleep))

    script = {
        "version": "1.0",
        "script": {
            "script_id": "test",
            "title": "test",
            "start_at": original_start_at,
        },
        "participants": [
            {
                "actor_id": "a1",
                "name": "test",
                "sender_type": "user",
                "sender_id": "a1",
            }
        ],
        "messages": [
            {
                "message_id": "m1",
                "after_start": 0,
                "actor_id": "a1",
                "reply_to": None,
                "typing_duration": 0,
                "content": {"text": "hello", "parse_mode": None},
            }
        ],
    }

    await HumanBotOperator.run_chat_script(
        script_json=script,
        chat_id=123,
        account_configs={"a1": {}},
    )

    start_at = datetime.fromisoformat(script["script"]["start_at"])
    assert resolved_at is not None
    if start_offset is None or start_offset < 0:
        assert start_at >= resolved_at + timedelta(seconds=30)
        assert start_at <= datetime.now(HumanBotOperator.DEFAULT_TIMEZONE) + timedelta(seconds=30)
    else:
        assert script["script"]["start_at"] == original_start_at
