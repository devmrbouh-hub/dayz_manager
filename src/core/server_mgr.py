"""Управление серверами DayZ"""

import os
import re
import subprocess
import threading
import time
import psutil
from collections import defaultdict
from pathlib import Path
from typing import Optional


LOCK_FILE_NAME = "SERVER_LOCK"
_MAX_PLAYERS_RE = re.compile(r'^\s*maxPlayers\s*=\s*(\d+)\s*;', re.MULTILINE | re.IGNORECASE)
_STOP_MODES = ("manual", "restart", "force")
_RCON_SHUTDOWN_GRACE_SEC = 5
_STOP_CONFIRM_TIMEOUT_SEC = 30


class ServerManager:
    """Управление серверами DayZ"""

    def __init__(self, config, logger=None, rpt_watcher=None, chat_watcher=None, live_stats=None):
        self.config = config
        self.logger = logger
        self.rpt_watcher = rpt_watcher
        self.chat_watcher = chat_watcher
        self.live_stats = live_stats
        self._max_players_cache: dict[str, int] = {}
        # Один lock на stop/start/pid: опрос и WatchDog ходят из других потоков.
        self._op_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
        self._state_lock = threading.Lock()
        self._stopping: set[str] = set()
        # WatchDog: первый опрос только baseline, рестарт после «видел запущенным».
        self._watchdog_baselined: set[str] = set()
        self._seen_running: set[str] = set()

    def _log(self, message: str, level: str = "INFO"):
        if self.logger:
            self.logger.log(message, level)
        else:
            print(f"[{level}] {message}")

    def _server_dir(self, server: dict) -> Path:
        return Path(server['path'])

    def _lock_path(self, server_dir: Path) -> Path:
        return server_dir / LOCK_FILE_NAME

    def _lock_context(self, server: dict) -> str:
        lock_file = self._lock_path(self._server_dir(server))
        if not lock_file.exists():
            return ""
        try:
            reason = lock_file.read_text(encoding='utf-8').strip()
        except OSError:
            return ""
        return f" ({reason})" if reason else ""

    def is_locked(self, server: dict) -> bool:
        return self._lock_path(self._server_dir(server)).exists()

    def acquire_lock(self, server: dict, reason: str = "busy") -> bool:
        """Создать SERVER_LOCK. False если уже заблокирован."""
        lock_file = self._lock_path(self._server_dir(server))
        try:
            with lock_file.open('x', encoding='utf-8') as f:
                f.write(reason)
        except FileExistsError:
            return False
        except OSError as e:
            self._log(f"Failed to create SERVER_LOCK for {server['id']}: {e}", "ERROR")
            return False
        return True

    def release_lock(self, server: dict):
        lock_file = self._lock_path(self._server_dir(server))
        try:
            lock_file.unlink(missing_ok=True)
        except OSError as e:
            self._log(f"Failed to release SERVER_LOCK for {server['id']}: {e}", "ERROR")

    def _clear_stopped_flag(self, server_dir: Path):
        stopped_flag = server_dir / ".stopped"
        if stopped_flag.exists():
            stopped_flag.unlink()

    def _clear_pid_file(self, server_dir: Path):
        pid_file = server_dir / "server.pid"
        pid_file.unlink(missing_ok=True)

    def _touch_manual_stop_flag(self, server_dir: Path):
        """Ручная остановка. Рестарт этот файл не создаёт."""
        (server_dir / ".stopped").touch()

    def _end_server_sessions(self, server_id: str):
        if self.rpt_watcher:
            self.rpt_watcher.end_session(server_id)
        if self.chat_watcher:
            self.chat_watcher.end_session(server_id)

    def _terminate_process(self, process, server_id: str):
        """Best-effort termination for a process spawned during startup."""
        if process is None:
            return

        try:
            poll = getattr(process, "poll", None)
            if callable(poll) and poll() is not None:
                return

            terminate = getattr(process, "terminate", None)
            if callable(terminate):
                terminate()

            wait = getattr(process, "wait", None)
            if callable(wait):
                try:
                    wait(timeout=5)
                    self._log(f"Server {server_id} startup process terminated after failed start", "WARN")
                    return
                except subprocess.TimeoutExpired:
                    pass

            kill = getattr(process, "kill", None)
            if callable(kill):
                kill()
                if callable(wait):
                    wait(timeout=5)
                self._log(f"Server {server_id} startup process killed after failed start", "WARN")
        except Exception as e:
            self._log(f"Failed to terminate startup process for {server_id}: {e}", "ERROR")

    def _cleanup_failed_start(self, server: dict, process=None):
        """Снять процесс неудачного старта. .stopped не трогать: его снимает только успешный старт."""
        server_id = server['id']
        server_dir = self._server_dir(server)
        self._terminate_process(process, server_id)
        self._clear_pid_file(server_dir)
        self._end_server_sessions(server_id)

    def _expected_exe_path(self, server: dict) -> Path:
        return self._server_dir(server) / server['exe']

    def _process_matches_server(self, process: psutil.Process, server: dict) -> bool:
        """Процесс принадлежит этому серверу (exe в папке servers[].path, не любой DayZ на хосте)."""
        try:
            expected_exe = str(self._expected_exe_path(server).resolve()).lower()
            try:
                exe = process.exe()
                if exe and str(Path(exe).resolve()).lower() == expected_exe:
                    return True
            except (psutil.AccessDenied, psutil.ZombieProcess):
                pass

            server_dir = str(self._server_dir(server).resolve()).lower()
            try:
                cwd = process.cwd()
                if cwd and str(Path(cwd).resolve()).lower() == server_dir:
                    name = (process.name() or '').lower()
                    if 'dayzserver' in name:
                        return True
            except (psutil.AccessDenied, psutil.ZombieProcess):
                pass
        except psutil.NoSuchProcess:
            return False
        return False

    def _pids_claimed_by_other_servers(self, server: dict) -> set[int]:
        """PID, уже привязанные к другим серверам из config (не перехватывать при recovery)."""
        claimed: set[int] = set()
        current_id = server['id']
        for other in self.config.servers:
            if other.get('id') == current_id:
                continue
            pid = self.get_pid(other)
            if pid:
                claimed.add(pid)
        return claimed

    def _scan_pid(self, server: dict, persist: bool) -> Optional[int]:
        """Найти живой процесс сервера. persist=False не пишет server.pid."""
        server_dir = self._server_dir(server)
        claimed = self._pids_claimed_by_other_servers(server)
        try:
            for proc in psutil.process_iter(['pid', 'name', 'exe']):
                try:
                    if proc.pid in claimed:
                        continue
                    if not self._process_matches_server(proc, server):
                        continue
                    pid = proc.pid
                    if not persist:
                        return pid
                    with self._state_lock:
                        # Пока идёт остановка, pid обратно не записывать.
                        if server['id'] in self._stopping:
                            return pid
                    (server_dir / "server.pid").write_text(str(pid))
                    self._log(
                        f"Recovered PID {pid} for {server['id']} from running process",
                        "DEBUG"
                    )
                    return pid
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            self._log(f"PID recovery scan failed for {server['id']}: {e}", "DEBUG")
        return None

    def _recover_pid(self, server: dict) -> Optional[int]:
        """Найти PID DayZ в папке сервера, если server.pid устарел."""
        with self._state_lock:
            if server['id'] in self._stopping:
                return None
        return self._scan_pid(server, persist=True)

    def _live_pid(self, server: dict) -> Optional[int]:
        """PID живого процесса. Во время остановки файл pid не восстанавливать."""
        pid = self.get_pid(server)
        if pid:
            return pid
        with self._state_lock:
            stopping = server['id'] in self._stopping
        return self._scan_pid(server, persist=not stopping)

    def _wait_until_dead(self, server: dict, timeout_sec: int = _STOP_CONFIRM_TIMEOUT_SEC) -> bool:
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            if self._live_pid(server) is None:
                return True
            time.sleep(1)
        return self._live_pid(server) is None

    def note_seen_running(self, server_id: str):
        """Сервер подтверждённо работал в этой сессии менеджера."""
        with self._state_lock:
            self._seen_running.add(server_id)

    def _validate_config_ports(self, server: dict):
        """Предупреждение при расхождении port/query_port с serverDZ.cfg."""
        server_dir = self._server_dir(server)
        config_file = server.get('config_file', 'serverDZ.cfg')
        cfg_path = server_dir / config_file
        if not cfg_path.is_file():
            return

        try:
            text = cfg_path.read_text(encoding='utf-8', errors='replace')
        except OSError as e:
            self._log(f"Cannot read config for port check {cfg_path}: {e}", "DEBUG")
            return

        cfg_port = None
        cfg_query = None
        port_match = re.search(r'^\s*port\s*=\s*(\d+)\s*;', text, re.MULTILINE | re.IGNORECASE)
        if port_match:
            cfg_port = int(port_match.group(1))
        query_match = re.search(
            r'^\s*steamQueryPort\s*=\s*(\d+)\s*;',
            text,
            re.MULTILINE | re.IGNORECASE
        )
        if query_match:
            cfg_query = int(query_match.group(1))

        if cfg_port is not None and cfg_port != int(server.get('port', 0)):
            self._log(
                f"{server['id']}: config.json port={server['port']} "
                f"differs from {config_file} port={cfg_port}",
                "WARN"
            )
        if cfg_query is not None and cfg_query != int(server.get('query_port', 0)):
            self._log(
                f"{server['id']}: config.json query_port={server.get('query_port')} "
                f"differs from {config_file} steamQueryPort={cfg_query}",
                "WARN"
            )

    def read_max_players(self, server: dict) -> Optional[int]:
        """Прочитать maxPlayers из serverDZ.cfg (с кэшем)."""
        server_id = server['id']
        if server_id in self._max_players_cache:
            return self._max_players_cache[server_id]

        server_dir = self._server_dir(server)
        config_file = server.get('config_file', 'serverDZ.cfg')
        cfg_path = server_dir / config_file
        if not cfg_path.is_file():
            return None

        try:
            text = cfg_path.read_text(encoding='utf-8', errors='replace')
        except OSError as e:
            self._log(f"Cannot read maxPlayers from {cfg_path}: {e}", "DEBUG")
            return None

        match = _MAX_PLAYERS_RE.search(text)
        if not match:
            return None

        value = int(match.group(1))
        self._max_players_cache[server_id] = value
        return value

    @staticmethod
    def _popen_kwargs_for_console(hide_console: bool) -> dict:
        """Параметры subprocess.Popen для скрытия/показа консоли DayZ на Windows."""
        kwargs: dict = {}
        if os.name != 'nt':
            return kwargs

        if hide_console:
            kwargs['creationflags'] = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0  # SW_HIDE
            kwargs['startupinfo'] = startupinfo
            kwargs['stdin'] = subprocess.DEVNULL
            kwargs['stdout'] = subprocess.DEVNULL
            kwargs['stderr'] = subprocess.DEVNULL
        else:
            kwargs['creationflags'] = subprocess.CREATE_NEW_CONSOLE
        return kwargs

    def wait_until_running(
        self,
        server: dict,
        timeout_sec: Optional[int] = None,
        poll_interval: float = 2.0
    ) -> bool:
        if timeout_sec is None:
            timeout_sec = int(self.config.get('settings.start_confirm_timeout', 90))

        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            if self.is_running(server):
                return True
            time.sleep(poll_interval)
        return self.is_running(server)

    def _prepare_mods_unlocked(self, server: dict) -> tuple[bool, str]:
        """Проверка/скачивание модов без управления lock (вызывать под внешним lock)."""
        server_id = server['id']

        from src.core.mod_sync import ModSync
        from src.core.steamcmd import SteamCMD

        mod_sync = ModSync(self.config, self.logger)
        mod_status = mod_sync.get_mod_update_status(server)
        updates = mod_status.get('updated_entries', [])

        if updates:
            update_names = ', '.join(item.get('name') or str(item.get('id')) for item in updates)
            self._log(f"Pre-start mod updates found for {server_id}: {update_names}", "WARN")

            steamcmd = SteamCMD(self.config, self.logger)
            if not steamcmd.is_installed():
                self._log(f"SteamCMD not installed, cannot update mods before starting {server_id}", "ERROR")
                return False, ""

            failed_downloads = []
            for mod in updates:
                mod_id = str(mod.get('id', '')).strip()
                mod_name = mod.get('name', '')
                if not mod_id.isdigit():
                    self._log(
                        f"Skipping pre-start download for {mod_name or mod_id}: invalid Workshop ID",
                        "WARN"
                    )
                    continue
                success = steamcmd.download_mod(mod_id, mod_name)
                if success and steamcmd.should_sync_mod_cache_after_download():
                    steamcmd.mark_mod_version_synced(server_id, mod_id)
                else:
                    failed_downloads.append(mod_name or mod_id)

            if failed_downloads:
                self._log(
                    f"Pre-start mod download failed for {server_id}: {', '.join(failed_downloads)}",
                    "ERROR"
                )
                return False, ""

            self._log(f"Pre-start mod updates downloaded for {server_id}", "INFO")

        mods_string = mod_sync.sync_mods(server)
        return True, mods_string

    def prepare_server_for_start(self, server: dict) -> tuple[bool, str]:
        """Перед стартом: lock, проверка модов, синхронизация."""
        if not self.acquire_lock(server, reason="prepare_server_for_start"):
            self._log(
                f"Server {server['id']} is locked, cannot prepare for start{self._lock_context(server)}",
                "WARN"
            )
            return False, ""

        try:
            return self._prepare_mods_unlocked(server)
        finally:
            self.release_lock(server)

    def _resolve_battleye_dir(self, server: dict) -> Optional[Path]:
        """Определить директорию BattlEye для сервера"""
        server_dir = self._server_dir(server)

        configured_path = server.get('battleye', {}).get('path')
        if configured_path:
            be_path = Path(configured_path)
            return be_path if be_path.is_absolute() else server_dir / be_path

        profiles = server.get('profiles')
        candidates = []
        if profiles:
            candidates.extend([
                server_dir / profiles / 'BattlEye',
                server_dir / profiles / 'battleye',
            ])

        candidates.extend([
            server_dir / 'BattlEye',
            server_dir / 'battleye',
        ])

        for candidate in candidates:
            if candidate.exists() and candidate.is_dir():
                return candidate

        return None

    def start_server(
        self,
        server: dict,
        mods_string: str = "",
        lock_already_held: bool = False,
        clear_stopped: bool = True
    ) -> bool:
        """Запустить сервер. .stopped снимается только после подтверждённого running.

        SERVER_LOCK берётся до lock процесса: обновление модов уже держит файл
        и потом входит в stop/start.
        """
        if lock_already_held:
            with self._op_locks[server['id']]:
                return self._start_server_locked(
                    server,
                    mods_string,
                    lock_already_held=True,
                    clear_stopped=clear_stopped,
                )

        if self.is_locked(server):
            self._log(
                f"Server {server['id']} is locked, cannot start{self._lock_context(server)}",
                "WARN",
            )
            return False
        if not self.acquire_lock(server, reason="start_server"):
            self._log(
                f"Server {server['id']} is locked, cannot start{self._lock_context(server)}",
                "WARN",
            )
            return False
        try:
            with self._op_locks[server['id']]:
                return self._start_server_locked(
                    server,
                    mods_string,
                    lock_already_held=True,
                    clear_stopped=clear_stopped,
                )
        finally:
            self.release_lock(server)

    def _start_server_locked(
        self,
        server: dict,
        mods_string: str = "",
        lock_already_held: bool = False,
        clear_stopped: bool = True
    ) -> bool:
        server_id = server['id']
        server_dir = self._server_dir(server)
        exe_path = self._expected_exe_path(server)

        if not exe_path.exists():
            self._log(f"Executable not found: {exe_path}", "ERROR")
            return False

        process = None
        try:
            if self.is_running(server):
                self._log(f"Server {server_id} is already running", "WARN")
                return False

            if not mods_string:
                from src.core.mod_sync import ModSync
                mod_sync = ModSync(self.config, self.logger)
                mods_string = mod_sync.sync_mods(server)

            config_file = server.get('config_file', 'serverDZ.cfg')
            profiles = server.get('profiles', 'Instance_1')

            self._validate_config_ports(server)

            args = [str(exe_path)]

            if config_file:
                args.append(f"-config={config_file}")

            args.append(f"-port={server['port']}")

            if mods_string:
                args.append(f"-mod={mods_string}")

            server_mods = server.get('server_mods', '')
            if server_mods:
                args.append(f"-servermod={server_mods}")

            args.append(f"-profiles={profiles}")

            be_dir = self._resolve_battleye_dir(server)
            if be_dir:
                self._log(f"BattlEye directory candidate for {server_id}: {be_dir}", "DEBUG")
                for cfg_name in ('BEServer_x64.cfg', 'BEServer.cfg', 'beserver_x64.cfg'):
                    cfg_path = be_dir / cfg_name
                    if cfg_path.exists():
                        self._log(f"BattlEye config candidate for {server_id}: {cfg_path}", "DEBUG")
            else:
                self._log(
                    f"BattlEye directory not found for {server_id}; "
                    f"expected under {server_dir / profiles / 'BattlEye'}",
                    "WARN"
                )

            args.extend(server.get('launch_args', []))

            self._log(f"Starting {server_id}: {' '.join(args[1:])}", "INFO")

            hide_console = server.get('hide_console', True)
            popen_kwargs = self._popen_kwargs_for_console(hide_console)

            process = subprocess.Popen(
                args,
                cwd=str(server_dir),
                **popen_kwargs,
            )

            pid_file = server_dir / "server.pid"
            pid_file.write_text(str(process.pid))

            self._log(f"Server {server_id} started with PID: {process.pid}", "INFO")

            if self.rpt_watcher:
                self.rpt_watcher.begin_session(server)
            if self.chat_watcher:
                self.chat_watcher.begin_session(server)

            if self.wait_until_running(server):
                self._log(f"Server {server_id} is running", "INFO")
                if clear_stopped:
                    self._clear_stopped_flag(server_dir)
                self.note_seen_running(server_id)
                return True

            self._log(f"Server {server_id} failed to start within timeout", "ERROR")
            self._cleanup_failed_start(server, process=process)
            return False

        except Exception as e:
            self._log(f"Failed to start {server_id}: {e}", "ERROR")
            self._cleanup_failed_start(server, process=process)
            return False

    def start_server_lock_held(self, server: dict, mods_string: str = "") -> bool:
        """Запуск при уже установленном SERVER_LOCK (mod-update / scheduler)."""
        return self.start_server(
            server,
            mods_string,
            lock_already_held=True,
            clear_stopped=True
        )

    def stop_server(self, server: dict, mode: str = "manual") -> bool:
        """Остановить сервер.

        manual пишет .stopped до убийства процесса.
        restart и force файл не создают: это остановка ради следующего старта.
        """
        if mode not in _STOP_MODES:
            mode = "manual"
        with self._op_locks[server['id']]:
            return self._stop_server_locked(server, mode)

    def _stop_server_locked(self, server: dict, mode: str) -> bool:
        server_id = server['id']
        server_dir = self._server_dir(server)
        with self._state_lock:
            self._stopping.add(server_id)
        manual = mode == "manual"
        if manual:
            self._touch_manual_stop_flag(server_dir)

        try:
            if mode != "force":
                graceful_done = self._try_graceful_shutdown(server)
                if graceful_done is False:
                    if manual:
                        self._clear_stopped_flag(server_dir)
                    return False
                if graceful_done:
                    time.sleep(_RCON_SHUTDOWN_GRACE_SEC)

            if self._live_pid(server) is not None:
                self._taskkill(server)

            if not self._wait_until_dead(server):
                self._log(f"Server {server_id} is still running after stop", "ERROR")
                if manual:
                    self._clear_stopped_flag(server_dir)
                return False

            self._clear_pid_file(server_dir)
            self._end_server_sessions(server_id)
            self._log(f"Server {server_id} stopped", "INFO")
            return True
        finally:
            with self._state_lock:
                self._stopping.discard(server_id)

    def _try_graceful_shutdown(self, server: dict) -> Optional[bool]:
        """True если #shutdown принят, False если RCON обязателен и не вышел, None если нужен taskkill."""
        server_id = server['id']
        try:
            from src.core.rcon_client import RconClient
            rcon = RconClient(self.config, self.logger)
            if rcon.shutdown_server(server):
                self._log(f"Server {server_id} shutdown via RCON", "INFO")
                return True
            if rcon.get_server_mode(server) == "required":
                self._log(f"RCON shutdown is required for {server_id}, force stop cancelled", "ERROR")
                return False
            self._log(f"RCON shutdown failed for {server_id}, using taskkill fallback", "WARN")
            return None
        except Exception as e:
            self._log(f"RCON shutdown failed, using taskkill: {e}", "WARN")
            return None

    def _taskkill(self, server: dict) -> bool:
        server_id = server['id']
        pid = self._live_pid(server)
        if not pid:
            return True
        try:
            result = subprocess.run(
                ['taskkill', '/F', '/PID', str(pid)],
                capture_output=True,
                text=True,
            )
        except Exception as e:
            self._log(f"Error stopping {server_id}: {e}", "ERROR")
            return False
        if result.returncode != 0:
            self._log(f"Failed to stop {server_id}: {result.stderr}", "ERROR")
            return False
        self._log(f"Server {server_id} taskkill sent (PID: {pid})", "INFO")
        return True

    def restart_server(self, server: dict, mods_string: str = "") -> bool:
        """Перезапустить сервер. .stopped не ставится: это не ручная остановка."""
        server_id = server['id']
        self._log(f"Restarting {server_id}...", "INFO")

        stop_ok = self.stop_server(server, mode="restart")
        if not stop_ok:
            self._log(f"Graceful restart stop failed for {server_id}, trying force stop", "WARN")
            stop_ok = self.stop_server(server, mode="force")
        if not stop_ok:
            self._log(f"Restart aborted for {server_id}: stop failed", "ERROR")
            return False

        if self.is_running(server):
            self._log(f"Restart aborted for {server_id}: server is still running after stop", "ERROR")
            return False

        return self.start_server(server, mods_string, clear_stopped=True)

    def is_running(self, server: dict) -> bool:
        """Проверить запущен ли сервер (PID + имя/exe процесса)."""
        pid = self.get_pid(server)
        if pid:
            return True
        recovered = self._recover_pid(server)
        return recovered is not None

    def get_pid(self, server: dict) -> Optional[int]:
        """Получить PID сервера с проверкой процесса DayZ."""
        server_dir = self._server_dir(server)
        pid_file = server_dir / "server.pid"

        if not pid_file.exists():
            return None

        try:
            pid = int(pid_file.read_text().strip())
        except (ValueError, OSError):
            pid_file.unlink(missing_ok=True)
            return None

        try:
            process = psutil.Process(pid)
            if process.is_running() and self._process_matches_server(process, server):
                return pid
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

        pid_file.unlink(missing_ok=True)
        return None

    def get_status(self, server: dict) -> dict:
        """Получить статус сервера"""
        running = self.is_running(server)
        pid = self.get_pid(server)

        max_players = self.read_max_players(server)

        status = {
            'id': server['id'],
            'name': server['name'],
            'port': server['port'],
            'running': running,
            'pid': pid,
            'auto_restart': server.get('auto_restart', False),
            'startup_phase': 'stopped',
            'ready_at': None,
            'current_rpt': None,
            'startup_warning': None,
            'server_fps': None,
            'player_count': 0,
            'max_players': max_players,
            'players': [],
            'rcon_players_ok': False,
            'chat_available': False,
        }

        if self.rpt_watcher:
            status.update(self.rpt_watcher.get_startup_info(server, running))

        if self.live_stats:
            status.update(self.live_stats.get_info(server['id'], running))

        if not running:
            status['player_count'] = 0
            status['players'] = []
            status['rcon_players_ok'] = False

        if self.chat_watcher:
            status['chat_available'] = self.chat_watcher.is_available(server)

        return status

    def get_all_status(self) -> list:
        """Получить статус всех серверов"""
        servers = self.config.servers
        return [self.get_status(s) for s in servers]

    def check_and_auto_restart(self, server: dict):
        """Поднять сервер, если он пропал после того, как эта сессия его уже видела.

        Файловый SERVER_LOCK берётся до lock процесса, как в start_server.
        """
        if not self._watchdog_should_start(server):
            return
        self._watchdog_start(server)

    def _watchdog_should_start(self, server: dict) -> bool:
        server_id = server['id']
        running = self.is_running(server)

        with self._state_lock:
            baselined = server_id in self._watchdog_baselined
            if not baselined:
                self._watchdog_baselined.add(server_id)
                if running:
                    self._seen_running.add(server_id)
            seen = server_id in self._seen_running

        if not baselined:
            if running:
                self._refresh_pid_file(server)
            return False

        if running:
            self.note_seen_running(server_id)
            self._refresh_pid_file(server)
            return False

        if not seen:
            return False
        if not server.get('auto_restart', False):
            return False
        if self.is_locked(server):
            return False
        if (self._server_dir(server) / ".stopped").exists():
            return False
        return True

    def _watchdog_start(self, server: dict):
        server_id = server['id']
        self._log(f"[WatchDog] {server_id} is down, auto restarting...", "WARN")

        from src.core.hooks import Hooks
        hooks = Hooks(self.config, self.logger)
        hooks.execute_hook(server, 'afterStop')
        hooks.execute_hook(server, 'beforeStart')

        if not self.acquire_lock(server, reason="watchdog_restart"):
            self._log(
                f"[WatchDog] {server_id} start skipped: server is locked{self._lock_context(server)}",
                "WARN"
            )
            return

        try:
            prepared, mods_string = self._prepare_mods_unlocked(server)
            if not prepared:
                self._log(
                    f"[WatchDog] {server_id} start cancelled because mod preflight failed",
                    "ERROR"
                )
                return

            self.start_server(server, mods_string, lock_already_held=True, clear_stopped=True)
        finally:
            self.release_lock(server)

    def _refresh_pid_file(self, server: dict):
        pid = self.get_pid(server)
        if pid:
            (self._server_dir(server) / "server.pid").write_text(str(pid))
