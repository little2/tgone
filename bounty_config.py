# bounty_config.py
import os
from pathlib import Path
from typing import Set

# =========================
# .env loader（一次即可）
# =========================

def _load_dotenv(path: str = ".env") -> None:
    p = Path(path)
    if not p.exists():
        return

    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue

        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip("'").strip('"')

        # 不覆盖系统已有变量（适配 Render / Docker）
        if k and k not in os.environ:
            os.environ[k] = v


_load_dotenv()


# =========================
# helpers
# =========================

def _get_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, default))
    except Exception:
        return default


def _get_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, default))
    except Exception:
        return default


def _get_set(key: str) -> Set[int]:
    raw = os.getenv(key, "").strip()
    if not raw:
        return set()
    return {int(x.strip()) for x in raw.split(",") if x.strip().isdigit()}


# =========================
# Telegram / DB
# =========================

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
DATABASE_DSN: str = os.getenv("DATABASE_DSN", "")
BOARD_CHAT_ID: int = _get_int("BOARD_CHAT_ID", 0)

ADMIN_IDS: Set[int] = _get_set("ADMIN_IDS")

SYSTEM_UID: int = _get_int("SYSTEM_UID", 0)


# =========================
# Bounty timeouts (seconds)
# =========================

CLAIM_TIMEOUT: int = _get_int("CLAIM_TIMEOUT", 10 * 60)
REVIEW_TIMEOUT: int = _get_int("REVIEW_TIMEOUT", 3 * 24 * 3600)
RETURN_TIMEOUT: int = _get_int("RETURN_TIMEOUT", 24 * 3600)
NO_HUNTER_TIMEOUT: int = _get_int("NO_HUNTER_TIMEOUT", 14 * 24 * 3600)


# =========================
# Refund
# =========================

REFUND_FEE_RATE: float = _get_float("REFUND_FEE_RATE", 0.05)
REFUND_FEE_MIN: int = _get_int("REFUND_FEE_MIN", 1)


# =========================
# Bounty status constants
# =========================

B0_DRAFT = 0        # 未发布
B1_OPEN = 1         # 悬赏中
B2_REVIEW = 2       # 审核中
B3_RETURN = 3       # 退回中
B4_ARBIT = 4        # 仲裁中
B7_SUBMIT = 7       # 资源提交中
B8_EXPIRED = 8      # 逾期未提交
B9_DONE = 9         # 已结束
B10_REFUNDED = 10   # 退款并关结


# =========================
# sanity check（启动即失败）
# =========================

def validate() -> None:
    missing = []
    if not BOT_TOKEN:
        missing.append("BOT_TOKEN")
    if not DATABASE_DSN:
        missing.append("DATABASE_DSN")
    if not BOARD_CHAT_ID:
        missing.append("BOARD_CHAT_ID")

    if missing:
        raise RuntimeError(f"Missing required config in .env: {', '.join(missing)}")
