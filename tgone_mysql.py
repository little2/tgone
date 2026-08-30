import aiomysql
import time
from typing import Optional, Dict, Any, List
from lz_memory_cache import MemoryCache
import asyncio
from functools import wraps
from inspect import stack

DBError = aiomysql.Error
DBIntegrityError = aiomysql.IntegrityError
DBOperationalError = aiomysql.OperationalError

def _caller_info():
    frames = stack()
    if len(frames) > 2:
        frame = frames[2]
        return f"{frame.filename.split('/')[-1]}:{frame.function}:{frame.lineno}"
    return "unknown"


def reconnecting(func):
    """
    通用断线重连装饰器：
    - 只针对 aiomysql.OperationalError
    - 若错误码为 2006 / 2013 → 认为是断线，重建连接池 + 自动重试一次
    - 第二次仍失败 / 其它错误 → 直接抛出
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        cls = args[0] if args else None
        for attempt in (1, 2):
            try:
                return await func(*args, **kwargs)
            except aiomysql.OperationalError as e:
                code = e.args[0] if e.args else None
                msg = e.args[1] if len(e.args) > 1 else ""

                if not cls or code not in (2006, 2013) or attempt == 2:
                    print(f"❌ [MySQLPool] OperationalError {code}: {msg}", flush=True)
                    raise

                print(f"⚠️ [MySQLPool] 检测到断线 {code}: {msg} → 重建连接池并重试一次", flush=True)
                try:
                    await cls._rebuild_pool()
                except Exception as e2:
                    print(f"❌ [MySQLPool] 重建连接池失败: {e2}", flush=True)
                    raise
    return wrapper

# tgone_mysql.py

class MySQLPool:
    _pool = None
    _config: Optional[Dict[str, Any]] = None
    _lock = asyncio.Lock()
    _cache_ready = False
    cache = None
    _closing = False  # ✅ 新增：标记正在 close/rebuild，避免 acquire 竞态
    _debug_mode = False

    @classmethod
    def configure(
        cls,
        *,
        host: str,
        user: str,
        password: str,
        database: str,
        port: int = 3306,
    ) -> None:
        """注入 MySQL 設定；必須在建立連線池之前呼叫。"""
        if cls._pool is not None:
            raise RuntimeError("MySQL pool 建立後不可重新設定")
        if not host or not user or not database:
            raise ValueError("MySQL host、user、database 不可為空")

        cls._config = {
            "host": host,
            "user": user,
            "password": password,
            "db": database,
            "port": int(port),
        }

    @classmethod
    def show_debug(cls,text):
        if cls._debug_mode:
            print(f"{text}", flush=True)

    @classmethod
    async def init_pool(cls):
        # 锁外快路径
        if cls._pool_usable():
            return cls._pool

        async with cls._lock:
            # 锁内二次检查
            if cls._pool_usable():
                return cls._pool
            return await cls._init_pool_locked()

    @classmethod
    async def _init_pool_locked(cls):
        # 注意：这里不再加锁（调用方必须持锁）
        # 若 pool 对象存在但不可用，强制置空重建
        if cls._pool is not None and not cls._pool_usable():
            cls._pool = None

        if cls._pool is None:
            if cls._config is None:
                raise RuntimeError(
                    "MySQLPool 尚未設定，請先呼叫 MySQLPool.configure()"
                )
            cls._pool = await aiomysql.create_pool(
                **cls._config,
                charset="utf8mb4",
                autocommit=True,
                minsize=2,
                maxsize=32,
                pool_recycle=1800,
                connect_timeout=10,
            )
            cls.show_debug("🔄 MySQL 连接池已创建")
            

        if not cls._cache_ready:
            cls.cache = MemoryCache()
            cls._cache_ready = True

        return cls._pool

    @classmethod
    async def ensure_pool(cls):
        if cls._pool_usable():
            cls.show_debug("【MySQLPool】连接池可用，直接返回。")
            return cls._pool

        cls.show_debug("【MySQLPool】连接池不可用，准备加锁重建...")
        async with cls._lock:
            cls.show_debug("【MySQLPool】锁内检查连接池状态...")
            if cls._pool_usable():
                cls.show_debug("【MySQLPool】连接池可用（锁内检查），直接返回。")
                return cls._pool

            cls._closing = False
            cls.show_debug("【MySQLPool】连接池不可用，正在初始化...")
            return await cls._init_pool_locked()
        
    @classmethod
    async def get_conn_cursor(cls):
        """
        ✅ 关键：acquire 前确保 pool 可用。
        这里不直接长时间持锁（避免吞吐下降），但要避免 acquire 与 close 交错。
        """
        cls.show_debug("【MySQLPool】获取连接池连接...")
        await cls.ensure_pool()
        cls.show_debug("【MySQLPool】连接池可用，正在 acquire 连接...")
        # acquire 仍可能在 close 刚发生时抛错 → 捕获并重建一次
        try:
            
            conn = await cls._pool.acquire()
            cls.show_debug("【MySQLPool】连接 acquire 成功。")
        except Exception as e:
            msg = str(e).lower()
            if "after closing pool" in msg or "closing pool" in msg:
                # 说明刚好撞上 close，重建并重试一次
                await cls._rebuild_pool()
                conn = await cls._pool.acquire()
            else:
                raise

        cursor = await conn.cursor(aiomysql.DictCursor)
        return conn, cursor

    @classmethod
    async def release(cls, conn, cursor):
        try:
            if cursor:
                await cursor.close()
        finally:
            if conn and cls._pool:
                cls._pool.release(conn)

    @classmethod
    async def close(cls):
        async with cls._lock:
            if cls._pool:
                cls._closing = True
                try:
                    cls._pool.close()
                    await cls._pool.wait_closed()
                finally:
                    cls._pool = None
                    cls._closing = False
                cls.show_debug("🛑 MySQL 连接池已关闭")

    @classmethod
    async def _rebuild_pool(cls):
        async with cls._lock:
            cls._closing = True
            if cls._pool:
                try:
                    cls._pool.close()
                    await cls._pool.wait_closed()
                except Exception as e:
                    print(f"⚠️ [MySQLPool] 关闭旧连接池出错: {e}", flush=True)

            cls._pool = None
            cls.show_debug("🔄 [MySQLPool] 正在重建 MySQL 连接池…")
            cls._closing = False
            await cls.init_pool()

    @classmethod
    def _pool_usable(cls) -> bool:
        """
        判断连接池是否可用：
        - _pool 为空不可用
        - 正在 closing 不可用
        - aiomysql pool 处于 closed/closing 不可用（兼容不同版本属性）
        """
        p = cls._pool
        if p is None:
            return False
        if cls._closing:
            return False

        # aiomysql pool 通常有 closed/closing 或 _closed/_closing
        if getattr(p, "closed", False):
            return False
        if getattr(p, "closing", False):
            return False
        if getattr(p, "_closed", False):
            return False
        if getattr(p, "_closing", False):
            return False

        return True

    # ==================================================
    #   ✨ 统一 SQL helper：execute / fetchone / fetchall
    # ==================================================

    @classmethod
    async def execute(cls, sql: str, params=None, error_tag: str = "", raise_on_error: bool = False) -> bool:
        conn, cur = await cls.get_conn_cursor()
        try:
            await cur.execute(sql, params or ())
            return True
        except Exception as e:
            if error_tag:
                tag = error_tag
            else:
                tag = _caller_info()   # 自动提取调用来源
            
            print(
                f"⚠️ [{tag}] SQL 执行出错 execute: {e} | \nsql={sql} | \nparams={params}",
                flush=True,
            )
            if raise_on_error:
                raise
            return False
        finally:
            await cls.release(conn, cur)

    @classmethod
    async def fetchone(cls, sql: str, params=None, error_tag: str = "") -> Optional[Dict[str, Any]]:
        
        conn, cur = await cls.get_conn_cursor()
        try:
            await cur.execute(sql, params or ())
            return await cur.fetchone()
        except Exception as e:
            print(f"{e}", flush=True)
            if error_tag:
                tag = error_tag
            else:
                tag = _caller_info()   # 自动提取调用来源
            
            print(
                f"⚠️ [{tag}] SQL 执行出错fetchone: {e} | sql={sql} | params={params}",
                flush=True,
            )
            return None
        finally:
            await cls.release(conn, cur)

    @classmethod
    async def fetchall(cls, sql: str, params=None, error_tag: str = "") -> List[Dict[str, Any]]:
        conn, cur = await cls.get_conn_cursor()
        try:
            await cur.execute(sql, params or ())
            return await cur.fetchall()
        except Exception as e:
            if error_tag:
                tag = error_tag
            else:
                tag = _caller_info()   # 自动提取调用来源
            
            print(
                f"⚠️ [{tag}] SQL 执行出错 fetchall: {e} | sql={sql} | params={params}",
                flush=True,
            )
            return []
        finally:
            await cls.release(conn, cur)

    @classmethod
    async def transaction(cls, fn):
        """
        通用事务执行器（与现有 _pool / release / DictCursor 对齐）
        fn: async def fn(cur): ...  # cur 为 DictCursor
        """
        await cls.ensure_pool()

        conn = None
        cur = None
        try:
            conn = await cls._pool.acquire()
            cur = await conn.cursor(aiomysql.DictCursor)

            await conn.begin()
            result = await fn(cur)
            await conn.commit()
            return result
        except Exception:
            if conn:
                await conn.rollback()
            raise
        finally:
            # 复用你已有的 release 逻辑
            if conn and cur:
                await cls.release(conn, cur)
            elif conn and cls._pool:
                cls._pool.release(conn)



''''''
