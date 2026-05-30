"""REST API маршруты"""

from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Optional

from src.api.auth import require_api_key
from src.core.planned_restart import (
    compute_next_restart_at,
    is_planned_restart_enabled,
    normalize_planned_restart,
)


router = APIRouter()


def get_components(request: Request):
    """Получить компоненты из app.state"""
    return {
        'config': request.app.state.config,
        'server_mgr': request.app.state.server_mgr,
        'mod_sync': request.app.state.mod_sync,
        'rcon': request.app.state.rcon,
        'logger': request.app.state.logger,
        'rpt_watcher': getattr(request.app.state, 'rpt_watcher', None),
        'chat_watcher': getattr(request.app.state, 'chat_watcher', None),
    }


def enrich_server_status(components: dict, status: dict) -> dict:
    """Добавить planned_restart и next_restart_at к статусу сервера."""
    server = components['config'].get_server(status['id'])
    if not server:
        return status

    planned = normalize_planned_restart(server.get('planned_restart'))
    enriched = dict(status)
    enriched['planned_restart'] = planned

    if is_planned_restart_enabled(server):
        next_at = compute_next_restart_at(int(planned['interval_minutes']))
        enriched['next_restart_at'] = next_at.isoformat(timespec='minutes') if next_at else None
    else:
        enriched['next_restart_at'] = None

    return enriched


async def read_json_object(request: Request, *, detail: str) -> dict:
    """Read a request body and ensure it is a JSON object."""
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail=detail)
    return body


# ============================================================
# Серверы
# ============================================================

@router.get("/api/servers")
async def list_servers(request: Request):
    """Список всех серверов"""
    components = get_components(request)
    status_list = components['server_mgr'].get_all_status()
    return {
        "servers": [enrich_server_status(components, status) for status in status_list]
    }


@router.get("/api/servers/{server_id}")
async def get_server(server_id: str, request: Request):
    """Инфо о сервере"""
    components = get_components(request)
    server = components['config'].get_server(server_id)

    if not server:
        raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found")

    status = components['server_mgr'].get_status(server)
    return {"server": enrich_server_status(components, status)}


@router.post("/api/servers/{server_id}/start")
async def start_server(server_id: str, request: Request, _: bool = Depends(require_api_key)):
    """Запуск сервера"""
    components = get_components(request)
    server = components['config'].get_server(server_id)

    if not server:
        raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found")

    prepared, mods_string = components['server_mgr'].prepare_server_for_start(server)
    if not prepared:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to prepare mods before starting server '{server_id}'"
        )

    # Запустить
    success = components['server_mgr'].start_server(server, mods_string)

    if success:
        return {"message": f"Server '{server_id}' started"}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to start server '{server_id}'")


@router.post("/api/servers/{server_id}/stop")
async def stop_server(server_id: str, request: Request, _: bool = Depends(require_api_key)):
    """Остановка сервера"""
    components = get_components(request)
    server = components['config'].get_server(server_id)

    if not server:
        raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found")

    success = components['server_mgr'].stop_server(server)

    if success:
        return {"message": f"Server '{server_id}' stopped"}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to stop server '{server_id}'")


@router.post("/api/servers/{server_id}/restart")
async def restart_server(server_id: str, request: Request, _: bool = Depends(require_api_key)):
    """Перезапуск сервера"""
    components = get_components(request)
    server = components['config'].get_server(server_id)

    if not server:
        raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found")

    prepared, mods_string = components['server_mgr'].prepare_server_for_start(server)
    if not prepared:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to prepare mods before restarting server '{server_id}'"
        )

    # Перезапустить
    success = components['server_mgr'].restart_server(server, mods_string)

    if success:
        return {"message": f"Server '{server_id}' restarted"}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to restart server '{server_id}'")


@router.get("/api/servers/{server_id}/logs/tail")
async def get_server_log_tail(server_id: str, request: Request, lines: int = 200):
    """Последние строки RPT из буфера watcher."""
    components = get_components(request)
    server = components['config'].get_server(server_id)

    if not server:
        raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found")

    watcher = components.get('rpt_watcher')
    if not watcher:
        return {"lines": []}

    lines = min(max(1, lines), 500)
    return {"lines": watcher.get_tail_lines(server_id, lines)}


@router.post("/api/servers/{server_id}/rcon/test")
async def test_server_rcon(server_id: str, request: Request, _: bool = Depends(require_api_key)):
    """Проверить RCON соединение для сервера"""
    components = get_components(request)
    server = components['config'].get_server(server_id)

    if not server:
        raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found")

    result = components['rcon'].test_server(server)
    return {
        "server_id": server_id,
        "rcon": result,
        "diagnostics": {
            "client_path": result.get('client_path'),
            "client_exists": result.get('client_exists'),
            "host": result.get('host'),
            "port": result.get('port'),
            "timeout": result.get('timeout'),
            "error_type": result.get('error_type'),
        }
    }


@router.get("/api/servers/{server_id}/chat")
async def get_server_chat(
    server_id: str,
    request: Request,
    limit: int = 200,
    since: Optional[str] = None,
):
    """История игрового чата (Expansion ExpLog)."""
    components = get_components(request)
    server = components['config'].get_server(server_id)

    if not server:
        raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found")

    watcher = components.get('chat_watcher')
    server_mgr = components.get('server_mgr')
    if watcher and server_mgr and server_mgr.is_running(server):
        watcher.ensure_session(server)

    if not watcher:
        return {"messages": [], "chat_available": False}

    return {
        "messages": watcher.get_messages(server_id, limit=limit, since=since),
        "chat_available": watcher.is_available(server),
    }


@router.post("/api/servers/{server_id}/chat/say")
async def say_in_game_chat(server_id: str, request: Request, _: bool = Depends(require_api_key)):
    """Отправить сообщение всем игрокам (RCON say -1). Только ручной текст админа."""
    components = get_components(request)
    server = components['config'].get_server(server_id)

    if not server:
        raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found")

    body = await read_json_object(request, detail="JSON body must be an object")
    message = (body.get("message") or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")
    if len(message) > 235:
        raise HTTPException(status_code=400, detail="message too long (max 235)")

    rcon = components['rcon']
    rcon_cfg = rcon._get_server_rcon_config(server)
    if not rcon_cfg.get("enabled"):
        raise HTTPException(status_code=400, detail="RCON is disabled for this server")

    ok = rcon.send_message(
        rcon_cfg["host"],
        rcon_cfg["port"],
        rcon_cfg["password"],
        message,
        rcon_cfg.get("timeout", 10),
    )
    if not ok:
        raise HTTPException(status_code=502, detail="RCON say failed")

    chat_entry = None
    watcher = components.get('chat_watcher')
    server_mgr = components.get('server_mgr')
    if watcher and server_mgr and server_mgr.is_running(server):
        watcher.ensure_session(server)
        chat_entry = watcher.inject_message(server_id, message, player="Admin", channel="Global")

    return {"ok": True, "message": message, "chat": chat_entry}


@router.post("/api/servers")
async def add_server(request: Request, _: bool = Depends(require_api_key)):
    """Добавить сервер"""
    components = get_components(request)
    body = await read_json_object(request, detail="Server payload must be an object")

    try:
        components['config'].add_server(body)
        return {"message": f"Server '{body.get('id')}' added"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/api/servers/{server_id}")
async def update_server(server_id: str, request: Request, _: bool = Depends(require_api_key)):
    """Обновить настройки сервера"""
    components = get_components(request)
    body = await read_json_object(request, detail="Server payload must be an object")

    if not components['config'].get_server(server_id):
        raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found")

    try:
        components['config'].update_server(server_id, body)
        return {"message": f"Server '{server_id}' updated"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/api/servers/{server_id}")
async def remove_server(server_id: str, request: Request, _: bool = Depends(require_api_key)):
    """Удалить сервер"""
    components = get_components(request)

    try:
        components['config'].remove_server(server_id)
        return {"message": f"Server '{server_id}' removed"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ============================================================
# Моды
# ============================================================

@router.post("/api/mods/check")
async def check_mods(request: Request, _: bool = Depends(require_api_key)):
    """Проверить обновления модов"""
    components = get_components(request)
    servers = components['config'].servers

    results = {}
    updates = {}
    for server in servers:
        status = components['mod_sync'].get_mod_update_status(server)
        results[server['id']] = status
        updates[server['id']] = status.get('updated_mods', [])

    return {"updates": updates, "details": results}


@router.post("/api/mods/sync")
async def sync_mods(request: Request, _: bool = Depends(require_api_key)):
    """Синхронизировать моды"""
    components = get_components(request)
    servers = components['config'].servers

    results = {}
    for server in servers:
        mods_string = components['mod_sync'].sync_mods(server)
        results[server['id']] = mods_string

    return {"synced": results}


# ============================================================
# Логи
# ============================================================

@router.get("/api/logs")
async def get_logs(request: Request, limit: int = 100):
    """Получить последние логи"""
    components = get_components(request)
    logs = components['logger'].get_recent_logs(limit)
    return {"logs": logs}


@router.post("/api/logs/clean")
async def clean_logs(request: Request, _: bool = Depends(require_api_key)):
    """Очистить старые логи"""
    components = get_components(request)
    days = components['config'].get('settings.log_retention_days', 2)
    components['logger'].clean_old_logs(days)
    return {"message": f"Logs cleaned (older than {days} days)"}


# ============================================================
# Настройки
# ============================================================

@router.get("/api/settings")
async def get_settings(request: Request):
    """Получить глобальные настройки"""
    components = get_components(request)
    settings = {
        'watchdog_interval': components['config'].get('settings.watchdog_interval'),
        'restart_notify_minutes': components['config'].get('settings.restart_notify_minutes'),
        'log_retention_days': components['config'].get('settings.log_retention_days'),
        'start_confirm_timeout': components['config'].get('settings.start_confirm_timeout'),
        'mod_check_interval': components['config'].get('scheduler.mod_check_interval'),
        'startup_ready_timeout_sec': components['config'].get('settings.startup_ready_timeout_sec'),
        'rpt_tail_buffer_lines': components['config'].get('settings.rpt_tail_buffer_lines'),
        'rpt_poll_interval_ms': components['config'].get('settings.rpt_poll_interval_ms'),
    }
    return {"settings": settings}


SETTINGS_KEY_PATHS = {
    'watchdog_interval': 'settings.watchdog_interval',
    'restart_notify_minutes': 'settings.restart_notify_minutes',
    'log_retention_days': 'settings.log_retention_days',
    'start_confirm_timeout': 'settings.start_confirm_timeout',
    'mod_check_interval': 'scheduler.mod_check_interval',
    'startup_ready_timeout_sec': 'settings.startup_ready_timeout_sec',
    'rpt_tail_buffer_lines': 'settings.rpt_tail_buffer_lines',
    'rpt_poll_interval_ms': 'settings.rpt_poll_interval_ms',
}


@router.put("/api/settings")
async def update_settings(request: Request, _: bool = Depends(require_api_key)):
    """Обновить настройки"""
    components = get_components(request)
    body = await read_json_object(request, detail="Settings payload must be an object")

    validated = []
    config = components['config']
    for key, value in body.items():
        path = SETTINGS_KEY_PATHS.get(key)
        if not path:
            continue
        try:
            config.validate_setting_value(path, value)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        validated.append((key, path, value))

    updated = []
    for key, path, value in validated:
        config.set(path, value)
        updated.append(key)

    if 'mod_check_interval' in updated:
        scheduler = getattr(request.app.state, 'scheduler', None)
        if scheduler:
            await scheduler.reschedule_mod_check(
                components['config'].get('scheduler.mod_check_interval', 600)
            )

    return {"message": "Settings updated", "updated": updated}


# ============================================================
# Управление менеджером
# ============================================================

@router.post("/api/shutdown")
async def shutdown_manager(request: Request, _: bool = Depends(require_api_key)):
    """Выключить менеджер (остановить все серверы и выйти)"""
    components = get_components(request)
    logger = components['logger']

    logger.info("Shutdown requested via API")

    # Остановить все серверы
    servers = components['config'].servers
    for server in servers:
        try:
            if components['server_mgr'].is_running(server):
                logger.info(f"Stopping {server['id']}...")
                components['server_mgr'].stop_server(server, force=True)
        except Exception as e:
            logger.error(f"Error stopping {server['id']}: {e}")

    # Запланировать выход
    import asyncio
    async def delayed_exit():
        await asyncio.sleep(1)
        import os
        os._exit(0)

    asyncio.create_task(delayed_exit())

    return {"message": "Manager shutting down"}
