import asyncio, os, asyncpg
from config import PG_DSN

async def main():
    dsn = os.getenv("PG_DSN", PG_DSN)
    print("Connecting:", dsn)
    conn = await asyncpg.connect(dsn=dsn, timeout=10)
    try:
        ver = await conn.fetchval("select version()")
        now = await conn.fetchval("select now()")
        print("OK:", ver)
        print("Time:", now)
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
