import os
from pathlib import Path

# --- Bot ---
TOKEN = os.getenv("TOKEN", "")

# --- Database (PG only by default) ---
USE_POSTGRES = os.getenv("USE_POSTGRES", "1") == "1"
PG_DSN = os.getenv(
    "PG_DSN",
    "postgresql://freshanon:postgres123@127.0.0.1:5433/freshanon?connect_timeout=5&sslmode=disable",
)

# --- Stats Web UI ---
STATS_HOST = os.getenv("STATS_HOST", "127.0.0.1")
STATS_PORT = int(os.getenv("STATS_PORT", "8000"))
AUTO_OPEN_STATS = os.getenv("AUTO_OPEN_STATS", "1") == "1"

# --- Media storage ---
BASE_DIR = Path(__file__).parent.resolve()
MEDIA_ROOT = Path(
    os.getenv("MEDIA_ROOT", str((BASE_DIR / "storage" / "media").resolve()))
)
