"""Resolve server id for helper scripts: DAYZ_MANAGER_SERVER or first entry in config."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resolve_server_id(config) -> str:
    sid = os.environ.get("DAYZ_MANAGER_SERVER", "").strip()
    if sid:
        if config.get_server(sid):
            return sid
        print(f"FAIL: DAYZ_MANAGER_SERVER={sid!r} not found in config.json")
        sys.exit(1)
    servers = config.get("servers") or []
    if not servers:
        print("FAIL: no servers in config.json")
        sys.exit(1)
    return servers[0]["id"]
