"""将 chat.py 的 script 导入 userbot 使用的 chat_script_message 表。"""

import argparse
import ast
import asyncio
import os
from decimal import Decimal, InvalidOperation
from pathlib import Path

from dotenv import load_dotenv
from tgone_mysql import MySQLPool


INSERT_SQL = """
    INSERT INTO chat_script_message
        (smsg_timestamp, smsg_id, leadtime, bot_id,
         reply_to_smsg_id, typing_duration, text, parse_mode)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
"""


def load_rows(path: Path) -> list[tuple]:
    """只读取 script 字典，不执行输入文件中的 Python 代码。"""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    assignments = [
        node for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "script" for target in node.targets)
    ]
    if len(assignments) != 1:
        raise ValueError("输入文件必须包含一个 script 字典赋值")
    script = ast.literal_eval(assignments[0].value)
    timestamp = script["info"]["start_at"]
    if type(timestamp) is not int or not 0 <= timestamp <= 2**63 - 1:
        raise ValueError("info.start_at 必须是秒级 Unix 整数时间戳")
    messages = script["messages"]
    if not isinstance(messages, list) or not messages:
        raise ValueError("messages 必须是非空数组")

    rows = []
    seen = set()
    for message in messages:
        smsg_id = message["smsg_id"]
        leadtime = message["leadtime"]
        bot_id = message["bot_id"]
        rid = message.get("rid", message.get("reply_to_smsg_id", 0))
        if rid is None:
            rid = 0
        for key, value, minimum, maximum in (
            ("smsg_id", smsg_id, 1, 2**32 - 1),
            ("leadtime", leadtime, 0, 2**32 - 1),
            ("bot_id", bot_id, 1, 2**63 - 1),
            ("rid", rid, 0, 2**31 - 1),
        ):
            if type(value) is not int or not minimum <= value <= maximum:
                raise ValueError(f"{key} 超出数据库整数字段范围")
        if smsg_id in seen:
            raise ValueError(f"重复的 smsg_id：{smsg_id}")
        seen.add(smsg_id)
        try:
            td = Decimal(str(message.get("td", message.get("typing_duration", 0))))
        except InvalidOperation as exc:
            raise ValueError(f"{smsg_id} 的输入时长无效") from exc
        if not td.is_finite() or not 0 <= td <= Decimal("99999.999"):
            raise ValueError(f"{smsg_id} 的输入时长超出范围")
        if td != td.quantize(Decimal("0.001")):
            raise ValueError(f"{smsg_id} 的输入时长最多支持三位小数")
        text = message["text"]
        if not isinstance(text, str) or len(text.encode("utf-8")) > 65535:
            raise ValueError(f"{smsg_id} 的 text 必须是符合 TEXT 容量的字符串")
        parse_mode = message.get("parse_mode") or "html"
        if not isinstance(parse_mode, str) or len(parse_mode) > 20:
            raise ValueError(f"{smsg_id} 的 parse_mode 无效")
        rows.append((timestamp, smsg_id, leadtime, bot_id, rid, td, text, parse_mode))
    for row in rows:
        if row[4] and (row[4] not in seen or row[4] == row[1]):
            raise ValueError(f"{row[1]} 的回复目标无效：{row[4]}")
    return rows


async def import_rows(rows: list[tuple]) -> int:
    """返回新增条数；该时间戳已有消息时跳过并返回 0。"""
    async def insert(cursor):
        # 避免重复执行时将整份剧本再次导入；不覆盖已有发送记录。
        await cursor.execute(
            "SELECT id FROM chat_script_message WHERE smsg_timestamp = %s LIMIT 1 FOR UPDATE",
            (rows[0][0],),
        )
        if await cursor.fetchone():
            return 0
        await cursor.executemany(INSERT_SQL, rows)
        return len(rows)

    return await MySQLPool.transaction(insert)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", type=Path, default=Path(__file__).with_name("chat.py"))
    parser.add_argument("--dry-run", action="store_true", help="只校验数据，不连接数据库")
    args = parser.parse_args()
    rows = load_rows(args.source)
    if args.dry_run:
        print(f"校验通过：{len(rows)} 条消息，smsg_timestamp={rows[0][0]}")
        return

    load_dotenv(Path(__file__).with_name(".env"))
    # 与 userbot.py 使用相同的配置来源、优先顺序和连接池。
    from user_account_manager import UserAccountManager
    config = UserAccountManager().load_config()
    MySQLPool.configure(
        host=config.get("db_host", os.getenv("MYSQL_DB_HOST", "localhost")),
        user=config.get("db_user", os.getenv("MYSQL_DB_USER", "")),
        password=config.get("db_password", os.getenv("MYSQL_DB_PASSWORD", "")),
        database=config.get("db_name", os.getenv("MYSQL_DB_NAME", "")),
        port=int(config.get("db_port", os.getenv("MYSQL_DB_PORT", 3306))),
    )
    try:
        count = await import_rows(rows)
        if count == 0:
            print(f"该时间戳已有消息，已跳过导入：smsg_timestamp={rows[0][0]}")
        else:
            print(f"导入成功：{count} 条消息，smsg_timestamp={rows[0][0]}")
    finally:
        await MySQLPool.close()


if __name__ == "__main__":
    asyncio.run(main())
