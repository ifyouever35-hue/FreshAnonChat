# match_core.py
# Core partner selection with filters and anti-rematch hook

from __future__ import annotations
from typing import Protocol, Callable, Optional, Dict, Any, List

class StoragePort(Protocol):
    async def get_waiting_users(self) -> List[int]: ...
    async def set_waiting(self, user_id: int, is_waiting: bool) -> None: ...
    async def get_user_profile(self, user_id: int) -> Dict[str, Any]: ...
    async def record_interaction(self, u1: int, u2: int) -> None: ...
    async def has_interacted_recently(self, u1: int, u2: int, minutes: int) -> bool: ...

Filter = Callable[[Dict[str, Any], Dict[str, Any]], bool]

def age_band_filter(window: int = 2) -> Filter:
    def _f(me: Dict[str, Any], cand: Dict[str, Any]) -> bool:
        a = me.get("age"); b = cand.get("age")
        try:
            return a is not None and b is not None and abs(int(a) - int(b)) <= window
        except Exception:
            return False
    return _f

def gender_preference_filter() -> Filter:
    def _f(me: Dict[str, Any], cand: Dict[str, Any]) -> bool:
        pref = (me.get("pref_gender") or "any").lower()
        if pref == "any":
            return True
        return (cand.get("gender") or "").lower() == pref
    return _f

def set_overlap_filter(key: str, min_overlap: int = 1) -> Filter:
    def _f(me: Dict[str, Any], cand: Dict[str, Any]) -> bool:
        a = me.get(key) or []
        b = cand.get(key) or []
        sa = set(map(str.lower, map(str, a)))
        sb = set(map(str.lower, map(str, b)))
        return len(sa & sb) >= min_overlap
    return _f

def premium_pairing_required_filter(flag_key: str = "premium_only") -> Filter:
    def _f(me: Dict[str, Any], cand: Dict[str, Any]) -> bool:
        if me.get(flag_key):
            return bool(cand.get("premium"))
        return True
    return _f

DEFAULT_FILTERS = [
    age_band_filter(window=2),
    gender_preference_filter(),
    set_overlap_filter("vibes", min_overlap=1),
    set_overlap_filter("interests", min_overlap=1),
    premium_pairing_required_filter(flag_key="premium_only"),
]

async def select_partner(me_id: int, store: StoragePort, filters: List[Filter], cooldown_min: int = 30) -> Optional[int]:
    candidates = await store.get_waiting_users()
    for cand_id in candidates:
        if cand_id == me_id:
            continue
        if await store.has_interacted_recently(me_id, cand_id, cooldown_min):
            continue
        me = await store.get_user_profile(me_id)
        cand = await store.get_user_profile(cand_id)
        if all(f(me, cand) for f in filters):
            return cand_id
    return None