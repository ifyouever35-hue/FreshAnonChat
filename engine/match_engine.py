
"""
engine/match_engine.py — Framework-agnostic matching engine.
Functions expected by handlers/UI-layer:
  - enqueue_for_search(user_id, profile_dict)
  - cancel_search(user_id)
  - try_match(user_id, profile_dict) -> partner_id | None
  - end_chat(user_id, partner_id)
Notes:
  * If USE_POSTGRES=1 → atomic queue match with SKIP LOCKED.
  * Else → fallback via users.waiting + best-effort filtering.
"""

import os, random
from typing import Optional, Dict, Any
from .database import (
    init_db,
    set_waiting, get_waiting_users,
    enqueue_user, dequeue_user, dequeue_two_atomic,
    add_recent_pair, was_recent_pair,
    record_pair_start, record_pair_end,
)

USE_POSTGRES = int(os.getenv("USE_POSTGRES","0"))

async def enqueue_for_search(user_id:int, profile:Dict[str,Any]) -> None:
    """
    profile: {language:str, age:int, gender:Optional[str], vibe:Optional[str], require_adult:bool}
    """
    if USE_POSTGRES:
        await enqueue_user(user_id, profile["language"], profile["age"], profile.get("gender"), profile.get("vibe"), profile.get("require_adult", False))
    else:
        # fallback: mark waiting in users table
        await set_waiting(user_id, 1)

async def cancel_search(user_id:int) -> None:
    if USE_POSTGRES:
        await dequeue_user(user_id)
    else:
        await set_waiting(user_id, 0)

async def try_match(user_id:int, profile:Dict[str,Any]) -> Optional[int]:
    """Return partner_id when matched (and perform bookkeeping), else None."""
    if USE_POSTGRES:
        pair = await dequeue_two_atomic(exclude_recent_of=user_id, within_secs=1800)
        if pair is None:
            return None
        a,b = pair
        partner = b if a == user_id else a
        await add_recent_pair(a,b)
        await record_pair_start(a,b)
        return partner if user_id in (a,b) else None
    else:
        candidates = await get_waiting_users(language=profile["language"], age=profile["age"],
                                            gender=profile.get("gender"), vibe=profile.get("vibe"),
                                            age_range=profile.get("age_range",2), min_rating=0,
                                            require_adult_access=profile.get("require_adult", False))
        pool = [row[0] for row in candidates if row[0] != user_id]
        pool = [cid for cid in pool if not await was_recent_pair(user_id, cid, within_secs=1800)]
        if not pool:
            return None
        partner_id = random.choice(pool)
        # finalize: stop waiting
        await set_waiting(user_id, 0)
        await set_waiting(partner_id, 0)
        await add_recent_pair(user_id, partner_id)
        await record_pair_start(user_id, partner_id)
        return partner_id

async def end_chat(user_id:int, partner_id:int) -> None:
    await record_pair_end(user_id, partner_id)
    # If in PG queue — do nothing; if SQLite path was used — users will re-enqueue on next search
    return None
