import os, asyncio, asyncpg

async def main():
    host=os.getenv("PGHOST","127.0.0.1")
    port=int(os.getenv("PGPORT","5455"))
    user=os.getenv("PGUSER","neverland")
    password=os.getenv("PGPASSWORD","")
    database=os.getenv("PGDATABASE","fresh_anon_chat")
    print(f"Connecting to {host}:{port} db={database} user={user}")
    conn = await asyncpg.connect(host=host, port=port, user=user, password=password, database=database, timeout=10)
    ver = await conn.fetchval("select version()")
    now = await conn.fetchval("select now()")
    print("OK:", ver)
    print("Time:", now)
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
