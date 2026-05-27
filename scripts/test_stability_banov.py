#!/usr/bin/env python3
"""Локальные проверки стабилизации на сервере banov (d:\\Banov)."""

import json
import os
import sys
import time
import urllib.request
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.core.config import Config
from src.core.server_mgr import ServerManager
from src.core.mod_sync import ModSync
from src.utils.logger import LoggerManager


API_KEY = None


def api_request(method: str, path: str, body: dict = None):
    url = f"http://127.0.0.1:8000{path}"
    data = None
    headers = {"X-API-Key": API_KEY}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    global API_KEY

    os.chdir(ROOT)
    config = Config()
    config.load()
    API_KEY = config.get("auth.api_key")

    server = config.get_server("banov")
    if not server:
        print("FAIL: server banov not in config")
        return 1

    logger = LoggerManager()
    mgr = ServerManager(config, logger)
    mod_sync = ModSync(config, logger)

    print("=== Banov stability checks ===\n")
    passed = 0
    failed = 0

    # Lock helpers
    if mgr.acquire_lock(server):
        print("OK  acquire_lock")
        passed += 1
        if mgr.is_locked(server):
            print("OK  is_locked while held")
            passed += 1
        mgr.release_lock(server)
        if not mgr.is_locked(server):
            print("OK  release_lock")
            passed += 1
    else:
        print("WARN acquire_lock failed (SERVER_LOCK may already exist)")
        failed += 1

    # Port warn (should not raise)
    try:
        mgr._validate_config_ports(server)
        print("OK  _validate_config_ports")
        passed += 1
    except Exception as e:
        print(f"FAIL _validate_config_ports: {e}")
        failed += 1

    # Mod IDs
    effective = mod_sync.get_effective_mods(server)
    bad = [m for m in effective if m.get("update_enabled") and not str(m.get("id", "")).isdigit()]
    if not bad:
        print(f"OK  effective_mods ({len(effective)} mods, digit IDs only)")
        passed += 1
    else:
        print(f"FAIL invalid update_enabled mods: {bad[:3]}")
        failed += 1

    status = mgr.get_status(server)
    print(f"INFO server status: running={status['running']} pid={status['pid']} auto_restart={status['auto_restart']}")
    stopped = (mgr._server_dir(server) / ".stopped").exists()
    print(f"INFO .stopped present: {stopped}")

    # API tests (manager must be running)
    print("\n--- API (manager on :8000) ---")
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/api/servers", timeout=5) as resp:
            data = json.loads(resp.read().decode())
        print("OK  GET /api/servers")
        passed += 1

        rcon = api_request("POST", "/api/servers/banov/rcon/test")
        ok = rcon.get("rcon", {}).get("success")
        print(f"{'OK' if ok else 'WARN'} POST rcon/test success={ok} msg={rcon.get('rcon', {}).get('message', '')[:80]}")
        if ok:
            passed += 1
        else:
            failed += 1

        settings_before = api_request("GET", "/api/settings")
        api_request("PUT", "/api/settings", {"mod_check_interval": 601})
        settings_after = api_request("GET", "/api/settings")
        if settings_after["settings"].get("mod_check_interval") == 601:
            print("OK  PUT mod_check_interval -> 601")
            passed += 1
        else:
            print("FAIL mod_check_interval not updated in GET")
            failed += 1
        api_request("PUT", "/api/settings", {"mod_check_interval": settings_before["settings"].get("mod_check_interval", 600)})
        print("OK  restored mod_check_interval")

        try:
            mods = api_request("POST", "/api/mods/check")
            updates = mods.get("updates", {}).get("banov", [])
            print(f"OK  POST /api/mods/check updates={len(updates)}")
            passed += 1
        except TimeoutError:
            print("WARN POST /api/mods/check timed out (Steam API slow; not a stability regression)")

    except urllib.error.URLError as e:
        print(f"SKIP API tests (start manager first): {e}")
        print("  Run: cd dayz_manager && python src/main.py")

    print(f"\n=== Done: passed={passed} failed={failed} ===")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
