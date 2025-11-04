
# media_store.py — per-user media storage + TTL cleanup
import asyncio, logging, time
from pathlib import Path
import os

MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", "./storage/media")).resolve()
TTL_SECONDS = int(os.getenv("MEDIA_TTL_SECONDS", str(14*24*3600)))  # default 14 days

TYPES = ("photos","voice","video","docs")

def ensure_structure():
    (MEDIA_ROOT).mkdir(parents=True, exist_ok=True)
    for sub in TYPES:
        (MEDIA_ROOT / sub).mkdir(parents=True, exist_ok=True)

def ensure_user_dir(user_id: int) -> Path:
    base = MEDIA_ROOT / str(user_id)
    base.mkdir(parents=True, exist_ok=True)
    for sub in TYPES:
        (base / sub).mkdir(parents=True, exist_ok=True)
    return base

def path_for(user_id: int, kind: str, filename: str) -> Path:
    assert kind in TYPES, f"Unsupported kind {kind}"
    ensure_user_dir(user_id)
    return (MEDIA_ROOT / str(user_id) / kind / filename)

async def run_cleanup_loop():
    ensure_structure()
    while True:
        try:
            now = time.time()
            for f in MEDIA_ROOT.rglob("*"):
                if f.is_file():
                    try:
                        if now - f.stat().st_mtime > TTL_SECONDS:
                            f.unlink()
                    except Exception:
                        pass
        except Exception:
            logging.exception("media cleanup error")
        await asyncio.sleep(6*3600)  # every 6 hours
