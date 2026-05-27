"""Background RCON poll for online players (card metrics)."""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Dict, List, Optional

from src.core.rcon_client import RconClient


class ServerLiveStats:
    """Poll RCON `players` for running servers."""

    def __init__(self, config, rcon: RconClient, server_mgr, logger=None):
        self.config = config
        self.rcon = rcon
        self.server_mgr = server_mgr
        self.logger = logger
        self._cache: Dict[str, dict] = {}
        self._lock = threading.Lock()
        self._task: Optional[asyncio.Task] = None
        self._running = False

    def _log(self, message: str, level: str = "INFO"):
        if self.logger:
            self.logger.log(message, level)

    def _interval_sec(self) -> float:
        return float(self.config.get("settings.live_stats_interval_sec", 5))

    async def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        self._log(f"Live stats poll started (every {self._interval_sec()}s)", "DEBUG")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _poll_loop(self):
        while self._running:
            try:
                await asyncio.to_thread(self._poll_all)
            except Exception as e:
                self._log(f"Live stats poll error: {e}", "WARN")
            await asyncio.sleep(self._interval_sec())

    def _poll_all(self):
        for server in self.config.servers:
            server_id = server["id"]
            max_players = self.server_mgr.read_max_players(server)

            if not self.server_mgr.is_running(server):
                with self._lock:
                    self._cache[server_id] = {
                        "player_count": 0,
                        "max_players": max_players,
                        "players": [],
                        "rcon_players_ok": False,
                    }
                continue

            rcon_cfg = self.rcon._get_server_rcon_config(server)
            players: List[Dict[str, Any]] = []
            ok = False

            if rcon_cfg.get("enabled"):
                output = self.rcon.send_players(
                    rcon_cfg["host"],
                    rcon_cfg["port"],
                    rcon_cfg["password"],
                    rcon_cfg.get("timeout", 10),
                )
                if output is not None:
                    players = self.rcon.parse_players(output)
                    ok = True

            with self._lock:
                self._cache[server_id] = {
                    "player_count": len(players),
                    "max_players": max_players,
                    "players": players,
                    "rcon_players_ok": ok,
                }

    def get_info(self, server_id: str, running: bool) -> dict:
        with self._lock:
            cached = dict(self._cache.get(server_id, {}))

        if not running:
            return {
                "player_count": 0,
                "max_players": cached.get("max_players"),
                "players": [],
                "rcon_players_ok": False,
            }

        return {
            "player_count": cached.get("player_count", 0),
            "max_players": cached.get("max_players"),
            "players": cached.get("players", []),
            "rcon_players_ok": cached.get("rcon_players_ok", False),
        }
