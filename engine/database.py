
"""
engine/database.py — Unified DB layer for FreshAnonChat
- SQLite by default
- Postgres (Docker) when USE_POSTGRES=1
Tables (auto-created):
  users(user_id PK, gender, age, language, premium, waiting, interests, rating, chat_count, chat_reset_at, vibe,
        adult_pass_expiry, adult_trial_used, adult_trial_until)
  queue(user_id PK, language, age, gender, vibe, require_adult, enqueued_at)
  pairs(user_a, user_b, started_at, ended_at NULL)
  recent_pairs(user_id, partner_id, matched_at) PK(user_id,partner_id)
  reports(...), ratings_log(...)
"""
import os, time
from typing import Optional, Tuple, List

USE_POSTGRES = int(os.getenv("USE_POSTGRES","0"))
SQLITE_PATH = os.getenv("SQLITE_PATH","./data/freshanon.sqlite3")
PG_DSN = os.getenv("PG_DSN","postgresql://freshanon:postgres!@localhost:5433/freshanon")

USERS_SQL = """
CREATE TABLE IF NOT EXISTS users (
  user_id              INTEGER PRIMARY KEY,
  gender               TEXT,
  age                  INTEGER,
  language             TEXT,
  premium              INTEGER DEFAULT 0,
  waiting              INTEGER DEFAULT 0,
  interests            TEXT DEFAULT '',
  rating               INTEGER DEFAULT 200,
  chat_count           INTEGER DEFAULT 0,
  chat_reset_at        INTEGER DEFAULT 0,
  vibe                 TEXT DEFAULT '',
  adult_pass_expiry    INTEGER DEFAULT 0,
  adult_trial_used     INTEGER DEFAULT 0,
  adult_trial_until    INTEGER DEFAULT 0
);
"""
QUEUE_SQL = """
CREATE TABLE IF NOT EXISTS queue (
  user_id       INTEGER PRIMARY KEY,
  language      TEXT,
  age           INTEGER,
  gender        TEXT,
  vibe          TEXT,
  require_adult INTEGER DEFAULT 0,
  enqueued_at   INTEGER
);
"""
PAIRS_SQL = """
CREATE TABLE IF NOT EXISTS pairs (
  user_a     INTEGER,
  user_b     INTEGER,
  started_at INTEGER,
  ended_at   INTEGER
);
"""
RECENT_PAIRS_SQL = """
CREATE TABLE IF NOT EXISTS recent_pairs (
  user_id     INTEGER,
  partner_id  INTEGER,
  matched_at  INTEGER,
  PRIMARY KEY (user_id, partner_id)
);
"""
REPORTS_SQL = """
CREATE TABLE IF NOT EXISTS reports (
  id          INTEGER PRIMARY KEY,
  reporter_id INTEGER,
  target_id   INTEGER,
  reason      TEXT,
  created_at  INTEGER
);
"""
RATINGS_LOG_SQL = """
CREATE TABLE IF NOT EXISTS ratings_log (
  id         INTEGER PRIMARY KEY,
  rater_id   INTEGER,
  target_id  INTEGER,
  created_at INTEGER
);
"""

# Public API
__all__ = [
  "init_db",
  "get_user", "save_user", "update_user",
  "set_waiting", "get_waiting_users",
  "enqueue_user", "dequeue_user", "dequeue_two_atomic",
  "record_pair_start", "record_pair_end",
  "add_recent_pair", "was_recent_pair",
  "add_report", "add_rating_log", "adjust_rating", "daily_rehabilitation",
  "set_adult_pass", "can_use_adult_trial", "start_adult_trial", "adult_access_active",
]

_backend = None

async def init_db(reset: bool=False):
    global _backend
    if USE_POSTGRES:
        _backend = _PG(PG_DSN)
    else:
        _backend = _SQLite(SQLITE_PATH)
    await _backend.init(reset)

# user/profile
async def get_user(user_id:int):
    return await _backend.get_user(user_id)

async def save_user(user_id:int, gender:str, age:int, language:str, premium:int=0, *, vibe:str="", interests:str=""):
    return await _backend.save_user(user_id, gender, age, language, premium, vibe=vibe, interests=interests)

async def update_user(user_id:int, **kwargs):
    return await _backend.update_user(user_id, **kwargs)

# waiting (SQLite fallback path)
async def set_waiting(user_id:int, waiting:int=1):
    return await _backend.set_waiting(user_id, waiting)

async def get_waiting_users(**kwargs):
    return await _backend.get_waiting_users(**kwargs)

# queue operations (PG path)
async def enqueue_user(user_id:int, language:str, age:int, gender:str|None, vibe:str|None, require_adult:bool):
    return await _backend.enqueue_user(user_id, language, age, gender, vibe, require_adult)

async def dequeue_user(user_id:int):
    return await _backend.dequeue_user(user_id)

async def dequeue_two_atomic(exclude_recent_of:int, within_secs:int=1800):
    return await _backend.dequeue_two_atomic(exclude_recent_of, within_secs)

# pairs
async def record_pair_start(a:int, b:int):
    return await _backend.record_pair_start(a,b)

async def record_pair_end(a:int, b:int):
    return await _backend.record_pair_end(a,b)

# recent pairs
async def add_recent_pair(a:int, b:int):
    return await _backend.add_recent_pair(a,b)

async def was_recent_pair(a:int, b:int, within_secs:int=1800)->bool:
    return await _backend.was_recent_pair(a,b,within_secs)

# misc
async def add_report(reporter_id:int, target_id:int, reason:str):
    return await _backend.add_report(reporter_id, target_id, reason)

async def add_rating_log(rater_id:int, target_id:int):
    return await _backend.add_rating_log(rater_id, target_id)

async def adjust_rating(user_id:int, delta:int):
    return await _backend.adjust_rating(user_id, delta)

async def daily_rehabilitation():
    return await _backend.daily_rehabilitation()

async def set_adult_pass(user_id:int, days:int):
    return await _backend.set_adult_pass(user_id, days)

async def can_use_adult_trial(user_id:int)->bool:
    return await _backend.can_use_adult_trial(user_id)

async def start_adult_trial(user_id:int, hours:int=24):
    return await _backend.start_adult_trial(user_id, hours)

async def adult_access_active(user_id:int)->bool:
    return await _backend.adult_access_active(user_id)

# --- Implementations ---
class _SQLite:
    def __init__(self, path:str):
        self.path = path
        import aiosqlite

    async def init(self, reset:bool):
        import aiosqlite, os
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        if reset and os.path.exists(self.path):
            os.remove(self.path)
        async with aiosqlite.connect(self.path) as db:
            await db.execute(USERS_SQL)
            await db.execute(QUEUE_SQL)
            await db.execute(PAIRS_SQL)
            await db.execute(RECENT_PAIRS_SQL)
            await db.execute(REPORTS_SQL)
            await db.execute(RATINGS_LOG_SQL)
            await db.commit()

    async def get_user(self, user_id:int):
        import aiosqlite
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("""
                SELECT gender, age, language, premium, interests, rating, chat_count, chat_reset_at, vibe,
                       adult_pass_expiry, adult_trial_used, adult_trial_until
                  FROM users WHERE user_id=?
            """,(user_id,))
            return await cur.fetchone()

    async def save_user(self, user_id:int, gender:str, age:int, language:str, premium:int, *, vibe:str, interests:str):
        import aiosqlite
        async with aiosqlite.connect(self.path) as db:
            await db.execute("""
              INSERT INTO users (user_id, gender, age, language, premium, waiting, interests, rating, chat_count, chat_reset_at, vibe)
              VALUES (?, ?, ?, ?, ?, 0, ?, 200, 0, 0, ?)
              ON CONFLICT(user_id) DO UPDATE SET gender=excluded.gender, age=excluded.age, language=excluded.language
            """,(user_id, gender, age, language, premium, (interests or "").lower(), (vibe or "").lower()))
            await db.commit()

    async def update_user(self, user_id:int, **kwargs):
        import aiosqlite
        allowed = ["gender","age","language","premium","rating","vibe","interests","waiting"]
        parts, params = [], []
        for k,v in kwargs.items():
            if k in allowed and v is not None:
                parts.append(f"{k}=?")
                params.append(v if k not in ("vibe","interests") else (v or "").lower())
        if not parts: return
        params.append(user_id)
        async with aiosqlite.connect(self.path) as db:
            await db.execute(f"UPDATE users SET {', '.join(parts)} WHERE user_id = ?", params)
            await db.commit()

    async def set_waiting(self, user_id:int, waiting:int=1):
        return await self.update_user(user_id, waiting=waiting)

    async def get_waiting_users(self, **kwargs):
        import aiosqlite, time as _t
        language = kwargs.get("language")
        age = kwargs.get("age")
        gender = kwargs.get("gender")
        vibe = (kwargs.get("vibe") or "").lower() if kwargs.get("vibe") else None
        age_range = kwargs.get("age_range",2)
        min_rating = kwargs.get("min_rating",0)
        require_adult_access = kwargs.get("require_adult_access", False)
        now = int(_t.time())
        min_age, max_age = age-age_range, age+age_range
        sql = """
          SELECT user_id, age, language, premium, rating, interests, vibe, adult_pass_expiry, adult_trial_until
            FROM users
           WHERE waiting=1 AND language=? AND age BETWEEN ? AND ? AND rating>=?
        """
        params = [language, min_age, max_age, min_rating]
        if gender:
            sql += " AND gender=?"; params.append(gender)
        if vibe:
            sql += " AND (vibe=? OR vibe='')"; params.append(vibe)
        if require_adult_access:
            sql += " AND (adult_pass_expiry > ? OR adult_trial_until > ?)"; params += [now, now]
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(sql, params)
            return await cur.fetchall()

    # queue for SQLite (best-effort, not truly atomic under concurrency)
    async def enqueue_user(self, user_id:int, language:str, age:int, gender:str|None, vibe:str|None, require_adult:bool):
        import aiosqlite, time as _t
        async with aiosqlite.connect(self.path) as db:
            await db.execute("""
              INSERT INTO queue (user_id, language, age, gender, vibe, require_adult, enqueued_at)
              VALUES (?, ?, ?, ?, ?, ?, ?)
              ON CONFLICT(user_id) DO UPDATE SET language=excluded.language, age=excluded.age,
                  gender=excluded.gender, vibe=excluded.vibe, require_adult=excluded.require_adult, enqueued_at=excluded.enqueued_at
            """,(user_id, language, age, gender, (vibe or "").lower() if vibe else None, 1 if require_adult else 0, int(_t.time())))
            await db.commit()

    async def dequeue_user(self, user_id:int):
        import aiosqlite
        async with aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM queue WHERE user_id=?", (user_id,))
            await db.commit()

    async def dequeue_two_atomic(self, exclude_recent_of:int, within_secs:int=1800):
        # SQLite: emulate with simple select; race conditions possible
        import aiosqlite, time as _t
        cutoff = int(_t.time()) - within_secs
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT user_id FROM queue ORDER BY enqueued_at LIMIT 10")
            ids = [r[0] for r in await cur.fetchall()]
            # filter by recent_pairs
            for a in ids:
                for b in ids:
                    if a==b or a==exclude_recent_of or b==exclude_recent_of: 
                        continue
                    # ensure not recent pair for (a,b) and (exclude_recent_of, a/b)
                    cur2 = await db.execute("SELECT 1 FROM recent_pairs WHERE user_id=? AND partner_id=? AND matched_at > ?", (a,b,cutoff))
                    if await cur2.fetchone(): 
                        continue
                    cur3 = await db.execute("SELECT 1 FROM recent_pairs WHERE user_id=? AND partner_id=? AND matched_at > ?", (exclude_recent_of,a,cutoff))
                    if await cur3.fetchone(): 
                        continue
                    # take pair a,b
                    await db.execute("DELETE FROM queue WHERE user_id IN (?,?)",(a,b))
                    await db.commit()
                    return a,b
        return None

    async def record_pair_start(self, a:int, b:int):
        import aiosqlite, time as _t
        now = int(_t.time())
        async with aiosqlite.connect(self.path) as db:
            await db.execute("INSERT INTO pairs (user_a, user_b, started_at, ended_at) VALUES (?,?,?,NULL)", (a,b,now))
            await db.commit()

    async def record_pair_end(self, a:int, b:int):
        import aiosqlite, time as _t
        now = int(_t.time())
        async with aiosqlite.connect(self.path) as db:
            await db.execute("""
              UPDATE pairs SET ended_at=? WHERE ended_at IS NULL AND (
                (user_a=? AND user_b=?) OR (user_a=? AND user_b=?)
              )
            """,(now,a,b,b,a))
            await db.commit()

    async def add_recent_pair(self, a:int, b:int):
        import aiosqlite, time as _t
        now = int(_t.time())
        async with aiosqlite.connect(self.path) as db:
            await db.executemany("INSERT OR REPLACE INTO recent_pairs (user_id, partner_id, matched_at) VALUES (?,?,?)", [(a,b,now),(b,a,now)])
            await db.commit()

    async def was_recent_pair(self, a:int, b:int, within_secs:int=1800)->bool:
        import aiosqlite, time as _t
        cutoff = int(_t.time()) - within_secs
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT 1 FROM recent_pairs WHERE user_id=? AND partner_id=? AND matched_at > ?", (a,b,cutoff))
            return (await cur.fetchone()) is not None

    async def add_report(self, reporter_id:int, target_id:int, reason:str):
        import aiosqlite, time as _t
        async with aiosqlite.connect(self.path) as db:
            await db.execute("INSERT INTO reports (reporter_id, target_id, reason, created_at) VALUES (?,?,?,?)",
                             (reporter_id, target_id, reason, int(_t.time())))
            await db.commit()

    async def add_rating_log(self, rater_id:int, target_id:int):
        import aiosqlite, time as _t
        async with aiosqlite.connect(self.path) as db:
            await db.execute("INSERT INTO ratings_log (rater_id, target_id, created_at) VALUES (?,?,?)",
                             (rater_id, target_id, int(_t.time())))
            await db.commit()

    async def adjust_rating(self, user_id:int, delta:int):
        import aiosqlite
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE users SET rating = MAX(0, rating + ?) WHERE user_id=?", (delta, user_id))
            await db.commit()

    async def daily_rehabilitation(self):
        # simple +1 to all without new reports in last 24h
        import aiosqlite, time as _t
        cutoff = int(_t.time()) - 86400
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT user_id FROM users WHERE user_id NOT IN (SELECT target_id FROM reports WHERE created_at > ?)", (cutoff,))
            for (uid,) in await cur.fetchall():
                await db.execute("UPDATE users SET rating = rating + 1 WHERE user_id = ?", (uid,))
            await db.commit()

    async def set_adult_pass(self, user_id:int, days:int):
        import aiosqlite, time as _t
        now = int(_t.time())
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT adult_pass_expiry FROM users WHERE user_id=?", (user_id,))
            row = await cur.fetchone()
            current = row[0] if row else 0
            base = current if current and current > now else now
            new_expiry = base + days*86400
            await db.execute("UPDATE users SET adult_pass_expiry=? WHERE user_id=?", (new_expiry, user_id))
            await db.commit()

    async def can_use_adult_trial(self, user_id:int)->bool:
        import aiosqlite
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT adult_trial_used FROM users WHERE user_id=?", (user_id,))
            row = await cur.fetchone()
            return not (row and row[0])

    async def start_adult_trial(self, user_id:int, hours:int=24):
        import aiosqlite, time as _t
        until = int(_t.time()) + hours*3600
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE users SET adult_trial_used=1, adult_trial_until=? WHERE user_id=?", (until, user_id))
            await db.commit()

    async def adult_access_active(self, user_id:int)->bool:
        import aiosqlite, time as _t
        now = int(_t.time())
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT adult_pass_expiry, adult_trial_until FROM users WHERE user_id=?", (user_id,))
            row = await cur.fetchone()
            if not row: return False
            return (row[0] and row[0]>now) or (row[1] and row[1]>now)


class _PG:
    def __init__(self, dsn:str):
        self.dsn = dsn
        self.pool = None
        import asyncpg

    async def init(self, reset:bool):
        import asyncpg
        self.pool = await asyncpg.create_pool(self.dsn, min_size=1, max_size=15, timeout=10)
        async with self.pool.acquire() as con:
            await con.execute(USERS_SQL)
            await con.execute(QUEUE_SQL)
            await con.execute(PAIRS_SQL)
            await con.execute(RECENT_PAIRS_SQL)
            await con.execute(REPORTS_SQL)
            await con.execute(RATINGS_LOG_SQL)
            # Helpful indexes
            await con.execute("CREATE INDEX IF NOT EXISTS idx_queue_enqueued ON queue(enqueued_at)")
            await con.execute("CREATE INDEX IF NOT EXISTS idx_recent_pairs_time ON recent_pairs(matched_at)")

    async def get_user(self, user_id:int):
        async with self.pool.acquire() as con:
            r = await con.fetchrow("""
              SELECT gender, age, language, premium, interests, rating, chat_count, chat_reset_at, vibe,
                     adult_pass_expiry, adult_trial_used, adult_trial_until
                FROM users WHERE user_id=$1
            """, user_id)
            return tuple(r) if r else None

    async def save_user(self, user_id:int, gender:str, age:int, language:str, premium:int, *, vibe:str, interests:str):
        async with self.pool.acquire() as con:
            await con.execute("""
              INSERT INTO users (user_id, gender, age, language, premium, waiting, interests, rating, chat_count, chat_reset_at, vibe)
              VALUES ($1,$2,$3,$4,$5,0,$6,200,0,0,$7)
              ON CONFLICT (user_id) DO UPDATE SET gender=EXCLUDED.gender, age=EXCLUDED.age, language=EXCLUDED.language
            """, user_id, gender, age, language, premium, (interests or "").lower(), (vibe or "").lower())

    async def update_user(self, user_id:int, **kwargs):
        parts, params = [], []
        for k in ["gender","age","language","premium","rating","vibe","interests","waiting"]:
            if k in kwargs and kwargs[k] is not None:
                parts.append(f"{k}=${len(params)+1}")
                params.append(kwargs[k] if k not in ("vibe","interests") else (kwargs[k] or "").lower())
        if not parts: return
        params.append(user_id)
        async with self.pool.acquire() as con:
            await con.execute(f"UPDATE users SET {', '.join(parts)} WHERE user_id=${len(params)}", *params)

    async def set_waiting(self, user_id:int, waiting:int=1):
        return await self.update_user(user_id, waiting=waiting)

    async def get_waiting_users(self, **kwargs):
        # Not used in PG atomic path, but keep parity for fallback usage
        language = kwargs.get("language")
        age = kwargs.get("age")
        gender = kwargs.get("gender")
        vibe = (kwargs.get("vibe") or "").lower() if kwargs.get("vibe") else None
        age_range = kwargs.get("age_range",2)
        min_rating = kwargs.get("min_rating",0)
        require_adult_access = kwargs.get("require_adult_access", False)
        now = int(time.time())
        min_age, max_age = age-age_range, age+age_range
        conditions = ["waiting=1", "language=$1", "age BETWEEN $2 AND $3", "rating>=$4"]
        params = [language, min_age, max_age, min_rating]
        if gender:
            conditions.append(f"gender=${len(params)+1}"); params.append(gender)
        if vibe:
            conditions.append(f"(vibe=${len(params)+1} OR vibe='')"); params.append(vibe)
        if require_adult_access:
            conditions.append(f"(adult_pass_expiry > ${len(params)+1} OR adult_trial_until > ${len(params)+2})")
            params += [now, now]
        sql = f"SELECT user_id, age, language, premium, rating, interests, vibe, adult_pass_expiry, adult_trial_until FROM users WHERE {' AND '.join(conditions)}"
        async with self.pool.acquire() as con:
            rows = await con.fetch(sql, *params)
            return [tuple(r) for r in rows]

    async def enqueue_user(self, user_id:int, language:str, age:int, gender:str|None, vibe:str|None, require_adult:bool):
        async with self.pool.acquire() as con:
            await con.execute("""
              INSERT INTO queue (user_id, language, age, gender, vibe, require_adult, enqueued_at)
              VALUES ($1,$2,$3,$4,$5,$6,$7)
              ON CONFLICT (user_id) DO UPDATE SET language=EXCLUDED.language, age=EXCLUDED.age, gender=EXCLUDED.gender,
                vibe=EXCLUDED.vibe, require_adult=EXCLUDED.require_adult, enqueued_at=EXCLUDED.enqueued_at
            """, user_id, language, age, gender, (vibe or "").lower() if vibe else None, 1 if require_adult else 0, int(time.time()))

    async def dequeue_user(self, user_id:int):
        async with self.pool.acquire() as con:
            await con.execute("DELETE FROM queue WHERE user_id=$1", user_id)

    async def dequeue_two_atomic(self, exclude_recent_of:int, within_secs:int=1800):
        # Atomic pair selection with FOR UPDATE SKIP LOCKED
        cutoff = int(time.time()) - within_secs
        async with self.pool.acquire() as con:
            async with con.transaction():
                # Lock a small batch to reduce contention
                rows = await con.fetch("""
                  SELECT user_id FROM queue
                   ORDER BY enqueued_at
                   LIMIT 12
                   FOR UPDATE SKIP LOCKED
                """)
                ids = [r["user_id"] for r in rows]
                if len(ids) < 2:
                    return None
                # filter recent pairs
                def recent(a,b): return False
                for i,a in enumerate(ids):
                    for b in ids[i+1:]:
                        # check recent a-b
                        r = await con.fetchrow("SELECT 1 FROM recent_pairs WHERE user_id=$1 AND partner_id=$2 AND matched_at > $3", a,b,cutoff)
                        if r: continue
                        r = await con.fetchrow("SELECT 1 FROM recent_pairs WHERE user_id=$1 AND partner_id=$2 AND matched_at > $3", exclude_recent_of,a,cutoff)
                        if r: continue
                        r = await con.fetchrow("SELECT 1 FROM recent_pairs WHERE user_id=$1 AND partner_id=$2 AND matched_at > $3", exclude_recent_of,b,cutoff)
                        if r: continue
                        # take pair
                        await con.execute("DELETE FROM queue WHERE user_id = ANY($1::int[])", [a,b])
                        return a,b
                return None

    async def record_pair_start(self, a:int, b:int):
        async with self.pool.acquire() as con:
            await con.execute("INSERT INTO pairs (user_a, user_b, started_at, ended_at) VALUES ($1,$2,$3,NULL)", a,b,int(time.time()))

    async def record_pair_end(self, a:int, b:int):
        async with self.pool.acquire() as con:
            await con.execute("""
              UPDATE pairs SET ended_at=$1 WHERE ended_at IS NULL AND (
                (user_a=$2 AND user_b=$3) OR (user_a=$3 AND user_b=$2)
              )
            """, int(time.time()), a, b)

    async def add_recent_pair(self, a:int, b:int):
        async with self.pool.acquire() as con:
            now = int(time.time())
            await con.execute("""
              INSERT INTO recent_pairs (user_id, partner_id, matched_at) VALUES ($1,$2,$3)
              ON CONFLICT (user_id, partner_id) DO UPDATE SET matched_at=EXCLUDED.matched_at
            """, a,b,now)
            await con.execute("""
              INSERT INTO recent_pairs (user_id, partner_id, matched_at) VALUES ($1,$2,$3)
              ON CONFLICT (user_id, partner_id) DO UPDATE SET matched_at=EXCLUDED.matched_at
            """, b,a,now)

    async def was_recent_pair(self, a:int, b:int, within_secs:int=1800)->bool:
        async with self.pool.acquire() as con:
            cutoff = int(time.time()) - within_secs
            r = await con.fetchrow("SELECT 1 FROM recent_pairs WHERE user_id=$1 AND partner_id=$2 AND matched_at > $3", a,b,cutoff)
            return r is not None

    async def add_report(self, reporter_id:int, target_id:int, reason:str):
        async with self.pool.acquire() as con:
            await con.execute("INSERT INTO reports (reporter_id, target_id, reason, created_at) VALUES ($1,$2,$3,$4)",
                              reporter_id, target_id, reason, int(time.time()))

    async def add_rating_log(self, rater_id:int, target_id:int):
        async with self.pool.acquire() as con:
            await con.execute("INSERT INTO ratings_log (rater_id, target_id, created_at) VALUES ($1,$2,$3)",
                              rater_id, target_id, int(time.time()))

    async def adjust_rating(self, user_id:int, delta:int):
        async with self.pool.acquire() as con:
            await con.execute("UPDATE users SET rating = GREATEST(0, rating + $1) WHERE user_id=$2", delta, user_id)

    async def daily_rehabilitation(self):
        async with self.pool.acquire() as con:
            cutoff = int(time.time()) - 86400
            users = await con.fetch("SELECT user_id FROM users WHERE user_id NOT IN (SELECT target_id FROM reports WHERE created_at > $1)", cutoff)
            for r in users:
                await con.execute("UPDATE users SET rating = rating + 1 WHERE user_id=$1", r["user_id"])

    async def set_adult_pass(self, user_id:int, days:int):
        async with self.pool.acquire() as con:
            now = int(time.time())
            row = await con.fetchrow("SELECT adult_pass_expiry FROM users WHERE user_id=$1", user_id)
            current = row["adult_pass_expiry"] if row and row["adult_pass_expiry"] else 0
            base = current if current and current > now else now
            new_expiry = base + days*86400
            await con.execute("UPDATE users SET adult_pass_expiry=$1 WHERE user_id=$2", new_expiry, user_id)

    async def can_use_adult_trial(self, user_id:int)->bool:
        async with self.pool.acquire() as con:
            row = await con.fetchrow("SELECT adult_trial_used FROM users WHERE user_id=$1", user_id)
            return not (row and row["adult_trial_used"])

    async def start_adult_trial(self, user_id:int, hours:int=24):
        async with self.pool.acquire() as con:
            until = int(time.time()) + hours*3600
            await con.execute("UPDATE users SET adult_trial_used=1, adult_trial_until=$1 WHERE user_id=$2", until, user_id)

    async def adult_access_active(self, user_id:int)->bool:
        async with self.pool.acquire() as con:
            now = int(time.time())
            row = await con.fetchrow("SELECT adult_pass_expiry, adult_trial_until FROM users WHERE user_id=$1", user_id)
            return bool(row and ((row["adult_pass_expiry"] and row["adult_pass_expiry"]>now) or (row["adult_trial_until"] and row["adult_trial_until"]>now)))
