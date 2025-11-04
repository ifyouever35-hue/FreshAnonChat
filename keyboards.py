from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def kb_main(lang: str, searching=False, in_chat=False):
    if lang not in ("ru", "en"):
        lang = "ru"

    if lang == "ru":
        BTN_RANDOM = "🎯 Случайный собеседник"
        BTN_FIND_GIRL = "👩 Поиск девушки"
        BTN_FIND_BOY = "👨 Поиск парня"
        BTN_SETTINGS = "⚙ Настройки"
        BTN_PREMIUM = "💎 Premium"
        BTN_STOP = "⛔ Остановить поиск"
        BTN_END = "🚫 Завершить диалог"
        BTN_NEXT = "🔄 Завершить и искать нового"
    else:
        BTN_RANDOM = "🎯 Random"
        BTN_FIND_GIRL = "👩 Find a girl"
        BTN_FIND_BOY = "👨 Find a boy"
        BTN_SETTINGS = "⚙ Settings"
        BTN_PREMIUM = "💎 Premium"
        BTN_STOP = "⛔ Stop search"
        BTN_END = "🚫 End dialog"
        BTN_NEXT = "🔄 End & next"

    if searching:
        return ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=BTN_STOP)]],
            resize_keyboard=True
        )
    if in_chat:
        return ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=BTN_END)],[KeyboardButton(text=BTN_NEXT)]],
            resize_keyboard=True
        )
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_RANDOM)],
            [KeyboardButton(text=BTN_FIND_GIRL), KeyboardButton(text=BTN_FIND_BOY)],
            [KeyboardButton(text=BTN_SETTINGS), KeyboardButton(text=BTN_PREMIUM)],
        ],
        resize_keyboard=True
    )

def kb_gender(lang: str):
    if lang == "en":
        a, b = "Boy", "Girl"
    else:
        a, b = "Парень", "Девушка"
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=a), KeyboardButton(text=b)]],
        resize_keyboard=True, one_time_keyboard=True
    )

def kb_language():
    # Only RU / EN
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Русский"), KeyboardButton(text="English")]],
        resize_keyboard=True, one_time_keyboard=True
    )

def kb_settings(lang: str):
    if lang == "en":
        items = [
            ["🔙 Back"],
            ["✏️ Change age", "🚻 Change gender"],
            ["🌐 Change language"],
        ]
    else:
        items = [
            ["🔙 Назад"],
            ["✏️ Сменить возраст", "🚻 Сменить пол"],
            ["🌐 Сменить язык"],
        ]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=txt) for txt in row] for row in items],
        resize_keyboard=True
    )
