# database.py — PostgreSQL only, asyncpg + pool, RU/EN Neverland
import os
import asyncio
import logging
from typing import Optional, List, Tuple, Any, Dict
from datetime import datetime, timedelta

import asyncpg

# ==========================
# Конфиг подключения к PG
# ==========================
PG_DSN = os.getenv(
    "PG_DSN",
    # ОБРАТИ ВНИМАНИЕ: IPv4 и явный порт. Поменяй пароль/порт при необходимости.
    "postgresql://freshanon:postgres123@127.0.0.1:5433/freshanon?sslmode=disable",
)
PG_POOL_MIN = int(os.getenv("PG_POOL_MIN", "1"))
PG_POOL_MAX = int(os.getenv("PG_POOL_MAX", "10"))
PG_TIMEOUT  = float(os.getenv("PG_TIMEOUT", "10"))

# Премиум «навсегда» (друзья) — через env-список ID
# пример: PERMANENT_PREMIUM_IDS="111,222,333"
_PERMA_ENV = os.getenv("PERMANENT_PREMIUM_IDS", "").strip()
PERMANENT_PREMIUM_USERS = {
    int(x) for x in (_PERMA_ENV.split(",") if _PERMA_ENV else []) if x.strip().isdigit()
}

# Глобальный пул
_POOL: Optional[asyncpg.Pool] = None

async def _ensure_pool() -> asyncpg.Pool:
    """Создаёт пул с ретраями (устойчив к «connection was closed in the middle of operation»)."""
    global _POOL
    if _POOL is not None:
        return _POOL

    last_err = None
    for attempt in range(1, 4):
        try:
            _POOL = await asyncpg.create_pool(
                dsn=PG_DSN,
                min_size=PG_POOL_MIN,
                max_size=PG_POOL_MAX,
                timeout=PG_TIMEOUT,
                command_timeout=PG_TIMEOUT,
                server_settings={"application_name": "neverland_bot"},
            )
            return _POOL
        except Exception as e:
            last_err = e
            logging.warning(f"[db] pool attempt {attempt}/3 failed: {e}")
            await asyncio.sleep(0.35 * attempt)
    raise last_err  # пусть увидим первопричину

# ==========================
# Инициализация схемы
# ==========================
INIT_SQL = """
CREATE TABLE IF NOT EXISTS users (
    user_id         BIGINT PRIMARY KEY,
    gender          TEXT NOT NULL,          -- 'male' / 'female'
    age             INTEGER NOT NULL,
    language        TEXT NOT NULL,          -- 'ru' / 'en'
    interests       TEXT DEFAULT '',        -- свободная строка (через запятую)
    rating          INTEGER NOT NULL DEFAULT 0,
    premium_until   TIMESTAMPTZ NULL,       -- премиум до даты
    waiting         BOOLEAN NOT NULL DEFAULT FALSE,
    vibe            TEXT NOT NULL DEFAULT '',  -- 'funny','calm',...
    premium_forever BOOLEAN NOT NULL DEFAULT FALSE, -- доп. флаг
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS reports (
    id         BIGSERIAL PRIMARY KEY,
    target     BIGINT NOT NULL,
    rater      BIGINT NOT NULL,
    reason     TEXT NOT NULL,
    penalty    INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rating_log (
    id         BIGSERIAL PRIMARY KEY,
    rater      BIGINT NOT NULL,
    target     BIGINT NOT NULL,
    delta      INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- опционально: журнал пар (для статистики / мониторинга)
CREATE TABLE IF NOT EXISTS pairs (
    id         BIGSERIAL PRIMARY KEY,
    user_a     BIGINT NOT NULL,
    user_b     BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- индексы под быстрый поиск
CREATE INDEX IF NOT EXISTS idx_users_waiting ON users (waiting);
CREATE INDEX IF NOT EXISTS idx_users_lang    ON users (language);
CREATE INDEX IF NOT EXISTS idx_users_gender  ON users (gender);
CREATE INDEX IF NOT EXISTS idx_users_age     ON users (age);
CREATE INDEX IF NOT EXISTS idx_users_rating  ON users (rating);
CREATE INDEX IF NOT EXISTS idx_users_vibe    ON users (vibe);
"""

TRIGGER_SQL = """
-- Триггер updated_at (если ещё не создан)
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'users_set_updated_at'
  ) THEN
    CREATE TRIGGER users_set_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
  END IF;
END$$;
"""

async def init_db():
    pool = await _ensure_pool()
    async with pool.acquire() as con:
        async with con.transaction():
            await con.execute(INIT_SQL)
            await con.execute(TRIGGER_SQL)
    logging.info("[db] schema ready")

# ==========================
# CRUD по пользователям
# ==========================
# ВАЖНО: Для совместимости с твоим bot_2.py возвращаем tuple с индексами:
# 0: gender, 1: age, 2: language, 3: reserved(''), 4: interests,
# 5: rating, 6: premium_until_epoch, 7: waiting, 8: vibe
# (именно так ты обращаешься к user[8], user[4], user[5] и т.д.)
USER_SELECT = """
SELECT
  gender,                      -- 0
  age,                         -- 1
  language,                    -- 2
  ''      AS reserved,         -- 3 (заглушка для совместимости)
  interests,                   -- 4
  rating,                      -- 5
  EXTRACT(EPOCH FROM premium_until)::BIGINT AS premium_until_epoch, -- 6
  waiting,                     -- 7
  vibe                         -- 8
FROM users
WHERE user_id = $1
"""

async def get_user(user_id: int) -> Optional[Tuple[Any, ...]]:
    pool = await _ensure_pool()
    async with pool.acquire() as con:
        row = await con.fetchrow(USER_SELECT, user_id)
        if not row:
            return None
        return tuple(row)

async def save_user(user_id: int, gender: str, age: int, language: str) -> None:
    pool = await _ensure_pool()
    async with pool.acquire() as con:
        await con.execute(
            """
            INSERT INTO users (user_id, gender, age, language)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id) DO UPDATE
            SET gender = EXCLUDED.gender,
                age    = EXCLUDED.age,
                language = EXCLUDED.language
            """,
            user_id, gender, age, language
        )

async def update_user(
    user_id: int,
    *,
    age: Optional[int] = None,
    gender: Optional[str] = None,
    language: Optional[str] = None,
    interests: Optional[str] = None,
    vibe: Optional[str] = None,
) -> None:
    sets = []
    args: List[Any] = []
    if age is not None:
        sets.append("age = $" + str(len(args) + 1)); args.append(age)
    if gender is not None:
        sets.append("gender = $" + str(len(args) + 1)); args.append(gender)
    if language is not None:
        sets.append("language = $" + str(len(args) + 1)); args.append(language)
    if interests is not None:
        sets.append("interests = $" + str(len(args) + 1)); args.append(interests)
    if vibe is not None:
        sets.append("vibe = $" + str(len(args) + 1)); args.append(vibe)
    if not sets:
        return
    args.append(user_id)
    sql = f"UPDATE users SET {', '.join(sets)} WHERE user_id = ${len(args)}"
    pool = await _ensure_pool()
    async with pool.acquire() as con:
        await con.execute(sql, *args)

async def set_waiting(user_id: int, flag: int | bool) -> None:
    pool = await _ensure_pool()
    async with pool.acquire() as con:
        await con.execute(
            "UPDATE users SET waiting = $1 WHERE user_id = $2",
            bool(flag), user_id
        )

async def get_waiting_users(
    *,
    language: str,
    age: int,
    gender: Optional[str],
    vibe: Optional[str],
    age_range: int,
    min_rating: int,
    require_adult_access: bool = False,   # игнорируется по ТЗ (18+ отключено)
) -> List[Tuple[int]]:
    """
    Возвращает [(user_id,), ...] подходящих кандидатов из очереди.
    """
    pool = await _ensure_pool()
    params: List[Any] = [language, min_rating, age - age_range, age + age_range]
    filters = [
        "waiting = TRUE",
        "language = $1",
        "rating >= $2",
        "age BETWEEN $3 AND $4",
    ]
    idx = 5
    if gender in ("male", "female"):
        filters.append(f"gender = ${idx}"); params.append(gender); idx += 1
    if vibe:
        filters.append(f"(vibe = ${idx})"); params.append(vibe); idx += 1

    sql = f"SELECT user_id FROM users WHERE {' AND '.join(filters)} ORDER BY rating DESC, created_at ASC LIMIT 200"
    async with pool.acquire() as con:
        rows = await con.fetch(sql, *params)
        return [(r["user_id"],) for r in rows]

# ==========================
# Premium
# ==========================
async def set_premium_expiry(user_id: int, months: int) -> None:
    """
    Устанавливает/продлевает премиум на months месяцев.
    (Используем +30 дней * months, чтобы не тащить dateutil)
    """
    pool = await _ensure_pool()
    async with pool.acquire() as con:
        dt = datetime.utcnow() + timedelta(days=30 * max(1, months))
        await con.execute(
            "UPDATE users SET premium_until = $1 WHERE user_id = $2",
            dt, user_id
        )

async def get_premium_expiry(user_id: int) -> Optional[int]:
    pool = await _ensure_pool()
    async with pool.acquire() as con:
        row = await con.fetchrow(
            "SELECT EXTRACT(EPOCH FROM premium_until)::BIGINT AS ts FROM users WHERE user_id = $1",
            user_id
        )
        return int(row["ts"]) if row and row["ts"] is not None else None

async def is_premium_active(user_id: int) -> bool:
    if user_id in PERMANENT_PREMIUM_USERS:
        return True
    pool = await _ensure_pool()
    async with pool.acquire() as con:
        row = await con.fetchrow(
            "SELECT (premium_forever OR (premium_until IS NOT NULL AND premium_until > now())) AS active "
            "FROM users WHERE user_id = $1",
            user_id
        )
        return bool(row["active"]) if row else False

# ==========================
# Рейтинг / жалобы
# ==========================
async def adjust_rating(user_id: int, delta: int) -> None:
    pool = await _ensure_pool()
    async with pool.acquire() as con:
        await con.execute(
            """
            UPDATE users
            SET rating = GREATEST(-100, LEAST(100, rating + $1))
            WHERE user_id = $2
            """,
            delta, user_id
        )

async def add_rating_log(rater: int, target: int, delta: int = 0) -> None:
    pool = await _ensure_pool()
    async with pool.acquire() as con:
        await con.execute(
            "INSERT INTO rating_log (rater, target, delta) VALUES ($1, $2, $3)",
            rater, target, delta
        )

async def add_report(target: int, rater: int, reason: str, penalty: int = 15) -> None:
    pool = await _ensure_pool()
    async with pool.acquire() as con:
        async with con.transaction():
            await con.execute(
                "INSERT INTO reports (target, rater, reason, penalty) VALUES ($1, $2, $3, $4)",
                target, rater, reason, penalty
            )
            await con.execute(
                """
                UPDATE users
                SET rating = GREATEST(-100, rating - $1)
                WHERE user_id = $2
                """,
                penalty, target
            )

# ==========================
# Реабилитация (раз в сутки)
# ==========================
async def daily_rehabilitation() -> None:
    """
    Простая «реабилитация» рейтинга: +1 всем, у кого рейтинг < 50.
    """
    pool = await _ensure_pool()
    async with pool.acquire() as con:
        await con.execute(
            "UPDATE users SET rating = LEAST(50, rating + 1) WHERE rating < 50"
        )

# ==========================
# Статистика для вебморды
# ==========================
async def get_stats() -> Dict[str, Any]:
    """
    Аккуратная версия: использует пул, не создаёт одиночных соединений.
    Возвращает {"ok": True, "data": {...}} либо кидает исключение
    (которое перехватит FastAPI и вернёт 503).
    """
    pool = await _ensure_pool()
    async with pool.acquire() as con:
        data: Dict[str, Any] = {}

        # пользователи
        row = await con.fetchrow("SELECT COUNT(*) AS c FROM users;")
        data["users_total"] = int(row["c"]) if row else 0

        row = await con.fetchrow("SELECT COUNT(*) AS c FROM users WHERE gender='male';")
        data["users_male"] = int(row["c"]) if row else 0

        row = await con.fetchrow("SELECT COUNT(*) AS c FROM users WHERE gender='female';")
        data["users_female"] = int(row["c"]) if row else 0

        # премиум
        row = await con.fetchrow(
            "SELECT COUNT(*) AS c FROM users WHERE premium_forever OR (premium_until IS NOT NULL AND premium_until > now());"
        )
        data["premium_users"] = int(row["c"]) if row else 0

        # в очереди
        row = await con.fetchrow("SELECT COUNT(*) AS c FROM users WHERE waiting = TRUE;")
        data["waiting_now"] = int(row["c"]) if row else 0

        # пары (если таблица используется)
        try:
            row = await con.fetchrow("SELECT COUNT(*) AS c FROM pairs;")
            data["pairs_total"] = int(row["c"]) if row else 0
        except Exception:
            data["pairs_total"] = 0

        # распределение по языкам
        rows = await con.fetch("SELECT language, COUNT(*) AS c FROM users GROUP BY language;")
        data["by_language"] = {r["language"]: int(r["c"]) for r in rows}

        # распределение по вайбу
        rows = await con.fetch("SELECT vibe, COUNT(*) AS c FROM users WHERE vibe <> '' GROUP BY vibe;")
        data["by_vibe"] = {r["vibe"]: int(r["c"]) for r in rows}

        return {"ok": True, "data": data}
