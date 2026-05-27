"""Tail Expansion ExpLog for in-game chat; broadcast to WebSocket subscribers."""

from __future__ import annotations

import asyncio
import json
import re
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Deque, Dict, List, Optional, Set, Tuple

EXPLOG_GLOB = "ExpLog_*.log"
EXPLOG_DIR = Path("ExpansionMod") / "Logs"
RESCAN_TAIL_BYTES = 256 * 1024
EXPLOG_NAME_RE = re.compile(
    r"ExpLog_(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})-(\d{2})\.log$"
)
CHAT_LINE_RE = re.compile(
    r'^(\d{2}:\d{2}:\d{2}\.\d{3})\s+\[Chat - ([^\]]+)\]\("([^"]+)"\(id=([^)]+)\)\):\s*(.*)$'
)
LINE_TIME_RE = re.compile(r"^(\d{2}):(\d{2}):(\d{2})\.(\d{3})")


@dataclass
class ChatMessage:
    ts: str
    channel: str
    player: str
    text: str

    def to_dict(self) -> dict:
        return {
            "ts": self.ts,
            "channel": self.channel,
            "player": self.player,
            "text": self.text,
        }


def message_key(msg: ChatMessage) -> Tuple[str, str, str, str]:
    return (msg.ts, msg.channel, msg.player, msg.text)


@dataclass
class ChatSession:
    server_id: str
    logs_dir: Path
    history_hours: float
    buffer_max: int
    stop_event: threading.Event = field(default_factory=threading.Event)
    thread: Optional[threading.Thread] = None
    buffer: Deque[ChatMessage] = field(default_factory=deque)
    subscribers: Set[asyncio.Queue] = field(default_factory=set)
    log_path: Optional[Path] = None
    file_pos: int = 0
    partial_line: bytes = b""
    file_base: Optional[datetime] = None
    seen_keys: Set[Tuple[str, str, str, str]] = field(default_factory=set)
    last_rescan: float = 0.0


def parse_explog_filename(path: Path) -> Optional[datetime]:
    match = EXPLOG_NAME_RE.match(path.name)
    if not match:
        return None
    y, mo, d, h, mi, s = (int(match.group(i)) for i in range(1, 7))
    return datetime(y, mo, d, h, mi, s)


def line_time_to_ts(file_base: datetime, line_time: str) -> str:
    """ExpLog line times are wall-clock (HH:MM:SS), not elapsed since log start."""
    match = LINE_TIME_RE.match(line_time)
    if not match:
        return file_base.isoformat(timespec="seconds")
    hours, minutes, seconds = (int(match.group(i)) for i in range(1, 4))
    millis = int(match.group(4))
    dt = file_base.replace(
        hour=hours,
        minute=minutes,
        second=seconds,
        microsecond=millis * 1000,
    )
    if dt < file_base:
        dt += timedelta(days=1)
    return dt.isoformat(timespec="milliseconds")


def parse_chat_line(line: str, file_base: datetime) -> Optional[ChatMessage]:
    match = CHAT_LINE_RE.match(line.rstrip("\r\n"))
    if not match:
        return None
    line_time, channel, player, _player_id, text = match.groups()
    return ChatMessage(
        ts=line_time_to_ts(file_base, line_time),
        channel=channel.strip(),
        player=player.strip(),
        text=text,
    )


class ServerChatWatcher:
    """Per-server Expansion chat tail and history buffer."""

    def __init__(self, config, logger=None, loop: Optional[asyncio.AbstractEventLoop] = None):
        self.config = config
        self.logger = logger
        self._loop = loop
        self._sessions: Dict[str, ChatSession] = {}
        self._lock = threading.Lock()

    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    def _log(self, message: str, level: str = "INFO"):
        if self.logger:
            self.logger.log(message, level)

    def _logs_dir(self, server: dict) -> Path:
        server_dir = Path(server["path"])
        profiles = server.get("profiles", "Instance_1")
        return server_dir / profiles / EXPLOG_DIR

    def _history_hours(self, server: dict) -> float:
        return float(server.get("chat_history_hours", 24))

    def _buffer_max(self, server: dict) -> int:
        return int(server.get("chat_buffer_max", 5000))

    def _poll_ms(self) -> float:
        return float(self.config.get("settings.chat_poll_interval_ms", 500)) / 1000.0

    def _rescan_interval_sec(self) -> float:
        return float(self.config.get("settings.chat_rescan_interval_sec", 5))

    def ensure_session(self, server: dict) -> bool:
        """Start chat tail session if missing (e.g. manager restarted while DayZ runs)."""
        server_id = server["id"]
        with self._lock:
            if server_id in self._sessions:
                return True
        self.begin_session(server)
        return True

    def is_available(self, server: dict) -> bool:
        server_id = server.get("id", "")
        with self._lock:
            if server_id in self._sessions:
                return True
        return self._logs_dir(server).is_dir()

    def _decode_line(self, raw: bytes) -> str:
        for enc in ("utf-8", "cp1251"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")

    def _cutoff_dt(self, hours: float) -> datetime:
        return datetime.now() - timedelta(hours=hours)

    def _prune_buffer(self, session: ChatSession):
        cutoff = self._cutoff_dt(session.history_hours)
        while session.buffer:
            try:
                first_ts = datetime.fromisoformat(session.buffer[0].ts)
            except ValueError:
                session.buffer.popleft()
                continue
            if first_ts >= cutoff:
                break
            session.buffer.popleft()

    def _append_message(self, session: ChatSession, msg: ChatMessage, broadcast: bool = True):
        cutoff = self._cutoff_dt(session.history_hours)
        try:
            msg_dt = datetime.fromisoformat(msg.ts)
        except ValueError:
            return
        if msg_dt < cutoff:
            return

        key = message_key(msg)
        if key in session.seen_keys:
            return
        session.seen_keys.add(key)

        session.buffer.append(msg)
        self._prune_buffer(session)
        if broadcast:
            self._broadcast_message(session, msg)

    def _load_history(self, session: ChatSession):
        logs_dir = session.logs_dir
        if not logs_dir.is_dir():
            return

        cutoff = self._cutoff_dt(session.history_hours)
        candidates: List[Path] = []
        for path in logs_dir.glob(EXPLOG_GLOB):
            base = parse_explog_filename(path)
            if base is None:
                try:
                    base = datetime.fromtimestamp(path.stat().st_mtime)
                except OSError:
                    continue
            if base >= cutoff:
                candidates.append(path)

        candidates.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0)

        for path in candidates:
            base = parse_explog_filename(path)
            if base is None:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for line in text.splitlines():
                msg = parse_chat_line(line, base)
                if msg:
                    self._append_message(session, msg, broadcast=False)

    def _rescan_recent(self, session: ChatSession):
        """Re-read tails of recent ExpLog files (catches new files and missed lines)."""
        logs_dir = session.logs_dir
        if not logs_dir.is_dir():
            return

        cutoff = self._cutoff_dt(session.history_hours)
        paths = sorted(
            logs_dir.glob(EXPLOG_GLOB),
            key=lambda p: p.stat().st_mtime if p.exists() else 0,
        )
        for path in paths:
            base = parse_explog_filename(path)
            if base is None:
                try:
                    base = datetime.fromtimestamp(path.stat().st_mtime)
                except OSError:
                    continue
            if base < cutoff:
                continue
            try:
                size = path.stat().st_size
                with open(path, "rb") as f:
                    f.seek(max(0, size - RESCAN_TAIL_BYTES))
                    text = self._decode_line(f.read())
            except OSError:
                continue
            for line in text.splitlines():
                msg = parse_chat_line(line, base)
                if msg:
                    self._append_message(session, msg)

    def inject_message(
        self,
        server_id: str,
        text: str,
        player: str = "Admin",
        channel: str = "Global",
    ) -> Optional[dict]:
        """Add message to buffer (RCON say does not appear in ExpLog)."""
        with self._lock:
            session = self._sessions.get(server_id)
        if not session:
            return None
        msg = ChatMessage(
            ts=datetime.now().isoformat(timespec="milliseconds"),
            channel=channel,
            player=player,
            text=text,
        )
        self._append_message(session, msg)
        return msg.to_dict()

    def _find_latest_log(self, logs_dir: Path) -> Optional[Path]:
        latest = None
        latest_mtime = 0.0
        for path in logs_dir.glob(EXPLOG_GLOB):
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if mtime > latest_mtime:
                latest_mtime = mtime
                latest = path
        return latest

    def _broadcast_message(self, session: ChatSession, msg: ChatMessage):
        if not session.subscribers:
            return
        payload = json.dumps({"t": "c", **msg.to_dict()}, ensure_ascii=False)
        self._dispatch(session, payload)

    def _dispatch(self, session: ChatSession, payload: str):
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

    def _process_line(self, session: ChatSession, line: str):
        if session.file_base is None:
            return
        msg = parse_chat_line(line, session.file_base)
        if msg:
            self._append_message(session, msg)

    def _tail_loop(self, session: ChatSession):
        poll = self._poll_ms()
        logs_dir = session.logs_dir

        while not session.stop_event.is_set():
            now = time.time()
            if now - session.last_rescan >= self._rescan_interval_sec():
                session.last_rescan = now
                self._rescan_recent(session)

            if session.log_path is None:
                path = self._find_latest_log(logs_dir)
                if path:
                    session.log_path = path
                    session.file_base = parse_explog_filename(path) or datetime.fromtimestamp(
                        path.stat().st_mtime
                    )
                    session.file_pos = path.stat().st_size if path.exists() else 0
                else:
                    time.sleep(poll)
                    continue

            path = session.log_path
            if path is None or not path.exists():
                time.sleep(poll)
                continue

            newer = self._find_latest_log(logs_dir)
            if newer and newer != path:
                try:
                    if newer.stat().st_mtime >= path.stat().st_mtime:
                        session.log_path = newer
                        session.file_base = parse_explog_filename(newer) or datetime.fromtimestamp(
                            newer.stat().st_mtime
                        )
                        session.file_pos = 0
                        session.partial_line = b""
                        path = newer
                        self._rescan_recent(session)
                except OSError:
                    pass

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

    def begin_session(self, server: dict):
        server_id = server["id"]
        self.end_session(server_id)

        logs_dir = self._logs_dir(server)
        buf_max = self._buffer_max(server)
        session = ChatSession(
            server_id=server_id,
            logs_dir=logs_dir,
            history_hours=self._history_hours(server),
            buffer_max=buf_max,
            buffer=deque(maxlen=buf_max),
        )

        if logs_dir.is_dir():
            self._load_history(session)

        with self._lock:
            self._sessions[server_id] = session

        session.thread = threading.Thread(
            target=self._tail_loop,
            args=(session,),
            name=f"chat-tail-{server_id}",
            daemon=True,
        )
        session.thread.start()
        self._log(f"Chat session started for {server_id}", "DEBUG")

    def end_session(self, server_id: str):
        with self._lock:
            session = self._sessions.pop(server_id, None)
        if not session:
            return
        session.stop_event.set()
        if session.thread and session.thread.is_alive():
            session.thread.join(timeout=3.0)
        session.subscribers.clear()
        self._log(f"Chat session ended for {server_id}", "DEBUG")

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

    def get_messages(
        self,
        server_id: str,
        limit: int = 200,
        since: Optional[str] = None,
    ) -> List[dict]:
        limit = min(max(1, limit), 500)
        with self._lock:
            session = self._sessions.get(server_id)
            if not session:
                return []
            messages = [m.to_dict() for m in session.buffer]

        if since:
            messages = [m for m in messages if m["ts"] > since]
        return messages[-limit:]

    def shutdown(self):
        with self._lock:
            ids = list(self._sessions.keys())
        for sid in ids:
            self.end_session(sid)
