param([switch]$sqlite)
$ErrorActionPreference = "Stop"
try { Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force | Out-Null } catch {}

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

# Ensure venv
if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    py -3 -m venv .venv 2>$null
    if (!(Test-Path ".\.venv\Scripts\python.exe")) {
        python -m venv .venv
    }
}

$python = ".\.venv\Scripts\python.exe"

# Upgrade pip and enforce aiogram==3.6.0
& $python -m pip install --upgrade pip
& $python -m pip uninstall -y aiogram
& $python -m pip install --no-cache-dir --force-reinstall "aiogram==3.6.0"

# Install the rest
& $python -m pip install --no-cache-dir -r requirements.txt

# Ensure .env
if (-not (Test-Path ".\.env")) {
    if (Test-Path ".\.env.example") {
        Copy-Item ".\.env.example" ".\.env" -Force
        Write-Host "INFO: Создан .env из .env.example. Открой .env и впиши TOKEN, затем перезапусти setup_and_run.ps1" -ForegroundColor Yellow
        exit 0
    } else {
        "TOKEN=6420964030:***`nUSE_POSTGRES=1`nPG_DSN=postgresql://freshanon:postgres!@localhost:5433/freshanon`nSQLITE_PATH=./data/freshanon.sqlite3`nMEDIA_DIR=./media`nMEDIA_TTL_HOURS=24`nDEBUG_MATCH=0`nADMIN_ID=0" | Out-File -Encoding utf8 ".\.env"
        Write-Host "INFO: Создан базовый .env. Впиши реальный TOKEN и перезапусти." -ForegroundColor Yellow
        exit 0
    }
}

# Choose DB mode
if ($sqlite) {
    $env:USE_POSTGRES = "0"
} else {
    $env:USE_POSTGRES = "1"
    # Start Docker DB if compose exists
    if (Test-Path ".\docker-compose.yml") {
        try { docker compose up -d } catch {}
    }
}

# Run bot
& $python bot_2.py
