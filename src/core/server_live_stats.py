"""Background RCON poll for online players (card metrics)."""

from __future__ import annotations

import asyncio
import threading
from collections import defaultdict
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
        self._server_poll_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
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

    def _poll_one_server(self, server: dict) -> dict:
        """RCON players for one server; updates cache. Caller should hold server poll lock."""
        server_id = server["id"]
        max_players = self.server_mgr.read_max_players(server)

        if not self.server_mgr.is_running(server):
            snapshot = {
                "player_count": 0,
                "max_players": max_players,
                "players": [],
                "rcon_players_ok": False,
            }
            with self._lock:
                self._cache[server_id] = snapshot
            return dict(snapshot)

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

        snapshot = {
            "player_count": len(players),
            "max_players": max_players,
            "players": players,
            "rcon_players_ok": ok,
        }
        with self._lock:
            self._cache[server_id] = snapshot
        return dict(snapshot)

    def _poll_all(self):
        for server in self.config.servers:
            server_id = server["id"]
            with self._server_poll_locks[server_id]:
                self._poll_one_server(server)

    def refresh_server(self, server_id: str) -> dict:
        """Force one RCON players poll for a server (API / UI refresh)."""
        server = self.config.get_server(server_id)
        if not server:
            raise KeyError(f"Server '{server_id}' not found")
        if not self.server_mgr.is_running(server):
            raise RuntimeError(f"Server '{server_id}' is not running")

        with self._server_poll_locks[server_id]:
            return self._poll_one_server(server)

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
