import os
import time
import aiosqlite

DB_PATH = "users.db"

# ===== СХЕМА =====
TABLE_SQL = """
CREATE TABLE IF NOT EXISTS users (
    user_id        INTEGER PRIMARY KEY,
    gender         TEXT,
    age            INTEGER,
    language       TEXT,
    premium        INTEGER DEFAULT 0,
    waiting        INTEGER DEFAULT 0,
    interests      TEXT    DEFAULT '',
    rating         INTEGER DEFAULT 200,
    chat_count     INTEGER DEFAULT 0,
    chat_reset_at  INTEGER DEFAULT 0
);
"""

COLUMNS = {
    "user_id", "gender", "age", "language", "premium", "waiting",
    "interests", "rating", "chat_count", "chat_reset_at"
}

async def init_db(reset: bool = False):
    """
    Инициализация БД.
    reset=True — ВРЕМЕННО: удаляет файл и создаёт заново (удобно для тестов).
    """
    if reset and os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(TABLE_SQL)
        # миграции на случай старого файла без новых колонок
        cols = await _get_columns(db)
        to_add = COLUMNS - cols
        for col in to_add:
            if col == "interests":
                await db.execute("ALTER TABLE users ADD COLUMN interests TEXT DEFAULT ''")
            elif col == "rating":
                await db.execute("ALTER TABLE users ADD COLUMN rating INTEGER DEFAULT 200")
            elif col == "chat_count":
                await db.execute("ALTER TABLE users ADD COLUMN chat_count INTEGER DEFAULT 0")
            elif col == "chat_reset_at":
                await db.execute("ALTER TABLE users ADD COLUMN chat_reset_at INTEGER DEFAULT 0")
            elif col == "waiting":
                await db.execute("ALTER TABLE users ADD COLUMN waiting INTEGER DEFAULT 0")
            elif col == "premium":
                await db.execute("ALTER TABLE users ADD COLUMN premium INTEGER DEFAULT 0")
            # gender, age, language, user_id — базовые, если их нет, значит таблица новая
        await db.commit()

async def _get_columns(db) -> set:
    cur = await db.execute("PRAGMA table_info(users)")
    rows = await cur.fetchall()
    return {row[1] for row in rows}

# ===== Пользователь =====
async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT gender, age, language, premium, interests, rating, chat_count, chat_reset_at
            FROM users WHERE user_id = ?
        """, (user_id,))
        row = await cur.fetchone()
        return row if row else None

async def save_user(user_id: int, gender: str, age: int, language: str, premium: int = 0):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, gender, age, language, premium, waiting, interests, rating, chat_count, chat_reset_at)
            VALUES (?, ?, ?, ?, ?, 0, '', 200, 0, 0)
            ON CONFLICT(user_id) DO UPDATE SET
                gender=excluded.gender,
                age=excluded.age,
                language=excluded.language
        """, (user_id, gender, age, language, premium))
        await db.commit()

async def update_user(user_id: int, gender: str = None, age: int = None, language: str = None, premium: int = None):
    updates, params = [], []
    if gender is not None:
        updates.append("gender = ?"); params.append(gender)
    if age is not None:
        updates.append("age = ?"); params.append(age)
    if language is not None:
        updates.append("language = ?"); params.append(language)
    if premium is not None:
        updates.append("premium = ?"); params.append(premium)
    if not updates:
        return
    params.append(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?", params)
        await db.commit()

# ===== Премиум =====
async def set_premium(user_id: int, premium: int = 1):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET premium = ? WHERE user_id = ?", (premium, user_id))
        await db.commit()

# ===== Поиск =====
async def set_waiting(user_id: int, waiting: int = 1):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET waiting = ? WHERE user_id = ?", (waiting, user_id))
        await db.commit()

async def get_waiting(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT waiting FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        return row[0] if row else 0

async def get_waiting_users(language: str, age: int, gender: str = None, age_range: int = 2, require_intersection: set | None = None, min_rating: int = 0):
    """
    Возвращает список кандидатов (user_id, age, language, premium, rating, interests)
    waiting=1, совпадает язык, по возрасту с допуском age_range.
    Если gender задан — фильтруем. Если require_intersection — требуем пересечение интересов.
    """
    min_age = max(0, (age - age_range) if age is not None else 0)
    max_age = (age + age_range) if age is not None else 200
    query = """
        SELECT user_id, age, language, premium, rating, interests
        FROM users
        WHERE waiting = 1 AND language = ? AND age BETWEEN ? AND ? AND rating >= ?
    """
    params = [language, min_age, max_age, min_rating]
    if gender:
        query += " AND gender = ?"
        params.append(gender)
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(query, params)
        rows = await cur.fetchall()
        # фильтр по интересам (если задано)
        if require_intersection:
            result = []
            for r in rows:
                their_set = set(filter(None, (r[5] or "").split(",")))
                if their_set & require_intersection:
                    result.append(r)
            return result
        return rows

# ===== Интересы / Рейтинг / Лимиты =====
async def set_interests(user_id: int, interest_keys: list[str]):
    interests = ",".join(interest_keys)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET interests = ? WHERE user_id = ?", (interests, user_id))
        await db.commit()

async def get_interests(user_id: int) -> list[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT interests FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        if not row or not row[0]:
            return []
        return list(filter(None, row[0].split(",")))

async def adjust_rating(user_id: int, delta: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET rating = MAX(0, rating + ?) WHERE user_id = ?", (delta, user_id))
        await db.commit()

DAILY_FREE_CHATS = 150

async def can_start_chat(user_id: int, is_premium: bool) -> bool:
    if is_premium:
        return True
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT chat_count, chat_reset_at FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        if not row:
            return True
        chat_count, reset_at = row
        # сбросить ли счётчик?
        if reset_at == 0 or now >= reset_at:
            await db.execute("UPDATE users SET chat_count = 0, chat_reset_at = ? WHERE user_id = ?", (now + 24*3600, user_id))
            await db.commit()
            return True
        return chat_count < DAILY_FREE_CHATS

async def on_chat_started(user_id: int):
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        # если таймер не задан — задать на 24ч
        cur = await db.execute("SELECT chat_reset_at FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        reset_at = row[0] if row else 0
        if reset_at == 0 or now >= reset_at:
            reset_at = now + 24*3600
            await db.execute("UPDATE users SET chat_count = 0, chat_reset_at = ? WHERE user_id = ?", (reset_at, user_id))
        await db.execute("UPDATE users SET chat_count = chat_count + 1 WHERE user_id = ?", (user_id,))
        await db.commit()
