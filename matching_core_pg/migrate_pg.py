import asyncio, sys, asyncpg

async def main(dsn: str):
    conn = await asyncpg.connect(dsn=dsn)
    try:
        schema_path = __file__.replace("migrate_pg.py", "schema_pg.sql")
        sql = open(schema_path, "r", encoding="utf-8").read()
        for stmt in sql.split(";"):
            s = stmt.strip()
            if s:
                await conn.execute(s)
        print("Schema applied.")
    finally:
        await conn.close()

if __name__ == "__main__":
    dsn = sys.argv[1] if len(sys.argv) > 1 else "postgresql://freshanon:postgres!@localhost:5433/freshanon"
    asyncio.run(main(dsn))
