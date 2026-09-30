import pytest

from captcha_bot_operator import CaptchaBotOperator
from human_bot_operator import HumanBotOperator


@pytest.mark.asyncio
async def test_human_bot_operator_handle_captcha_returns_delegate_result(monkeypatch):
    bot = object.__new__(HumanBotOperator)
    bot.client = object()

    async def fake_handle_captcha(self, response, user_id=None, reward_bot_name=None):
        assert response == "captcha"
        assert user_id == 123
        assert reward_bot_name == "reward"
        return True

    monkeypatch.setattr(CaptchaBotOperator, "handle_captcha", fake_handle_captcha)

    result = await bot.handle_captcha(response="captcha", user_id=123, reward_bot_name="reward")

    assert result is True
