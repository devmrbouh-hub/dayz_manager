#!/usr/bin/env python3
"""Start a server without SteamCMD pre-download (sync mods + start only)."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.core.config import Config
from src.core.server_mgr import ServerManager
from src.core.mod_sync import ModSync
from src.utils.logger import LoggerManager
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _resolve_server import resolve_server_id


def main():
    os.chdir(ROOT)
    config = Config()
    config.load()
    server_id = resolve_server_id(config)
    server = config.get_server(server_id)
    logger = LoggerManager()
    mgr = ServerManager(config, logger)
    mod_sync = ModSync(config, logger)

    server_dir = mgr._server_dir(server)
    print(f"server_id={server_id}")
    print(f".stopped before: {(server_dir / '.stopped').exists()}")
    print(f"lock before: {mgr.is_locked(server)}")

    mods_string = mod_sync.sync_mods(server)
    print(f"mods_string length: {len(mods_string)}")

    ok = mgr.start_server(server, mods_string, clear_stopped=True)
    status = mgr.get_status(server)
    print(f"start_server: {ok}")
    print(f"status: {status}")
    print(f".stopped after: {(server_dir / '.stopped').exists()}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
