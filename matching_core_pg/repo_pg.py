import time
import asyncpg
from typing import Optional, Sequence

class PGRepo:
    def __init__(self, dsn: str, *, pool_min:int=1, pool_max:int=15, timeout_ms:int=5000, anti_rematch_window_sec:int=3600):
        self.dsn = dsn
        self.pool_min = pool_min
        self.pool_max = pool_max
        self.timeout_ms = timeout_ms
        self.window = anti_rematch_window_sec
        self.pool: Optional[asyncpg.Pool] = None

    async def init(self):
        self.pool = await asyncpg.create_pool(dsn=self.dsn, min_size=self.pool_min, max_size=self.pool_max, timeout=self.timeout_ms/1000.0)
        async with self.pool.acquire() as conn:
            schema_path = __file__.replace("repo_pg.py", "schema_pg.sql")
            sql = open(schema_path, "r", encoding="utf-8").read()
            for stmt in sql.split(";"):
                s = stmt.strip()
                if s:
                    await conn.execute(s)

    async def close(self):
        if self.pool:
            await self.pool.close()
            self.pool = None

    async def enqueue(self, user_id:int, *, sex=None, age=None, lang=None, interests:Optional[Sequence[str]]=None, vibe=None, adult_ok=False, is_premium=False):
        interests_str = None
        if interests:
            if isinstance(interests, (list, tuple, set)):
                interests_str = ",".join(map(str, interests))
            else:
                interests_str = str(interests)
        now = int(time.time())
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO queue(user_id, sex, age, lang, interests, vibe, adult_ok, is_premium, enqueued_at)
                VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)
                ON CONFLICT(user_id) DO UPDATE SET
                  sex=EXCLUDED.sex, age=EXCLUDED.age, lang=EXCLUDED.lang,
                  interests=EXCLUDED.interests, vibe=EXCLUDED.vibe,
                  adult_ok=EXCLUDED.adult_ok, is_premium=EXCLUDED.is_premium,
                  enqueued_at=EXCLUDED.enqueued_at
                """,
                user_id, sex, age, lang, interests_str, vibe, bool(adult_ok), bool(is_premium), now
            )

    async def dequeue(self, user_id:int):
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM queue WHERE user_id=$1", user_id)

    async def end_chat(self, a_id:int, b_id:int):
        now = int(time.time())
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE pairs SET ended_at=$1 WHERE ((a_id=$2 AND b_id=$3) OR (a_id=$3 AND b_id=$2)) AND ended_at IS NULL",
                now, a_id, b_id
            )

    async def match_user(self, user_id:int, *, sex=None, age=None, lang=None, interests:Optional[Sequence[str]]=None, vibe=None, adult_ok=False, is_premium=False) -> Optional[int]:
        now = int(time.time())
        interests_csv = None
        if interests:
            if isinstance(interests, (list, tuple, set)):
                interests_csv = ",".join(map(str, interests))
            else:
                interests_csv = str(interests)

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Remove self from queue to avoid matching ourselves
                await conn.execute("DELETE FROM queue WHERE user_id=$1", user_id)

                row = await conn.fetchrow(
                    """
                    SELECT q.user_id
                    FROM queue q
                    WHERE q.user_id <> $1
                      AND ($2::text IS NULL OR q.sex = $2)
                      AND ($3::text IS NULL OR q.lang = $3)
                      AND ($4::bool = false OR q.adult_ok = true)
                      AND ($5::text IS NULL OR q.vibe = $5)
                      AND ($6::int IS NULL OR q.age BETWEEN $7 AND $8)
                      AND (
                        $9::text IS NULL OR q.interests IS NULL OR POSITION(','||$9||',' IN ','||q.interests||',') > 0
                      )
                      AND NOT EXISTS (
                        SELECT 1 FROM recent_pairs rp
                        WHERE rp.a_id = $1 AND rp.b_id = q.user_id AND rp.matched_at > $10
                      )
                    ORDER BY q.is_premium DESC, q.enqueued_at
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                    """,
                    user_id,
                    sex,
                    lang,
                    bool(adult_ok),
                    vibe,
                    age if isinstance(age, int) else None,
                    (age - 2) if isinstance(age, int) else None,
                    (age + 2) if isinstance(age, int) else None,
                    interests_csv,
                    now - self.window,
                )

                if not row:
                    # No partner — put self back into queue
                    await conn.execute(
                        "INSERT INTO queue(user_id, sex, age, lang, interests, vibe, adult_ok, is_premium, enqueued_at) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) ON CONFLICT (user_id) DO UPDATE SET sex=EXCLUDED.sex, age=EXCLUDED.age, lang=EXCLUDED.lang, interests=EXCLUDED.interests, vibe=EXCLUDED.vibe, adult_ok=EXCLUDED.adult_ok, is_premium=EXCLUDED.is_premium, enqueued_at=EXCLUDED.enqueued_at",
                        user_id, sex, age, lang, interests_csv, vibe, bool(adult_ok), bool(is_premium), now
                    )
                    return None

                partner_id = row["user_id"]

                # Remove partner from queue (row is locked by SKIP LOCKED)
                await conn.execute("DELETE FROM queue WHERE user_id = $1", partner_id)

                # Record pair + recent_pairs in both directions
                await conn.execute("INSERT INTO pairs(a_id,b_id,started_at) VALUES ($1,$2,$3) ON CONFLICT DO NOTHING", user_id, partner_id, now)
                await conn.execute("INSERT INTO recent_pairs(a_id,b_id,matched_at) VALUES ($1,$2,$3) ON CONFLICT (a_id,b_id) DO UPDATE SET matched_at=EXCLUDED.matched_at", user_id, partner_id, now)
                await conn.execute("INSERT INTO recent_pairs(a_id,b_id,matched_at) VALUES ($1,$2,$3) ON CONFLICT (a_id,b_id) DO UPDATE SET matched_at=EXCLUDED.matched_at", partner_id, user_id, now)

                return partner_id
