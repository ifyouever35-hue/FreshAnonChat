# test_match.py
import asyncio, os, time
from engine.database import init_db, save_user, update_user, _backend
from engine.match_engine import enqueue_for_search, try_match, end_chat, cancel_search

UID1, UID2 = 1001, 2002  # фейковые пользователи

async def main():
    # 0) включи нужный бэкенд перед запуском:
    #    os.environ["USE_POSTGRES"]="0"  # SQLite
    #    os.environ["USE_POSTGRES"]="1"  # Postgres (Docker)
    await init_db(reset=True)

    # 1) создадим два профиля
    await save_user(UID1, gender="m", age=22, language="ru", premium=0, vibe="calm")
    await save_user(UID2, gender="f", age=22, language="ru", premium=0, vibe="calm")

    profile = dict(language="ru", age=22, gender=None, vibe="calm", require_adult=False, age_range=2)

    # 2) постановка в очередь и попытка свести
    await enqueue_for_search(UID1, profile)
    await enqueue_for_search(UID2, profile)

    p1 = await try_match(UID1, profile)
    p2 = await try_match(UID2, profile)

    print("Шаг 1: сведение")
    print(" partner для UID1:", p1)
    print(" partner для UID2:", p2)
    assert (p1 in (UID2, None)) and (p2 in (UID1, None)) and ((p1==UID2) or (p2==UID1)), "Ожидалось сведение пары"

    # 3) анти-рематч — сразу после разрыва эта же пара свестись не должна
    await end_chat(UID1, UID2)

    # сразу снова в очередь
    await enqueue_for_search(UID1, profile)
    await enqueue_for_search(UID2, profile)
    rematch = await try_match(UID1, profile)
    print("Шаг 2: анти-рематч =>", rematch)
    assert rematch is None, "Анти-рематч не сработал (слишком рано свелись повторно)"

    # 4) симулируем «прошло 31 минута», чтобы разрешить повторную сводку
    if _backend.__class__.__name__ == "_SQLite":
        import aiosqlite
        async with aiosqlite.connect(_backend.path) as db:
            await db.execute("UPDATE recent_pairs SET matched_at = matched_at - 3600")
            await db.commit()
    else:
        async with _backend.pool.acquire() as con:
            await con.execute("UPDATE recent_pairs SET matched_at = matched_at - 3600")

    await cancel_search(UID1); await cancel_search(UID2)
    await enqueue_for_search(UID1, profile)
    await enqueue_for_search(UID2, profile)
    p1_again = await try_match(UID1, profile)
    print("Шаг 3: повторная сводка после «ожидания» =>", p1_again)
    assert p1_again == UID2, "После окна анти-рематча ожидалось сведение UID1↔UID2"

    print("\n✅ Тест пройден: очередь, сведение, анти-рематч, повторная сводка — ОК")

if __name__ == "__main__":
    # 👉 включи нужный режим тут:
    # os.environ["USE_POSTGRES"] = "0"   # SQLite
    os.environ["USE_POSTGRES"] = "1"     # Postgres (Docker)
    asyncio.run(main())
