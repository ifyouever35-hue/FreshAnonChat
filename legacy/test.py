import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

API_TOKEN = "6420964030:AAHmu7z5y9mf0byOHyDFwLisuvW6qnEpjfY"
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Очередь поиска
search_queue = []  # {"user_id": int, "gender": str or None, "state": FSMContext}
active_chats = {}  # user_id: peer_id

class SearchStates(StatesGroup):
    searching = State()
    chatting = State()

def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton("🎲 Случайный собеседник")],
            [KeyboardButton("Искать по полу")]
        ],
        resize_keyboard=True
    )

def get_search_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton("⏹ Завершить поиск")]],
        resize_keyboard=True
    )

def get_chat_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton("⏹ Завершить чат")]],
        resize_keyboard=True
    )

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("Привет! Выбери действие:", reply_markup=get_main_keyboard())

# Добавляем пользователя в очередь и проверяем совпадение
async def add_to_queue(user_id, gender, state):
    if not any(u["user_id"] == user_id for u in search_queue):
        search_queue.append({"user_id": user_id, "gender": gender, "state": state})
    await try_match()

# Попытка соединить пользователей в очереди
async def try_match():
    for i, u1 in enumerate(search_queue):
        for j, u2 in enumerate(search_queue):
            if i >= j:
                continue
            if u1["user_id"] == u2["user_id"]:
                continue
            # Совместимость по полу
            if u1["gender"] is None or u2["gender"] is None or u1["gender"] == u2["gender"]:
                # Создаем чат
                user1_id = u1["user_id"]
                user2_id = u2["user_id"]
                active_chats[user1_id] = user2_id
                active_chats[user2_id] = user1_id

                await u1["state"].set_state(SearchStates.chatting)
                await u2["state"].set_state(SearchStates.chatting)

                await bot.send_message(user1_id, "Собеседник найден! Начинаем чат.", reply_markup=get_chat_keyboard())
                await bot.send_message(user2_id, "Собеседник найден! Начинаем чат.", reply_markup=get_chat_keyboard())

                # Убираем из очереди
                search_queue[:] = [x for x in search_queue if x["user_id"] not in (user1_id, user2_id)]
                return

# Обработка случайного поиска
@dp.message(lambda m: m.text == "🎲 Случайный собеседник")
async def random_search_handler(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    await message.answer("Поиск случайного собеседника...", reply_markup=get_search_keyboard())
    await state.set_state(SearchStates.searching)
    await add_to_queue(user_id, None, state)

# Обработка поиска по полу
@dp.message(lambda m: m.text == "Искать по полу")
async def gender_search_handler(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    is_premium = True  # Проверка премиум
    if not is_premium:
        await message.answer("Эта функция доступна только премиум-пользователям.", reply_markup=get_main_keyboard())
        return
    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton("♂ Мужской"), KeyboardButton("♀ Женский")],
            [KeyboardButton("⏹ Завершить поиск")]
        ],
        resize_keyboard=True
    )
    await message.answer("Выбери пол собеседника:", reply_markup=markup)
    await state.set_state(SearchStates.searching)

@dp.message(lambda m: m.text in ["♂ Мужской", "♀ Женский"])
async def select_gender_handler(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    gender = "male" if message.text == "♂ Мужской" else "female"
    await message.answer(f"Поиск собеседника выбранного пола ({message.text})...", reply_markup=get_search_keyboard())
    await add_to_queue(user_id, gender, state)

# Завершить поиск
@dp.message(lambda m: m.text == "⏹ Завершить поиск")
async def stop_search_handler(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    search_queue[:] = [u for u in search_queue if u["user_id"] != user_id]
    await state.clear()
    await message.answer("Поиск остановлен. Нажми снова для нового поиска.", reply_markup=get_main_keyboard())

# Завершить чат
@dp.message(lambda m: m.text == "⏹ Завершить чат")
async def stop_chat_handler(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    peer_id = active_chats.pop(user_id, None)
    if peer_id:
        active_chats.pop(peer_id, None)
        await bot.send_message(peer_id, "Собеседник завершил чат.", reply_markup=get_main_keyboard())
    await state.clear()
    await message.answer("Чат завершен.", reply_markup=get_main_keyboard())

# Пересылка сообщений между собеседниками
@dp.message()
async def forward_messages(message: types.Message):
    user_id = message.from_user.id
    peer_id = active_chats.get(user_id)
    if peer_id:
        await bot.send_message(peer_id, message.text)
