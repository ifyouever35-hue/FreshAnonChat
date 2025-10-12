import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, LabeledPrice
from config import TOKEN
from database import init_db, get_user, save_user, set_waiting, get_waiting_users, set_premium

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
# Тестовый режим
TEST_MODE = False  # Выключи False для production

if TEST_MODE:
    @dp.message(Command("test_pair"))
    async def test_pair_handler(message: types.Message):
        user_id = message.from_user.id
        test_partner = 999999  # Фиктивный ID
        active_pairs[user_id] = test_partner
        active_pairs[test_partner] = user_id
        await message.answer("Тест: Пара создана. Пиши — бот симулирует ответ.")
        # Симуляция ответа от "партнёра"
        asyncio.create_task(simulate_response(test_partner, user_id))

async def simulate_response(from_id, to_id):
    await asyncio.sleep(2)  # Задержка
    await bot.send_message(to_id, f"Аноним (симуляция): Привет! Как дела?")

active_pairs = {}

class Registration(StatesGroup):
    waiting_gender = State()
    waiting_age = State()
    waiting_language = State()

# Маппинг
GENDER_MAP = {"male": "Парень", "female": "Девушка"}
LANGUAGE_MAP = {"ru": "Русский", "en": "Английский", "id": "Индонезийский", "th": "Тайский"}

# Меню
def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Случайный собеседник")],
        [KeyboardButton(text="Поиск Ж"), KeyboardButton(text="Поиск М")],
        [KeyboardButton(text="Помощь")]
    ], resize_keyboard=True)
    return keyboard

def get_gender_keyboard():
    keyboard = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Парень"), KeyboardButton(text="Девушка")]
    ], resize_keyboard=True, one_time_keyboard=True)
    return keyboard

def get_language_keyboard():
    keyboard = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Русский"), KeyboardButton(text="English")],
        [KeyboardButton(text="Indonesian"), KeyboardButton(text="Thai")]
    ], resize_keyboard=True, one_time_keyboard=True)
    return keyboard

@dp.message(Command("start"))
async def start_handler(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user = await get_user(user_id)
    if user is None:
        await message.answer("Заполни анкету. Выбери пол:", reply_markup=get_gender_keyboard())
        await state.set_state(Registration.waiting_gender)
    else:
        gender_ru = GENDER_MAP.get(user[0], user[0])
        language_ru = LANGUAGE_MAP.get(user[2], user[2])
        premium_status = "Премиум" if user[3] else "Базовый"
        await message.answer(f"Привет! Мы тебя помним! Пол: {gender_ru}, Возраст: {user[1]}, Язык: {language_ru}, Аккаунт: {premium_status}.", reply_markup=get_main_keyboard())

@dp.message(Registration.waiting_gender)
async def gender_handler(message: types.Message, state: FSMContext):
    gender = message.text.lower()
    if gender in ["парень", "мужчина"]:
        gender = "male"
    elif gender in ["девушка", "женщина"]:
        gender = "female"
    else:
        await message.answer("Выбери 'Парень' или 'Девушка'. Заново:", reply_markup=get_gender_keyboard())
        return
    await state.update_data(gender=gender)
    await message.answer("Укажи возраст (например 18):")
    await state.set_state(Registration.waiting_age)

@dp.message(Registration.waiting_age)
async def age_handler(message: types.Message, state: FSMContext):
    try:
        age = int(message.text)
        if 13 <= age <= 100:
            await state.update_data(age=age)
            await message.answer("Выбери язык:", reply_markup=get_language_keyboard())
            await state.set_state(Registration.waiting_language)
        else:
            await message.answer("Возраст от 13 до 100. Введи заново.")
    except ValueError:
        await message.answer("Введи число. Заново.")

@dp.message(Registration.waiting_language)
async def language_handler(message: types.Message, state: FSMContext):
    language = message.text.lower()
    if language == "русский":
        language = "ru"
    elif language == "english":
        language = "en"
    elif language == "indonesian":
        language = "id"
    elif language == "thai":
        language = "th"
    else:
        await message.answer("Выбери 'Русский', 'English', 'Indonesian' или 'Thai'. Заново:", reply_markup=get_language_keyboard())
        return
    data = await state.get_data()
    user_id = message.from_user.id
    await save_user(user_id, data['gender'], data['age'], language)
    gender_ru = GENDER_MAP.get(data['gender'], data['gender'])
    language_ru = LANGUAGE_MAP.get(language, language)
    await message.answer(f"Анкета заполнена! Пол: {gender_ru}, Возраст: {data['age']}, Язык: {language_ru}.", reply_markup=get_main_keyboard())
    await state.clear()
    await start_search(user_id, None, data['age'], language)

@dp.message(F.text == "Случайный собеседник")
async def random_search_handler(message: types.Message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    if user:
        await start_search(user_id, None, user[1], user[2])
        await set_waiting(user_id, 1)
        await message.answer("Идёт поиск...", reply_markup=get_main_keyboard())
    else:
        await message.answer("Сначала /start.", reply_markup=get_main_keyboard())

@dp.message(F.text == "Поиск Ж")
async def female_search_handler(message: types.Message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    if user and user[3] == 1:
        await start_search(user_id, "female", user[1], user[2])
        await set_waiting(user_id, 1)
        await message.answer("Идёт поиск девушки...", reply_markup=get_main_keyboard())
    else:
        await message.answer("Премиум функция. Купи подписку: /premium", reply_markup=get_main_keyboard())

@dp.message(F.text == "Поиск М")
async def male_search_handler(message: types.Message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    if user and user[3] == 1:
        await start_search(user_id, "male", user[1], user[2])
        await set_waiting(user_id, 1)
        await message.answer("Идёт поиск парня...", reply_markup=get_main_keyboard())
    else:
        await message.answer("Премиум функция. Купи подписку: /premium", reply_markup=get_main_keyboard())

@dp.message(Command("premium"))
async def premium_handler(message: types.Message):
    user_id = message.from_user.id
    await bot.send_invoice(
        chat_id=user_id,
        title="Премиум подписка",
        description="Доступ к поиску по полу (1 месяц)",
        payload="premium_month",
        provider_token="",  # В production от @PaymentsBot
        currency="RUB",
        prices=[LabeledPrice(label="Подписка", amount=9900)]  # 99 RUB
    )

@dp.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.successful_payment)
async def successful_payment_handler(message: types.SuccessfulPayment):
    user_id = message.from_user.id
    await set_premium(user_id, 1)
    await message.answer("Премиум активирован! Теперь доступен поиск по полу.", reply_markup=get_main_keyboard())

@dp.message(F.text == "Помощь")
async def help_handler(message: types.Message):
    help_text = "/next — следующий\n/stop — стоп\n/premium — купить подписку\nСлучайный — бесплатный поиск\nПоиск Ж/М — премиум"
    await message.answer(help_text, reply_markup=get_main_keyboard())

@dp.message(Command("next"))
async def next_handler(message: types.Message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    if user:
        await stop_pair(user_id)
        await start_search(user_id, None, user[1], user[2])
        await set_waiting(user_id, 1)
        await message.answer("Идёт поиск...", reply_markup=get_main_keyboard())
    else:
        await message.answer("Сначала /start.", reply_markup=get_main_keyboard())

@dp.message(Command("stop"))
async def stop_handler(message: types.Message):
    user_id = message.from_user.id
    await stop_pair(user_id)
    await message.answer("Чат закончен. /next для следующего.", reply_markup=get_main_keyboard())

async def stop_pair(user_id):
    partner = active_pairs.pop(user_id, None)
    if partner:
        active_pairs.pop(partner, None)
        await set_waiting(user_id, 0)
        await set_waiting(partner, 0)
        await bot.send_message(partner, "Собеседник ушёл. /next для следующего.", reply_markup=get_main_keyboard())

async def start_search(user_id, gender, age, language):
    candidates = await get_waiting_users(language, age, gender)
    if len(candidates) >= 2:
        user1_id, u1_age, u1_lang, u1_premium = candidates[0]
        user2_id, u2_age, u2_lang, u2_premium = candidates[1]
        if user1_id != user2_id and user1_id != user_id and user2_id != user_id:
            active_pairs[user1_id] = user2_id
            active_pairs[user2_id] = user1_id
            await bot.send_message(user1_id, "Собеседник найден!")
            await bot.send_message(user2_id, "Собеседник найден!")
            await set_waiting(user1_id, 0)
            await set_waiting(user2_id, 0)
    else:
        await set_waiting(user_id, 1)
        await bot.send_message(user_id, "Поиск собеседника...")

@dp.message(F.text.not_in_(["Случайный собеседник", "Поиск Ж", "Поиск М", "Помощь", "Парень", "Девушка", "Русский", "English", "Indonesian", "Thai"]))
async def forward_message(message: types.Message):
    user_id = message.from_user.id
    partner = active_pairs.get(user_id)
    if partner:
        await bot.send_message(partner, f"Аноним: {message.text}")
        await message.answer("Отправлено!", reply_markup=get_main_keyboard())
    else:
        await message.answer("Нет чата. Нажми 'Случайный собеседник'.", reply_markup=get_main_keyboard())

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())