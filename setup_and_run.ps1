$ErrorActionPreference = "Stop"
try { Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force | Out-Null } catch {}

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    py -3 -m venv .venv 2>$null
    if (!(Test-Path ".\.venv\Scripts\python.exe")) { python -m venv .venv }
}
$py = ".\.venv\Scripts\python.exe"

& $py -m pip install --upgrade pip
if (Test-Path ".\requirements.txt") {
  & $py -m pip install -r .\requirements.txt
} else {
  & $py -m pip install "aiogram>=3.7.0" "asyncpg>=0.29.0" "fastapi>=0.115.0" "uvicorn>=0.30.0" "aiohttp>=3.9.5"
}

if (-not (Test-Path ".\.env")) {
  if (Test-Path ".\.env.example") {
    Copy-Item ".\.env.example" ".\.env" -Force
    Write-Host "Created .env from .env.example — fill TOKEN & PG_DSN, then rerun." -ForegroundColor Yellow
    exit 0
  } else {
    "TOKEN=PUT_YOUR_BOT_TOKEN_HERE`nUSE_POSTGRES=1`nPG_DSN=postgresql://neverland:StrongPass!@127.0.0.1:5433/fresh_anon_chat" | Out-File ".\.env" -Encoding UTF8
    Write-Host "Created minimal .env — fill TOKEN, then rerun." -ForegroundColor Yellow
    exit 0
  }
}

& $py - << 'PYCODE'
import asyncio, os
os.environ.setdefault("PYTHONASYNCIODEBUG","0")
from database import init_db, get_stats
async def main():
    await init_db()
    s = await get_stats()
    print("DB OK; stats:", s)
asyncio.run(main())
PYCODE

& $py .\bot_2.py
