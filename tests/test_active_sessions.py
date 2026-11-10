import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch


class GetAuthorizationsRequest:
    pass


class ResetAuthorizationRequest:
    def __init__(self, hash):
        self.hash = hash


class Authorizations:
    def __init__(self, authorizations):
        self.authorizations = authorizations


def load_check_active_sessions():
    source = Path(__file__).resolve().parents[1] / "user_account_manager.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    manager = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "UserAccountManager"
    )
    function = next(
        node for node in manager.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "check_active_sessions"
    )
    namespace = {
        "datetime": datetime,
        "timedelta": timedelta,
        "APP_TIMEZONE": timezone.utc,
        "TelegramClient": Client,
        "GetAuthorizationsRequest": GetAuthorizationsRequest,
        "ResetAuthorizationRequest": ResetAuthorizationRequest,
        "Authorizations": Authorizations,
        "WHITELIST": {"trusted"},
        "BLACKLIST": {"blocked"},
        "SharedConfig": SimpleNamespace(get=Mock(return_value=123)),
    }
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), namespace)
    return namespace["check_active_sessions"]


def authorization(hash, device, age):
    return SimpleNamespace(
        hash=hash, device_model=device, platform="test", ip="test",
        date_created=datetime.now(timezone.utc) - timedelta(days=age),
    )


class Client:
    def __init__(self, authorizations, fail_hash=None):
        self.authorizations = authorizations
        self.fail_hash = fail_hash
        self.reset_hashes = []
        self.send_message = AsyncMock()

    async def __call__(self, request):
        if isinstance(request, GetAuthorizationsRequest):
            return Authorizations(self.authorizations)
        if request.hash == self.fail_hash:
            raise RuntimeError("reset failed")
        self.reset_hashes.append(request.hash)


class ActiveSessionsTests(unittest.IsolatedAsyncioTestCase):
    async def test_preserves_session_rules_and_sends_report(self):
        sessions = [
            authorization(0, "current", 30),
            authorization(1, "trusted", 30),
            authorization(2, "blocked", 1),
            authorization(3, "blocked", 30),
            authorization(-212406687192506612, "other", 30),
            authorization(4, "other", 30),
        ]
        client = Client(sessions)
        with patch("builtins.print"):
            result = await load_check_active_sessions()(None, client)
        self.assertEqual(client.reset_hashes, [3, -212406687192506612])
        self.assertEqual(
            result,
            "✅ (本身)current\n✅ (白名单)trusted\n❗️ (七天新增)blocked\n"
            "❌ (黑名单)blocked\n❌ (特殊)other\n⚠️ (建議删除)other\n",
        )
        client.send_message.assert_awaited_once_with(
            123, f"\ndevice_model=\n{result}", parse_mode="HTML"
        )

    async def test_failed_reset_is_logged_and_remaining_sessions_are_processed(self):
        client = Client([
            authorization(3, "blocked", 30),
            authorization(4, "blocked", 30),
        ], fail_hash=3)
        with patch("builtins.print") as print_mock:
            result = await load_check_active_sessions()(None, client)
        print_mock.assert_any_call("❌ 删除 3 失败: reset failed")
        self.assertEqual(client.reset_hashes, [4])
        self.assertEqual(result, "❌ (黑名单)blocked\n")
        client.send_message.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
