FreshAnonChat — сборка с Postgres-мэтчингом (готово к многим воркерам)

1) Зависимости (в активном venv):
   pip install -r requirements.txt

2) Поднять Postgres (варианты):
   A) Docker (рекомендовано):
      docker run --name freshanon_pg -e POSTGRES_USER=freshanon -e POSTGRES_PASSWORD=postgres! -e POSTGRES_DB=freshanon -p 5433:5432 -d postgres:16
   B) Локальный установленный PG: создайте БД/пользователя и используйте DSN из .env

3) Применить схему:
   python -m pip install asyncpg
   python -m matching_core_pg.migrate_pg postgresql://freshanon:postgres!@localhost:5433/freshanon

4) Настроить .env:
   Скопируйте .env.example в .env и вставьте TOKEN и при необходимости измените PG_DSN.

5) Запуск бота обычным способом (ваш UI/кнопки остаются прежними).
   Если в коде был импорт из match_pg — он теперь работает поверх нового ядра.

Примечание: устаревшие/опасные файлы перемещены в папку legacy/.
