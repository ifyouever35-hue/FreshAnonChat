import os
from aiogram import Router, F, types
from aiogram.filters import Command
from engine.database import save_user, add_recent_pair, record_pair_start, record_pair_end

router_dev = Router(name="dev-router")
def is_debug() -> bool: return os.getenv("DEBUG_MATCH") == "1"
def admin_id() -> int:
    try: return int(os.getenv("ADMIN_ID","0"))
    except Exception: return 0

@router_dev.message(Command("dev_match"))
async def dev_match(message: types.Message):
    if not is_debug() or message.from_user.id != admin_id(): return
    uid1 = message.from_user.id; uid2 = uid1 + 999999
    await save_user(uid1, "m", 22, "ru", 0, vibe="calm")
    await save_user(uid2, "f", 22, "ru", 0, vibe="calm")
    await record_pair_start(uid1, uid2); await add_recent_pair(uid1, uid2)
    await message.answer("🌟 Собеседник найден! (DEV)")

@router_dev.message(Command("dev_end"))
async def dev_end(message: types.Message):
    if not is_debug() or message.from_user.id != admin_id(): return
    uid1 = message.from_user.id; uid2 = uid1 + 999999
    await record_pair_end(uid1, uid2)
    await message.answer("✅ Диалог завершён (DEV).")
