import os
import asyncio
import logging
from typing import Optional, Any, Sequence, Mapping
import asyncpg

log = logging.getLogger("db")

_PG_DSN = os.getenv(
    "PG_DSN",
    "postgresql://freshanon:postgres123@127.0.0.1:5433/freshanon?connect_timeout=5&sslmode=disable",
)
_POOL_MIN = int(os.getenv("PG_POOL_MIN", "1"))
_POOL_MAX = int(os.getenv("PG_POOL_MAX", "10"))
_POOL_TIMEOUT = float(os.getenv("PG_TIMEOUT", "10"))

_pool: Optional[asyncpg.Pool] = None

async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool:
        return _pool
    delays = [0.5, 1, 2, 3, 5]
    last_err = None
    for attempt, delay in enumerate(delays, 1):
        try:
            _pool = await asyncpg.create_pool(
                dsn=_PG_DSN,
                min_size=_POOL_MIN,
                max_size=_POOL_MAX,
                timeout=_POOL_TIMEOUT,
                command_timeout=60,
            )
            async with _pool.acquire() as con:
                await con.execute("SELECT 1;")
            log.info("[db] pool ready → %s", _PG_DSN)
            return _pool
        except Exception as e:
            last_err = e
            log.warning("[db] pool attempt %s/%s failed: %s", attempt, len(delays), e)
            await asyncio.sleep(delay)
    raise last_err

async def fetch(query: str, *args: Any) -> Sequence[asyncpg.Record]:
    pool = await get_pool()
    async with pool.acquire() as con:
        return await con.fetch(query, *args)

async def fetchrow(query: str, *args: Any) -> Optional[asyncpg.Record]:
    pool = await get_pool()
    async with pool.acquire() as con:
        return await con.fetchrow(query, *args)

async def fetchval(query: str, *args: Any) -> Any:
    pool = await get_pool()
    async with pool.acquire() as con:
        return await con.fetchval(query, *args)

async def execute(query: str, *args: Any) -> str:
    pool = await get_pool()
    async with pool.acquire() as con:
        return await con.execute(query, *args)

async def executemany(query: str, args_iterable: Sequence[Sequence[Any]]) -> None:
    pool = await get_pool()
    async with pool.acquire() as con:
        await con.executemany(query, args_iterable)
