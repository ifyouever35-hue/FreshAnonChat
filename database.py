import os
import time
import aiosqlite

DB_PATH = "users.db"

USERS_SQL = """
CREATE TABLE IF NOT EXISTS users (
    user_id        INTEGER PRIMARY KEY,
    gender         TEXT,
    age            INTEGER,
    language       TEXT,
    premium        INTEGER DEFAULT 0,
    waiting        INTEGER DEFAULT 0,
    interests      TEXT DEFAULT '',
    rating         INTEGER DEFAULT 200,
    chat_count     INTEGER DEFAULT 0,
    chat_reset_at  INTEGER DEFAULT 0,
    vibe           TEXT DEFAULT '',
    -- 18+ доступ
    adult_pass_expiry  INTEGER DEFAULT 0,  -- до какого времени оплачен 18+ (unix ts)
    adult_trial_used   INTEGER DEFAULT 0,  -- пробный доступ уже использован (0/1)
    adult_trial_until  INTEGER DEFAULT 0   -- если активен пробный доступ — до какого времени (unix ts)
);
"""

REPORTS_SQL = """
CREATE TABLE IF NOT EXISTS reports (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id     INTEGER NOT NULL,
    reporter_id   INTEGER NOT NULL,
    reason        TEXT    NOT NULL,
    penalty       INTEGER NOT NULL,
    created_at    INTEGER NOT NULL
);
"""

RATINGS_LOG_SQL = """
CREATE TABLE IF NOT EXISTS ratings_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    rater_id    INTEGER NOT NULL,
    target_id   INTEGER NOT NULL,
    created_at  INTEGER NOT NULL
);
"""

# ✨ Перманентные премиум-пользователи
PERMANENT_PREMIUM_USERS = {5129915553}

async def _ensure_columns(db):
    """Добавляем недостающие колонки без сброса базы."""
    cur = await db.execute("PRAGMA table_info(users)")
    cols = {row[1] for row in await cur.fetchall()}
    add = []
    if "interests" not in cols:
        add.append(("interests", "TEXT DEFAULT ''"))
    if "vibe" not in cols:
        add.append(("vibe", "TEXT DEFAULT ''"))
    if "adult_pass_expiry" not in cols:
        add.append(("adult_pass_expiry", "INTEGER DEFAULT 0"))
    if "adult_trial_used" not in cols:
        add.append(("adult_trial_used", "INTEGER DEFAULT 0"))
    if "adult_trial_until" not in cols:
        add.append(("adult_trial_until", "INTEGER DEFAULT 0"))
    for name, ddl in add:
        await db.execute(f"ALTER TABLE users ADD COLUMN {name} {ddl}")
    if add:
        await db.commit()

async def init_db(reset: bool = False):
    if reset and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(USERS_SQL)
        await db.execute(REPORTS_SQL)
        await db.execute(RATINGS_LOG_SQL)
        await _ensure_columns(db)
        await db.commit()

async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT gender, age, language, premium, interests, rating, chat_count, chat_reset_at, vibe,
                   adult_pass_expiry, adult_trial_used, adult_trial_until
            FROM users WHERE user_id = ?
        """, (user_id,))
        return await cur.fetchone()

async def save_user(user_id: int, gender: str, age: int, language: str, premium: int = 0, *, vibe: str = "", interests: str = ""):
    """Создать или обновить основные поля пользователя (с сохранением доп. полей)."""
    interests = (interests or "").strip().lower()
    vibe = (vibe or "").strip().lower()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, gender, age, language, premium, waiting, interests, rating, chat_count, chat_reset_at, vibe)
            VALUES (?, ?, ?, ?, ?, 0, ?, 200, 0, 0, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                gender=excluded.gender,
                age=excluded.age,
                language=excluded.language
        """, (user_id, gender, age, language, premium, interests, vibe))
        await db.commit()

async def update_user(user_id: int, *, gender: str = None, age: int = None, language: str = None,
                      premium: int = None, rating: int = None, vibe: str = None, interests: str = None):
    parts, params = [], []
    if gender is not None:
        parts.append("gender=?"); params.append(gender)
    if age is not None:
        parts.append("age=?"); params.append(age)
    if language is not None:
        parts.append("language=?"); params.append(language)
    if premium is not None:
        parts.append("premium=?"); params.append(premium)
    if rating is not None:
        parts.append("rating=?"); params.append(rating)
    if vibe is not None:
        parts.append("vibe=?"); params.append((vibe or "").strip().lower())
    if interests is not None:
        parts.append("interests=?"); params.append((interests or "").strip().lower())
    if not parts:
        return
    params.append(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE users SET {', '.join(parts)} WHERE user_id = ?", params)
        await db.commit()

# === Поиск / ожидание ===
async def set_waiting(user_id: int, waiting: int = 1):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET waiting=? WHERE user_id=?", (waiting, user_id))
        await db.commit()

async def get_waiting_users(language: str, age: int, gender: str | None,
                            vibe: str | None = None,
                            age_range: int = 2, min_rating: int = 0,
                            require_adult_access: bool = False):
    """
    Возвращает кандидатов: user_id, age, language, premium, rating, interests, vibe.
    Фильтры: waiting=1, язык, возраст, рейтинг, (пол), (вайб).
    Если require_adult_access=True — берём только с активным 18+ доступом.
    """
    min_age = max(0, age - age_range)
    max_age = age + age_range
    now = int(time.time())
    sql = """
        SELECT user_id, age, language, premium, rating, interests, vibe,
               adult_pass_expiry, adult_trial_until
        FROM users
        WHERE waiting=1 AND language=? AND age BETWEEN ? AND ? AND rating>=?
    """
    params = [language, min_age, max_age, min_rating]
    if gender:
        sql += " AND gender=?"; params.append(gender)
    if vibe:
        sql += " AND (vibe = ? OR vibe = '')"; params.append(vibe.strip().lower())
    if require_adult_access:
        sql += " AND (adult_pass_expiry > ? OR adult_trial_until > ?)"; params.extend([now, now])

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(sql, params)
        return await cur.fetchall()

# === Рейтинг / жалобы ===
async def adjust_rating(user_id: int, delta: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET rating = MAX(0, rating + ?) WHERE user_id = ?", (delta, user_id))
        await db.commit()

async def add_rating_log(rater_id: int, target_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO ratings_log (rater_id, target_id, created_at) VALUES (?, ?, ?)",
                         (rater_id, target_id, int(time.time())))
        await db.commit()

async def add_report(target_id: int, reporter_id: int, reason: str, penalty: int):
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO reports (target_id, reporter_id, reason, penalty, created_at) VALUES (?, ?, ?, ?, ?)",
            (target_id, reporter_id, reason, penalty, now)
        )
        await db.commit()

# === Ежедневная реабилитация ===
async def daily_rehabilitation():
    cutoff = int(time.time()) - 24 * 3600
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT user_id FROM users
            WHERE user_id NOT IN (SELECT target_id FROM reports WHERE created_at > ?)
        """, (cutoff,))
        users = await cur.fetchall()
        for (uid,) in users:
            await db.execute("UPDATE users SET rating = rating + 1 WHERE user_id = ?", (uid,))
        await db.commit()

# === 18+: доступ и пробный период ===
async def set_adult_pass(user_id: int, days: int):
    """Установить/продлить платный доступ на days дней (1/7/30)."""
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT adult_pass_expiry FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        current = row[0] if row else 0
        base = current if current and current > now else now
        new_expiry = base + days * 86400
        await db.execute("UPDATE users SET adult_pass_expiry=? WHERE user_id=?", (new_expiry, user_id))
        await db.commit()

async def can_use_adult_trial(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT adult_trial_used FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        return False if (row and row[0]) else True

async def start_adult_trial(user_id: int, hours: int = 3):
    now = int(time.time())
    until = now + hours * 3600
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET adult_trial_used=1, adult_trial_until=? WHERE user_id=?", (until, user_id))
        await db.commit()

async def adult_access_active(user_id: int) -> bool:
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT adult_pass_expiry, adult_trial_until FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        if not row:
            return False
        pass_exp, trial_until = row
        return (pass_exp and pass_exp > now) or (trial_until and trial_until > now)

# Заглушки/совместимость со старым кодом премиума
async def set_premium_expiry(user_id: int, months: int): pass
async def get_premium_expiry(user_id: int): return None
async def is_premium_active(user_id: int): return False
async def can_start_chat(a: int, b: int): return True
async def on_chat_started(user_id: int): pass
