"""Управление серверами DayZ"""

import os
import re
import subprocess
import time
import psutil
from pathlib import Path
from typing import Optional


LOCK_FILE_NAME = "SERVER_LOCK"
_MAX_PLAYERS_RE = re.compile(r'^\s*maxPlayers\s*=\s*(\d+)\s*;', re.MULTILINE | re.IGNORECASE)


class ServerManager:
    """Управление серверами DayZ"""

    def __init__(self, config, logger=None, rpt_watcher=None, chat_watcher=None, live_stats=None):
        self.config = config
        self.logger = logger
        self.rpt_watcher = rpt_watcher
        self.chat_watcher = chat_watcher
        self.live_stats = live_stats
        self._max_players_cache: dict[str, int] = {}

    def _log(self, message: str, level: str = "INFO"):
        if self.logger:
            self.logger.log(message, level)
        else:
            print(f"[{level}] {message}")

    def _server_dir(self, server: dict) -> Path:
        return Path(server['path'])

    def _lock_path(self, server_dir: Path) -> Path:
        return server_dir / LOCK_FILE_NAME

    def is_locked(self, server: dict) -> bool:
        return self._lock_path(self._server_dir(server)).exists()

    def acquire_lock(self, server: dict) -> bool:
        """Создать SERVER_LOCK. False если уже заблокирован."""
        lock_file = self._lock_path(self._server_dir(server))
        if lock_file.exists():
            return False
        lock_file.touch()
        return True

    def release_lock(self, server: dict):
        lock_file = self._lock_path(self._server_dir(server))
        if lock_file.exists():
            lock_file.unlink()

    def _clear_stopped_flag(self, server_dir: Path):
        stopped_flag = server_dir / ".stopped"
        if stopped_flag.exists():
            stopped_flag.unlink()

    def _set_manual_stop_flag(self, server_dir: Path):
        """Пометить сервер как остановленный вручную/контролируемо."""
        pid_file = server_dir / "server.pid"
        if pid_file.exists():
            pid_file.unlink()
        stopped_flag = server_dir / ".stopped"
        stopped_flag.touch()

    def _expected_exe_path(self, server: dict) -> Path:
        return self._server_dir(server) / server['exe']

    def _process_matches_server(self, process: psutil.Process, server: dict) -> bool:
        try:
            name = (process.name() or '').lower()
            if 'dayzserver' in name:
                return True
            exe = process.exe()
            if exe:
                expected = str(self._expected_exe_path(server).resolve()).lower()
                if str(Path(exe).resolve()).lower() == expected:
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return False
        return False

    def _recover_pid(self, server: dict) -> Optional[int]:
        """Найти PID DayZ в папке сервера, если server.pid устарел."""
        server_dir = self._server_dir(server)
        try:
            for proc in psutil.process_iter(['pid', 'name', 'exe']):
                try:
                    if self._process_matches_server(proc, server):
                        pid = proc.pid
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
                if success:
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
        if not self.acquire_lock(server):
            self._log(f"Server {server['id']} is locked, cannot prepare for start", "WARN")
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
        """Запустить сервер"""
        server_id = server['id']
        server_dir = self._server_dir(server)
        exe_path = self._expected_exe_path(server)

        if not exe_path.exists():
            self._log(f"Executable not found: {exe_path}", "ERROR")
            return False

        lock_acquired_here = False
        if not lock_already_held:
            if self.is_locked(server):
                self._log(f"Server is locked, cannot start", "WARN")
                return False
            if not self.acquire_lock(server):
                self._log(f"Server is locked, cannot start", "WARN")
                return False
            lock_acquired_here = True

        try:
            if clear_stopped:
                self._clear_stopped_flag(server_dir)

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
                self._clear_stopped_flag(server_dir)
                return True

            self._log(f"Server {server_id} failed to start within timeout", "ERROR")
            if self.rpt_watcher:
                self.rpt_watcher.end_session(server_id)
            if self.chat_watcher:
                self.chat_watcher.end_session(server_id)
            if clear_stopped:
                self._clear_stopped_flag(server_dir)
            return False

        except Exception as e:
            self._log(f"Failed to start {server_id}: {e}", "ERROR")
            if self.rpt_watcher:
                self.rpt_watcher.end_session(server_id)
            if self.chat_watcher:
                self.chat_watcher.end_session(server_id)
            if clear_stopped:
                self._clear_stopped_flag(server_dir)
            return False
        finally:
            if lock_acquired_here:
                self.release_lock(server)

    def start_server_lock_held(self, server: dict, mods_string: str = "") -> bool:
        """Запуск при уже установленном SERVER_LOCK (mod-update / scheduler)."""
        return self.start_server(
            server,
            mods_string,
            lock_already_held=True,
            clear_stopped=True
        )

    def stop_server(self, server: dict, force: bool = False) -> bool:
        """Остановить сервер"""
        server_id = server['id']
        server_dir = self._server_dir(server)

        def _finish_stop() -> bool:
            if self.rpt_watcher:
                self.rpt_watcher.end_session(server_id)
            if self.chat_watcher:
                self.chat_watcher.end_session(server_id)
            return True

        if not force:
            try:
                from src.core.rcon_client import RconClient
                rcon = RconClient(self.config, self.logger)
                rcon_mode = rcon.get_server_mode(server)

                if rcon.shutdown_server(server):
                    self._log(f"Server {server_id} shutdown via RCON", "INFO")
                    time.sleep(5)
                    if not self.is_running(server):
                        self._set_manual_stop_flag(server_dir)
                        return _finish_stop()
                elif rcon_mode == 'required':
                    self._log(f"RCON shutdown is required for {server_id}, force stop cancelled", "ERROR")
                    return False
                else:
                    self._log(f"RCON shutdown failed for {server_id}, using taskkill fallback", "WARN")
            except Exception as e:
                self._log(f"RCON shutdown failed, using taskkill: {e}", "WARN")

        pid = self.get_pid(server)
        if pid:
            try:
                result = subprocess.run(
                    ['taskkill', '/F', '/PID', str(pid)],
                    capture_output=True,
                    text=True
                )

                if result.returncode == 0:
                    self._log(f"Server {server_id} stopped (PID: {pid})", "INFO")
                    self._set_manual_stop_flag(server_dir)
                    return _finish_stop()
                else:
                    self._log(f"Failed to stop {server_id}: {result.stderr}", "ERROR")
                    return False

            except Exception as e:
                self._log(f"Error stopping {server_id}: {e}", "ERROR")
                return False
        else:
            self._log(f"Server {server_id} is not running (no PID)", "WARN")
            self._set_manual_stop_flag(server_dir)
            return _finish_stop()

    def restart_server(self, server: dict, mods_string: str = "") -> bool:
        """Перезапустить сервер"""
        server_id = server['id']
        self._log(f"Restarting {server_id}...", "INFO")

        self.stop_server(server)
        time.sleep(5)

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
        """Проверить и автоматически перезапустить если упал"""
        server_id = server['id']

        if not server.get('auto_restart', False):
            return

        if self.is_locked(server):
            return

        stopped_flag = self._server_dir(server) / ".stopped"
        if stopped_flag.exists():
            return

        if not self.is_running(server):
            self._log(f"[WatchDog] {server_id} is down, auto restarting...", "WARN")

            from src.core.hooks import Hooks
            hooks = Hooks(self.config, self.logger)
            hooks.execute_hook(server, 'afterStop')
            hooks.execute_hook(server, 'beforeStart')

            if not self.acquire_lock(server):
                self._log(f"[WatchDog] {server_id} start skipped: server is locked", "WARN")
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
        else:
            pid = self.get_pid(server)
            if pid:
                pid_file = self._server_dir(server) / "server.pid"
                pid_file.write_text(str(pid))
