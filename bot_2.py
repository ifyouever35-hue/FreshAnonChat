import asyncio
import logging
import re
import random
import time
from datetime import datetime
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, PreCheckoutQuery
)
from aiogram.client.default import DefaultBotProperties

from config import TOKEN
from database import (
    init_db, get_user, save_user, update_user,
    set_waiting, get_waiting_users,
    daily_rehabilitation, PERMANENT_PREMIUM_USERS,
    set_premium_expiry, is_premium_active, get_premium_expiry,
    adjust_rating, add_report, add_rating_log,
    set_adult_pass, can_use_adult_trial, start_adult_trial, adult_access_active
)

# ===================== ЛОГИ и БОТ =====================
logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())
REHAB_INTERVAL = 24 * 3600  # 24 часа

# ===================== ТЕКСТЫ =====================
ABOUT_TEXT = (
    "🌌 <b>Neverland Chat</b> — анонимный уют среди звёзд.\n"
    "Без масок и лишних соцсетей — только живой разговор с незнакомцем на одной волне.\n\n"
    "<b>Почему здесь классно</b>\n"
    "• 🎯 <b>Умный подбор</b> — учитываем твой вайб и интересы, чтобы находить «своих».\n"
    "• ✨ <b>Вайб и темы</b> — выбери настроение общения и отметь, о чём приятно говорить.\n"
    "• 💬 <b>Чистый диалог</b> — один-единственный чат без лишнего шума.\n"
    "• 🌟 <b>Карма</b> — получай «спасибо» за доброжелательность, теряй очки за токсичность.\n"
    "• 🔒 <b>Анонимность</b> — никаких личных ссылок и контактов, всё внутри чата.\n"
    "• 🛡 <b>Защита от абуза</b> — жалобы и дизлайки с умными ограничениями.\n"
    "• ⏳ <b>Честное ожидание</b> — предупредим, если подходящих пока нет.\n\n"
    "<b>Premium — по желанию</b>\n"
    "• 👩‍❤️‍👨 Поиск по полу\n"
    "• 🚀 Приоритет в выдаче\n"
    "• ♾ Без ограничений на количество чатов\n"
    "(Базовый режим остаётся бесплатным и комфортным.)\n\n"
    "<b>Как начать</b>\n"
    "1) Нажми «/start» и заполни мини-профиль.\n"
    "2) Выбери вайб и интересы.\n"
    "3) Жми «🎯 Случайный собеседник» — и знакомься.\n\n"
    "<b>Правила Neverland</b>\n"
    "• Будь вежлив. Не раскрывай личные данные.\n"
    "• Без оскорблений, спама и навязчивых просьб.\n"
    "• NSFW — только в отдельном 18+ режиме и по взаимному согласию.\n"
    "• Нарушения снижают карму и могут привести к блокировке.\n\n"
    "💫 <i>Neverland — место, где легко быть собой и находить тёплые диалоги. Добро пожаловать.</i>"
)

# ===================== КНОПКИ =====================
BTN_RANDOM = "🎯 Случайный собеседник"
BTN_FIND_GIRL = "👩 Поиск девушки"
BTN_FIND_BOY = "👨 Поиск парня"
BTN_SETTINGS = "⚙ Настройки"
BTN_PROFILE = "👁 Профиль"
BTN_ABOUT = "🌌 О Neverland"
BTN_STOP_SEARCH = "⛔ Остановить поиск"
BTN_END_CHAT = "🚫 Завершить диалог"
BTN_RESTART_CHAT = "🔄 Завершить и искать нового"
BTN_BACK = "🔙 Назад"

BTN_SET_AGE = "✏️ Сменить возраст"
BTN_SET_GENDER = "🚻 Сменить пол"
BTN_SET_LANG = "🌐 Сменить язык"
BTN_SET_VIBE = "✨ Сменить вайб"
BTN_SET_INTERESTS = "🎯 Сменить интересы"
BTN_PREMIUM = "💎 Premium"
BTN_ADULT = "🔞 Приватные темы"

# ===================== СЛОВАРИ ДАННЫХ =====================
VIBES = {
    "весёлый": "😂 Весёлый",
    "спокойный": "🧘 Спокойный",
    "романтичный": "❤️ Романтичный",
    "философский": "🎭 Философский",
    "тёмный": "💀 Тёмный",
    "расслабленный": "😎 Расслабленный",
}

INTERESTS = [
    "💬 Флирт", "😂 Мемы", "🎵 Музыка", "🎬 Фильмы",
    "📚 Книги", "💭 Одиночество", "💻 Технологии", "🌍 Путешествия"
]

# Premium (Stars)
PREMIUM_PRICES = {
    1: [LabeledPrice(label="💎 Neverland Premium — 1 месяц", amount=100)],
    3: [LabeledPrice(label="💎 Neverland Premium — 3 месяца", amount=300)],
    6: [LabeledPrice(label="💎 Neverland Premium — 6 месяцев", amount=500)],
}
PREMIUM_TEXT = (
    "💎 <b>Neverland Premium</b>\n\n"
    "✨ Что даёт Premium:\n"
    "• Поиск по полу (👩 / 👨)\n"
    "• Без ограничений на количество чатов\n"
    "• Приоритет в поиске и выдаче\n"
    "• Маленький знак 💎 в профиле\n\n"
    "Оплата через Telegram Stars ⭐"
)

# 18+ пропуска (Stars)
ADULT_PRICES = {
    "day":   [LabeledPrice(label="🔞 18+ — сутки (24 часа)", amount=10)],
    "week":  [LabeledPrice(label="🔞 18+ — неделя (7 дней)", amount=50)],
    "month": [LabeledPrice(label="🔞 18+ — месяц (30 дней)", amount=150)],
}

# ===================== ПАМЯТЬ В ОЗУ =====================
active_chats: dict[int, int] = {}
active_chats_adult: set[int] = set()
media_allowed_until: dict[tuple[int, int], float] = {}
pending_adult_pairs: dict[int, int] = {}
consent_yes: set[tuple[int, int]] = set()
searching_users: set[int] = set()
search_tasks: dict[int, asyncio.Task] = {}
adult_searching: set[int] = set()

# ===================== FSM =====================
class Change(StatesGroup):
    changing_age = State()
    changing_gender = State()
    changing_language = State()

class Reg(StatesGroup):
    gender = State()
    age = State()
    language = State()

# ===================== ВСПОМОГАТЕЛЬНЫЕ UI =====================
def main_keyboard(searching=False, in_chat=False):
    if searching:
        return ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=BTN_STOP_SEARCH)]],
            resize_keyboard=True
        )
    if in_chat:
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=BTN_END_CHAT)],
                [KeyboardButton(text=BTN_RESTART_CHAT)]
            ],
            resize_keyboard=True
        )
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_RANDOM)],
            [KeyboardButton(text=BTN_FIND_GIRL), KeyboardButton(text=BTN_FIND_BOY)],
            [KeyboardButton(text=BTN_SETTINGS), KeyboardButton(text=BTN_PROFILE)],
            [KeyboardButton(text=BTN_ABOUT), KeyboardButton(text=BTN_PREMIUM)],
        ],
        resize_keyboard=True
    )

def settings_keyboard():
    # «Назад» — в первой строке, чтобы всегда был виден
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_BACK)],
            [KeyboardButton(text=BTN_SET_AGE), KeyboardButton(text=BTN_SET_GENDER)],
            [KeyboardButton(text=BTN_SET_LANG)],
            [KeyboardButton(text=BTN_SET_VIBE), KeyboardButton(text=BTN_SET_INTERESTS)],
            [KeyboardButton(text=BTN_ADULT)],
        ],
        resize_keyboard=True
    )

def gender_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Парень"), KeyboardButton(text="Девушка")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def language_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Русский"), KeyboardButton(text="English")],
            [KeyboardButton(text="Indonesian"), KeyboardButton(text="Thai")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def normalize_interests(text: str) -> list[str]:
    if not text:
        return []
    return [re.sub(r"[^\w\s]", "", p).strip().lower() for p in text.split(",") if p.strip()]

def build_interests_keyboard(selected: set[str]) -> InlineKeyboardMarkup:
    buttons = []
    for interest in INTERESTS:
        clean = re.sub(r"[^\w\s]", "", interest).strip().lower()
        prefix = "✅ " if clean in selected else ""
        buttons.append(InlineKeyboardButton(text=f"{prefix}{interest}", callback_data=f"interest_{clean}"))
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton(text="🔄 Сбросить всё", callback_data="interests_reset")])
    rows.append([InlineKeyboardButton(text="⬅ Назад", callback_data="settings_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def build_vibe_keyboard(selected: str) -> InlineKeyboardMarkup:
    buttons = []
    for key, label in VIBES.items():
        prefix = "✅ " if key == selected else ""
        buttons.append(InlineKeyboardButton(text=f"{prefix}{label}", callback_data=f"vibe_{key}"))
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton(text="❌ Сбросить", callback_data="vibe_reset")])
    rows.append([InlineKeyboardButton(text="⬅ Назад", callback_data="settings_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def premium_inline_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💫 1 месяц — 100⭐", callback_data="buy_premium_1")],
        [InlineKeyboardButton(text="🌠 3 месяца — 300⭐", callback_data="buy_premium_3")],
        [InlineKeyboardButton(text="🌌 6 месяцев — 500⭐", callback_data="buy_premium_6")],
    ])

# ==== 18+ UI ====
def adult_paywall_keyboard(trial_available: bool):
    rows = [
        [InlineKeyboardButton(text="Сутки — 10⭐", callback_data="adult_buy_day")],
        [InlineKeyboardButton(text="Неделя — 50⭐", callback_data="adult_buy_week")],
        [InlineKeyboardButton(text="Месяц — 150⭐", callback_data="adult_buy_month")]
    ]
    if trial_available:
        rows.insert(0, [InlineKeyboardButton(text="Пробный доступ 3 часа — 0⭐", callback_data="adult_trial")])
    rows.append([InlineKeyboardButton(text="⬅ Назад", callback_data="settings_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def adult_banner_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔞 Что такое 18+ режим?", callback_data="adult_about")],
        [InlineKeyboardButton(text="⚙ Открыть настройки", callback_data="adult_open_settings")]
    ])

def adult_consent_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, начинаем", callback_data="adult_ok"),
         InlineKeyboardButton(text="↩️ Вернуться", callback_data="adult_back")]
    ])

def adult_media_keyboard(allowed: bool) -> InlineKeyboardMarkup:
    if allowed:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔒 Запретить медиа", callback_data="adult_media_off")]
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔓 Разрешить медиа (15 минут)", callback_data="adult_media_on")]
        ])

def _pair_key(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a < b else (b, a)

def _is_registered(user_row) -> bool:
    return bool(user_row and user_row[0] and isinstance(user_row[1], int) and user_row[1] >= 13 and user_row[2])

def vibe_and_interests_for(uid: int, user_row) -> tuple[str, str]:
    vibe_key = (user_row[8] or "") if user_row and len(user_row) > 8 else ""
    vibe_disp = VIBES.get(vibe_key, "—") if vibe_key else "—"
    interests_disp = (user_row[4] or "—") if user_row and len(user_row) > 4 else "—"
    return vibe_disp, interests_disp

# ===================== БАЗОВЫЕ КОМАНДЫ/КНОПКИ =====================
@dp.message(Command("start"))
async def start_cmd(message: types.Message, state: FSMContext):
    await init_db()
    uid = message.from_user.id
    user = await get_user(uid)
    if not _is_registered(user):
        await state.clear()
        await message.answer("💫 Добро пожаловать в <b>Neverland Chat</b> — давай настроим профиль.")
        await message.answer("Выбери пол:", reply_markup=gender_keyboard())
        await state.set_state(Reg.gender)
        return
    await message.answer("💬 Главное меню:", reply_markup=main_keyboard())

@dp.message(Command("menu"))
@dp.message(lambda m: m.text == BTN_BACK)
async def show_menu(message: types.Message):
    await message.answer("💬 Главное меню:", reply_markup=main_keyboard())

# --- Регистрация ---
@dp.message(Reg.gender, F.text.in_(["Парень", "Девушка"]))
async def reg_gender_ok(message: types.Message, state: FSMContext):
    g = "male" if message.text == "Парень" else "female"
    await state.update_data(gender=g)
    await message.answer("📅 Введи возраст (13–100):", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(Reg.age)

@dp.message(Reg.age, F.text.regexp(r"^\d+$"))
async def reg_age_ok(message: types.Message, state: FSMContext):
    age = int(message.text)
    if not (13 <= age <= 100):
        await message.answer("Возраст должен быть от 13 до 100. Попробуй ещё раз:")
        return
    await state.update_data(age=age)
    await message.answer("Выбери язык:", reply_markup=language_keyboard())
    await state.set_state(Reg.language)

@dp.message(Reg.language)
async def reg_lang(message: types.Message, state: FSMContext):
    lang_map = {"русский": "ru", "english": "en", "indonesian": "id", "thai": "th"}
    code = lang_map.get((message.text or "").lower())
    if not code:
        await message.answer("Выбери язык из списка:", reply_markup=language_keyboard())
        return
    data = await state.get_data()
    await save_user(message.from_user.id, gender=data["gender"], age=data["age"], language=code)
    await state.clear()
    # Вайб/интересы сразу после регистрации
    uid = message.from_user.id
    user = await get_user(uid)
    current_interests = set(normalize_interests(user[4] or "")) if user else set()
    await message.answer("✨ Выбери вайб:", reply_markup=build_vibe_keyboard(user[8] or ""))
    await message.answer("🎯 Выбери интересы (нажатие — сразу сохраняет):", reply_markup=build_interests_keyboard(current_interests))
    await message.answer("Готово! Всё можно поменять в ⚙ Настройках.", reply_markup=main_keyboard())

# Профиль
@dp.message(Command("profile"))
@dp.message(lambda m: m.text == BTN_PROFILE)
async def show_profile(message: types.Message):
    user = await get_user(message.from_user.id)
    if not _is_registered(user):
        await message.answer("❌ Профиль не найден. Используй /start для регистрации.")
        return
    gender_ru = "Парень" if user[0] == "male" else "Девушка"
    lang_map = {"ru": "Русский", "en": "English", "id": "Indonesian", "th": "Thai"}
    lang_ru = lang_map.get(user[2], user[2])
    rating = user[5] if len(user) > 5 else 0
    vibe_disp, interests_disp = vibe_and_interests_for(message.from_user.id, user)

    access = await adult_access_active(message.from_user.id)
    adult_exp_ts = 0
    try:
        for idx in (9, 10, 11, 12):
            if len(user) > idx and isinstance(user[idx], int):
                adult_exp_ts = max(adult_exp_ts, user[idx] or 0)
    except Exception:
        adult_exp_ts = 0

    adult_line = "🔞 18+: активен" if access else "🔞 18+: выкл."
    if access and adult_exp_ts:
        dt = datetime.fromtimestamp(adult_exp_ts).strftime('%d.%m.%Y %H:%M')
        adult_line = f"🔞 18+: активен до {dt}"

    expiry_ts = await get_premium_expiry(message.from_user.id)
    premium_status = "💎 Premium (навсегда)" if message.from_user.id in PERMANENT_PREMIUM_USERS \
        else (f"💎 Premium (до {datetime.fromtimestamp(expiry_ts).strftime('%d.%m.%Y')})" if expiry_ts else "🆓 Базовый")

    await message.answer(
        f"👤 <b>Твой профиль</b>\n\n"
        f"🆔 ID: <code>{message.from_user.id}</code>\n"
        f"Пол: <b>{gender_ru}</b>\n"
        f"Возраст: <b>{user[1]}</b>\n"
        f"Язык: <b>{lang_ru}</b>\n"
        f"Вайб: <b>{vibe_disp}</b>\n"
        f"Интересы: <b>{interests_disp}</b>\n"
        f"Карма: <b>{rating}</b> 🌟\n"
        f"{adult_line}\n"
        f"Статус: {premium_status}",
        reply_markup=main_keyboard()
    )

# О проекте / Правила / ID
@dp.message(Command("about"))
@dp.message(lambda m: m.text == BTN_ABOUT)
async def about_project(message: types.Message):
    await message.answer(ABOUT_TEXT, reply_markup=main_keyboard())

@dp.message(Command("rules"))
async def show_rules(message: types.Message):
    await message.answer(
        "📜 <b>Правила Neverland Chat</b>\n\n"
        "1. Уважай анонимность — не раскрывай личные данные.\n"
        "2. Не отправляй личные фото без согласия.\n"
        "3. Без оскорблений, спама и рекламы.\n"
        "4. NSFW — только в 18+ режиме и по взаимному согласию.\n"
        "5. Нарушения снижают карму и могут привести к бану."
    )

@dp.message(Command("id"))
async def show_id(message: types.Message):
    await message.answer(f"🪪 Твой Telegram ID: <code>{message.from_user.id}</code>")

# ===================== НАСТРОЙКИ =====================
@dp.message(Command("settings"))
@dp.message(lambda m: m.text == BTN_SETTINGS)
async def settings_menu(message: types.Message):
    await message.answer("⚙️ Настройки профиля:", reply_markup=settings_keyboard())

class _RegDummy(StatesGroup): pass

@dp.message(F.text == BTN_SET_AGE)
async def ask_age(message: types.Message, state: FSMContext):
    await message.answer("📅 Введи новый возраст (13–100):")
    await state.set_state(Change.changing_age)

@dp.message(Change.changing_age, F.text.regexp(r"^\d+$"))
async def save_age(message: types.Message, state: FSMContext):
    age = int(message.text)
    if not (13 <= age <= 100):
        await message.answer("Возраст должен быть от 13 до 100 лет.")
        return
    await update_user(message.from_user.id, age=age)
    await state.clear()
    await message.answer(f"✅ Возраст обновлён: {age}", reply_markup=settings_keyboard())

@dp.message(F.text == BTN_SET_GENDER)
async def ask_gender(message: types.Message, state: FSMContext):
    await message.answer("Выбери пол:", reply_markup=gender_keyboard())
    await state.set_state(Change.changing_gender)

@dp.message(Change.changing_gender, F.text.in_(["Парень", "Девушка"]))
async def save_gender(message: types.Message, state: FSMContext):
    gender = "male" if message.text.lower() == "парень" else "female"
    await update_user(message.from_user.id, gender=gender)
    await state.clear()
    await message.answer("✅ Пол обновлён.", reply_markup=settings_keyboard())

@dp.message(F.text == BTN_SET_LANG)
async def ask_lang(message: types.Message, state: FSMContext):
    await message.answer("Выбери язык:", reply_markup=language_keyboard())
    await state.set_state(Change.changing_language)

@dp.message(Change.changing_language)
async def save_lang(message: types.Message, state: FSMContext):
    lang_map = {"русский": "ru", "english": "en", "indonesian": "id", "thai": "th"}
    code = lang_map.get((message.text or "").lower())
    if not code:
        await message.answer("Выбери язык из списка:", reply_markup=language_keyboard())
        return
    await update_user(message.from_user.id, language=code)
    await state.clear()
    await message.answer("✅ Язык обновлён.", reply_markup=settings_keyboard())

# Вайб
@dp.message(Command("vibes"))
@dp.message(lambda m: m.text == BTN_SET_VIBE)
async def choose_vibe(message: types.Message):
    user = await get_user(message.from_user.id)
    selected = (user[8] or "") if user and len(user) > 8 else ""
    await message.answer("💫 Выбери свой вайб:", reply_markup=build_vibe_keyboard(selected))

@dp.callback_query(F.data.startswith("vibe_"))
async def set_vibe(callback: types.CallbackQuery):
    uid = callback.from_user.id
    key = callback.data.split("_", 1)[1]
    await update_user(uid, vibe=key)
    await callback.message.edit_reply_markup(reply_markup=build_vibe_keyboard(key))
    await callback.answer(f"✨ Вайб обновлён: {VIBES[key]}")

@dp.callback_query(F.data == "vibe_reset")
async def reset_vibe(callback: types.CallbackQuery):
    uid = callback.from_user.id
    await update_user(uid, vibe="")
    await callback.message.edit_reply_markup(reply_markup=build_vibe_keyboard(""))
    await callback.answer("🔄 Вайб сброшен.")

# Интересы — мгновенное сохранение
@dp.message(Command("topics"))
@dp.message(lambda m: m.text == BTN_SET_INTERESTS)
async def set_interests(message: types.Message):
    user = await get_user(message.from_user.id)
    current = set(normalize_interests(user[4] or "")) if user and len(user) > 4 else set()
    await message.answer("🎯 Выбери интересы (нажатие — сразу сохраняет):", reply_markup=build_interests_keyboard(current))

@dp.callback_query(F.data.startswith("interest_"))
async def toggle_interest(callback: types.CallbackQuery):
    uid = callback.from_user.id
    user = await get_user(uid)
    selected = set(normalize_interests(user[4] or "")) if user and len(user) > 4 else set()
    key = callback.data.split("_", 1)[1]
    if key in selected:
        selected.remove(key); action = "убрано"
    else:
        selected.add(key); action = "добавлено"
    await update_user(uid, interests=", ".join(sorted(selected)))
    await callback.message.edit_reply_markup(reply_markup=build_interests_keyboard(selected))
    await callback.answer(f"{key} — {action}")

@dp.callback_query(F.data == "interests_reset")
async def reset_interests(callback: types.CallbackQuery):
    uid = callback.from_user.id
    await update_user(uid, interests="")
    await callback.message.edit_reply_markup(reply_markup=build_interests_keyboard(set()))
    await callback.answer("🔄 Все интересы очищены.")

# ===== Общий «Назад» из инлайн-меню настроек =====
@dp.callback_query(F.data == "settings_back")
async def inline_back_to_settings(cb: types.CallbackQuery):
    try:
        await cb.message.edit_reply_markup(None)
    except Exception:
        pass
    await cb.message.answer("⚙️ Настройки профиля:", reply_markup=settings_keyboard())
    await cb.answer()

# ===================== PREMIUM =====================
@dp.message(Command("vip"))
@dp.message(lambda m: m.text == BTN_PREMIUM)
async def show_vip(message: types.Message):
    await message.answer(PREMIUM_TEXT, reply_markup=premium_inline_keyboard())

@dp.callback_query(F.data.startswith("buy_premium_"))
async def process_premium_payment(callback: types.CallbackQuery):
    months = int(callback.data.split("_")[-1])
    try:
        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title="Neverland Premium",
            description=f"Подписка на {months} мес. Premium в Neverland Chat",
            payload=f"premium_{months}",
            provider_token="",  # для Stars — пустая строка
            currency="XTR",
            prices=PREMIUM_PRICES[months],
            start_parameter="neverland-premium",
        )
        await callback.answer()
    except Exception as e:
        logging.error(f"Ошибка при выставлении инвойса: {e}")
        await callback.message.answer("⚠️ Ошибка при формировании оплаты. Попробуй позже.")

# ===================== 18+ РЕЖИМ =====================
@dp.message(F.text == BTN_ADULT)
async def adult_settings(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user or not _is_registered(user):
        await message.answer("Сначала регистрация: /start"); return
    if user[1] < 18:
        await message.answer("🔞 Режим доступен только 18+."); return
    trial_ok = await can_use_adult_trial(message.from_user.id)
    access_now = await adult_access_active(message.from_user.id)
    status = "активен" if access_now else "выключен"
    await message.answer(
        f"🔞 <b>Приватные темы</b> — отдельный пул для тех, кому это действительно нужно.\n"
        f"Статус: <b>{status}</b>\n\n"
        f"Выбери доступ:",
        reply_markup=adult_paywall_keyboard(trial_ok)
    )

@dp.callback_query(F.data.in_(["adult_buy_day","adult_buy_week","adult_buy_month"]))
async def adult_buy(callback: types.CallbackQuery):
    plan = callback.data.split("_")[-1]  # day/week/month
    titles = {"day": "Доступ 18+ — сутки", "week": "Доступ 18+ — неделя", "month": "Доступ 18+ — месяц"}
    try:
        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title=titles.get(plan, "Доступ 18+"),
            description="Доступ к приватному чату 18+",
            payload=f"adult_{plan}",
            provider_token="",
            currency="XTR",
            prices=ADULT_PRICES[plan],
            start_parameter="neverland-adult",
        )
        await callback.answer()
    except Exception as e:
        logging.error(f"adult invoice error: {e}")
        await callback.message.answer("⚠️ Не удалось сформировать оплату. Попробуй позже.")

@dp.callback_query(F.data == "adult_trial")
async def adult_trial(callback: types.CallbackQuery):
    uid = callback.from_user.id
    user = await get_user(uid)
    if user[1] < 18:
        await callback.answer("Доступно только 18+.", show_alert=True); return
    if not await can_use_adult_trial(uid):
        await callback.answer("Пробный доступ уже использован.", show_alert=False); return
    await start_adult_trial(uid, hours=3)
    await callback.message.answer("✅ Пробный доступ 18+ активирован на 3 часа.")
    await callback.answer()

@dp.callback_query(F.data == "adult_open_settings")
async def adult_open_settings(cb: types.CallbackQuery):
    await inline_back_to_settings(cb)

@dp.callback_query(F.data == "adult_about")
async def adult_about(cb: types.CallbackQuery):
    await cb.message.answer(
        "🔞 18+ режим — отдельный пул пользователей, которые оплатили доступ и согласились с рамками.\n"
        "Перед началом — двойное согласие. Медиа по умолчанию выключены и включаются только обеими сторонами на 15 минут."
    )
    await cb.answer()

# ===================== ПОИСК / ПОДБОР (общий цикл) =====================
def _cancel_search_task(uid: int):
    task = search_tasks.pop(uid, None)
    if task and not task.done():
        task.cancel()

async def _search_loop(uid: int, gender_filter: str | None, adult_only: bool = False):
    """Пытаемся найти собеседника до 60 сек; затем показываем баннер/сообщение."""
    deadline = asyncio.get_event_loop().time() + 60.0
    try:
        while asyncio.get_event_loop().time() < deadline:
            if uid not in searching_users or uid in active_chats:
                return
            partner_id = await find_partner(uid, gender_filter, adult_only)
            if partner_id:
                if adult_only:
                    await ask_adult_consent(uid, partner_id)
                else:
                    await on_chat_started(uid, partner_id, is_adult=False)
                return
            await asyncio.sleep(3.0)
        # 60+ сек
        if uid in searching_users and uid not in active_chats:
            if not adult_only:
                await bot.send_message(
                    uid,
                    "⏳ Пока нет подходящих собеседников.\n"
                    "Ищешь конкретнее? Попробуй 18+ режим (Сутки — 10⭐).",
                    reply_markup=adult_banner_keyboard()
                )
            else:
                await bot.send_message(uid, "😔 Пока нет подходящих собеседников, ищем дальше…")
    except asyncio.CancelledError:
        pass
    except Exception:
        logging.exception("Ошибка в _search_loop")

async def find_partner(user_id: int, gender_filter: str | None, adult_only: bool):
    user = await get_user(user_id)
    if not user:
        return None
    require_adult = adult_only
    candidates = await get_waiting_users(
        language=user[2] or "ru",
        age=user[1] or 18,
        gender=gender_filter,
        vibe=(user[8] or None),
        age_range=2,
        min_rating=0,
        require_adult_access=require_adult
    )
    pool_ids = [row[0] for row in candidates if row[0] != user_id and row[0] in searching_users and row[0] not in active_chats]
    if not pool_ids and not adult_only:
        pool_ids = [uid for uid in (searching_users - {user_id}) if uid not in active_chats]
    return random.choice(pool_ids) if pool_ids else None

async def ask_adult_consent(a: int, b: int):
    pending_adult_pairs[a] = b
    pending_adult_pairs[b] = a
    msg = (
        "🔞 <b>18+ собеседник найден.</b>\n"
        "Вы оба включили приватный режим. Установим рамки и начнём?"
    )
    await bot.send_message(a, msg, reply_markup=adult_consent_keyboard())
    await bot.send_message(b, msg, reply_markup=adult_consent_keyboard())

@dp.callback_query(F.data.in_(["adult_ok","adult_back"]))
async def adult_consent_click(cb: types.CallbackQuery):
    uid = cb.from_user.id
    pid = pending_adult_pairs.get(uid)
    if not pid:
        await cb.answer(); return
    pair = _pair_key(uid, pid)
    if cb.data == "adult_back":
        pending_adult_pairs.pop(uid, None)
        pending_adult_pairs.pop(pid, None)
        await cb.message.edit_reply_markup(None)
        await bot.send_message(uid, "Возвращаемся в поиск.", reply_markup=main_keyboard())
        await bot.send_message(pid, "Собеседник вернулся в поиск.", reply_markup=main_keyboard())
        return
    # «Да»
    consent_yes.add(pair)
    await cb.message.edit_reply_markup(None)
    if pair in consent_yes:
        pending_adult_pairs.pop(uid, None)
        pending_adult_pairs.pop(pid, None)
        consent_yes.discard(pair)
        await on_chat_started(uid, pid, is_adult=True)
    else:
        await cb.answer("Ожидаем подтверждение собеседника…", show_alert=False)

async def on_chat_started(uid: int, pid: int, is_adult: bool):
    _cancel_search_task(uid)
    _cancel_search_task(pid)
    searching_users.discard(uid); searching_users.discard(pid)
    adult_searching.discard(uid); adult_searching.discard(pid)
    active_chats[uid] = pid; active_chats[pid] = uid
    await set_waiting(uid, 0); await set_waiting(pid, 0)
    if is_adult:
        active_chats_adult.add(uid); active_chats_adult.add(pid)
        media_allowed_until.pop(_pair_key(uid, pid), None)

    text = (
        "🌟 <b>Собеседник найден!</b>\n"
        + ("🔞 Режим: 18+ (медиа отключены по умолчанию)\n" if is_adult else "")
        + "\n🪄 Команды:\n/stop — завершить диалог\n/restart — завершить и искать нового"
    )
    kb = adult_media_keyboard(False) if is_adult else None
    await bot.send_message(uid, text, reply_markup=main_keyboard(in_chat=True))
    await bot.send_message(pid, text, reply_markup=main_keyboard(in_chat=True))
    if is_adult:
        await bot.send_message(uid, "Управление медиа:", reply_markup=kb)
        await bot.send_message(pid, "Управление медиа:", reply_markup=kb)

@dp.callback_query(F.data.in_(["adult_media_on","adult_media_off"]))
async def adult_media_toggle(cb: types.CallbackQuery):
    uid = cb.from_user.id
    pid = active_chats.get(uid)
    if not pid or uid not in active_chats_adult:
        await cb.answer(); return
    pair = _pair_key(uid, pid)

    if cb.data == "adult_media_off":
        media_allowed_until.pop(pair, None)
        await cb.message.edit_reply_markup(reply_markup=adult_media_keyboard(False))
        await bot.send_message(pid, "🔒 Собеседник запретил медиа.")
        await cb.answer("Медиа запрещены.")
        return

    prev = media_allowed_until.get(pair)
    if prev and prev > time.time():
        await cb.answer("Медиа уже разрешены на период окна."); return

    if pair not in media_allowed_until:
        media_allowed_until[pair] = -1.0
        await bot.send_message(pid, "🔓 Собеседник предлагает включить медиа на 15 минут. Нажми «Разрешить медиа (15 минут)», если согласен.")
        await cb.answer("Ждём подтверждения собеседника…")
    else:
        media_allowed_until[pair] = time.time() + 15 * 60
        await cb.message.edit_reply_markup(reply_markup=adult_media_keyboard(True))
        await bot.send_message(pid, "✅ Медиа включены на 15 минут.", reply_markup=adult_media_keyboard(True))
        await cb.answer("Медиа включены на 15 минут.")

# ===================== ПОИСК / ПОДБОР (обычный вход) =====================
@dp.message(Command("search"))
@dp.message(lambda m: m.text == BTN_RANDOM)
async def start_search_random(message: types.Message):
    await _start_search_flow(message, gender_filter=None)

@dp.message(lambda m: m.text in [BTN_FIND_BOY, BTN_FIND_GIRL])
async def start_search_gendered(message: types.Message):
    gender = "male" if message.text == BTN_FIND_BOY else "female"
    if not await is_premium_active(message.from_user.id) and message.from_user.id not in PERMANENT_PREMIUM_USERS:
        await message.answer(
            "💎 <b>Эта функция доступна только Premium-пользователям.</b>",
            reply_markup=premium_inline_keyboard()
        )
        return
    await _start_search_flow(message, gender_filter=gender)

async def _start_search_flow(message: types.Message, gender_filter: str | None):
    uid = message.from_user.id
    if uid in searching_users or uid in active_chats:
        await message.answer("🔍 Уже идёт поиск или ты в чате.", reply_markup=main_keyboard(searching=True)); return
    user = await get_user(uid)
    if not _is_registered(user):
        await message.answer("Сначала регистрация: /start"); return

    searching_users.add(uid)
    await set_waiting(uid, 1)

    vibe_disp, interests_disp = vibe_and_interests_for(uid, user)
    gender_line = "" if gender_filter is None else f"Предпочтение по полу: <b>{'Парень' if gender_filter=='male' else 'Девушка'}</b>\n"
    await message.answer(
        "🌠 Начинаем поиск собеседника...\n\n"
        f"{gender_line}"
        f"Вайб: <b>{vibe_disp}</b>\n"
        f"Интересы: <b>{interests_disp}</b>\n\n"
        "Ищем того, кто на одной волне с тобой 💫",
        reply_markup=main_keyboard(searching=True)
    )
    search_tasks[uid] = asyncio.create_task(_search_loop(uid, gender_filter, adult_only=False))

# стоп поиска / рестарт / завершить
@dp.message(Command("stop"))
@dp.message(lambda m: m.text == BTN_STOP_SEARCH)
async def stop_search(message: types.Message):
    uid = message.from_user.id
    task = search_tasks.pop(uid, None)
    if task and not task.done():
        task.cancel()
    searching_users.discard(uid); adult_searching.discard(uid)
    await set_waiting(uid, 0)
    await message.answer("🛑 Поиск остановлен.", reply_markup=main_keyboard())

@dp.message(Command("restart"))
@dp.message(Command("next"))
@dp.message(lambda m: m.text == BTN_RESTART_CHAT)
async def restart_chat(message: types.Message):
    uid = message.from_user.id
    pid = active_chats.pop(uid, None)
    if pid:
        active_chats.pop(pid, None)
        active_chats_adult.discard(uid); active_chats_adult.discard(pid)
        await bot.send_message(pid, "😔 Собеседник покинул чат.", reply_markup=main_keyboard())
        task = search_tasks.pop(pid, None)
        if task and not task.done():
            task.cancel()

    await message.answer("🔄 Ищу нового собеседника…", reply_markup=main_keyboard(searching=True))
    searching_users.add(uid); adult_searching.discard(uid)
    await set_waiting(uid, 1)
    task = search_tasks.pop(uid, None)
    if task and not task.done():
        task.cancel()
    search_tasks[uid] = asyncio.create_task(_search_loop(uid, gender_filter=None, adult_only=False))

@dp.message(lambda m: m.text == BTN_END_CHAT)
async def end_chat(message: types.Message):
    uid = message.from_user.id
    pid = active_chats.pop(uid, None)
    if not pid:
        await message.answer("❗ У тебя нет активного диалога.", reply_markup=main_keyboard())
        return
    active_chats.pop(pid, None)
    active_chats_adult.discard(uid); active_chats_adult.discard(pid)
    media_allowed_until.pop(_pair_key(uid, pid), None)
    await bot.send_message(pid, "😔 Собеседник завершил диалог.", reply_markup=main_keyboard())
    await message.answer("💬 Диалог завершён.", reply_markup=main_keyboard())

# ===================== ОЦЕНКИ И ЖАЛОБЫ =====================
def rating_keyboard(target_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👍", callback_data=f"rate_up_{target_id}"),
            InlineKeyboardButton(text="👎", callback_data=f"rate_down_{target_id}")
        ],
        [InlineKeyboardButton(text="🚫 Пожаловаться", callback_data=f"complain_{target_id}")]
    ])

@dp.callback_query(F.data.startswith("rate_up_"))
async def rate_up(callback: types.CallbackQuery):
    rater = callback.from_user.id
    target = int(callback.data.split("_")[-1])
    await add_rating_log(rater, target)
    await adjust_rating(target, +3)
    await callback.message.edit_reply_markup(None)
    await callback.message.answer("👍 Спасибо за оценку!")
    await callback.answer("Оценка учтена!")

@dp.callback_query(F.data.startswith("rate_down_"))
async def rate_down(callback: types.CallbackQuery):
    rater = callback.from_user.id
    target = int(callback.data.split("_")[-1])
    await add_rating_log(rater, target)
    await adjust_rating(target, -5)
    await callback.message.edit_reply_markup(None)
    await callback.message.answer("👎 Спасибо, мы учли твою оценку.")
    await callback.answer("Оценка учтена!")

@dp.callback_query(F.data.startswith("complain_"))
async def complain(callback: types.CallbackQuery):
    target = int(callback.data.split("_")[-1])
    complaint_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎭 Фейк / ложный пол", callback_data=f"rep_fake_{target}")],
        [InlineKeyboardButton(text="💬 Спам / реклама", callback_data=f"rep_spam_{target}")],
        [InlineKeyboardButton(text="🔞 Порнография / 18+", callback_data=f"rep_nsfw_{target}")],
        [InlineKeyboardButton(text="💰 Скам / мошенничество", callback_data=f"rep_scam_{target}")]
    ])
    await callback.message.edit_reply_markup(reply_markup=complaint_kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("rep_"))
async def process_report(callback: types.CallbackQuery):
    _, reason, target = callback.data.split("_")
    rater = callback.from_user.id
    target = int(target)
    reasons = {
        "fake": "Фейк / ложный пол",
        "spam": "Спам / реклама",
        "nsfw": "Порнография / 18+",
        "scam": "Скам / мошенничество"
    }
    reason_text = reasons.get(reason, "Другое")
    await add_report(target, rater, reason_text, penalty=15)
    await adjust_rating(target, -15)
    await callback.message.edit_reply_markup(None)
    await callback.message.answer(f"🚫 Жалоба отправлена: {reason_text}")
    await callback.answer("Спасибо, жалоба зафиксирована.")

# ===================== РЕАБИЛИТАЦИЯ =====================
async def start_rehabilitation_loop():
    while True:
        try:
            await daily_rehabilitation()
        except Exception:
            logging.exception("daily_rehabilitation error")
        await asyncio.sleep(REHAB_INTERVAL)

# ===================== ОПЛАТЫ (Telegram Stars) =====================
@dp.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_q: PreCheckoutQuery):
    """ВАЖНО: подтверждаем pre_checkout, иначе оплата «висит»."""
    try:
        await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)
    except Exception as e:
        logging.error(f"pre_checkout error: {e}")

@dp.message(F.successful_payment)
async def payment_success(message: types.Message):
    payload = message.successful_payment.invoice_payload
    if payload.startswith("premium_"):
        months = int(payload.split("_")[-1])
        await set_premium_expiry(message.from_user.id, months)
        await message.answer(f"💎 Premium активирован на {months} мес!", reply_markup=main_keyboard())
        return
    if payload.startswith("adult_"):
        plan = payload.split("_")[-1]
        days = 1 if plan == "day" else (7 if plan == "week" else 30)
        await set_adult_pass(message.from_user.id, days=days)
        await message.answer(f"🔞 Доступ 18+ активирован на {days} дн.", reply_markup=main_keyboard())
        return

# ===================== УНИВЕРСАЛЬНЫЙ РЕЛЕЙ =====================
@dp.message()
async def relay_any(message: types.Message):
    uid = message.from_user.id
    pid = active_chats.get(uid)
    if not pid:
        return
    is_adult = uid in active_chats_adult
    pk = _pair_key(uid, pid)
    allowed = media_allowed_until.get(pk, 0) and media_allowed_until.get(pk, 0) > time.time()
    try:
        if message.text is not None:
            await bot.send_message(pid, message.text); return
        if is_adult and not allowed:
            await message.answer("🔒 В 18+ чате медиа отключены. Включить можно кнопкой «Разрешить медиа (15 минут)».")
            return
        if message.photo:
            await bot.send_photo(pid, message.photo[-1].file_id, caption=message.caption or ""); return
        if message.sticker:
            await bot.send_sticker(pid, message.sticker.file_id); return
        if message.voice:
            await bot.send_voice(pid, message.voice.file_id, caption=message.caption or ""); return
        if message.audio:
            await bot.send_audio(pid, message.audio.file_id, caption=message.caption or ""); return
        if message.document:
            await bot.send_document(pid, message.document.file_id, caption=message.caption or ""); return
        if message.video:
            await bot.send_video(pid, message.video.file_id, caption=message.caption or ""); return
        if message.video_note:
            await bot.send_video_note(pid, message.video_note.file_id); return
        if message.location:
            await bot.send_location(pid, message.location.latitude, message.location.longitude); return
        await bot.send_message(pid, "📎 Получен неподдерживаемый тип сообщения.")
    except Exception:
        logging.exception(f"relay failed {uid} -> {pid}")
        await message.answer("⚠️ Не удалось переслать сообщение собеседнику.")

# ===================== MAIN =====================
async def main():
    await init_db()
    asyncio.create_task(start_rehabilitation_loop())
    logging.info("💫 Neverland запущен.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
