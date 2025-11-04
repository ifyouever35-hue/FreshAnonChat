# bot_2.py — RU/EN, PG-only, автозапуск вебморды, гашение TelegramForbiddenError
import asyncio
import logging
import os
import random
import re
from datetime import datetime

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramForbiddenError
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, ReplyKeyboardMarkup, LabeledPrice, PreCheckoutQuery
)
from aiogram.types.error_event import ErrorEvent

# ==== конфиг токена ====
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    try:
        from config import TOKEN as TOKEN_FROM_FILE  # type: ignore
        TOKEN = TOKEN_FROM_FILE
    except Exception:
        raise RuntimeError("TOKEN не найден ни в переменных окружения, ни в config.py")

# ==== импорт БД API ====
from database import (  # type: ignore
    init_db, get_user, save_user, update_user,
    set_waiting, get_waiting_users,
    daily_rehabilitation, PERMANENT_PREMIUM_USERS,
    set_premium_expiry, is_premium_active, get_premium_expiry,
    adjust_rating, add_report, add_rating_log,
)

# ==== вебморда статистики ====
try:
    from stats_api import start_stats_server  # type: ignore
except Exception:
    start_stats_server = None

# ==== опциональная настройка команд ====
try:
    from setup_commands import ensure_bot_commands as _ensure_bot_commands  # type: ignore
except Exception:
    _ensure_bot_commands = None

# ===================== ЛОГИ, БОТ =====================
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())

REHAB_INTERVAL = 24 * 3600  # 24 часа

# ===================== ЛОКАЛИЗАЦИЯ =====================
def tr(lang: str, key: str) -> str:
    L = {
        "ru": {
            # Кнопки главного меню
            "btn_random": "🎯 Случайный собеседник",
            "btn_find_girl": "👩 Поиск девушки",
            "btn_find_boy": "👨 Поиск парня",
            "btn_settings": "⚙ Настройки",
            "btn_profile": "👁 Профиль",
            "btn_about": "🌌 О Neverland",
            "btn_premium": "💎 Premium",
            # Кнопки состояний
            "btn_stop_search": "⛔ Остановить поиск",
            "btn_end_chat": "🚫 Завершить диалог",
            "btn_restart_chat": "🔄 Завершить и искать нового",
            "btn_back": "🔙 Назад",
            # Кнопки настроек
            "btn_set_age": "✏️ Сменить возраст",
            "btn_set_gender": "🚻 Сменить пол",
            "btn_set_lang": "🌐 Сменить язык",
            "btn_set_vibe": "✨ Сменить вайб",
            "btn_set_interests": "🎯 Сменить интересы",

            # Регистрация/общие
            "welcome": "💫 Добро пожаловать в <b>Neverland Chat</b> — давай настроим профиль.",
            "ask_gender": "Выбери пол:",
            "gender_male": "Парень",
            "gender_female": "Девушка",
            "ask_age": "📅 Введи возраст (13–100):",
            "err_age": "Возраст должен быть от 13 до 100. Попробуй ещё раз:",
            "ask_lang": "Выбери язык:",
            "lang_ru": "Русский",
            "lang_en": "English",

            # Меню/профиль/правила/о проекте
            "menu_title": "💬 Главное меню:",
            "settings_title": "⚙️ Настройки профиля:",
            "profile_title": "👤 <b>Твой профиль</b>",
            "rules": (
                "📜 <b>Правила Neverland Chat</b>\n\n"
                "1. Уважай анонимность — не раскрывай личные данные.\n"
                "2. Не отправляй личные фото без согласия.\n"
                "3. Без оскорблений, спама и рекламы.\n"
                "4. Контент 18+ запрещён.\n"
                "5. Нарушения снижают карму и могут привести к бану."
            ),
            "about": (
                "🌌 <b>Neverland Chat</b> — анонимный уют среди звёзд.\n"
                "Без масок и лишних соцсетей — только живой разговор с незнакомцем на одной волне.\n\n"
                "<b>Почему здесь классно</b>\n"
                "• 🎯 Умный подбор по вайбу и интересам\n"
                "• 💬 Чистый диалог — один приватный чат\n"
                "• 🌟 Карма и защита от абуза\n"
                "• ⏳ Честное ожидание\n\n"
                "💫 <i>Neverland — место, где легко быть собой и находить тёплые диалоги.</i>"
            ),

            # Профиль
            "id_line": "🪪 Твой Telegram ID: <code>{id}</code>",
            "gender_line": "Пол: <b>{gender}</b>",
            "age_line": "Возраст: <b>{age}</b>",
            "lang_line": "Язык: <b>{lang}</b>",
            "vibe_line": "Вайб: <b>{vibe}</b>",
            "interests_line": "Интересы: <b>{interests}</b>",
            "rating_line": "Карма: <b>{rating}</b> 🌟",
            "premium_status": "Статус: {status}",
            "premium_forever": "💎 Premium (навсегда)",
            "premium_until": "💎 Premium (до {date})",
            "premium_free": "🆓 Базовый",

            # Поиск/чат
            "search_started": "🌠 Начинаем поиск собеседника...\n\n{gender_pref}{vibe}\n{interests}\n\nИщем того, кто на одной волне с тобой 💫",
            "pref_gender": "Предпочтение по полу: <b>{gender}</b>\n",
            "chat_found": "🌟 <b>Собеседник найден!</b>\n\n🪄 Команды:\n/stop — завершить диалог\n/restart — завершить и искать нового",
            "already_searching": "🔍 Уже идёт поиск или ты в чате.",
            "search_stopped": "🛑 Поиск остановлен.",
            "no_active_chat": "❗ У тебя нет активного диалога.",
            "partner_left": "😔 Собеседник покинул чат.",
            "chat_ended": "💬 Диалог завершён.",
            "unsupported": "📎 Получен неподдерживаемый тип сообщения.",
            "chat_partner_left": "😔 Собеседник завершил диалог.",

            # Настройки/сохранение
            "ask_new_age": "📅 Введи новый возраст (13–100):",
            "age_saved": "✅ Возраст обновлён: {age}",
            "gender_saved": "✅ Пол обновлён.",
            "ask_new_lang": "Выбери язык:",
            "lang_saved": "✅ Язык обновлён.",
            "choose_vibe": "💫 Выбери свой вайб:",
            "choose_interests": "🎯 Выбери интересы (нажатие — сразу сохраняет):",
            "vibe_reset": "🔄 Вайб сброшен.",
            "interests_reset": "🔄 Все интересы очищены.",
            "interest_add": "{key} — добавлено",
            "interest_remove": "{key} — убрано",

            # Premium
            "premium_text": (
                "💎 <b>Neverland Premium</b>\n\n"
                "✨ Что даёт Premium:\n"
                "• Поиск по полу (👩 / 👨)\n"
                "• Без ограничений на количество чатов\n"
                "• Приоритет в поиске и выдаче\n"
                "• Маленький значок 💎 в профиле\n\n"
                "Оплата через Telegram Stars ⭐"
            ),
            "premium_only": "💎 <b>Эта функция доступна только Premium-пользователям.</b>",
            "premium_activated": "💎 Premium активирован на {months} мес!",
        },
        "en": {
            # Buttons
            "btn_random": "🎯 Random match",
            "btn_find_girl": "👩 Find a girl",
            "btn_find_boy": "👨 Find a boy",
            "btn_settings": "⚙ Settings",
            "btn_profile": "👁 Profile",
            "btn_about": "🌌 About Neverland",
            "btn_premium": "💎 Premium",
            "btn_stop_search": "⛔ Stop searching",
            "btn_end_chat": "🚫 End chat",
            "btn_restart_chat": "🔄 End & find new",
            "btn_back": "🔙 Back",
            "btn_set_age": "✏️ Change age",
            "btn_set_gender": "🚻 Change gender",
            "btn_set_lang": "🌐 Change language",
            "btn_set_vibe": "✨ Change vibe",
            "btn_set_interests": "🎯 Change interests",

            # Registration/general
            "welcome": "💫 Welcome to <b>Neverland Chat</b> — let’s set up your profile.",
            "ask_gender": "Choose your gender:",
            "gender_male": "Boy",
            "gender_female": "Girl",
            "ask_age": "📅 Enter age (13–100):",
            "err_age": "Age must be between 13 and 100. Try again:",
            "ask_lang": "Choose language:",
            "lang_ru": "Русский",
            "lang_en": "English",

            # Menu/profile/rules/about
            "menu_title": "💬 Main menu:",
            "settings_title": "⚙️ Profile settings:",
            "profile_title": "👤 <b>Your profile</b>",
            "rules": (
                "📜 <b>Neverland Chat Rules</</b>\n\n"
                "1. Respect anonymity — no personal data.\n"
                "2. Don’t send personal photos without consent.\n"
                "3. No insults, spam or ads.\n"
                "4. 18+ content is not allowed.\n"
                "5. Violations reduce karma and may lead to a ban."
            ),
            "about": (
                "🌌 <b>Neverland Chat</b> — anonymous cozy space among stars.\n"
                "No masks, no socials — just real talk with a like-minded stranger.\n\n"
                "<b>Why it’s nice</b>\n"
                "• 🎯 Smart matching via vibe & interests\n"
                "• 💬 Single clean private dialog\n"
                "• 🌟 Karma & abuse protection\n"
                "• ⏳ Fair waiting\n\n"
                "💫 <i>Neverland — a place to be yourself and find warm conversations.</i>"
            ),

            # Profile
            "id_line": "🪪 Your Telegram ID: <code>{id}</code>",
            "gender_line": "Gender: <b>{gender}</b>",
            "age_line": "Age: <b>{age}</b>",
            "lang_line": "Language: <b>{lang}</b>",
            "vibe_line": "Vibe: <b>{vibe}</b>",
            "interests_line": "Interests: <b>{interests}</b>",
            "rating_line": "Karma: <b>{rating}</b> 🌟",
            "premium_status": "Status: {status}",
            "premium_forever": "💎 Premium (forever)",
            "premium_until": "💎 Premium (till {date})",
            "premium_free": "🆓 Free",

            # Search/chat
            "search_started": "🌠 Starting the search...\n\n{gender_pref}{vibe}\n{interests}\n\nLooking for someone on your wavelength 💫",
            "pref_gender": "Gender preference: <b>{gender}</b>\n",
            "chat_found": "🌟 <b>Match found!</b>\n\n🪄 Commands:\n/stop — end chat\n/restart — end & find new",
            "already_searching": "🔍 You’re already searching or in a chat.",
            "search_stopped": "🛑 Search stopped.",
            "no_active_chat": "❗ You have no active dialog.",
            "partner_left": "😔 Your partner left the chat.",
            "chat_ended": "💬 Dialog ended.",
            "unsupported": "📎 Unsupported message type.",
            "chat_partner_left": "😔 Your partner ended the dialog.",

            # Settings/saving
            "ask_new_age": "📅 Enter new age (13–100):",
            "age_saved": "✅ Age updated: {age}",
            "gender_saved": "✅ Gender updated.",
            "ask_new_lang": "Choose language:",
            "lang_saved": "✅ Language updated.",
            "choose_vibe": "💫 Choose your vibe:",
            "choose_interests": "🎯 Choose interests (tap saves instantly):",
            "vibe_reset": "🔄 Vibe cleared.",
            "interests_reset": "🔄 Interests cleared.",
            "interest_add": "{key} — added",
            "interest_remove": "{key} — removed",

            # Premium
            "premium_text": (
                "💎 <b>Neverland Premium</b>\n\n"
                "✨ What you get:\n"
                "• Gender search (👩 / 👨)\n"
                "• No chat count limits\n"
                "• Priority in queue & matching\n"
                "• Small 💎 badge in profile\n\n"
                "Payment via Telegram Stars ⭐"
            ),
            "premium_only": "💎 <b>This feature is for Premium users only.</b>",
            "premium_activated": "💎 Premium activated for {months} mo!",
        },
    }
    lang = "en" if lang == "en" else "ru"
    return L[lang].get(key, L["ru"].get(key, key))


def user_lang_from_row(row) -> str:
    if row and len(row) > 2 and row[2] in ("ru", "en"):
        return row[2]
    return "ru"


# ===== Вайбы/интересы =====
VIBES_MAP = {
    "ru": {
        "funny": "😂 Весёлый",
        "calm": "🧘 Спокойный",
        "romantic": "❤️ Романтичный",
        "philosophic": "🎭 Философский",
        "dark": "💀 Тёмный",
        "chill": "😎 Расслабленный",
    },
    "en": {
        "funny": "😂 Funny",
        "calm": "🧘 Calm",
        "romantic": "❤️ Romantic",
        "philosophic": "🎭 Philosophic",
        "dark": "💀 Dark",
        "chill": "😎 Chill",
    },
}

INTERESTS_MAP = {
    "ru": ["💬 Флирт", "😂 Мемы", "🎵 Музыка", "🎬 Фильмы", "📚 Книги", "💭 Одиночество", "💻 Технологии", "🌍 Путешествия"],
    "en": ["💬 Flirt", "😂 Memes", "🎵 Music", "🎬 Movies", "📚 Books", "💭 Loneliness", "💻 Tech", "🌍 Travel"],
}


def normalize_interests(text: str) -> list[str]:
    if not text:
        return []
    return [re.sub(r"[^\w\s]", "", p).strip().lower() for p in text.split(",") if p.strip()]


def vibe_and_interests_for(user_row) -> tuple[str, str]:
    l = user_lang_from_row(user_row)
    vibe_key = (user_row[8] or "") if user_row and len(user_row) > 8 else ""
    vibe_disp = VIBES_MAP[l].get(vibe_key, "—") if vibe_key else "—"
    interests_disp = (user_row[4] or "—") if user_row and len(user_row) > 4 else "—"
    return vibe_disp, interests_disp


# ===================== КЛАВИАТУРЫ =====================
def kb_main(lang: str, searching=False, in_chat=False):
    t = lambda k: tr(lang, k)
    if searching:
        return ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=t("btn_stop_search"))]],
            resize_keyboard=True
        )
    if in_chat:
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=t("btn_end_chat"))],
                [KeyboardButton(text=t("btn_restart_chat"))],
            ],
            resize_keyboard=True
        )
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("btn_random"))],
            [KeyboardButton(text=t("btn_find_girl")), KeyboardButton(text=t("btn_find_boy"))],
            [KeyboardButton(text=t("btn_settings")), KeyboardButton(text=t("btn_profile"))],
            [KeyboardButton(text=t("btn_about")), KeyboardButton(text=t("btn_premium"))],
        ],
        resize_keyboard=True
    )


def kb_settings(lang: str):
    t = lambda k: tr(lang, k)
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("btn_back"))],
            [KeyboardButton(text=t("btn_set_age")), KeyboardButton(text=t("btn_set_gender"))],
            [KeyboardButton(text=t("btn_set_lang"))],
            [KeyboardButton(text=t("btn_set_vibe")), KeyboardButton(text=t("btn_set_interests"))],
        ],
        resize_keyboard=True
    )


def kb_gender(lang: str):
    t = lambda k: tr(lang, k)
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t("gender_male")), KeyboardButton(text=t("gender_female"))]],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def kb_language_only_ru_en(lang: str):
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=tr("ru", "lang_ru")), KeyboardButton(text=tr("en", "lang_en"))]],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def kb_vibes_inline(lang: str, selected_key: str) -> InlineKeyboardMarkup:
    items = []
    for key, label in VIBES_MAP[lang].items():
        prefix = "✅ " if key == selected_key else ""
        items.append(InlineKeyboardButton(text=f"{prefix}{label}", callback_data=f"vibe_{key}"))
    rows = [items[i:i + 2] for i in range(0, len(items), 2)]
    rows.append([InlineKeyboardButton(text=tr(lang, "vibe_reset"), callback_data="vibes_reset")])
    rows.append([InlineKeyboardButton(text=tr(lang, "btn_back"), callback_data="settings_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_interests_inline(lang: str, selected: set[str]) -> InlineKeyboardMarkup:
    items = []
    for it in INTERESTS_MAP[lang]:
        clean = re.sub(r"[^\w\s]", "", it).strip().lower()
        prefix = "✅ " if clean in selected else ""
        items.append(InlineKeyboardButton(text=f"{prefix}{it}", callback_data=f"interest_{clean}"))
    rows = [items[i:i + 2] for i in range(0, len(items), 2)]
    rows.append([InlineKeyboardButton(text=tr(lang, "interests_reset"), callback_data="interests_reset")])
    rows.append([InlineKeyboardButton(text=tr(lang, "btn_back"), callback_data="settings_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_premium_inline(lang: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💫 1 мес — 100⭐ / 1 mo — 100⭐", callback_data="buy_premium_1")],
        [InlineKeyboardButton(text="🌠 3 мес — 300⭐ / 3 mo — 300⭐", callback_data="buy_premium_3")],
        [InlineKeyboardButton(text="🌌 6 мес — 500⭐ / 6 mo — 500⭐", callback_data="buy_premium_6")],
    ])


# ===================== ПАМЯТЬ В ОЗУ =====================
active_chats: dict[int, int] = {}
searching_users: set[int] = set()
search_tasks: dict[int, asyncio.Task] = {}

# ===================== FSM =====================
class Reg(StatesGroup):
    gender = State()
    age = State()
    language = State()


class Change(StatesGroup):
    changing_age = State()
    changing_gender = State()
    changing_language = State()


# ===================== ХЕЛПЕРЫ ОТПРАВКИ/ОЧИСТКИ =====================
async def _cleanup_blocked_user(uid: int):
    try:
        task = search_tasks.pop(uid, None)
        if task and not task.done():
            task.cancel()
        searching_users.discard(uid)
        await set_waiting(uid, 0)
    except Exception:
        pass
    try:
        pid = active_chats.pop(uid, None)
        if pid:
            active_chats.pop(pid, None)
            row = await get_user(pid)
            l = user_lang_from_row(row)
            try:
                await bot.send_message(pid, tr(l, "chat_partner_left"), reply_markup=kb_main(l))
            except TelegramForbiddenError:
                pass
    except Exception:
        logging.exception("cleanup: active chat cleanup failed")


async def safe_send_message(chat_id: int, text: str, **kw):
    try:
        return await bot.send_message(chat_id, text, **kw)
    except TelegramForbiddenError:
        await _cleanup_blocked_user(chat_id)
        return None


async def safe_answer(message: types.Message, text: str, **kw):
    try:
        return await message.answer(text, **kw)
    except TelegramForbiddenError:
        await _cleanup_blocked_user(message.chat.id)
        return None


# ===================== БАЗОВЫЕ КОМАНДЫ/КНОПКИ =====================
@dp.message(CommandStart())
async def start_cmd(message: types.Message, state: FSMContext):
    await init_db()
    uid = message.from_user.id
    user = await get_user(uid)
    l = user_lang_from_row(user)
    if not (user and isinstance(user[1], int) and user[1] >= 13 and user[2]):
        await state.clear()
        await safe_answer(message, tr("ru", "welcome"))
        await safe_answer(message, tr("ru", "ask_gender"), reply_markup=kb_gender("ru"))
        await state.set_state(Reg.gender)
        return
    await safe_answer(message, tr(l, "menu_title"), reply_markup=kb_main(l))


@dp.message(Command("menu"))
@dp.message(lambda m: m.text in {tr("ru", "btn_back"), tr("en", "btn_back")})
async def show_menu(message: types.Message):
    user = await get_user(message.from_user.id)
    l = user_lang_from_row(user)
    await safe_answer(message, tr(l, "menu_title"), reply_markup=kb_main(l))


# --- Регистрация ---
@dp.message(Reg.gender, F.text.in_({tr("ru","gender_male"), tr("ru","gender_female"), tr("en","gender_male"), tr("en","gender_female")}))
async def reg_gender_ok(message: types.Message, state: FSMContext):
    txt = (message.text or "").lower()
    g = "male" if txt in {"парень", "boy"} else "female"
    await state.update_data(gender=g)
    await safe_answer(message, tr("ru", "ask_age"), reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(Reg.age)


@dp.message(Reg.age, F.text.regexp(r"^\d+$"))
async def reg_age_ok(message: types.Message, state: FSMContext):
    age = int(message.text)
    if not (13 <= age <= 100):
        await safe_answer(message, tr("ru", "err_age"))
        return
    await state.update_data(age=age)
    await safe_answer(message, tr("ru", "ask_lang"), reply_markup=kb_language_only_ru_en("ru"))
    await state.set_state(Reg.language)


@dp.message(Reg.language)
async def reg_lang(message: types.Message, state: FSMContext):
    txt = (message.text or "").lower()
    code = "ru" if "рус" in txt else ("en" if "english" in txt else None)
    if not code:
        await safe_answer(message, tr("ru", "ask_lang"), reply_markup=kb_language_only_ru_en("ru"))
        return
    data = await state.get_data()
    await save_user(message.from_user.id, gender=data["gender"], age=data["age"], language=code)
    await state.clear()

    user = await get_user(message.from_user.id)
    l = user_lang_from_row(user)
    current_interests = set(normalize_interests(user[4] or "")) if user else set()
    await safe_answer(message, tr(l, "choose_vibe"), reply_markup=kb_vibes_inline(l, user[8] or ""))
    await safe_answer(message, tr(l, "choose_interests"), reply_markup=kb_interests_inline(l, current_interests))
    await safe_answer(message, tr(l, "menu_title"), reply_markup=kb_main(l))


# Профиль / О проекте / Правила / ID
@dp.message(Command("profile"))
@dp.message(lambda m: m.text in {tr("ru", "btn_profile"), tr("en", "btn_profile")})
async def show_profile(message: types.Message):
    user = await get_user(message.from_user.id)
    if not (user and isinstance(user[1], int) and user[1] >= 13 and user[2]):
        await safe_answer(message, "❌ Профиль не найден. Используй /start для регистрации.")
        return
    l = user_lang_from_row(user)
    gender_disp = tr(l, "gender_male") if user[0] == "male" else tr(l, "gender_female")
    lang_disp = tr(l, "lang_ru") if l == "ru" else tr(l, "lang_en")
    rating = user[5] if len(user) > 5 else 0
    vibe_disp, interests_disp = vibe_and_interests_for(user)

    expiry_ts = await get_premium_expiry(message.from_user.id)
    if message.from_user.id in PERMANENT_PREMIUM_USERS:
        status = tr(l, "premium_forever")
    elif expiry_ts:
        status = tr(l, "premium_until").format(date=datetime.fromtimestamp(expiry_ts).strftime('%d.%m.%Y'))
    else:
        status = tr(l, "premium_free")

    text = (
        f"{tr(l,'profile_title')}\n\n"
        f"{tr(l,'id_line').format(id=message.from_user.id)}\n"
        f"{tr(l,'gender_line').format(gender=gender_disp)}\n"
        f"{tr(l,'age_line').format(age=user[1])}\n"
        f"{tr(l,'lang_line').format(lang=lang_disp)}\n"
        f"{tr(l,'vibe_line').format(vibe=vibe_disp)}\n"
        f"{tr(l,'interests_line').format(interests=interests_disp)}\n"
        f"{tr(l,'rating_line').format(rating=rating)}\n"
        f"{tr(l,'premium_status').format(status=status)}"
    )
    await safe_answer(message, text, reply_markup=kb_main(l))


@dp.message(Command("about"))
@dp.message(lambda m: m.text in {tr("ru", "btn_about"), tr("en", "btn_about")})
async def about_project(message: types.Message):
    user = await get_user(message.from_user.id)
    l = user_lang_from_row(user)
    await safe_answer(message, tr(l, "about"), reply_markup=kb_main(l))


@dp.message(Command("rules"))
async def show_rules(message: types.Message):
    user = await get_user(message.from_user.id)
    l = user_lang_from_row(user)
    await safe_answer(message, tr(l, "rules"))


@dp.message(Command("id"))
async def show_id(message: types.Message):
    await safe_answer(message, f"🪪 <code>{message.from_user.id}</code>")


# ===================== НАСТРОЙКИ =====================
@dp.message(Command("settings"))
@dp.message(lambda m: m.text in {tr("ru","btn_settings"), tr("en","btn_settings")})
async def settings_menu(message: types.Message):
    user = await get_user(message.from_user.id)
    l = user_lang_from_row(user)
    await safe_answer(message, tr(l, "settings_title"), reply_markup=kb_settings(l))


@dp.message(lambda m: m.text in {tr("ru","btn_set_age"), tr("en","btn_set_age")})
async def ask_age(message: types.Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    l = user_lang_from_row(user)
    await safe_answer(message, tr(l, "ask_new_age"))
    await state.set_state(Change.changing_age)


@dp.message(Change.changing_age, F.text.regexp(r"^\d+$"))
async def save_age(message: types.Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    l = user_lang_from_row(user)
    age = int(message.text)
    if not (13 <= age <= 100):
        await safe_answer(message, tr(l, "err_age"))
        return
    await update_user(message.from_user.id, age=age)
    await state.clear()
    await safe_answer(message, tr(l, "age_saved").format(age=age), reply_markup=kb_settings(l))


@dp.message(lambda m: m.text in {tr("ru","btn_set_gender"), tr("en","btn_set_gender")})
async def ask_gender_change(message: types.Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    l = user_lang_from_row(user)
    await safe_answer(message, tr(l, "ask_gender"), reply_markup=kb_gender(l))
    await state.set_state(Change.changing_gender)


@dp.message(Change.changing_gender, F.text.in_({tr("ru","gender_male"), tr("ru","gender_female"), tr("en","gender_male"), tr("en","gender_female")}))
async def save_gender(message: types.Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    l = user_lang_from_row(user)
    txt = (message.text or "").lower()
    gender = "male" if txt in {"парень", "boy"} else "female"
    await update_user(message.from_user.id, gender=gender)
    await state.clear()
    await safe_answer(message, tr(l, "gender_saved"), reply_markup=kb_settings(l))


@dp.message(lambda m: m.text in {tr("ru","btn_set_lang"), tr("en","btn_set_lang")})
async def ask_lang(message: types.Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    l = user_lang_from_row(user)
    await safe_answer(message, tr(l, "ask_new_lang"), reply_markup=kb_language_only_ru_en(l))
    await state.set_state(Change.changing_language)


@dp.message(Change.changing_language)
async def save_lang(message: types.Message, state: FSMContext):
    txt = (message.text or "").lower()
    code = "ru" if "рус" in txt else ("en" if "english" in txt else None)
    if not code:
        await safe_answer(message, tr("ru", "ask_lang"), reply_markup=kb_language_only_ru_en("ru"))
        return
    await update_user(message.from_user.id, language=code)
    await state.clear()
    l = code
    await safe_answer(message, tr(l, "lang_saved"), reply_markup=kb_settings(l))


# ===== Вайбы =====
@dp.message(Command("vibes"))
@dp.message(lambda m: m.text in {tr("ru","btn_set_vibe"), tr("en","btn_set_vibe")})
async def choose_vibe(message: types.Message):
    user = await get_user(message.from_user.id)
    l = user_lang_from_row(user)
    selected = (user[8] or "") if user and len(user) > 8 else ""
    await safe_answer(message, tr(l, "choose_vibe"), reply_markup=kb_vibes_inline(l, selected))


@dp.callback_query(F.data.startswith("vibe_"))
async def set_vibe(callback: types.CallbackQuery):
    uid = callback.from_user.id
    user = await get_user(uid)
    l = user_lang_from_row(user)
    key = callback.data.split("_", 1)[1]
    if key not in VIBES_MAP[l]:
        await callback.answer("Unknown choice" if l == "en" else "Неизвестный выбор")
        return
    await update_user(uid, vibe=key)
    await callback.message.edit_reply_markup(reply_markup=kb_vibes_inline(l, key))
    await callback.answer("Saved" if l == "en" else "Сохранено")


@dp.callback_query(F.data.in_(["vibes_reset", "vibe_reset"]))
async def reset_vibe(callback: types.CallbackQuery):
    uid = callback.from_user.id
    user = await get_user(uid)
    l = user_lang_from_row(user)
    await update_user(uid, vibe="")
    await callback.message.edit_reply_markup(reply_markup=kb_vibes_inline(l, ""))
    await callback.answer(tr(l, "vibe_reset"))


# ===== Интересы =====
@dp.message(Command("topics"))
@dp.message(lambda m: m.text in {tr("ru","btn_set_interests"), tr("en","btn_set_interests")})
async def set_interests(message: types.Message):
    user = await get_user(message.from_user.id)
    l = user_lang_from_row(user)
    current = set(normalize_interests(user[4] or "")) if user and len(user) > 4 else set()
    await safe_answer(message, tr(l, "choose_interests"), reply_markup=kb_interests_inline(l, current))


@dp.callback_query(F.data.startswith("interest_"))
async def toggle_interest(callback: types.CallbackQuery):
    uid = callback.from_user.id
    user = await get_user(uid)
    l = user_lang_from_row(user)
    selected = set(normalize_interests(user[4] or "")) if user and len(user) > 4 else set()
    key = callback.data.split("_", 1)[1]
    if key in selected:
        selected.remove(key); msg = tr(l, "interest_remove").format(key=key)
    else:
        selected.add(key); msg = tr(l, "interest_add").format(key=key)
    await update_user(uid, interests=", ".join(sorted(selected)))
    await callback.message.edit_reply_markup(reply_markup=kb_interests_inline(l, selected))
    await callback.answer(msg)


@dp.callback_query(F.data == "interests_reset")
async def reset_interests(callback: types.CallbackQuery):
    uid = callback.from_user.id
    user = await get_user(uid)
    l = user_lang_from_row(user)
    await update_user(uid, interests="")
    await callback.message.edit_reply_markup(reply_markup=kb_interests_inline(l, set()))
    await callback.answer(tr(l, "interests_reset"))


@dp.callback_query(F.data == "settings_back")
async def inline_back_to_settings(cb: types.CallbackQuery):
    try:
        await cb.message.edit_reply_markup(None)
    except Exception:
        pass
    user = await get_user(cb.from_user.id)
    l = user_lang_from_row(user)
    await cb.message.answer(tr(l, "settings_title"), reply_markup=kb_settings(l))
    await cb.answer()


# ===================== PREMIUM =====================
from aiogram.types import LabeledPrice

PREMIUM_PRICES = {
    1: [LabeledPrice(label="💎 Neverland Premium — 1 месяц / 1 month", amount=100)],
    3: [LabeledPrice(label="💎 Neverland Premium — 3 месяца / 3 months", amount=300)],
    6: [LabeledPrice(label="💎 Neverland Premium — 6 месяцев / 6 months", amount=500)],
}

@dp.message(Command("vip"))
@dp.message(lambda m: m.text in {tr("ru","btn_premium"), tr("en","btn_premium")})
async def show_vip(message: types.Message):
    user = await get_user(message.from_user.id)
    l = user_lang_from_row(user)
    await safe_answer(message, tr(l, "premium_text"), reply_markup=kb_premium_inline(l))


@dp.callback_query(F.data.startswith("buy_premium_"))
async def process_premium_payment(callback: types.CallbackQuery):
    months = int(callback.data.split("_")[-1])
    try:
        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title="Neverland Premium",
            description=f"Premium for {months} mo",
            payload=f"premium_{months}",
            provider_token="",  # Stars
            currency="XTR",
            prices=PREMIUM_PRICES[months],
            start_parameter="neverland-premium",
        )
        await callback.answer()
    except Exception as e:
        logging.error(f"invoice error: {e}")
        await callback.message.answer("⚠️ Error creating payment. Try later.")


@dp.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_q: PreCheckoutQuery):
    try:
        await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)
    except Exception as e:
        logging.error(f"pre_checkout error: {e}")


@dp.message(F.successful_payment)
async def payment_success(message: types.Message):
    payload = message.successful_payment.invoice_payload
    user = await get_user(message.from_user.id)
    l = user_lang_from_row(user)
    if payload.startswith("premium_"):
        months = int(payload.split("_")[-1])
        await set_premium_expiry(message.from_user.id, months)
        await safe_answer(message, tr(l, "premium_activated").format(months=months), reply_markup=kb_main(l))


# ===================== ПОИСК / ПОДБОР =====================
def _cancel_search_task(uid: int):
    task = search_tasks.pop(uid, None)
    if task and not task.done():
        task.cancel()


async def find_partner(user_id: int, gender_filter: str | None):
    user = await get_user(user_id)
    if not user:
        return None
    candidates = await get_waiting_users(
        language=user[2] or "ru",
        age=user[1] or 18,
        gender=gender_filter,
        vibe=(user[8] or None),
        age_range=2,
        min_rating=0,
        require_adult_access=False
    )
    pool_ids = [row[0] for row in candidates if row[0] != user_id and row[0] in searching_users and row[0] not in active_chats]
    if not pool_ids:
        pool_ids = [uid for uid in (searching_users - {user_id}) if uid not in active_chats]
    return random.choice(pool_ids) if pool_ids else None


async def _search_loop(uid: int, gender_filter: str | None):
    deadline = asyncio.get_event_loop().time() + 60.0
    try:
        while asyncio.get_event_loop().time() < deadline:
            if uid not in searching_users or uid in active_chats:
                return
            partner_id = await find_partner(uid, gender_filter)
            if partner_id:
                await on_chat_started(uid, partner_id)
                return
            await asyncio.sleep(3.0)
    except asyncio.CancelledError:
        pass
    except Exception:
        logging.exception("Ошибка в _search_loop")


@dp.message(Command("search"))
@dp.message(lambda m: m.text in {tr("ru","btn_random"), tr("en","btn_random")})
async def start_search_random(message: types.Message):
    await _start_search_flow(message, gender_filter=None)


@dp.message(lambda m: m.text in {tr("ru","btn_find_boy"), tr("en","btn_find_boy"), tr("ru","btn_find_girl"), tr("en","btn_find_girl")})
async def start_search_gendered(message: types.Message):
    txt = message.text
    gender = "male" if txt in {tr("ru","btn_find_boy"), tr("en","btn_find_boy")} else "female"
    if not await is_premium_active(message.from_user.id) and message.from_user.id not in PERMANENT_PREMIUM_USERS:
        user = await get_user(message.from_user.id)
        l = user_lang_from_row(user)
        await safe_answer(message, tr(l, "premium_only"), reply_markup=kb_premium_inline(l))
        return
    await _start_search_flow(message, gender_filter=gender)


async def _start_search_flow(message: types.Message, gender_filter: str | None):
    uid = message.from_user.id
    user = await get_user(uid)
    l = user_lang_from_row(user)
    if uid in searching_users or uid in active_chats:
        await safe_answer(message, tr(l, "already_searching"), reply_markup=kb_main(l, searching=True))
        return
    if not (user and isinstance(user[1], int) and user[1] >= 13 and user[2]):
        await safe_answer(message, "Use /start first" if l == "en" else "Сначала регистрация: /start")
        return

    searching_users.add(uid)
    await set_waiting(uid, 1)

    vibe_disp, interests_disp = vibe_and_interests_for(user)
    gender_line = "" if gender_filter is None else tr(l, "pref_gender").format(
        gender=(tr(l, "gender_male") if gender_filter == "male" else tr(l, "gender_female"))
    )
    await safe_answer(
        message,
        tr(l, "search_started").format(
            gender_pref=gender_line,
            vibe=f"{tr(l,'vibe_line').split(':')[0]}: <b>{vibe_disp}</b>",
            interests=f"{tr(l,'interests_line').split(':')[0]}: <b>{interests_disp}</b>",
        ),
        reply_markup=kb_main(l, searching=True)
    )
    search_tasks[uid] = asyncio.create_task(_search_loop(uid, gender_filter))


async def on_chat_started(uid: int, pid: int):
    _cancel_search_task(uid)
    _cancel_search_task(pid)
    searching_users.discard(uid); searching_users.discard(pid)
    active_chats[uid] = pid; active_chats[pid] = uid
    await set_waiting(uid, 0); await set_waiting(pid, 0)

    urow = await get_user(uid)
    prow = await get_user(pid)
    lu = user_lang_from_row(urow)
    lp = user_lang_from_row(prow)

    await safe_send_message(uid, tr(lu, "chat_found"), reply_markup=kb_main(lu, in_chat=True))
    await safe_send_message(pid, tr(lp, "chat_found"), reply_markup=kb_main(lp, in_chat=True))


@dp.message(Command("stop"))
@dp.message(lambda m: m.text in {tr("ru","btn_stop_search"), tr("en","btn_stop_search")})
async def stop_search(message: types.Message):
    uid = message.from_user.id
    task = search_tasks.pop(uid, None)
    if task and not task.done():
        task.cancel()
    searching_users.discard(uid)
    await set_waiting(uid, 0)
    user = await get_user(uid)
    l = user_lang_from_row(user)
    await safe_answer(message, tr(l, "search_stopped"), reply_markup=kb_main(l))


@dp.message(Command("restart"))
@dp.message(Command("next"))
@dp.message(lambda m: m.text in {tr("ru","btn_restart_chat"), tr("en","btn_restart_chat")})
async def restart_chat(message: types.Message):
    uid = message.from_user.id
    pid = active_chats.pop(uid, None)
    user = await get_user(uid)
    l = user_lang_from_row(user)
    if pid:
        active_chats.pop(pid, None)
        prow = await get_user(pid)
        lp = user_lang_from_row(prow)
        await safe_send_message(pid, tr(lp, "partner_left"), reply_markup=kb_main(lp))
        task = search_tasks.pop(pid, None)
        if task and not task.done():
            task.cancel()

    await safe_answer(message, tr(l, "btn_restart_chat"), reply_markup=kb_main(l, searching=True))
    searching_users.add(uid)
    await set_waiting(uid, 1)
    task = search_tasks.pop(uid, None)
    if task and not task.done():
        task.cancel()
    search_tasks[uid] = asyncio.create_task(_search_loop(uid, gender_filter=None))


@dp.message(lambda m: m.text in {tr("ru","btn_end_chat"), tr("en","btn_end_chat")})
async def end_chat(message: types.Message):
    uid = message.from_user.id
    user = await get_user(uid)
    l = user_lang_from_row(user)

    pid = active_chats.pop(uid, None)
    if not pid:
        await safe_answer(message, tr(l, "no_active_chat"), reply_markup=kb_main(l))
        return
    active_chats.pop(pid, None)
    prow = await get_user(pid)
    lp = user_lang_from_row(prow)
    await safe_send_message(pid, tr(lp, "partner_left"), reply_markup=kb_main(lp))
    await safe_answer(message, tr(l, "chat_ended"), reply_markup=kb_main(l))


# ===================== ОЦЕНКИ И ЖАЛОБЫ =====================
def rating_keyboard(target_id: int, lang: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👍", callback_data=f"rate_up_{target_id}"),
            InlineKeyboardButton(text="👎", callback_data=f"rate_down_{target_id}")
        ],
        [InlineKeyboardButton(text="🚫 " + ("Report" if lang == "en" else "Пожаловаться"),
                              callback_data=f"complain_{target_id}")]
    ])


@dp.callback_query(F.data.startswith("rate_up_"))
async def rate_up(callback: types.CallbackQuery):
    rater = callback.from_user.id
    target = int(callback.data.split("_")[-1])
    await add_rating_log(rater, target)
    await adjust_rating(target, +3)
    try:
        await callback.message.edit_reply_markup(None)
    except Exception:
        pass
    await callback.message.answer("👍 Thanks!" if user_lang_from_row(await get_user(rater)) == "en" else "👍 Спасибо за оценку!")
    await callback.answer("OK")


@dp.callback_query(F.data.startswith("rate_down_"))
async def rate_down(callback: types.CallbackQuery):
    rater = callback.from_user.id
    target = int(callback.data.split("_")[-1])
    await add_rating_log(rater, target)
    await adjust_rating(target, -5)
    try:
        await callback.message.edit_reply_markup(None)
    except Exception:
        pass
    await callback.message.answer("👎 Noted." if user_lang_from_row(await get_user(rater)) == "en" else "👎 Спасибо, мы учли твою оценку.")
    await callback.answer("OK")


@dp.callback_query(F.data.startswith("complain_"))
async def complain(callback: types.CallbackQuery):
    target = int(callback.data.split("_")[-1])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎭 Fake gender / Фейк пол", callback_data=f"rep_fake_{target}")],
        [InlineKeyboardButton(text="💬 Spam / Спам", callback_data=f"rep_spam_{target}")],
        [InlineKeyboardButton(text="💰 Scam / Скам", callback_data=f"rep_scam_{target}")]
    ])
    try:
        await callback.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass
    await callback.answer()


@dp.callback_query(F.data.startswith("rep_"))
async def process_report(callback: types.CallbackQuery):
    _, reason, target = callback.data.split("_")
    rater = callback.from_user.id
    target = int(target)
    reasons = {"fake": "Fake/Gender mismatch", "spam": "Spam/Ads", "scam": "Scam/Fraud"}
    await add_report(target, rater, reasons.get(reason, "Other"), penalty=15)
    await adjust_rating(target, -15)
    try:
        await callback.message.edit_reply_markup(None)
    except Exception:
        pass
    await callback.message.answer("🚫 Report submitted." if user_lang_from_row(await get_user(rater)) == "en"
                                  else "🚫 Жалоба отправлена.")
    await callback.answer("OK")


# ===================== РЕАБИЛИТАЦИЯ =====================
async def start_rehabilitation_loop():
    while True:
        try:
            await daily_rehabilitation()
        except Exception:
            logging.exception("daily_rehabilitation error")
        await asyncio.sleep(REHAB_INTERVAL)


# ===================== ГЛОБАЛЬНЫЙ ПЕРЕХВАТ ОШИБОК =====================
@dp.error()
async def _errors_handler(event: ErrorEvent):
    exc = event.exception
    if isinstance(exc, TelegramForbiddenError):
        uid = None
        try:
            upd = event.update
            if getattr(upd, "message", None):
                uid = upd.message.chat.id
            elif getattr(upd, "callback_query", None):
                uid = upd.callback_query.from_user.id
        except Exception:
            pass
        logging.warning(f"[forbidden] user={uid} blocked bot — ignoring & cleanup")
        if uid:
            try:
                await _cleanup_blocked_user(uid)
            except Exception:
                logging.exception("cleanup failed after forbidden")
        return True
    logging.error(f"[aiogram-error] {type(exc).__name__}: {exc}")


# ===================== УНИВЕРСАЛЬНЫЙ РЕЛЕЙ =====================
@dp.message()
async def relay_any(message: types.Message):
    uid = message.from_user.id
    pid = active_chats.get(uid)
    if not pid:
        return
    try:
        if message.text is not None:
            await bot.send_message(pid, message.text); return
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
        await bot.send_message(pid, tr(user_lang_from_row(await get_user(pid)), "unsupported"))
    except TelegramForbiddenError:
        await _cleanup_blocked_user(pid)
    except Exception:
        logging.exception(f"relay failed {uid} -> {pid}")


# ===================== MAIN =====================
async def main():
    await init_db()

    if _ensure_bot_commands:
        try:
            await _ensure_bot_commands(bot)
        except Exception as e:
            logging.warning(f"setup_commands skipped: {e}")

    # старт вебморды статистики
    if start_stats_server:
        host = os.getenv("STATS_HOST", "127.0.0.1")
        port = int(os.getenv("STATS_PORT", "8000"))
        asyncio.create_task(start_stats_server(host=host, port=port, open_browser=True))

    asyncio.create_task(start_rehabilitation_loop())
    logging.info("💫 Neverland запущен.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    # --- Windows event loop policy fix (prevents WinError 64 on asyncio sockets) ---
import sys, asyncio  # injected by patch
if sys.platform.startswith('win'):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass
# ------------------------------------------------------------------------------
asyncio.run(main())
