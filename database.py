
# database.py — PostgreSQL only, asyncpg pool + schema + helpers for Neverland
import os, asyncio
from typing import Any, Dict, List, Optional, Sequence, Tuple
import asyncpg
from datetime import datetime, timezone, timedelta

_PG_DSN = os.getenv("PG_DSN", "postgresql://freshanon:postgres123@127.0.0.1:5433/freshanon")
_POOL_MIN = int(os.getenv("PG_POOL_MIN", "1"))
_POOL_MAX = int(os.getenv("PG_POOL_MAX", "10"))
_POOL_TIMEOUT = float(os.getenv("PG_TIMEOUT", "10"))

_pool: Optional[asyncpg.Pool] = None

import logging

def _env(name: str, default=None):
    v = os.getenv(name, default)
    return v.strip() if isinstance(v, str) else v

_DB_URL = _env("DATABASE_URL") or _env("PG_DSN")
if not _DB_URL:
    _DB_HOST = _env("PGHOST", "127.0.0.1")
    _DB_PORT = int(_env("PGPORT", "5432"))
    _DB_NAME = _env("PGDATABASE", "freshanon")
    _DB_USER = _env("PGUSER", "freshanon")
    _DB_PASS = _env("PGPASSWORD", "postgres123")
    _DB_URL = f"postgresql://{_DB_USER}:{_DB_PASS}@{_DB_HOST}:{_DB_PORT}/{_DB_NAME}"

_POOL_MIN = int(_env("PG_POOL_MIN", "1"))
_POOL_MAX = int(_env("PG_POOL_MAX", "10"))
_POOL_TIMEOUT = float(_env("PG_TIMEOUT", "10"))

async def _ensure_pool() -> asyncpg.Pool:
    global _pool
    if _pool and not getattr(_pool, "_closed", False):
        return _pool
    last_err = None
    for attempt in range(1, 6):
        try:
            _pool = await asyncpg.create_pool(
                dsn=_DB_URL,
                min_size=_POOL_MIN,
                max_size=_POOL_MAX,
                timeout=_POOL_TIMEOUT,
                command_timeout=60,
            )
            async with _pool.acquire() as _conn:
                await _conn.execute("SELECT 1;")
            logging.info("[db] pool ready → %s", _DB_URL.replace(_DB_URL.split('@')[0].split('//')[1], "***", 1))
            return _pool
        except (asyncio.TimeoutError, ConnectionResetError, OSError, asyncpg.CannotConnectNowError, asyncpg.exceptions.ConnectionDoesNotExistError) as e:
            last_err = e
            import asyncio as _aio
            _attempt = attempt if attempt < 5 else 5
            _sec = _attempt
            try:
                _aio.get_running_loop()
                await _aio.sleep(_sec)
            except RuntimeError:
                import time as _t
                _t.sleep(_sec)
    raise last_err


# permanent premium (env-based fallback)
_PERMA_IDS_ENV = os.getenv("PERMANENT_PREMIUM_IDS", "")
PERMANENT_PREMIUM_USERS: List[int] = [int(x) for x in _PERMA_IDS_ENV.split(",") if x.strip().isdigit()]

SCHEMA_SQL = r'''
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    lang TEXT,
    age INT,
    gender TEXT,
    wants_gender TEXT DEFAULT 'any',
    age_min INT,
    age_max INT,
    vibe TEXT,
    interests TEXT,
    premium_until TIMESTAMPTZ,
    is_banned BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE IF NOT EXISTS premium_overrides (
    user_id BIGINT PRIMARY KEY,
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS queue (
    user_id BIGINT PRIMARY KEY,
    ts TIMESTAMPTZ NOT NULL DEFAULT now(),
    lang TEXT,
    age INT,
    gender TEXT,
    wants_gender TEXT DEFAULT 'any',
    age_min INT,
    age_max INT,
    vibe TEXT,
    interests TEXT
);
CREATE TABLE IF NOT EXISTS recent_pairs (
    user_a BIGINT NOT NULL,
    user_b BIGINT NOT NULL,
    ts TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS chats (
    id BIGSERIAL PRIMARY KEY,
    user_a BIGINT NOT NULL,
    user_b BIGINT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS ratings (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    delta INT NOT NULL,
    reason TEXT,
    ts TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS reports (
    id BIGSERIAL PRIMARY KEY,
    reporter_id BIGINT NOT NULL,
    target_id BIGINT NOT NULL,
    reason TEXT,
    ts TIMESTAMPTZ NOT NULL DEFAULT now()
);
'''

async def _ensure_schema(conn: asyncpg.Connection):
    await conn.execute(SCHEMA_SQL)

async def init_db() -> asyncpg.Pool:
    global _pool
    if _pool:
        return _pool
    _pool = await asyncpg.create_pool(
        dsn=_PG_DSN, min_size=_POOL_MIN, max_size=_POOL_MAX,
        timeout=_POOL_TIMEOUT
    )
    async with _pool.acquire() as conn:
        await _ensure_schema(conn)
    return _pool

# --- User CRUD ---

async def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    pool = await init_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)
        return dict(row) if row else None

async def save_user(user_id: int, gender: Optional[str]=None, age: Optional[int]=None, language: Optional[str]=None,
                    wants_gender: Optional[str]=None, age_min: Optional[int]=None, age_max: Optional[int]=None,
                    vibe: Optional[str]=None, interests: Optional[Sequence[str]]=None) -> None:
    pool = await init_db()
    async with pool.acquire() as conn:
        await conn.execute("""
        INSERT INTO users (user_id, gender, age, lang, wants_gender, age_min, age_max, vibe, interests, updated_at)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9, now())
        ON CONFLICT (user_id) DO UPDATE SET
            gender=COALESCE(EXCLUDED.gender, users.gender),
            age=COALESCE(EXCLUDED.age, users.age),
            lang=COALESCE(EXCLUDED.lang, users.lang),
            wants_gender=COALESCE(EXCLUDED.wants_gender, users.wants_gender),
            age_min=COALESCE(EXCLUDED.age_min, users.age_min),
            age_max=COALESCE(EXCLUDED.age_max, users.age_max),
            vibe=COALESCE(EXCLUDED.vibe, users.vibe),
            interests=COALESCE(EXCLUDED.interests, users.interests),
            updated_at=now()
        """, user_id, gender, age, language, wants_gender, age_min, age_max, vibe, list(interests) if interests else None)

async def update_user(user_id: int, **fields):
    if not fields:
        return
    cols = []
    vals = []
    i = 1
    for k, v in fields.items():
        cols.append(f"{k}=${i}")
        vals.append(v); i += 1
    set_sql = ", ".join(cols + ["updated_at=now()"])
    sql = f"UPDATE users SET {set_sql} WHERE user_id=${i}"
    vals.append(user_id)
    pool = await init_db()
    async with pool.acquire() as conn:
        await conn.execute(sql, *vals)

# --- Premium ---

async def set_premium_expiry(user_id: int, until: Optional[datetime]):
    pool = await init_db()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET premium_until=$1, updated_at=now() WHERE user_id=$2", until, user_id)

async def _permanent_premium_from_db(user_id: int) -> bool:
    pool = await init_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT 1 FROM premium_overrides WHERE user_id=$1", user_id)
        return row is not None

async def is_premium_active(user_id: int) -> bool:
    if user_id in PERMANENT_PREMIUM_USERS:
        return True
    if await _permanent_premium_from_db(user_id):
        return True
    pool = await init_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT premium_until FROM users WHERE user_id=$1", user_id)
        if not row: return False
        until = row["premium_until"]
        return bool(until and until > datetime.now(timezone.utc))

async def get_premium_expiry(user_id: int) -> Optional[datetime]:
    pool = await init_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT premium_until FROM users WHERE user_id=$1", user_id)
        return row["premium_until"] if row else None

# --- Queue & Matching helpers (used by match_pg) ---

async def set_waiting(user_id: int, waiting: bool, snapshot: Optional[Dict[str, Any]]=None):
    pool = await init_db()
    async with pool.acquire() as conn:
        if waiting:
            if snapshot is None:
                # snapshot from users
                u = await conn.fetchrow("SELECT lang, age, gender, wants_gender, age_min, age_max, vibe, interests FROM users WHERE user_id=$1", user_id)
                if not u:
                    return
                snapshot = dict(u)
            await conn.execute("""
            INSERT INTO queue (user_id, ts, lang, age, gender, wants_gender, age_min, age_max, vibe, interests)
            VALUES ($1, now(), $2,$3,$4,$5,$6,$7,$8,$9)
            ON CONFLICT (user_id) DO UPDATE SET
                ts=excluded.ts, lang=excluded.lang, age=excluded.age, gender=excluded.gender,
                wants_gender=excluded.wants_gender, age_min=excluded.age_min, age_max=excluded.age_max,
                vibe=excluded.vibe, interests=excluded.interests
            """, user_id, snapshot.get("lang"), snapshot.get("age"), snapshot.get("gender"),
                 snapshot.get("wants_gender","any"), snapshot.get("age_min"), snapshot.get("age_max"),
                 snapshot.get("vibe"), snapshot.get("interests"))
        else:
            await conn.execute("DELETE FROM queue WHERE user_id=$1", user_id)

async def get_waiting_users(limit: int = 100) -> List[int]:
    pool = await init_db()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM queue ORDER BY ts ASC LIMIT $1", limit)
        return [r["user_id"] for r in rows]

async def set_chat(a_id: int, b_id: int):
    if a_id == b_id:
        return
    pool = await init_db()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("DELETE FROM queue WHERE user_id=ANY($1::BIGINT[])", [a_id, b_id])
            await conn.execute("INSERT INTO recent_pairs (user_a,user_b) VALUES ($1,$2),($2,$1)", a_id, b_id)
            await conn.execute("INSERT INTO chats (user_a,user_b) VALUES ($1,$2)", a_id, b_id)

async def end_chat(a_id: int, b_id: int):
    pool = await init_db()
    async with pool.acquire() as conn:
        await conn.execute("""
        UPDATE chats SET ended_at=now()
        WHERE ended_at IS NULL AND (
            (user_a=$1 AND user_b=$2) OR (user_a=$2 AND user_b=$1)
        )
        """, a_id, b_id)

async def get_active_partner(user_id: int) -> Optional[int]:
    pool = await init_db()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
        SELECT CASE WHEN user_a=$1 THEN user_b ELSE user_a END AS partner
        FROM chats WHERE ended_at IS NULL AND (user_a=$1 OR user_b=$1)
        ORDER BY started_at DESC LIMIT 1
        """, user_id)
        return int(row["partner"]) if row else None

# --- Moderation / logs ---

async def adjust_rating(user_id: int, delta: int, reason: Optional[str]=None):
    pool = await init_db()
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO ratings (user_id, delta, reason) VALUES ($1,$2,$3)", user_id, delta, reason)

async def add_report(reporter_id: int, target_id: int, reason: Optional[str]=None):
    pool = await init_db()
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO reports (reporter_id, target_id, reason) VALUES ($1,$2,$3)", reporter_id, target_id, reason)

async def add_rating_log(*args, **kwargs):
    # Backward alias
    await adjust_rating(*args, **kwargs)

# --- Daily maintenance ---

async def daily_rehabilitation():
    # Placeholder for scheduled ops (e.g., decay negative rating flags)
    return

# --- Stats ---

async def get_stats() -> Dict[str, Any]:
    pool = await init_db()
    async with pool.acquire() as conn:
        total_users = await conn.fetchval("SELECT COUNT(*) FROM users")
        genders = await conn.fetch("SELECT COALESCE(gender,'unknown') g, COUNT(*) c FROM users GROUP BY 1")
        gender_map = {r["g"]: r["c"] for r in genders}
        premium_count = await conn.fetchval("""
            SELECT COUNT(*) FROM users WHERE premium_until > now()
        """) or 0
        premium_overrides = await conn.fetchval("SELECT COUNT(*) FROM premium_overrides") or 0
        active_chats = await conn.fetchval("SELECT COUNT(*) FROM chats WHERE ended_at IS NULL") or 0
        matches_today = await conn.fetchval("""
            SELECT COUNT(*) FROM chats WHERE started_at::date = now()::date
        """) or 0
        return {
            "users_total": total_users,
            "gender": gender_map,
            "premium_active": premium_count + premium_overrides,
            "active_chats": active_chats,
            "matches_today": matches_today,
        }

async def _ensure_pool():
    # Ensure a global asyncpg pool with sane defaults for Windows + Docker mapping.
    # Retries a few times on startup, forces IPv4, and avoids invalid server GUCs.
    global _POOL
    if _POOL and not getattr(_POOL, "_closed", False):
        return _POOL

    import os, asyncio, asyncpg, logging
    log = logging.getLogger(__name__)

    def _env(name, default=None):
        v = os.getenv(name)
        return v if v not in (None, "") else default

    host = _env("PGHOST", "127.0.0.1")
    try:
        port = int(_env("PGPORT", "5455"))
    except Exception:
        port = 5455
    user = _env("PGUSER", "neverland")
    password = _env("PGPASSWORD", "")
    database = _env("PGDATABASE", "fresh_anon_chat")
    max_size = int(_env("PGPOOL_MAX", "10"))

    delays = [0.5, 1.5, 3, 5]
    last_err = None

    for attempt, delay in enumerate(delays, 1):
        try:
            _POOL = await asyncpg.create_pool(
                host=host,
                port=port,
                user=user,
                password=password,
                database=database,
                min_size=0,
                max_size=max_size,
                timeout=10,
                command_timeout=60,
                server_settings={
                    "application_name": "FreshAnonChat",
                    "tcp_keepalives_idle": "10",
                    "tcp_keepalives_interval": "5",
                    "tcp_keepalives_count": "3",
                },
            )
            log.info(f"[db] pool ready -> {host}:{port}")
            return _POOL
        except Exception as e:
            last_err = e
            log.warning(f"[db] pool attempt {attempt}/{len(delays)} failed: {e}")
            await asyncio.sleep(delay)

    raise last_err
