
# match_pg.py — Atomic matching on PostgreSQL using SKIP LOCKED
import asyncpg, os
from typing import Optional
from database import init_db, set_chat, get_active_partner

ANTI_REMATCH_MINUTES = int(os.getenv("ANTI_REMATCH_MINUTES", "120"))

def _gender_ok(wants: str, other: Optional[str]) -> bool:
    wants = (wants or "any").lower()
    if wants == "any": return True
    return (other or "").lower() == wants

async def init_pool():
    await init_db()

async def remove_from_queue(user_id: int):
    pool = await init_db()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM queue WHERE user_id=$1", user_id)

async def get_partner_id(user_id: int) -> Optional[int]:
    return await get_active_partner(user_id)

async def end_chat(a_id: int, b_id: int):
    from database import end_chat as _pg_end_chat
    await _pg_end_chat(a_id, b_id)

async def match_user(new_user_id: int) -> Optional[int]:
    pool = await init_db()
    async with pool.acquire() as conn:
        async with conn.transaction():
            me = await conn.fetchrow("SELECT * FROM queue WHERE user_id=$1", new_user_id)
            if not me:
                return None
            # Candidate selection ordered by time, filtered by prefs; lock one row
            cand = await conn.fetchrow("""
            SELECT q.*
            FROM queue q
            WHERE q.user_id <> $1
              AND ($2 = 'any' OR q.gender = $2)
              AND ($3 IS NULL OR q.age BETWEEN $3 AND COALESCE($4, 200))
              AND ($5 IS NULL OR q.age_min IS NULL OR $5 BETWEEN q.age_min AND COALESCE(q.age_max, 200))
              AND q.user_id NOT IN (
                  SELECT rp.user_b FROM recent_pairs rp
                  WHERE rp.user_a = $1 AND rp.ts > (now() - make_interval(mins => $6))
              )
            ORDER BY q.ts ASC
            FOR UPDATE SKIP LOCKED
            LIMIT 1
            """,
            new_user_id,
            (me["wants_gender"] or "any"),
            me["age_min"], me["age_max"],
            me["age"],
            ANTI_REMATCH_MINUTES
            )
            if not cand:
                return None
            # Create chat and pop both from queue
            await conn.execute("DELETE FROM queue WHERE user_id=ANY($1::BIGINT[])", [new_user_id, cand["user_id"]])
            await conn.execute("INSERT INTO recent_pairs (user_a,user_b) VALUES ($1,$2),($2,$1)", new_user_id, cand["user_id"])
            await conn.execute("INSERT INTO chats (user_a,user_b) VALUES ($1,$2)", new_user_id, cand["user_id"])
            return int(cand["user_id"])
