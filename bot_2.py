import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from config import TOKEN
from database import (
    init_db, get_user, save_user, update_user,
    set_waiting, get_waiting_users
)

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN, parse_mode="HTML")
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

active_pairs = {}
search_start_time = {}

# ===================== КЛАВИАТУРЫ =====================
def main_keyboard(searching=False):
    buttons = [
        [KeyboardButton(text="🎯 Случайный собеседник")],
        [KeyboardButton(text="👩 Поиск девушки"), KeyboardButton(text="👨 Поиск парня")],
        [KeyboardButton(text="⚙ Настройки"), KeyboardButton(text="👁 Профиль")]
    ]
    if searching:
        buttons = [[KeyboardButton(text="⏹ Завершить поиск")]]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def start_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚀 Начать регистрацию")],
            [KeyboardButton(text="ℹ️ О проекте")]
        ],
        resize_keyboard=True
    )

def gender_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Парень"), KeyboardButton(text="Девушка")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def settings_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✏️ Сменить возраст")],
            [KeyboardButton(text="🚻 Сменить пол")],
            [KeyboardButton(text="🌐 Сменить язык")],
            [KeyboardButton(text="🔙 Назад")]
        ],
        resize_keyboard=True
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

# ===================== FSM =====================
class Registration(StatesGroup):
    waiting_gender = State()
    waiting_age = State()
    waiting_language = State()
    changing_age = State()
    changing_gender = State()
    changing_language = State()

# ===================== АНИМИРОВАННОЕ ПРИВЕТСТВИЕ =====================
@dp.message(Command("start"))
async def start_cmd(message: types.Message, state: FSMContext):
    await init_db()
    user_id = message.from_user.id
    user = await get_user(user_id)

    if user:
        await message.answer("💬 Главное меню:", reply_markup=main_keyboard())
        return

    await message.answer("🌌 Добро пожаловать в Neverland Chat...")
    await asyncio.sleep(1.2)
    await message.answer("💬 Здесь всё анонимно и по-настоящему.")
    await asyncio.sleep(1.2)
    await message.answer("🪄 Давай создадим твою анкету — займёт меньше минуты.", reply_markup=start_keyboard())

# ===================== КНОПКА "О ПРОЕКТЕ" =====================
@dp.message(F.text == "ℹ️ О проекте")
async def about_project(message: types.Message):
    text = (
        "✨ <b>Neverland Chat</b> — это анонимный чат, где можно быть собой.\n\n"
        "💭 Общение без регистрации и личных данных.\n"
        "🎯 Подбор собеседников по возрасту и интересам.\n"
        "💎 <b>Премиум</b> открывает поиск по полу и приоритетные подключения.\n\n"
        "🚀 Нажми «Начать регистрацию», чтобы войти в Neverland!"
    )
    await message.answer(text, reply_markup=start_keyboard())

# ===================== КНОПКА "НАЧАТЬ РЕГИСТРАЦИЮ" =====================
@dp.message(F.text == "🚀 Начать регистрацию")
async def begin_registration(message: types.Message, state: FSMContext):
    await message.answer("✨ Отлично! Сейчас создадим твою анкету.")
    await asyncio.sleep(1.5)
    await message.answer("Выбери свой пол:", reply_markup=gender_keyboard())
    await state.set_state(Registration.waiting_gender)

# ===================== РЕГИСТРАЦИЯ =====================
@dp.message(F.text.in_(["Парень", "Девушка"]), Registration.waiting_gender)
async def gender_set(message: types.Message, state: FSMContext):
    gender = "male" if message.text.lower() == "парень" else "female"
    await state.update_data(gender=gender)
    await message.answer("📅 Укажи свой возраст:")
    await state.set_state(Registration.waiting_age)

@dp.message(F.text.regexp(r"^\d+$"), Registration.waiting_age)
async def age_set(message: types.Message, state: FSMContext):
    age = int(message.text)
    if 13 <= age <= 100:
        await state.update_data(age=age)
        await message.answer("🌐 Выбери язык:", reply_markup=language_keyboard())
        await state.set_state(Registration.waiting_language)
    else:
        await message.answer("Возраст должен быть от 13 до 100 лет.")

@dp.message(Registration.waiting_language)
async def language_set(message: types.Message, state: FSMContext):
    lang_map = {"русский": "ru", "english": "en", "indonesian": "id", "thai": "th"}
    language = lang_map.get(message.text.lower())
    if not language:
        await message.answer("Выбери язык из списка:", reply_markup=language_keyboard())
        return
    data = await state.get_data()
    await save_user(message.from_user.id, data["gender"], data["age"], language)
    await state.clear()
    await message.answer("✅ Анкета создана!", reply_markup=main_keyboard())

# ===================== НАСТРОЙКИ =====================
@dp.message(F.text == "⚙ Настройки")
async def settings_menu(message: types.Message):
    await message.answer("🔧 Что хочешь изменить?", reply_markup=settings_keyboard())

@dp.message(F.text == "✏️ Сменить возраст")
async def change_age(message: types.Message, state: FSMContext):
    await message.answer("📅 Введи новый возраст:")
    await state.set_state(Registration.changing_age)

@dp.message(Registration.changing_age)
async def save_new_age(message: types.Message, state: FSMContext):
    try:
        age = int(message.text)
        await update_user(message.from_user.id, age=age)
        await message.answer(f"✅ Возраст обновлён: {age}", reply_markup=settings_keyboard())
        await state.clear()
    except ValueError:
        await message.answer("Введите число:")

@dp.message(F.text == "🚻 Сменить пол")
async def change_gender(message: types.Message, state: FSMContext):
    await message.answer("Выбери новый пол:", reply_markup=gender_keyboard())
    await state.set_state(Registration.changing_gender)

@dp.message(F.text.in_(["Парень", "Девушка"]), Registration.changing_gender)
async def save_new_gender(message: types.Message, state: FSMContext):
    gender = "male" if message.text.lower() == "парень" else "female"
    await update_user(message.from_user.id, gender=gender)
    await message.answer("✅ Пол изменён!", reply_markup=settings_keyboard())
    await state.clear()

@dp.message(F.text == "🌐 Сменить язык")
async def change_language(message: types.Message, state: FSMContext):
    await message.answer("Выбери язык:", reply_markup=language_keyboard())
    await state.set_state(Registration.changing_language)

@dp.message(Registration.changing_language)
async def save_new_language(message: types.Message, state: FSMContext):
    lang_map = {"русский": "ru", "english": "en", "indonesian": "id", "thai": "th"}
    language = lang_map.get(message.text.lower())
    if not language:
        await message.answer("Выбери язык из списка:", reply_markup=language_keyboard())
        return
    await update_user(message.from_user.id, language=language)
    await message.answer("✅ Язык обновлён!", reply_markup=settings_keyboard())
    await state.clear()

@dp.message(F.text == "🔙 Назад")
async def back_to_main(message: types.Message):
    await message.answer("🔍 Главное меню:", reply_markup=main_keyboard())

# ===================== ПРОФИЛЬ =====================
@dp.message(F.text == "👁 Профиль")
async def profile_info(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("Профиль не найден. Используй /start для регистрации.")
        return
    gender_ru = "Парень" if user[0] == "male" else "Девушка"
    lang_map = {"ru": "Русский", "en": "English", "id": "Indonesian", "th": "Thai"}
    lang_ru = lang_map.get(user[2], user[2])
    premium_status = "💎 Премиум" if user[3] else "🆓 Бесплатный"
    await message.answer(
        f"<b>👤 Профиль</b>\n\n"
        f"Пол: <b>{gender_ru}</b>\n"
        f"Возраст: <b>{user[1]}</b>\n"
        f"Язык: <b>{lang_ru}</b>\n"
        f"Статус: {premium_status}",
        reply_markup=main_keyboard()
    )

# ===================== ПОИСК =====================
@dp.message(F.text.in_(["🎯 Случайный собеседник", "👩 Поиск девушки", "👨 Поиск парня"]))
async def start_search(message: types.Message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    if not user:
        await message.answer("Сначала зарегистрируйся: /start")
        return

    if message.text in ["👩 Поиск девушки", "👨 Поиск парня"]:
        await message.answer(
            "🔒 Поиск по полу доступен только с <b>Премиум подпиской</b>.\n\n"
            "💎 Преимущества:\n"
            "• Поиск по полу (парень / девушка)\n"
            "• Приоритетный подбор собеседников\n"
            "• Отсутствие лимита на чаты\n\n"
            "🪙 Цена: 100 Stars / месяц",
            reply_markup=main_keyboard()
        )
        return

    await set_waiting(user_id, 1)
    search_start_time[user_id] = datetime.now()
    await message.answer("🔎 Поиск собеседника...", reply_markup=main_keyboard(searching=True))
    asyncio.create_task(search_loop(user_id, None, user[1], user[2]))

async def search_loop(user_id, gender, age, language):
    while True:
        candidates = await get_waiting_users(language, age, gender)
        for c in candidates:
            if c[0] != user_id:
                active_pairs[user_id] = c[0]
                active_pairs[c[0]] = user_id
                await set_waiting(user_id, 0)
                await set_waiting(c[0], 0)
                await bot.send_message(user_id, "✅ Собеседник найден!", reply_markup=main_keyboard())
                await bot.send_message(c[0], "✅ Собеседник найден!", reply_markup=main_keyboard())
                return
        await asyncio.sleep(2)

@dp.message(F.text == "⏹ Завершить поиск")
async def stop_search(message: types.Message):
    await set_waiting(message.from_user.id, 0)
    await message.answer("Поиск остановлен.", reply_markup=main_keyboard())

# ===================== ПЕРЕСЫЛКА =====================
@dp.message()
async def relay_message(message: types.Message):
    user_id = message.from_user.id
    partner = active_pairs.get(user_id)
    if partner:
        await bot.copy_message(chat_id=partner, from_chat_id=message.chat.id, message_id=message.message_id)
    else:
        await message.answer("Нет активного чата. Нажми 🎯 Случайный собеседник.", reply_markup=main_keyboard())

# ===================== MAIN =====================
async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
