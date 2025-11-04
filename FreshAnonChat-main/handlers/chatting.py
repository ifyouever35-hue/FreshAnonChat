from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from database import change_rating
from asyncio import sleep

chat_router = Router()

# Храним активные пары чата
active_pairs = {}

# --- Основная клавиатура чата ---
def get_chat_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Завершить чат")]
        ],
        resize_keyboard=True
    )

# --- Клавиатура после завершения ---
def get_feedback_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👍 Нравится", callback_data="rate_up")],
        [InlineKeyboardButton(text="👎 Не понравился", callback_data="rate_down")]
    ])

# --- Подключение пары пользователей ---
async def connect_pair(user1, user2, bot):
    """Создаёт связь между пользователями и уведомляет их."""
    active_pairs[user1] = user2
    active_pairs[user2] = user1

    await bot.send_message(user1, "✨ Собеседник найден! Можешь начинать общение.", reply_markup=get_chat_keyboard())
    await bot.send_message(user2, "✨ Собеседник найден! Можешь начинать общение.", reply_markup=get_chat_keyboard())

# --- Разрыв пары пользователей ---
async def disconnect_pair(user_id, bot):
    """Разрывает текущий чат."""
    partner_id = active_pairs.pop(user_id, None)
    if partner_id:
        active_pairs.pop(partner_id, None)

        await bot.send_message(user_id, "❌ Чат завершён.\n\nОцени собеседника 👇", reply_markup=get_feedback_keyboard())
        await bot.send_message(partner_id, "Собеседник покинул чат 😢", reply_markup=None)
    else:
        await bot.send_message(user_id, "Нет активного чата.", reply_markup=None)

# --- Завершение по кнопке ---
@chat_router.message(F.text == "❌ Завершить чат")
async def end_chat(message: types.Message):
    from loader import bot  # если бот инициализируется отдельно
    await disconnect_pair(message.from_user.id, bot)

# --- Оценка собеседника ---
@chat_router.callback_query(F.data.in_(["rate_up", "rate_down"]))
async def handle_feedback(call: types.CallbackQuery):
    """Обработка оценки собеседника."""
    user_id = call.from_user.id

    # Находим партнёра, которого нужно оценить
    partner_id = None
    for uid, pid in active_pairs.items():
        if pid == user_id:
            partner_id = uid
            break

    if partner_id:
        if call.data == "rate_up":
            await change_rating(partner_id, +1)
            await call.message.edit_text("💖 Спасибо за отзыв! Рейтинг собеседника увеличен.")
        else:
            await change_rating(partner_id, -1)
            await call.message.edit_text("👎 Спасибо! Мы учтём вашу оценку.")
    else:
        await call.message.edit_text("Спасибо за отзыв 💬")

    await sleep(2)
    await call.message.answer("🔙 Возвращаемся в меню поиска.", reply_markup=None)

# --- Пересылка сообщений между собеседниками ---
@chat_router.message(F.text)
async def relay_message(message: types.Message):
    """Отправка текста между пользователями."""
    user_id = message.from_user.id
    partner_id = active_pairs.get(user_id)

    if not partner_id:
        await message.answer("⚠️ Нет активного чата. Нажми «Поиск собеседника».")
        return

    await message.bot.send_message(partner_id, message.text)

# --- Пересылка медиа ---
@chat_router.message(F.photo | F.video | F.voice | F.document)
async def relay_media(message: types.Message):
    """Отправка медиафайлов между пользователями."""
    user_id = message.from_user.id
    partner_id = active_pairs.get(user_id)

    if not partner_id:
        await message.answer("⚠️ Нет активного чата. Начни новый поиск.")
        return

    # Фото
    if message.photo:
        await message.bot.send_photo(partner_id, message.photo[-1].file_id, caption=message.caption or "")
    # Видео
    elif message.video:
        await message.bot.send_video(partner_id, message.video.file_id, caption=message.caption or "")
    # Голосовое
    elif message.voice:
        await message.bot.send_voice(partner_id, message.voice.file_id, caption=message.caption or "")
    # Документ
    elif message.document:
        await message.bot.send_document(partner_id, message.document.file_id, caption=message.caption or "")
