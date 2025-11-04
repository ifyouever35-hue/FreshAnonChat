from aiogram.exceptions import TelegramBadRequest
async def safe_edit_text(message, text, **kwargs):
    try:
        if getattr(message, "text", None) == text:
            return message
        return await message.edit_text(text, **kwargs)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            return message
        raise
async def safe_edit_kb(message, reply_markup=None, **kwargs):
    try:
        return await message.edit_reply_markup(reply_markup=reply_markup, **kwargs)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            return message
        raise
