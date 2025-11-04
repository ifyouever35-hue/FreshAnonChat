# FreshAnonChat — Patch (Postgres/Docker unification) — 2025-11-04

## Что в архиве
- `docker-compose.yml` — единые переменные для Postgres (user/db/password/port 5433)
- `config.py` — единый DSN
- `database.py` — пул asyncpg и хелперы
- `matching_core_pg/migrate_pg.py` — идемпотентная миграция
- `db_ping.py` — проверка соединения
- `scripts/ps_disable_windows_pg.ps1` — отключить локальные службы Postgres на Windows
- `.env.example` и `.gitignore`

## Как применить (Windows PowerShell 7+)
1) Распаковать архив **в корень проекта** и согласиться на замену файлов.

2) Отключить локальный Postgres (если установлен):
```powershell
./scripts/ps_disable_windows_pg.ps1
```

3) Перезапустить контейнер БД:
```powershell
docker compose down -v
docker compose up -d
docker ps
docker logs -f freshanon-pg
```

4) Установить зависимости (если нужно):
```powershell
python -m pip install -r requirements.txt
python -m pip install asyncpg
```

5) Прогнать миграцию (создаст таблицы, безопасна к повторному запуску):
```powershell
python -m matching_core_pg.migrate_pg "postgresql://freshanon:postgres123@127.0.0.1:5433/freshanon"
```

6) Проверка подключения:
```powershell
python db_ping.py
```

7) Запустить бота:
```powershell
python bot_2.py
```

### Ожидаемые логи
- `[db] pool ready → postgresql://…5433/freshanon…`
- `Neverland запущен` и URL статистики, если включено.

## Примечания
- Если у тебя есть свой `.env`, **не затирай** его — просто убедись, что `PG_DSN` совпадает с тем, что в `config.py`.
- Если бот/веб-морда используют другие таблицы — добавь их в `migrate_pg.py` по аналогии (CREATE TABLE IF NOT EXISTS).
