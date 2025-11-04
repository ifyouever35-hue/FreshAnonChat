# Minimal RU/EN texts
T = {
    "ru": {
        "welcome": "💫 Добро пожаловать в <b>Neverland Chat</b> — давай настроим профиль.",
        "pick_gender": "Выбери пол:",
        "ask_age": "📅 Введи возраст (13–100):",
        "pick_lang": "Выбери язык:",
        "menu_title": "💬 Главное меню:",
        "about": (
            "🌌 <b>Neverland Chat</b> — анонимный уют среди звёзд.\n\n"
            "<b>Почему тут комфортно</b>\n"
            "• 🎯 Умный подбор по вайбу и интересам\n"
            "• 💬 Один чистый диалог без шума\n"
            "• 🔒 Анонимность и вежливость\n\n"
            "Команды: /menu, /profile, /rules"
        ),
        "rules": (
            "📜 <b>Правила Neverland</b>\n"
            "1) Не раскрывай личные данные.\n"
            "2) Без спама и оскорблений.\n"
            "3) Нарушения снижают карму и ведут к бану."
        ),
        "search_start": "🌠 Начинаем поиск собеседника…",
        "already_search": "🔍 Уже идёт поиск или ты в чате.",
        "stopped": "🛑 Поиск остановлен.",
        "no_dialog": "❗ У тебя нет активного диалога.",
        "ended": "💬 Диалог завершён.",
        "profile_title": "👤 <b>Твой профиль</b>",
    },
    "en": {
        "welcome": "💫 Welcome to <b>Neverland Chat</b> — let’s set up your profile.",
        "pick_gender": "Choose your gender:",
        "ask_age": "📅 Enter age (13–100):",
        "pick_lang": "Choose language:",
        "menu_title": "💬 Main menu:",
        "about": (
            "🌌 <b>Neverland Chat</b> — cozy anonymous talks.\n\n"
            "<b>Why it’s good here</b>\n"
            "• 🎯 Smart matching by vibe & interests\n"
            "• 💬 One clean dialog\n"
            "• 🔒 Anonymity & kindness\n\n"
            "Commands: /menu, /profile, /rules"
        ),
        "rules": (
            "📜 <b>Neverland Rules</b>\n"
            "1) Don’t share personal data.\n"
            "2) No spam or insults.\n"
            "3) Violations reduce to ban."
        ),
        "search_start": "🌠 Starting search…",
        "already_search": "🔍 You’re already searching or in a chat.",
        "stopped": "🛑 Search stopped.",
        "no_dialog": "❗ You have no active dialog.",
        "ended": "💬 Dialog ended.",
        "profile_title": "👤 <b>Your profile</b>",
    },
}

def t(lang: str, key: str) -> str:
    lang = lang if lang in T else "ru"
    return T[lang].get(key, key)
