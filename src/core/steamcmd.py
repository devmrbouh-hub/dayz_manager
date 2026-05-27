"""SteamCMD интеграция"""

import os
import subprocess
import asyncio
import json
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

from src.utils.http import urlopen as http_urlopen

MOD_VERSIONS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    'data',
    'mod_versions.json'
)


class SteamCMD:
    """Управление SteamCMD"""

    def __init__(self, config, logger=None):
        self.config = config
        self.steamcmd_path = config.get('steam.steamcmd_path', r'C:\SteamCMD\steamcmd.exe')
        self.dayz_install_path = config.get('steam.dayz_install_path', r'C:\Program Files (x86)\Steam\steamapps\common\DayZ')
        self.workshop_path = config.get('steam.workshop_path', r'C:\Program Files (x86)\Steam\steamapps\common\DayZ\!Workshop')
        self.username = config.get('steam.username', '') or os.getenv('DAYZ_STEAM_USERNAME', '')
        self.password = config.get('steam.password', '') or os.getenv('DAYZ_STEAM_PASSWORD', '')
        self.guard_code = config.get('steam.guard_code') or os.getenv('DAYZ_STEAM_GUARD_CODE')
        self.auth_mode = (config.get('steam.auth_mode', 'session') or 'session').strip().lower()
        self.logger = logger
        self.mod_versions = self._load_mod_versions()

    def _log(self, message: str, level: str = "INFO"):
        if self.logger:
            self.logger.log(message, level)
        else:
            print(f"[{level}] {message}")

    def _append_login_args(self, cmd: list) -> bool:
        """Добавить аргументы авторизации SteamCMD согласно режиму."""
        if self.auth_mode == 'credentials':
            if self.username and self.password:
                self._log("Steam auth mode: credentials", "DEBUG")
                cmd.extend(['+login', self.username, self.password])
                if self.guard_code:
                    cmd.append(self.guard_code)
                return True

            self._log("steam.auth_mode=credentials but username/password are empty", "ERROR")
            return False

        if self.auth_mode == 'anonymous':
            self._log("Steam auth mode: anonymous", "DEBUG")
            cmd.extend(['+login', 'anonymous'])
            return True

        # session:
        # чистый запуск без +login часто не имеет auth-контекста у нового процесса steamcmd.
        # Если креды доступны через config/env, используем их как безопасный fallback.
        if self.username and self.password:
            self._log("Steam auth mode: session with credential fallback", "DEBUG")
            cmd.extend(['+login', self.username, self.password])
            if self.guard_code:
                cmd.append(self.guard_code)
        else:
            self._log("Steam auth mode: session (no credentials available, trying existing SteamCMD state)", "DEBUG")

        return True

    def is_installed(self) -> bool:
        """Проверить установлен ли SteamCMD"""
        return Path(self.steamcmd_path).exists()

    def get_steam_root_path(self) -> Path:
        """Корень Steam, который используется как force_install_dir."""
        dayz_dir = Path(self.dayz_install_path)
        try:
            return dayz_dir.parent.parent.parent
        except IndexError:
            return dayz_dir

    def get_workshop_content_path(self, workshop_id: int = 221100) -> Path:
        """Фактический путь Workshop content, куда кладёт SteamCMD."""
        workshop_root = Path(self.workshop_path)
        candidates = []

        try:
            candidates.append(workshop_root.parent.parent.parent / 'workshop' / 'content' / str(workshop_id))
        except IndexError:
            pass

        dayz_dir = Path(self.dayz_install_path)
        try:
            candidates.append(dayz_dir.parent.parent / 'workshop' / 'content' / str(workshop_id))
        except IndexError:
            pass

        for candidate in candidates:
            if candidate.exists():
                return candidate

        return candidates[0] if candidates else workshop_root

    def _load_mod_versions(self) -> dict:
        if os.path.exists(MOD_VERSIONS_FILE):
            try:
                with open(MOD_VERSIONS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_mod_versions(self):
        os.makedirs(os.path.dirname(MOD_VERSIONS_FILE), exist_ok=True)
        with open(MOD_VERSIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.mod_versions, f, indent=2, ensure_ascii=False)

    def _get_remote_mod_update_time(self, mod_id: str) -> Optional[int]:
        """Получить time_updated мода из Steam Web API."""
        data = urllib.parse.urlencode({
            'itemcount': 1,
            'publishedfileids[0]': str(mod_id)
        }).encode('utf-8')
        req = urllib.request.Request(
            url='https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/',
            data=data,
            method='POST'
        )

        with http_urlopen(req, timeout=20) as response:
            payload = json.loads(response.read().decode('utf-8', errors='replace'))

        details = payload.get('response', {}).get('publishedfiledetails', [])
        if not details:
            return None

        item = details[0]
        # result=1 -> OK, 9/15 и т.п. -> access denied/not found
        if item.get('result') != 1:
            return None

        updated = item.get('time_updated')
        if updated is None:
            return None
        return int(updated)

    def has_mod_update(self, server_id: str, mod_id: str, mod_name: str = "") -> bool:
        """
        Проверить обновление мода без скачивания:
        сравнивает remote time_updated из Steam API с локальным кэшем.
        """
        label = f"{mod_name} ({mod_id})" if mod_name else str(mod_id)
        cache_key = f"{server_id}:{mod_id}"

        try:
            remote_time = self._get_remote_mod_update_time(mod_id)
            if remote_time is None:
                self._log(f"Workshop details unavailable for {label}", "DEBUG")
                return False

            cached_time = self.mod_versions.get(cache_key)
            if cached_time is None:
                # Первая инициализация кэша: не считать это обновлением,
                # чтобы не рестартовать сервер сразу на первом цикле.
                self.mod_versions[cache_key] = remote_time
                self._save_mod_versions()
                self._log(f"Workshop version cached for {label}", "DEBUG")
                return False

            if int(remote_time) > int(cached_time):
                self._log(f"Workshop update detected for {label}", "INFO")
                return True

            return False
        except Exception as e:
            self._log(f"Failed to check workshop version for {label}: {e}", "WARN")
            return False

    def mark_mod_version_synced(self, server_id: str, mod_id: str):
        """Обновить локальный кэш версии после успешной синхронизации."""
        try:
            remote_time = self._get_remote_mod_update_time(mod_id)
            if remote_time is None:
                return
            self.mod_versions[f"{server_id}:{mod_id}"] = int(remote_time)
            self._save_mod_versions()
        except Exception as e:
            self._log(f"Failed to update mod version cache for {mod_id}: {e}", "WARN")

    def install(self) -> bool:
        """Установить SteamCMD"""
        self._log("Installing SteamCMD...", "INFO")

        try:
            # Создать папку
            steamcmd_dir = Path(self.steamcmd_path).parent
            steamcmd_dir.mkdir(parents=True, exist_ok=True)

            # Скачать SteamCMD
            url = "https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip"
            import urllib.request
            zip_path = steamcmd_dir / "steamcmd.zip"

            self._log("Downloading SteamCMD...", "INFO")
            urllib.request.urlretrieve(url, zip_path)

            # Распаковать
            import zipfile
            with zipfile.ZipFile(zip_path, 'r') as z:
                z.extractall(steamcmd_dir)

            zip_path.unlink()

            # Запустить для обновления
            self._log("Updating SteamCMD...", "INFO")
            subprocess.run(
                [self.steamcmd_path, '+login', 'anonymous', '+quit'],
                check=True,
                timeout=60
            )

            self._log("SteamCMD installed successfully", "INFO")
            return True

        except Exception as e:
            self._log(f"Failed to install SteamCMD: {e}", "ERROR")
            return False

    def download_mod(self, mod_id: str, mod_name: str = "", workshop_id: int = 221100) -> bool:
        """Скачать/обновить мод из Workshop.
        Скачивает в dayz_install_path → steamapps\workshop\content\221100\<ID>
        """
        mod_id = str(mod_id or '').strip()
        if not mod_id.isdigit():
            label = mod_name or mod_id or 'unknown'
            self._log(f"Invalid Workshop ID for mod {label}, download skipped", "WARN")
            return False

        if not self.is_installed():
            self._log("SteamCMD not installed", "ERROR")
            return False

        label = f"{mod_name} ({mod_id})" if mod_name else mod_id
        self._log(f"Downloading mod {label}...", "INFO")

        try:
            cmd = [self.steamcmd_path]

            # Указать директорию установки (чтобы SteamCMD использовал тот же Steam root)
            steam_root = self.get_steam_root_path()
            workshop_content = self.get_workshop_content_path(workshop_id)
            cmd.extend(['+force_install_dir', str(steam_root)])
            self._log(f"SteamCMD force_install_dir: {steam_root}", "DEBUG")
            self._log(f"Workshop content path: {workshop_content}", "DEBUG")
            self._log(f"Workshop alias root: {self.workshop_path}", "DEBUG")

            if not self._append_login_args(cmd):
                return False

            # Скачать мод (отдельные аргументы для парсера SteamCMD)
            cmd.extend([
                '+workshop_download_item',
                str(workshop_id),
                str(mod_id),
                '+quit'
            ])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10 минут на скачивание
            )

            # Проверить успех в stdout (SteamCMD может вернуть 0 даже при ошибке)
            output = result.stdout + result.stderr
            lowered = output.lower()
            success = 'success.' in lowered or 'item downloaded' in lowered
            not_logged = 'not logged on' in lowered
            access_denied = 'access denied' in lowered

            if success:
                self._log(f"Mod {label} downloaded successfully", "INFO")
                return True
            else:
                self._log(f"Failed to download mod {label}", "ERROR")
                if not_logged:
                    self._log(
                        "SteamCMD is not logged in. Set DAYZ_STEAM_USERNAME/DAYZ_STEAM_PASSWORD (or steam.username/password) so the manager can authenticate each run.",
                        "ERROR"
                    )
                if access_denied:
                    self._log(
                        f"Workshop item access denied for {label}. The mod may be private/friends-only.",
                        "WARN"
                    )
                if output:
                    # Показать последние строки лога (чуть больше контекста)
                    lines = output.strip().split('\n')
                    for line in lines[-15:]:
                        self._log(f"  {line}", "DEBUG")
                return False

        except subprocess.TimeoutExpired:
            self._log(f"Timeout downloading mod {label}", "ERROR")
            return False
        except Exception as e:
            self._log(f"Error downloading mod {label}: {e}", "ERROR")
            return False

    def download_all_mods(self, mods: list) -> dict:
        """Скачать все моды из списка [{name, id}].
        Возвращает {mod_id: success}
        """
        results = {}
        for mod in mods:
            mod_id = mod['id']
            mod_name = mod.get('name', '')
            results[mod_id] = self.download_mod(mod_id, mod_name)
        return results

    def get_mod_path(self, mod_id: str, workshop_id: int = 221100) -> Path:
        """Получить путь к скачанному моду в Steam workshop content."""
        return self.get_workshop_content_path(workshop_id) / str(mod_id)

    def check_for_updates(self, mod_id: str, workshop_id: int = 221100) -> bool:
        """Проверить есть ли обновление для мода (сравнение дат)"""
        mod_path = self.get_mod_path(mod_id, workshop_id)

        if not mod_path.exists():
            return True  # Мода нет, нужно скачать

        # Проверить возраст мода (если старше 24 часов — проверить обновление)
        import time
        mod_age = time.time() - mod_path.stat().st_mtime
        return mod_age > 86400  # 24 часа
