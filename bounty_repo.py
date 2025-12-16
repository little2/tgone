# bounty_repo.py
from __future__ import annotations

from typing import Optional, List, Tuple
import asyncpg

import bounty_config as cfg
from tgone_pgsql import PGPool


class BountyRepo:
    """
    DB access layer for bounty system.

    bounty_status:
      0: 未发布
      1: 悬赏中
      2: 审核中
      3: 退回中
      4: 仲裁中
      7: 资源提交中
      8: 逾期未提交
      9: 已结束
      10: 退款并关结
    """

    # -----------------------------
    # Schema
    # -----------------------------

    SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS bounty (
      bounty_id              BIGSERIAL PRIMARY KEY,

      creator_id             BIGINT NOT NULL,
      create_time            TIMESTAMPTZ NOT NULL DEFAULT now(),

      bonus                  INT NOT NULL DEFAULT 0,
      bounty_status          INT NOT NULL DEFAULT 0,

      hunter_id              BIGINT NULL,
      bot_name               TEXT NULL,

      due_timestamp          BIGINT NULL,

      board_chat_id          BIGINT NULL,
      board_message_id       BIGINT NULL,

      bounty_content         TEXT NULL,

      file_unique_id         TEXT NULL,
      file_type              TEXT NULL,
      file_id                TEXT NULL,

      current_bounty_user_id BIGINT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_bounty_status_due
      ON bounty (bounty_status, due_timestamp);

    CREATE INDEX IF NOT EXISTS idx_bounty_creator
      ON bounty (creator_id, create_time DESC);

    CREATE INDEX IF NOT EXISTS idx_bounty_board_msg
      ON bounty (board_chat_id, board_message_id);


    CREATE TABLE IF NOT EXISTS bounty_user (
      bounty_user_id   BIGSERIAL PRIMARY KEY,

      bounty_id        BIGINT NOT NULL REFERENCES bounty(bounty_id) ON DELETE CASCADE,
      user_id          BIGINT NOT NULL,

      create_timestamp TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE INDEX IF NOT EXISTS idx_bu_bounty
      ON bounty_user (bounty_id, create_timestamp DESC);

    CREATE INDEX IF NOT EXISTS idx_bu_user
      ON bounty_user (user_id, create_timestamp DESC);


    CREATE TABLE IF NOT EXISTS bounty_user_item (
      bounty_user_item_id BIGSERIAL PRIMARY KEY,

      bounty_user_id  BIGINT NOT NULL REFERENCES bounty_user(bounty_user_id) ON DELETE CASCADE,

      bot_name        TEXT NULL,
      file_unique_id  TEXT NULL,
      file_id         TEXT NOT NULL,
      file_type       TEXT NOT NULL,

      create_time     TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE INDEX IF NOT EXISTS idx_bui_bu
      ON bounty_user_item (bounty_user_id);
    """

    @staticmethod
    async def ensure_schema() -> None:
        parts = [p.strip() for p in BountyRepo.SCHEMA_SQL.split(";") if p.strip()]
        for stmt in parts:
            await PGPool.execute(stmt + ";")

    # -----------------------------
    # Bounty basic
    # -----------------------------

    @staticmethod
    async def create_bounty(
        creator_id: int,
        bonus: int,
        bounty_content: str,
        file_id: Optional[str],
        file_unique_id: Optional[str],
        file_type: Optional[str],
        bot_name: Optional[str],
    ) -> int:
        row = await PGPool.fetchrow(
            """
            INSERT INTO bounty
              (creator_id, bonus, bounty_status, bounty_content, file_id, file_unique_id, file_type, bot_name)
            VALUES
              ($1,$2,$3,$4,$5,$6,$7,$8)
            RETURNING bounty_id
            """,
            creator_id, bonus, cfg.B1_OPEN, bounty_content, file_id, file_unique_id, file_type, bot_name
        )
        return int(row["bounty_id"])

    @staticmethod
    async def set_board_message(bounty_id: int, board_chat_id: int, board_message_id: int) -> None:
        await PGPool.execute(
            "UPDATE bounty SET board_chat_id=$2, board_message_id=$3 WHERE bounty_id=$1",
            bounty_id, board_chat_id, board_message_id
        )

    @staticmethod
    async def get_bounty(bounty_id: int) -> Optional[asyncpg.Record]:
        return await PGPool.fetchrow("SELECT * FROM bounty WHERE bounty_id=$1", bounty_id)

    # -----------------------------
    # Claim / Submit
    # -----------------------------

    @staticmethod
    async def claim_bounty(bounty_id: int, hunter_id: int, due_ts: int) -> int:
        """
        并发安全领取：
        - bounty_status 必须为 1
        - current_bounty_user_id 必须为空
        成功返回 bounty_user_id
        """
        async def _tx(conn: asyncpg.Connection):
            b = await conn.fetchrow("SELECT * FROM bounty WHERE bounty_id=$1 FOR UPDATE", bounty_id)
            if not b or int(b["bounty_status"]) != cfg.B1_OPEN or b["current_bounty_user_id"] is not None:
                return 0

            bu = await conn.fetchrow(
                "INSERT INTO bounty_user (bounty_id, user_id) VALUES ($1,$2) RETURNING bounty_user_id",
                bounty_id, hunter_id
            )
            bounty_user_id = int(bu["bounty_user_id"])

            await conn.execute(
                """
                UPDATE bounty
                   SET bounty_status=$2,
                       hunter_id=$3,
                       current_bounty_user_id=$4,
                       due_timestamp=$5
                 WHERE bounty_id=$1
                """,
                bounty_id, cfg.B7_SUBMIT, hunter_id, bounty_user_id, due_ts
            )
            return bounty_user_id

        return await PGPool.in_tx(_tx)

    @staticmethod
    async def add_bounty_item(
        bounty_user_id: int,
        bot_name: Optional[str],
        file_unique_id: Optional[str],
        file_id: str,
        file_type: str,
    ) -> None:
        await PGPool.execute(
            """
            INSERT INTO bounty_user_item (bounty_user_id, bot_name, file_unique_id, file_id, file_type)
            VALUES ($1,$2,$3,$4,$5)
            """,
            bounty_user_id, bot_name, file_unique_id, file_id, file_type
        )

    @staticmethod
    async def get_current_submitting_bounty_by_hunter(hunter_id: int) -> Optional[asyncpg.Record]:
        return await PGPool.fetchrow(
            """
            SELECT bounty_id, creator_id, current_bounty_user_id
              FROM bounty
             WHERE hunter_id=$1 AND bounty_status=$2
            """,
            hunter_id, cfg.B7_SUBMIT
        )

    @staticmethod
    async def submit_to_review(hunter_id: int, review_due_ts: int):
        """
        hunter /submit：
        - 锁定 bounty (status=7)
        - 检查 bounty_user_item >0
        - 更新 bounty_status=2, due_timestamp=review_due_ts
        返回:
          - None
          - ("NO_ITEMS", bounty_id, creator_id, bounty_user_id)
          - (bounty_id, creator_id, bounty_user_id)
        """
        async def _tx(conn: asyncpg.Connection):
            b = await conn.fetchrow(
                """
                SELECT bounty_id, creator_id, current_bounty_user_id
                  FROM bounty
                 WHERE hunter_id=$1 AND bounty_status=$2
                 FOR UPDATE
                """,
                hunter_id, cfg.B7_SUBMIT
            )
            if not b:
                return None

            bounty_id = int(b["bounty_id"])
            creator_id = int(b["creator_id"])
            bounty_user_id = int(b["current_bounty_user_id"])

            cnt = await conn.fetchval(
                "SELECT COUNT(1) FROM bounty_user_item WHERE bounty_user_id=$1",
                bounty_user_id
            )
            if int(cnt or 0) <= 0:
                return ("NO_ITEMS", bounty_id, creator_id, bounty_user_id)

            await conn.execute(
                "UPDATE bounty SET bounty_status=$2, due_timestamp=$3 WHERE bounty_id=$1",
                bounty_id, cfg.B2_REVIEW, review_due_ts
            )
            return (bounty_id, creator_id, bounty_user_id)

        return await PGPool.in_tx(_tx)

    @staticmethod
    async def list_items(bounty_user_id: int) -> List[Tuple[str, str]]:
        rows = await PGPool.fetch(
            """
            SELECT file_type, file_id
              FROM bounty_user_item
             WHERE bounty_user_id=$1
             ORDER BY bounty_user_item_id
            """,
            bounty_user_id
        )
        return [(r["file_type"], r["file_id"]) for r in rows]

    # -----------------------------
    # Review decision
    # -----------------------------

    @staticmethod
    async def accept_bounty(bounty_id: int, creator_id: int) -> Optional[Tuple[int, int, int]]:
        async def _tx(conn: asyncpg.Connection):
            b = await conn.fetchrow("SELECT * FROM bounty WHERE bounty_id=$1 FOR UPDATE", bounty_id)
            if not b or int(b["bounty_status"]) != cfg.B2_REVIEW or int(b["creator_id"]) != creator_id:
                return None
            hunter_id = int(b["hunter_id"])
            bonus = int(b["bonus"])
            bounty_user_id = int(b["current_bounty_user_id"])
            await conn.execute("UPDATE bounty SET bounty_status=$2, due_timestamp=NULL WHERE bounty_id=$1", bounty_id, cfg.B9_DONE)
            return (hunter_id, bonus, bounty_user_id)

        return await PGPool.in_tx(_tx)

    @staticmethod
    async def reject_bounty(bounty_id: int, creator_id: int, return_due_ts: int) -> Optional[Tuple[int, int]]:
        async def _tx(conn: asyncpg.Connection):
            b = await conn.fetchrow("SELECT * FROM bounty WHERE bounty_id=$1 FOR UPDATE", bounty_id)
            if not b or int(b["bounty_status"]) != cfg.B2_REVIEW or int(b["creator_id"]) != creator_id:
                return None
            hunter_id = int(b["hunter_id"])
            bounty_user_id = int(b["current_bounty_user_id"])
            await conn.execute("DELETE FROM bounty_user_item WHERE bounty_user_id=$1", bounty_user_id)
            await conn.execute(
                "UPDATE bounty SET bounty_status=$2, due_timestamp=$3 WHERE bounty_id=$1",
                bounty_id, cfg.B3_RETURN, return_due_ts
            )
            return (hunter_id, bounty_user_id)

        return await PGPool.in_tx(_tx)

    @staticmethod
    async def set_arbitration(bounty_id: int, hunter_id: int) -> bool:
        async def _tx(conn: asyncpg.Connection):
            b = await conn.fetchrow("SELECT * FROM bounty WHERE bounty_id=$1 FOR UPDATE", bounty_id)
            if not b or int(b["bounty_status"]) != cfg.B3_RETURN or int(b["hunter_id"]) != hunter_id:
                return False
            await conn.execute("UPDATE bounty SET bounty_status=$2, due_timestamp=NULL WHERE bounty_id=$1", bounty_id, cfg.B4_ARBIT)
            return True
        return await PGPool.in_tx(_tx)

    # -----------------------------
    # Refund & close (status 9 -> 10)
    # -----------------------------

    @staticmethod
    async def refund_and_close(bounty_id: int, creator_id: int):
        """
        Returns:
          ("OK", refund_amount, fee)
          ("NOT_FOUND",)
          ("NO_PERM",)
          ("BAD_STATUS", current_status)
        """
        async def _tx(conn: asyncpg.Connection):
            b = await conn.fetchrow("SELECT * FROM bounty WHERE bounty_id=$1 FOR UPDATE", bounty_id)
            if not b:
                return ("NOT_FOUND",)
            if int(b["creator_id"]) != creator_id:
                return ("NO_PERM",)
            st = int(b["bounty_status"])
            if st != cfg.B9_DONE:
                return ("BAD_STATUS", st)

            bonus = int(b["bonus"])
            fee = max(cfg.REFUND_FEE_MIN, int(bonus * cfg.REFUND_FEE_RATE))
            refund_amount = max(0, bonus - fee)

            await conn.execute(
                "UPDATE bounty SET bounty_status=$2, due_timestamp=NULL WHERE bounty_id=$1",
                bounty_id, cfg.B10_REFUNDED
            )
            return ("OK", refund_amount, fee)

        return await PGPool.in_tx(_tx)

    # -----------------------------
    # Timeout utilities
    # -----------------------------

    @staticmethod
    async def end_open_bounties_without_hunter(no_hunter_timeout_sec: int) -> int:
        res = await PGPool.execute(
            """
            UPDATE bounty
               SET bounty_status=$1, due_timestamp=NULL
             WHERE bounty_status=$2
               AND create_time <= (now() - ($3 || ' seconds')::interval)
            """,
            cfg.B9_DONE, cfg.B1_OPEN, no_hunter_timeout_sec
        )
        try:
            return int(str(res).split()[-1])
        except Exception:
            return 0

    @staticmethod
    async def list_due_expired(now_ts: int) -> List[Tuple[int, int]]:
        rows = await PGPool.fetch(
            """
            SELECT bounty_id, bounty_status
              FROM bounty
             WHERE due_timestamp IS NOT NULL
               AND due_timestamp <= $1
            """,
            now_ts
        )
        return [(int(r["bounty_id"]), int(r["bounty_status"])) for r in rows]

    @staticmethod
    async def timeout_submit_to_reopen(bounty_id: int) -> bool:
        async def _tx(conn: asyncpg.Connection):
            b = await conn.fetchrow("SELECT bounty_status FROM bounty WHERE bounty_id=$1 FOR UPDATE", bounty_id)
            if not b or int(b["bounty_status"]) != cfg.B7_SUBMIT:
                return False

            await conn.execute("UPDATE bounty SET bounty_status=$2 WHERE bounty_id=$1", bounty_id, cfg.B8_EXPIRED)
            await conn.execute(
                """
                UPDATE bounty
                   SET bounty_status=$2,
                       hunter_id=NULL,
                       current_bounty_user_id=NULL,
                       due_timestamp=NULL
                 WHERE bounty_id=$1
                """,
                bounty_id, cfg.B1_OPEN
            )
            return True

        return await PGPool.in_tx(_tx)

    @staticmethod
    async def timeout_return_to_reopen(bounty_id: int) -> bool:
        async def _tx(conn: asyncpg.Connection):
            b = await conn.fetchrow("SELECT bounty_status FROM bounty WHERE bounty_id=$1 FOR UPDATE", bounty_id)
            if not b or int(b["bounty_status"]) != cfg.B3_RETURN:
                return False
            await conn.execute("UPDATE bounty SET bounty_status=$2, due_timestamp=NULL WHERE bounty_id=$1", bounty_id, cfg.B1_OPEN)
            return True

        return await PGPool.in_tx(_tx)

    @staticmethod
    async def timeout_review_auto_accept(bounty_id: int) -> Optional[Tuple[int, Optional[int], int, int]]:
        async def _tx(conn: asyncpg.Connection):
            b = await conn.fetchrow("SELECT * FROM bounty WHERE bounty_id=$1 FOR UPDATE", bounty_id)
            if not b or int(b["bounty_status"]) != cfg.B2_REVIEW:
                return None

            creator_id = int(b["creator_id"])
            hunter_id = int(b["hunter_id"]) if b["hunter_id"] is not None else None
            bonus = int(b["bonus"])
            bounty_user_id = int(b["current_bounty_user_id"])

            await conn.execute(
                "UPDATE bounty SET bounty_status=$2, due_timestamp=NULL WHERE bounty_id=$1",
                bounty_id, cfg.B9_DONE
            )
            return (creator_id, hunter_id, bonus, bounty_user_id)

        return await PGPool.in_tx(_tx)
