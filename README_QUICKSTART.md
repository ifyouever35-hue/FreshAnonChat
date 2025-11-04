# FreshAnonChat — PG Ready (RU/EN), Stats auto-open, Media path in DB

## 1) Setup
```powershell
py -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env`:
- `TOKEN=...`
- `PG_DSN=postgresql://freshanon:postgres123@127.0.0.1:5433/freshanon?connect_timeout=5&sslmode=disable`
- `AUTO_OPEN_STATS=1` to auto-open the stats page.
- `MEDIA_ROOT=./storage/media`

## 2) Run
```powershell
python .\bot_2.py
```
The bot will:
- init PG schema, store `media_root` to DB (`settings` table).
- start media cleanup loop.
- run FastAPI stats server on http://127.0.0.1:8000 and auto-open browser.
- install RU/EN commands.
