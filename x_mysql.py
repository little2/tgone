import aiomysql
from app_timezone import MYSQL_TIMEZONE
import time
from tgone_config import MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB, MYSQL_DB_PORT
from typing import Optional, Dict, Any
from lz_memory_cache import MemoryCache
import asyncio


class MySQLPool:
    _pool = None
    _lock = asyncio.Lock()
    _cache_ready = False
    cache: Optional[MemoryCache] = None

    @classmethod
    async def init_pool(cls):
        """
        初始化 MySQL 连接池（幂等）。
        """
        if cls._pool is not None:
            if not cls._cache_ready:
                cls.cache = MemoryCache()
                cls._cache_ready = True
            return cls._pool

        async with cls._lock:
            if cls._pool is None:
                cls._pool = await aiomysql.create_pool(
                    host=MYSQL_HOST,
                    user=MYSQL_USER,
                    password=MYSQL_PASSWORD,
                    db=MYSQL_DB,
                    port=MYSQL_DB_PORT,
                    charset="utf8mb4",
                    autocommit=True,
                    minsize=2,
                    maxsize=32,
                    pool_recycle=1800,
                    connect_timeout=10,
                    init_command=f"SET time_zone = '{MYSQL_TIMEZONE}'",
                )
                print("✅ MySQL 连接池初始化完成")
            if not cls._cache_ready:
                cls.cache = MemoryCache()
                cls._cache_ready = True
        return cls._pool

    @classmethod
    async def ensure_pool(cls):
        if cls._pool is None:
            await cls.init_pool()
        return cls._pool

    @classmethod
    async def get_conn_cursor(cls):
        """
        取得 (conn, cursor)，cursor 为 DictCursor。
        """
        await cls.ensure_pool()
        conn = await cls._pool.acquire()
        cursor = await conn.cursor(aiomysql.DictCursor)
        return conn, cursor

    @classmethod
    async def release(cls, conn, cursor):
        """
        释放 cursor 与连接回连接池。
        """
        try:
            if cursor:
                await cursor.close()
        finally:
            if conn and cls._pool:
                cls._pool.release(conn)

    @classmethod
    async def close(cls):
        """
        关闭连接池（通常不需要主动调用）。
        """
        async with cls._lock:
            if cls._pool:
                cls._pool.close()
                await cls._pool.wait_closed()
                cls._pool = None
                print("🛑 MySQL 连接池已关闭")

    # ======================
    # 交易相关方法
    # ======================
    @classmethod
    async def transaction_log(cls, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        记录一次交易，并更新双方 point。

        transaction_data 结构示例：
        {
            'sender_id': 发起人 user_id 或 '',
            'receiver_id': 收款人 user_id 或 '',
            'transaction_type': 'hb' / 'play' / 'payment' / ...,
            'transaction_description': 'chat_id message_id' 或其他描述,
            'sender_fee': int,   # 扣款（若是负值则为扣、正值为加）
            'receiver_fee': int, # 收款
        }
        """
        conn, cur = await cls.get_conn_cursor()
        print(f"🔍 处理交易记录: {transaction_data}")

        user_info_row = None

        if transaction_data.get('transaction_description', '') == '':
            return {
                'ok': '',
                'status': 'no_description',
                'transaction_data': transaction_data
            }

        try:
            # 构造 WHERE 条件，避免重复记录
            where_clauses = []
            params = []

            if transaction_data.get('sender_id', '') != '':
                where_clauses.append('sender_id = %s')
                params.append(transaction_data['sender_id'])

            if transaction_data.get('receiver_id', '') != '':
                where_clauses.append('receiver_id = %s')
                params.append(transaction_data['receiver_id'])

            where_clauses.append('transaction_type = %s')
            params.append(transaction_data['transaction_type'])

            where_clauses.append('transaction_description = %s')
            params.append(transaction_data['transaction_description'])

            where_sql = ' AND '.join(where_clauses)

            # 查询是否已有相同记录
            await cur.execute(f"""
                SELECT transaction_id FROM transaction
                WHERE {where_sql}
                LIMIT 1
            """, params)

            transaction_result = await cur.fetchone()

            if transaction_result and transaction_result.get('transaction_id'):
                return {
                    'ok': '1',
                    'status': 'exist',
                    'transaction_data': transaction_result
                }

            # 禁止自己打赏自己
            if transaction_data.get('sender_id') == transaction_data.get('receiver_id'):
                return {
                    'ok': '',
                    'status': 'reward_self',
                    'transaction_data': transaction_data
                }

            # 更新 sender point
            if transaction_data.get('sender_id', '') != '':
                try:
                    await cur.execute("""
                        SELECT *
                        FROM user
                        WHERE user_id = %s
                        LIMIT 0, 1
                    """, (transaction_data['sender_id'],))
                    user_info_row = await cur.fetchone()
                except Exception as e:
                    print(f"⚠️ 数据库执行出错: {e}")
                    user_info_row = None

                # 检查余额是否足够（sender_fee 通常为负数）
                if not user_info_row or user_info_row['point'] < abs(transaction_data['sender_fee']):
                    return {
                        'ok': '',
                        'status': 'insufficient_funds',
                        'transaction_data': transaction_data,
                        'user_info': user_info_row
                    }
                else:
                    # 扣除 sender point
                    await cur.execute("""
                        UPDATE user
                        SET point = point + %s
                        WHERE user_id = %s
                    """, (transaction_data['sender_fee'], transaction_data['sender_id']))

            # 更新 receiver point，如果不在 block list
            if transaction_data.get('receiver_id', '') != '':
                if not await cls.in_block_list(transaction_data['receiver_id']):
                    await cur.execute("""
                        UPDATE user
                        SET point = point + %s
                        WHERE user_id = %s
                    """, (transaction_data['receiver_fee'], transaction_data['receiver_id']))

            # 插入 transaction 记录
            transaction_data['transaction_timestamp'] = int(time.time())

            insert_columns = ', '.join(transaction_data.keys())
            insert_placeholders = ', '.join(['%s'] * len(transaction_data))
            insert_values = list(transaction_data.values())

            await cur.execute(f"""
                INSERT INTO transaction ({insert_columns})
                VALUES ({insert_placeholders})
            """, insert_values)

            transaction_id = cur.lastrowid
            transaction_data['transaction_id'] = transaction_id

            return {
                'ok': '1',
                'status': 'insert',
                'transaction_data': transaction_data,
                'user_info': user_info_row
            }

        finally:
            await cls.release(conn, cur)

    @classmethod
    async def in_block_list(cls, user_id: int) -> bool:
        """
        检查 user 是否在 block list 中。
        如需真正实现，请改成查询 block_list 表。
        当前默认全部不在黑名单。
        """
        return False

    @classmethod
    async def find_transaction_by_description(cls, desc: str) -> Optional[Dict[str, Any]]:
        """
        根据 transaction_description 查询一笔交易记录。
        :param desc: 例如 "chat_id message_id"
        :return: dict or None
        """
        conn, cur = await cls.get_conn_cursor()
        try:
            await cur.execute(
                """
                SELECT *
                FROM transaction
                WHERE transaction_description = %s
                LIMIT 1
                """,
                (desc,),
            )
            row = await cur.fetchone()
            return row if row else None
        except Exception as e:
            print(f"⚠️ find_transaction_by_description 出错: {e}", flush=True)
            return None
        finally:
            await cls.release(conn, cur)
