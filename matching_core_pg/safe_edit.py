from aiogram.exceptions import TelegramBadRequest

async def safe_edit_text(message, **kwargs):
    try:
        return await message.edit_text(**kwargs)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            return
        raise

async def safe_edit_reply_markup(message, **kwargs):
    try:
        return await message.edit_reply_markup(**kwargs)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            return
        raise
