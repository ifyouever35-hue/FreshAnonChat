# relay_core.py
# Unified relay for common Telegram message types (aiogram 3)

from aiogram import Bot, types

async def relay_message(bot: Bot, target_id: int, msg: types.Message) -> None:
    if msg.text is not None:
        if msg.text.startswith("/"):
            # ignore commands in dialog
            return
        await bot.send_message(target_id, msg.text)
        return
    if msg.photo:
        await bot.send_photo(target_id, msg.photo[-1].file_id, caption=msg.caption)
        return
    if msg.sticker:
        await bot.send_sticker(target_id, msg.sticker.file_id)
        return
    if msg.voice:
        await bot.send_voice(target_id, msg.voice.file_id, caption=msg.caption)
        return
    if msg.audio:
        await bot.send_audio(target_id, msg.audio.file_id, caption=msg.caption)
        return
    if msg.video:
        await bot.send_video(target_id, msg.video.file_id, caption=msg.caption)
        return
    if msg.video_note:
        await bot.send_video_note(target_id, msg.video_note.file_id)
        return
    if msg.document:
        await bot.send_document(target_id, msg.document.file_id, caption=msg.caption)
        return
    if msg.location or msg.contact:
        # security: do not relay sensitive data by default
        return