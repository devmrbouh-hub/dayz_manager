"""Tail DayZ server RPT logs, detect READY phase, broadcast to WebSocket subscribers."""

from __future__ import annotations

import asyncio
import json
import re
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Deque, Dict, List, Optional, Set

DEFAULT_READY_MARKER = "[IdleMode] Entering IN - save processed"
WEAPON_SPAM_PREFIX = "WEAPON       : wpn:"
MAX_LINE_BYTES = 16 * 1024
TAIL_SCAN_BYTES = 128 * 1024
RPT_GLOB = "DayZServer_x64_*.RPT"
FPS_LINE_RE = re.compile(r"Average server FPS:\s*([\d.]+)")


def parse_fps_line(line: str) -> Optional[float]:
    match = FPS_LINE_RE.search(line)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


@dataclass
class ServerSession:
    server_id: str
    profiles_dir: Path
    ready_marker: str
    started_at: float
    phase: str = "starting"
    ready_once: bool = False
    ready_at: Optional[str] = None
    current_rpt: Optional[str] = None
    startup_warning: Optional[str] = None
    rpt_path: Optional[Path] = None
    stop_event: threading.Event = field(default_factory=threading.Event)
    thread: Optional[threading.Thread] = None
    buffer: Deque[str] = field(default_factory=lambda: deque(maxlen=500))
    subscribers: Set[asyncio.Queue] = field(default_factory=set)
    partial_line: bytes = b""
    file_pos: int = 0
    hide_weapon_spam: bool = True
    ready_deadline: float = 0.0
    last_fps: Optional[float] = None


class ServerRptWatcher:
    """Per-server RPT tail and startup phase tracking."""

    def __init__(self, config, logger=None, loop: Optional[asyncio.AbstractEventLoop] = None):
        self.config = config
        self.logger = logger
        self._loop = loop
        self._sessions: Dict[str, ServerSession] = {}
        self._lock = threading.Lock()
        self._is_running_cb: Optional[Callable[[dict], bool]] = None

    def set_running_checker(self, callback: Callable[[dict], bool]):
        self._is_running_cb = callback

    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    def _log(self, message: str, level: str = "INFO"):
        if self.logger:
            self.logger.log(message, level)

    def _profiles_dir(self, server: dict) -> Path:
        server_dir = Path(server["path"])
        profiles = server.get("profiles", "Instance_1")
        return server_dir / profiles

    def _ready_marker(self, server: dict) -> str:
        marker = (server.get("startup_ready_marker") or "").strip()
        if not marker:
            return DEFAULT_READY_MARKER
        if len(marker) < 10:
            self._log(
                f"startup_ready_marker too short for {server.get('id')}, using default",
                "WARN",
            )
            return DEFAULT_READY_MARKER
        return marker

    def _buffer_max(self) -> int:
        return int(self.config.get("settings.rpt_tail_buffer_lines", 500))

    def _poll_ms(self) -> float:
        return float(self.config.get("settings.rpt_poll_interval_ms", 200)) / 1000.0

    def _ready_timeout_sec(self) -> float:
        return float(self.config.get("settings.startup_ready_timeout_sec", 180))

    def _find_rpt(self, profiles_dir: Path, after_ts: float) -> Optional[Path]:
        if not profiles_dir.is_dir():
            return None
        cutoff = after_ts - 2.0
        candidates = []
        for path in profiles_dir.glob(RPT_GLOB):
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if mtime >= cutoff:
                candidates.append((mtime, path))
        if not candidates:
            return None
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    def _find_latest_rpt(self, profiles_dir: Path) -> Optional[Path]:
        if not profiles_dir.is_dir():
            return None
        latest = None
        latest_mtime = 0.0
        for path in profiles_dir.glob(RPT_GLOB):
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if mtime > latest_mtime:
                latest_mtime = mtime
                latest = path
        return latest

    def _decode_line(self, raw: bytes) -> str:
        for enc in ("utf-8", "cp1251"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")

    def _should_filter_weapon(self, line: str, session: ServerSession) -> bool:
        return session.hide_weapon_spam and WEAPON_SPAM_PREFIX in line

    def _truncate_line(self, line: str) -> str:
        if len(line.encode("utf-8", errors="replace")) <= MAX_LINE_BYTES:
            return line
        return line[:2000] + "…"

    def _process_line(self, session: ServerSession, line: str):
        line = line.rstrip("\r\n")
        if not line:
            return

        fps = parse_fps_line(line)
        if fps is not None:
            session.last_fps = fps

        highlight = False
        if not session.ready_once and session.ready_marker in line:
            session.ready_once = True
            session.phase = "ready"
            session.ready_at = datetime.now().isoformat(timespec="seconds")
            session.startup_warning = None
            highlight = True
            self._broadcast_ready(session)

        session.buffer.append(line)
        if self._should_filter_weapon(line, session):
            return

        self._broadcast_line(session, line, highlight)

    def _broadcast_line(self, session: ServerSession, line: str, highlight: bool):
        if not session.subscribers:
            return
        payload = json.dumps(
            {"t": "l", "m": self._truncate_line(line), "h": highlight},
            ensure_ascii=False,
        )
        self._dispatch(session, payload)

    def _broadcast_ready(self, session: ServerSession):
        payload = json.dumps({"t": "r", "at": session.ready_at})
        self._dispatch(session, payload)

    def _broadcast_status(self, session: ServerSession):
        payload = json.dumps(
            {
                "t": "s",
                "phase": session.phase,
                "warning": session.startup_warning,
                "rpt": session.current_rpt,
            }
        )
        self._dispatch(session, payload)

    def _dispatch(self, session: ServerSession, payload: str):
        loop = self._loop
        if loop is None:
            return
        for queue in list(session.subscribers):
            try:
                loop.call_soon_threadsafe(self._put_queue, queue, payload)
            except RuntimeError:
                pass

    @staticmethod
    def _put_queue(queue: asyncio.Queue, payload: str):
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                pass

    def _scan_tail_for_ready(self, session: ServerSession, path: Path) -> bool:
        try:
            size = path.stat().st_size
        except OSError:
            return False
        read_from = max(0, size - TAIL_SCAN_BYTES)
        try:
            with open(path, "rb") as f:
                f.seek(read_from)
                data = f.read()
        except OSError:
            return False
        text = self._decode_line(data)
        for line in text.splitlines():
            if session.ready_marker in line:
                session.ready_once = True
                session.phase = "ready"
                session.ready_at = datetime.now().isoformat(timespec="seconds")
                session.startup_warning = None
                return True
        return False

    def _tail_loop(self, session: ServerSession):
        profiles_dir = session.profiles_dir
        poll = self._poll_ms()
        find_deadline = time.time() + 30.0

        while not session.stop_event.is_set():
            if session.rpt_path is None:
                if time.time() > find_deadline:
                    session.startup_warning = "rpt_not_found"
                    self._log(
                        f"RPT not found for {session.server_id} in {profiles_dir}",
                        "WARN",
                    )
                    self._broadcast_status(session)
                    while not session.stop_event.is_set():
                        if self._is_running_cb:
                            server = self.config.get_server(session.server_id)
                            if server and not self._is_running_cb(server):
                                session.phase = "stopped"
                                return
                        time.sleep(1.0)
                    return
                path = self._find_rpt(profiles_dir, session.started_at)
                if path:
                    session.rpt_path = path
                    session.current_rpt = path.name
                    session.file_pos = 0
                    if self._scan_tail_for_ready(session, path):
                        session.file_pos = path.stat().st_size
                        self._broadcast_ready(session)
                else:
                    time.sleep(0.5)
                    continue

            path = session.rpt_path
            if path is None or not path.exists():
                time.sleep(poll)
                continue

            newer = self._find_rpt(profiles_dir, session.started_at)
            if newer and newer != path:
                try:
                    if newer.stat().st_mtime > path.stat().st_mtime:
                        session.rpt_path = newer
                        session.current_rpt = newer.name
                        session.file_pos = 0
                        session.partial_line = b""
                        path = newer
                except OSError:
                    pass

            if (
                not session.ready_once
                and session.ready_deadline
                and time.time() > session.ready_deadline
                and session.startup_warning != "ready_timeout"
            ):
                session.startup_warning = "ready_timeout"
                self._log(f"Ready marker timeout for {session.server_id}", "WARN")
                self._broadcast_status(session)

            try:
                with open(path, "rb") as f:
                    f.seek(session.file_pos)
                    chunk = f.read()
            except OSError:
                time.sleep(poll)
                continue

            if not chunk:
                time.sleep(poll)
                continue

            session.file_pos += len(chunk)
            data = session.partial_line + chunk
            lines = data.split(b"\n")
            session.partial_line = lines[-1]
            for raw in lines[:-1]:
                self._process_line(session, self._decode_line(raw))

            if chunk:
                continue
            time.sleep(poll)

    def begin_session(self, server: dict):
        server_id = server["id"]
        self.end_session(server_id)

        buf_max = self._buffer_max()
        session = ServerSession(
            server_id=server_id,
            profiles_dir=self._profiles_dir(server),
            ready_marker=self._ready_marker(server),
            started_at=time.time(),
            phase="starting",
            ready_deadline=time.time() + self._ready_timeout_sec(),
            buffer=deque(maxlen=buf_max),
        )
        session.buffer = deque(maxlen=buf_max)

        with self._lock:
            self._sessions[server_id] = session

        session.thread = threading.Thread(
            target=self._tail_loop,
            args=(session,),
            name=f"rpt-tail-{server_id}",
            daemon=True,
        )
        session.thread.start()
        self._log(f"RPT session started for {server_id}", "DEBUG")

    def end_session(self, server_id: str):
        with self._lock:
            session = self._sessions.pop(server_id, None)
        if not session:
            return
        session.stop_event.set()
        session.phase = "stopped"
        session.ready_once = False
        session.ready_at = None
        session.current_rpt = None
        session.startup_warning = None
        if session.thread and session.thread.is_alive():
            session.thread.join(timeout=3.0)
        session.subscribers.clear()
        self._log(f"RPT session ended for {server_id}", "DEBUG")

    def sync_process_state(self, server: dict, running: bool):
        """Reset phase when process died; lazy attach when running without session."""
        server_id = server["id"]
        with self._lock:
            session = self._sessions.get(server_id)

        if not running:
            if session:
                self.end_session(server_id)
            return

        if session is None:
            self._lazy_attach(server)
            return

        if session.phase != "stopped" and not running:
            self.end_session(server_id)

    def _lazy_attach(self, server: dict):
        server_id = server["id"]
        profiles_dir = self._profiles_dir(server)
        path = self._find_latest_rpt(profiles_dir)
        if not path:
            return

        buf_max = self._buffer_max()
        session = ServerSession(
            server_id=server_id,
            profiles_dir=profiles_dir,
            ready_marker=self._ready_marker(server),
            started_at=path.stat().st_mtime,
            phase="starting",
            rpt_path=path,
            current_rpt=path.name,
            file_pos=max(0, path.stat().st_size - TAIL_SCAN_BYTES),
            ready_deadline=time.time() + self._ready_timeout_sec(),
            buffer=deque(maxlen=buf_max),
        )

        if self._scan_tail_for_ready(session, path):
            session.file_pos = path.stat().st_size
        else:
            session.file_pos = max(0, path.stat().st_size - TAIL_SCAN_BYTES)

        with self._lock:
            if server_id in self._sessions:
                return
            self._sessions[server_id] = session

        session.thread = threading.Thread(
            target=self._tail_loop,
            args=(session,),
            name=f"rpt-tail-{server_id}",
            daemon=True,
        )
        session.thread.start()
        self._log(f"RPT lazy attach for {server_id} ({path.name})", "INFO")

    def get_startup_info(self, server: dict, running: bool) -> dict:
        server_id = server["id"]
        if not running:
            return {
                "startup_phase": "stopped",
                "ready_at": None,
                "current_rpt": None,
                "startup_warning": None,
                "server_fps": None,
            }

        self.sync_process_state(server, running)

        with self._lock:
            session = self._sessions.get(server_id)

        if not session:
            return {
                "startup_phase": "starting",
                "ready_at": None,
                "current_rpt": None,
                "startup_warning": None,
                "server_fps": None,
            }

        fps = session.last_fps
        return {
            "startup_phase": session.phase if session.phase else "starting",
            "ready_at": session.ready_at,
            "current_rpt": session.current_rpt,
            "startup_warning": session.startup_warning,
            "server_fps": round(fps) if fps is not None else None,
        }

    def subscribe(self, server_id: str) -> Optional[asyncio.Queue]:
        with self._lock:
            session = self._sessions.get(server_id)
            if not session:
                return None
            queue: asyncio.Queue = asyncio.Queue(maxsize=200)
            session.subscribers.add(queue)
            return queue

    def unsubscribe(self, server_id: str, queue: asyncio.Queue):
        with self._lock:
            session = self._sessions.get(server_id)
            if session and queue in session.subscribers:
                session.subscribers.discard(queue)

    def get_tail_lines(self, server_id: str, lines: int = 200) -> List[str]:
        lines = min(max(1, lines), 500)
        with self._lock:
            session = self._sessions.get(server_id)
            if not session:
                return []
            buf = list(session.buffer)
        return buf[-lines:]

    def shutdown(self):
        with self._lock:
            ids = list(self._sessions.keys())
        for sid in ids:
            self.end_session(sid)
