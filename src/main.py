#!/usr/bin/env python3
"""
DayZ Server Manager - Точка входа
"""

import os
import sys
import asyncio
from pathlib import Path

# Добавить проект в path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from src.core.config import Config
from src.core.server_mgr import ServerManager
from src.core.server_rpt_watcher import ServerRptWatcher
from src.core.server_chat_watcher import ServerChatWatcher
from src.core.server_live_stats import ServerLiveStats
from src.core.mod_sync import ModSync
from src.core.rcon_client import RconClient
from src.core.scheduler import Scheduler
from src.utils.logger import LoggerManager
from src.utils.system_check import SystemChecker
from src.api.routes import router


# ============================================================
# Создание приложения
# ============================================================

app = FastAPI(title="DayZ Server Manager", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Глобальные компоненты
config = None
logger = None
server_mgr = None
mod_sync = None
rcon = None
scheduler = None
rpt_watcher = None
chat_watcher = None
live_stats = None


# ============================================================
# События
# ============================================================

@app.on_event("startup")
async def startup():
    """При запуске"""
    global config, logger, server_mgr, mod_sync, rcon, scheduler, rpt_watcher, chat_watcher, live_stats

    print("=" * 60)
    print("  DayZ Server Manager v1.0")
    print("=" * 60)
    print()

    # Загрузить конфиг
    print("[1/5] Loading config...")
    config = Config()
    print(f"  Config path: {config.config_path}")
    config.load()
    print(f"  OK - {len(config.servers)} servers loaded")

    # Блокировать небезопасную конфигурацию с дефолтным API-ключом
    api_key = config.get('auth.api_key', '')
    if not api_key or api_key == 'change_this_api_key':
        raise ValueError(
            "Unsafe auth.api_key in config/config.json. "
            "Set a non-default API key before startup."
        )

    # Сохранить в app.state для API
    app.state.config = config

    # Создать логгер
    print("[2/5] Initializing logger...")
    logger = LoggerManager()
    app.state.logger = logger
    logger.info("DayZ Server Manager starting...")

    # Проверить систему
    print("[3/5] Checking system dependencies...")
    checker = SystemChecker(logger)
    checker.print_report()

    # Создать компоненты
    print("[4/5] Initializing components...")

    rpt_watcher = ServerRptWatcher(config, logger, loop=asyncio.get_running_loop())
    app.state.rpt_watcher = rpt_watcher
    print("  RPT Watcher: OK")

    chat_watcher = ServerChatWatcher(config, logger, loop=asyncio.get_running_loop())
    app.state.chat_watcher = chat_watcher
    print("  Chat Watcher: OK")

    server_mgr = ServerManager(
        config,
        logger,
        rpt_watcher=rpt_watcher,
        chat_watcher=chat_watcher,
    )
    rpt_watcher.set_running_checker(server_mgr.is_running)
    app.state.server_mgr = server_mgr
    print("  Server Manager: OK")

    mod_sync = ModSync(config, logger)
    app.state.mod_sync = mod_sync
    print("  Mod Sync: OK")

    rcon = RconClient(config, logger)

    def rcon_chat_inject(server, text, player="Server", channel="Broadcast"):
        if chat_watcher and server_mgr.is_running(server):
            chat_watcher.ensure_session(server)
            chat_watcher.inject_message(server["id"], text, player=player, channel=channel)

    rcon.set_chat_inject(rcon_chat_inject)
    app.state.rcon = rcon
    print("  RCON Client: OK")

    live_stats = ServerLiveStats(config, rcon, server_mgr, logger)
    server_mgr.live_stats = live_stats
    app.state.live_stats = live_stats
    await live_stats.start()
    print("  Live Stats: OK")

    for server in config.servers:
        if server_mgr.is_running(server):
            chat_watcher.ensure_session(server)

    # Планировщик
    scheduler = Scheduler(config, logger)
    scheduler.server_mgr = server_mgr
    scheduler.mod_sync = mod_sync
    scheduler.rcon = rcon
    app.state.scheduler = scheduler

    # Запустить планировщик (async)
    await scheduler.start()

    print("[5/5] Components initialized")
    print()

    # Показать адреса
    web_host = config.get('web.host', '0.0.0.0')
    web_port = config.get('web.port', 8000)
    print("=" * 60)
    print(f"  Web UI: http://localhost:{web_port}")
    print(f"  API:    http://localhost:{web_port}/api/servers")
    print("=" * 60)
    print()

    logger.info("Server manager ready")


@app.on_event("shutdown")
async def shutdown():
    """При остановке"""
    global scheduler, rpt_watcher, chat_watcher, live_stats

    if logger:
        logger.info("Shutting down...")

    if live_stats:
        await live_stats.stop()

    if scheduler:
        await scheduler.stop()

    if rpt_watcher:
        rpt_watcher.shutdown()

    if chat_watcher:
        chat_watcher.shutdown()

    if logger:
        logger.info("DayZ Server Manager stopped")


# ============================================================
# Маршруты
# ============================================================

# REST API
app.include_router(router)


# WebSocket
@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    if logger is None:
        await websocket.close(code=1013, reason="Manager not ready")
        return

    await websocket.accept()
    queue = logger.subscribe()

    try:
        while True:
            log_entry = await queue.get()
            await websocket.send_text(log_entry)
    except Exception:
        logger.unsubscribe(queue)


@app.websocket("/ws/servers/{server_id}/logs")
async def websocket_server_logs(websocket: WebSocket, server_id: str):
    if rpt_watcher is None or config is None:
        await websocket.close(code=1013, reason="Manager not ready")
        return

    server = config.get_server(server_id)
    if not server:
        await websocket.close(code=1008, reason="Server not found")
        return

    await websocket.accept()

    import json as _json

    running = server_mgr.is_running(server) if server_mgr else False
    info = rpt_watcher.get_startup_info(server, running)
    await websocket.send_text(
        _json.dumps(
            {
                "t": "s",
                "phase": info.get("startup_phase", "stopped"),
                "warning": info.get("startup_warning"),
                "rpt": info.get("current_rpt"),
            }
        )
    )

    for line in rpt_watcher.get_tail_lines(server_id, 200):
        await websocket.send_text(_json.dumps({"t": "l", "m": line, "h": False}))

    queue = rpt_watcher.subscribe(server_id)
    if queue is None and not running:
        try:
            while True:
                await websocket.receive_text()
        except Exception:
            pass
        return

    if queue is None:
        queue = asyncio.Queue(maxsize=200)

    try:
        while True:
            msg = await queue.get()
            await websocket.send_text(msg)
    except Exception:
        pass
    finally:
        if queue:
            rpt_watcher.unsubscribe(server_id, queue)


@app.websocket("/ws/servers/{server_id}/chat")
async def websocket_server_chat(websocket: WebSocket, server_id: str):
    if chat_watcher is None or config is None:
        await websocket.close(code=1013, reason="Manager not ready")
        return

    server = config.get_server(server_id)
    if not server:
        await websocket.close(code=1008, reason="Server not found")
        return

    await websocket.accept()

    import json as _json

    if server_mgr and server_mgr.is_running(server):
        chat_watcher.ensure_session(server)

    for msg in chat_watcher.get_messages(server_id, limit=200):
        await websocket.send_text(_json.dumps({"t": "c", **msg}, ensure_ascii=False))

    queue = chat_watcher.subscribe(server_id)
    if queue is None:
        try:
            while True:
                await websocket.receive_text()
        except Exception:
            pass
        return

    try:
        while True:
            msg = await queue.get()
            await websocket.send_text(msg)
    except Exception:
        pass
    finally:
        if queue:
            chat_watcher.unsubscribe(server_id, queue)


# Web UI (статика)
if getattr(sys, 'frozen', False):
    web_dir = Path(sys.executable).resolve().parent / "web"
else:
    web_dir = Path(__file__).parent.parent / "web"


@app.get("/")
async def serve_index():
    return FileResponse(str(web_dir / "index.html"))


@app.get("/{path:path}")
async def serve_static(path: str):
    file_path = web_dir / path
    if file_path.exists():
        return FileResponse(str(file_path))
    return FileResponse(str(web_dir / "index.html"))


# ============================================================
# Запуск
# ============================================================

def main():
    """Точка входа"""
    # Загрузить конфиг для получения порта
    cfg = Config()
    cfg.load()

    web_host = cfg.get('web.host', '0.0.0.0')
    web_port = cfg.get('web.port', 8000)

    # Запустить uvicorn
    uvicorn.run(
        app,
        host=web_host,
        port=web_port,
        reload=False,
        log_level="info"
    )


if __name__ == "__main__":
    main()
