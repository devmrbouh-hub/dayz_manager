#!/usr/bin/env python3
"""Smoke: RPT/READY fields on live manager (optional, manager must be running)."""

import json
import os
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.core.config import Config  # noqa: E402

API_BASE = os.environ.get("DAYZ_MANAGER_API", "http://127.0.0.1:8000")
SERVER_ID = os.environ.get("DAYZ_MANAGER_SERVER", "banov")


def api_get(path: str, api_key: str = None):
    headers = {}
    if api_key:
        headers["X-API-Key"] = api_key
    req = urllib.request.Request(f"{API_BASE}{path}", headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    os.chdir(ROOT)
    try:
        config = Config()
        config.load()
        api_key = config.get("auth.api_key")
    except Exception as e:
        print(f"SKIP: config not loadable: {e}")
        return 0

    try:
        data = api_get(f"/api/servers/{SERVER_ID}", api_key)
    except urllib.error.URLError as e:
        print(f"SKIP: manager not reachable at {API_BASE}: {e}")
        return 0

    server = data.get("server", {})
    required = ("startup_phase", "ready_at", "current_rpt", "startup_warning", "running")
    missing = [k for k in required if k not in server]
    if missing:
        print(f"FAIL: missing fields: {missing}")
        return 1

    print(f"OK  GET /api/servers/{SERVER_ID}")
    print(f"    running={server.get('running')} phase={server.get('startup_phase')}")
    print(f"    rpt={server.get('current_rpt')} warning={server.get('startup_warning')}")

    tail = api_get(f"/api/servers/{SERVER_ID}/logs/tail?lines=5", api_key)
    if "lines" not in tail:
        print("FAIL: logs/tail missing 'lines'")
        return 1
    print(f"OK  logs/tail ({len(tail['lines'])} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
