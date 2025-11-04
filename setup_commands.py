
# setup_commands.py — robust set_my_commands for RU/EN
import logging
from aiogram import Bot
from aiogram.types import BotCommand

async def ensure_bot_commands(bot: Bot):
    ru = [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="menu", description="Главное меню"),
        BotCommand(command="settings", description="Настройки профиля"),
        BotCommand(command="profile", description="Мой профиль"),
        BotCommand(command="about", description="О Neverland"),
        BotCommand(command="rules", description="Правила"),
        BotCommand(command="id", description="Показать мой ID"),
        BotCommand(command="search", description="Случайный поиск"),
        BotCommand(command="stop", description="Остановить поиск / Завершить"),
        BotCommand(command="restart", description="Завершить и искать нового"),
        BotCommand(command="vibes", description="Выбрать вайб"),
        BotCommand(command="topics", description="Выбрать интересы"),
        BotCommand(command="vip", description="Neverland Premium"),
    ]
    en = [
        BotCommand(command="start", description="Start the bot"),
        BotCommand(command="menu", description="Main menu"),
        BotCommand(command="settings", description="Profile settings"),
        BotCommand(command="profile", description="My profile"),
        BotCommand(command="about", description="About Neverland"),
        BotCommand(command="rules", description="Rules"),
        BotCommand(command="id", description="Show my ID"),
        BotCommand(command="search", description="Random search"),
        BotCommand(command="stop", description="Stop search / End chat"),
        BotCommand(command="restart", description="End & find new"),
        BotCommand(command="vibes", description="Pick a vibe"),
        BotCommand(command="topics", description="Pick interests"),
        BotCommand(command="vip", description="Neverland Premium"),
    ]
    try:
        await bot.set_my_commands(ru, language_code="ru")
        await bot.set_my_commands(en, language_code="en")
        # default scope (no language) for safety
        await bot.set_my_commands(ru)
    except Exception as e:
        logging.warning("setup_commands skipped: %s", e)
