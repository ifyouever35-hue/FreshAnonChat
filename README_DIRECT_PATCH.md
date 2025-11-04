# FreshAnonChat — Direct Patch v2 (Windows + Docker, 1 порт)

Этот пакет:
1) Чинит `bot_2.py` (фикс Windows-цикла) — вставляет блок строго в самый верх файла.
2) Переписывает `_ensure_pool()` в `database.py` — ретраи, IPv4, таймауты, без `connect_timeout` в server_settings.
3) Стандартизирует 1 порт: используем Docker на **5455**.
4) Скрипт `set_db_password.ps1` — создаёт/меняет пользователя `neverland` и БД `fresh_anon_chat` с вашим паролем.
5) (Опционально) `ps_disable_windows_pg.ps1` — отключает Windows‑службы Postgres, чтобы не было конфликтов.

## Применение
1. Скопируйте файлы архива в папку с вашими `bot_2.py` и `database.py` (обычно `FreshAnonChat-main`).
2. Запустите: `python apply_direct_patch.py`
3. Установите пароль: `./set_db_password.ps1 -Password "ВашПароль"`
4. Обновите `.env` по образцу.
5. `python db_ping.py` → должен показать `OK: PostgreSQL...`
6. `python bot_2.py`

Откат: файлы‑бэкапы лежат в `_backup_YYYYmmdd_HHMMSS/`.
