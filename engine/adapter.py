# engine/adapter.py — keeps old function names so UI code stays untouched
from typing import Optional, Dict, Any
from .match_engine import enqueue_for_search, cancel_search, try_match, end_chat
from .database import init_db
from .database import _backend  # internal access for partner lookup

# Legacy-compatible names (no-op placeholders when not used by UI)
async def match_user(user_id: int, profile: Dict[str, Any]) -> Optional[int]:
    await enqueue_for_search(user_id, profile)
    return await try_match(user_id, profile)

async def remove_from_queue(user_id: int) -> None:
    await cancel_search(user_id)

async def get_partner_id(user_id: int) -> Optional[int]:
    """Return active partner if there is an ongoing pair (ended_at is NULL)."""
    # direct DB lookup on 'pairs' table
    # This relies on database implementation to expose a connection via _backend
    be = _backend
    if be is None:
        return None
    try:
        # SQLite path
        if be.__class__.__name__ == "_SQLite":
            import aiosqlite
            async with aiosqlite.connect(be.path) as db:
                cur = await db.execute("""
                  SELECT CASE WHEN user_a = ? THEN user_b ELSE user_a END AS partner
                    FROM pairs
                   WHERE ended_at IS NULL AND (user_a=? OR user_b=?)
                   ORDER BY started_at DESC LIMIT 1
                """, (user_id, user_id, user_id))
                row = await cur.fetchone()
                return row[0] if row else None
        else:
            # Postgres path
            async with be.pool.acquire() as con:
                row = await con.fetchrow("""
                  SELECT CASE WHEN user_a = $1 THEN user_b ELSE user_a END AS partner
                    FROM pairs
                   WHERE ended_at IS NULL AND (user_a=$1 OR user_b=$1)
                   ORDER BY started_at DESC LIMIT 1
                """, user_id)
                return int(row["partner"]) if row and row["partner"] is not None else None
    except Exception:
        return None

async def end_chat_legacy(user_id: int, partner_id: int) -> None:
    await end_chat(user_id, partner_id)

# Backward alias
end_chat = end_chat_legacy
