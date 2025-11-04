import re, os, shutil, datetime

NEW_FUNC = """async def _ensure_pool():
    # Ensure a global asyncpg pool with sane defaults for Windows + Docker mapping.
    # Retries a few times on startup, forces IPv4, and avoids invalid server GUCs.
    global _POOL
    if _POOL and not getattr(_POOL, "_closed", False):
        return _POOL

    import os, asyncio, asyncpg, logging
    log = logging.getLogger(__name__)

    def _env(name, default=None):
        v = os.getenv(name)
        return v if v not in (None, "") else default

    host = _env("PGHOST", "127.0.0.1")
    try:
        port = int(_env("PGPORT", "5455"))
    except Exception:
        port = 5455
    user = _env("PGUSER", "neverland")
    password = _env("PGPASSWORD", "")
    database = _env("PGDATABASE", "fresh_anon_chat")
    max_size = int(_env("PGPOOL_MAX", "10"))

    delays = [0.5, 1.5, 3, 5]
    last_err = None

    for attempt, delay in enumerate(delays, 1):
        try:
            _POOL = await asyncpg.create_pool(
                host=host,
                port=port,
                user=user,
                password=password,
                database=database,
                min_size=0,
                max_size=max_size,
                timeout=10,
                command_timeout=60,
                server_settings={
                    "application_name": "FreshAnonChat",
                    "tcp_keepalives_idle": "10",
                    "tcp_keepalives_interval": "5",
                    "tcp_keepalives_count": "3",
                },
            )
            log.info(f"[db] pool ready -> {host}:{port}")
            return _POOL
        except Exception as e:
            last_err = e
            log.warning(f"[db] pool attempt {attempt}/{len(delays)} failed: {e}")
            await asyncio.sleep(delay)

    raise last_err
"""

def backup_file(path, backup_dir):
    os.makedirs(backup_dir, exist_ok=True)
    dst = os.path.join(backup_dir, os.path.basename(path))
    shutil.copy2(path, dst)
    return dst

def read_text(p):
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        return f.read()

def write_text(p, t):
    with open(p, "w", encoding="utf-8", errors="replace") as f:
        f.write(t)

def inject_bot_policy(text):
    marker = "WindowsSelectorEventLoopPolicy"
    if marker in text:
        return text
    # insert at the very top, preserving shebang/encoding/comments
    lines = text.splitlines()
    i = 0
    while i < len(lines) and (lines[i].startswith('#!') or 'coding' in lines[i] or lines[i].strip().startswith('#')):
        i += 1
    snippet = (
        "# --- Windows event loop policy fix (prevents WinError 64 on asyncio sockets) ---\n"
        "import sys, asyncio  # injected by patch\n"
        "if sys.platform.startswith('win'):\n"
        "    try:\n"
        "        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())\n"
        "    except Exception:\n"
        "        pass\n"
        "# ------------------------------------------------------------------------------\n"
    )
    return "\n".join(lines[:i] + [snippet] + lines[i:])

def replace_ensure_pool(text):
    pattern = re.compile(r'async\s+def\s+_ensure_pool\s*\([^)]*\)\s*:\s*(?:\n|\r\n).*?(?=\n(?:def\s+|async\s+def\s+|class\s+)|\Z)', re.S)
    if pattern.search(text):
        return pattern.sub(NEW_FUNC.strip()+"\n", text, count=1)
    else:
        if text.endswith("\n"):
            return text + "\n" + NEW_FUNC.strip() + "\n"
        else:
            return text + "\n\n" + NEW_FUNC.strip() + "\n"

def main():
    base = os.getcwd()
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(base, f"_backup_{ts}")
    changed = []

    bot = os.path.join(base, "bot_2.py")
    if os.path.exists(bot):
        before = read_text(bot)
        after = inject_bot_policy(before)
        if after != before:
            backup_file(bot, backup_dir)
            write_text(bot, after)
            changed.append("bot_2.py (policy injected at top)")

    db = os.path.join(base, "database.py")
    if os.path.exists(db):
        before = read_text(db)
        after = replace_ensure_pool(before)
        if after != before:
            backup_file(db, backup_dir)
            write_text(db, after)
            changed.append("database.py (_ensure_pool replaced/appended)")

    if changed:
        print("Изменено:", ", ".join(changed))
        print("Бэкап:", backup_dir)
    else:
        print("Нечего менять — возможно, уже пропатчено.")

if __name__ == "__main__":
    main()
