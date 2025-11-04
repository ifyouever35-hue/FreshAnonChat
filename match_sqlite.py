import time, os
from typing import Optional, List, Any
import aiosqlite
SQLITE_PATH = os.getenv("SQLITE_PATH", "users.db")
ANTI_REMATCH = os.getenv("ANTI_REMATCH", "0") == "1"
ANTI_REMATCH_MINUTES = int(os.getenv("ANTI_REMATCH_MINUTES", "120"))
CREATE_SQL = [
    '''
    CREATE TABLE IF NOT EXISTS queue (
        user_id INTEGER PRIMARY KEY,
        ts REAL,
        lang TEXT,
        age INTEGER,
        gender TEXT,
        wants_gender TEXT,
        age_min INTEGER,
        age_max INTEGER,
        vibe TEXT,
        interests TEXT
    )''',
    '''
    CREATE TABLE IF NOT EXISTS chats (
        pair_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user1 INTEGER,
        user2 INTEGER,
        started_at REAL
    )''',
    '''
    CREATE TABLE IF NOT EXISTS media_index (
        user_id INTEGER,
        kind TEXT,
        path TEXT,
        ts REAL
    )'''
]
if ANTI_REMATCH:
    CREATE_SQL.append('''
        CREATE TABLE IF NOT EXISTS recent_pairs (
            user1 INTEGER,
            user2 INTEGER,
            ts REAL
        )''')
async def init_db():
    async with aiosqlite.connect(SQLITE_PATH) as db:
        for sql in CREATE_SQL:
            await db.execute(sql)
        await db.commit()
def _csv_set(raw: Any) -> set[str]:
    if not raw: return set()
    if isinstance(raw, str):
        items = [x.strip().lower() for x in raw.split(",")]
    else:
        items = [str(x).strip().lower() for x in raw]
    return {x for x in items if x}
def _gender_ok(wants: str, partner_gender: Optional[str]) -> bool:
    if wants in (None, "", "any"): return True
    if partner_gender is None: return True
    return wants == partner_gender
def _score(me: dict, cand: dict) -> float:
    s_inter = _csv_set(me.get("interests")); c_inter = _csv_set(cand.get("interests"))
    score = len(s_inter & c_inter)
    if (me.get("vibe") or "").strip().lower() == (cand.get("vibe") or "").strip().lower() and me.get("vibe"):
        score += 0.5
    if (me.get("lang") or "").strip().lower() == (cand.get("lang") or "").strip().lower() and me.get("lang"):
        score += 0.2
    return score
async def add_to_queue(user_id: int, lang: str, age: int, gender: Optional[str],
                       wants_gender: str, age_min: int, age_max: int,
                       vibe: Optional[str], interests: List[str]):
    await init_db()
    interests_csv = ",".join(x.strip().lower() for x in (interests or []))
    async with aiosqlite.connect(SQLITE_PATH) as db:
        await db.execute(
            "REPLACE INTO queue(user_id, ts, lang, age, gender, wants_gender, age_min, age_max, vibe, interests) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (user_id, time.time(), lang, age, gender, wants_gender, age_min, age_max, vibe, interests_csv)
        )
        await db.commit()
async def remove_from_queue(user_id: int):
    async with aiosqlite.connect(SQLITE_PATH) as db:
        await db.execute("DELETE FROM queue WHERE user_id=?", (user_id,))
        await db.commit()
async def in_queue(user_id: int) -> bool:
    async with aiosqlite.connect(SQLITE_PATH) as db:
        async with db.execute("SELECT 1 FROM queue WHERE user_id=?", (user_id,)) as cur:
            return (await cur.fetchone()) is not None
async def set_chat(a: int, b: int):
    async with aiosqlite.connect(SQLITE_PATH) as db:
        now = time.time()
        await db.execute("INSERT INTO chats(user1, user2, started_at) VALUES(?,?,?)", (a, b, now))
        await db.execute("DELETE FROM queue WHERE user_id IN (?,?)", (a, b))
        if ANTI_REMATCH:
            await db.execute("INSERT INTO recent_pairs(user1, user2, ts) VALUES(?,?,?)", (a, b, now))
            await db.execute("INSERT INTO recent_pairs(user1, user2, ts) VALUES(?,?,?)", (b, a, now))
        await db.commit()
async def get_partner_id(my_id: int) -> Optional[int]:
    async with aiosqlite.connect(SQLITE_PATH) as db:
        async with db.execute("SELECT user2 FROM chats WHERE user1=? UNION SELECT user1 FROM chats WHERE user2=?", (my_id, my_id)) as cur:
            r = await cur.fetchone()
            return r[0] if r else None
async def end_chat(my_id: int) -> Optional[int]:
    async with aiosqlite.connect(SQLITE_PATH) as db:
        async with db.execute("SELECT pair_id, user1, user2 FROM chats WHERE user1=? OR user2=?", (my_id, my_id)) as cur:
            row = await cur.fetchone()
        if not row: return None
        pair_id, u1, u2 = row
        await db.execute("DELETE FROM chats WHERE pair_id=?", (pair_id,))
        await db.commit()
        return u2 if u1 == my_id else u1
async def _recent_rows(user_id: int):
    if not ANTI_REMATCH: return []
    async with aiosqlite.connect(SQLITE_PATH) as db:
        async with db.execute("SELECT user2, ts FROM recent_pairs WHERE user1=?", (user_id,)) as cur:
            return await cur.fetchall()
def _recent_blocked(rows, cand_id: int, now_ts: float) -> bool:
    win = ANTI_REMATCH_MINUTES * 60
    for u2, ts in rows:
        if u2 == cand_id and (now_ts - ts) < win:
            return True
    return False
async def try_match(new_user_id: int, profile_cb):
    await init_db()
    me = await profile_cb(new_user_id)
    if not me: return None
    now = time.time()
    rp_me = await _recent_rows(new_user_id)
    async with aiosqlite.connect(SQLITE_PATH) as db:
        async with db.execute("SELECT user_id, lang, age, gender, wants_gender, age_min, age_max, vibe, interests FROM queue WHERE user_id!=? ORDER BY ts ASC", (new_user_id,)) as cur:
            rows = await cur.fetchall()
    def age_ok_mutual(cand_age, me_lo, me_hi, me_age, cand_lo, cand_hi):
        if me_age is not None and not (cand_lo <= me_age <= cand_hi): return False
        if cand_age is not None and not (me_lo <= cand_age <= me_hi): return False
        return True
    pool = []
    for (uid, lang, age, gender, wants_gender, lo, hi, vibe, interests_csv) in rows:
        cand = dict(user_id=uid, lang=lang, age=age, gender=gender, wants_gender=wants_gender,
                    age_min=lo, age_max=hi, vibe=vibe, interests=interests_csv)
        if not age_ok_mutual(age, me.get("age_min"), me.get("age_max"), me.get("age"), lo, hi): continue
        if me.get("lang") and lang and me["lang"] != lang: continue
        if not _gender_ok(me.get("wants_gender", "any"), gender): continue
        pool.append(cand)
    if ANTI_REMATCH:
        filtered = []
        for cand in pool:
            rp_cand = await _recent_rows(cand["user_id"])
            if _recent_blocked(rp_me, cand["user_id"], now): continue
            if _recent_blocked(rp_cand, new_user_id, now): continue
            filtered.append(cand)
        pool = filtered
    if not pool: return None
    best = max(pool, key=lambda c: _score(me, c))
    await set_chat(new_user_id, best["user_id"])
    return best["user_id"]
