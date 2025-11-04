from typing import Optional
from .repo_pg import PGRepo

_repo: Optional[PGRepo] = None

async def init_matching(dsn: str, *, pool_min:int=1, pool_max:int=15, timeout_ms:int=5000, recent_window_sec:int=3600):
    global _repo
    _repo = PGRepo(dsn, pool_min=pool_min, pool_max=pool_max, timeout_ms=timeout_ms, anti_rematch_window_sec=recent_window_sec)
    await _repo.init()

async def close():
    if _repo:
        await _repo.close()

# Donor-like API
async def enqueue(user_id: int, **prefs):
    assert _repo, "Call init_matching() first"
    await _repo.enqueue(user_id, **prefs)

async def remove_from_queue(user_id: int):
    assert _repo, "Call init_matching() first"
    await _repo.dequeue(user_id)

async def match_user(user_id: int, **prefs) -> Optional[int]:
    assert _repo, "Call init_matching() first"
    return await _repo.match_user(user_id, **prefs)

async def end_chat(a_id: int, b_id: int):
    assert _repo, "Call init_matching() first"
    await _repo.end_chat(a_id, b_id)

# Compatibility API with existing UI
async def set_waiting(user_id: int, is_waiting: bool, **prefs):
    if is_waiting:
        await enqueue(user_id, **prefs)
    else:
        await remove_from_queue(user_id)

async def get_partner_id(user_id: int, **prefs):
    return await match_user(user_id, **prefs)
