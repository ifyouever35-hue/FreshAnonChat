
# stats_api.py — FastAPI + uvicorn, background server
import asyncio, logging, webbrowser
from typing import Any, Dict
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

from database import get_stats

log = logging.getLogger("stats")
app = FastAPI(title="Neverland Stats")

@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    stats = await get_stats()
    html = f"""
    <html><head><title>Neverland Stats</title></head>
    <body style="font-family:system-ui;padding:16px;">
      <h1>Neverland — Realtime Stats</h1>
      <ul>
        <li>Total users: <b>{stats.get('users_total',0)}</b></li>
        <li>Premium active: <b>{stats.get('premium_active',0)}</b></li>
        <li>Active chats: <b>{stats.get('active_chats',0)}</b></li>
        <li>Matches today: <b>{stats.get('matches_today',0)}</b></li>
      </ul>
      <p><a href="/stats">/stats</a> (JSON)</p>
    </body></html>
    """
    return html

@app.get("/stats", response_class=JSONResponse)
async def stats() -> Dict[str, Any]:
    return await get_stats()

async def start_stats_server(host: str="127.0.0.1", port: int=8000, open_browser: bool=False):
    config = uvicorn.Config(app, host=host, port=port, loop="asyncio", log_level="info")
    server = uvicorn.Server(config)
    async def _open():
        await asyncio.sleep(0.8)
        try:
            url = f"http://{host}:{port}/"
            webbrowser.open(url, new=2)
            log.info("Opened browser: %s", url)
        except Exception:
            log.warning("Failed to open browser")
    if open_browser:
        asyncio.create_task(_open())
    await server.serve()


@app.get('/healthz')
async def healthz():
    return {'ok': True}
