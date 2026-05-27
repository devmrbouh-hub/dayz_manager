"""Умная синхронизация модов (mod_list -> симлинки -> Workshop ID -> обновления)"""

import os
import json
import hashlib
import shutil
import subprocess
from pathlib import Path
from typing import List, Dict, Optional


# Путь к кэшу хэшей
MOD_HASHES_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'mod_hashes.json')
WORKSHOP_APP_ID = '221100'


class ModSync:
    """Синхронизация модов"""

    def __init__(self, config, logger=None):
        self.config = config
        self.logger = logger
        self.hashes = self._load_hashes()

    def _log(self, message: str, level: str = "INFO"):
        if self.logger:
            self.logger.log(message, level)
        else:
            print(f"[{level}] {message}")

    def _load_hashes(self) -> dict:
        """Загрузить кэш хэшей"""
        if os.path.exists(MOD_HASHES_FILE):
            try:
                with open(MOD_HASHES_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_hashes(self):
        """Сохранить кэш хэшей"""
        os.makedirs(os.path.dirname(MOD_HASHES_FILE), exist_ok=True)
        with open(MOD_HASHES_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.hashes, f, indent=2, ensure_ascii=False)

    def _hash_file(self, file_path: Path) -> str:
        """SHA256 хэш файла"""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _get_dir_hash(self, dir_path: Path) -> Dict[str, str]:
        """Хэши всех файлов в папке.
        Ограничиваем глубину до 3 уровней для избежания рекурсии в junction.
        """
        hashes = {}
        if not dir_path.exists():
            return hashes

        try:
            # Хэшируем только файлы верхних уровней модов (обычно: Addons/, keys/)
            max_depth = 3
            base_depth = len(dir_path.parts)

            for file_path in dir_path.rglob('*'):
                if file_path.is_file():
                    rel_path = str(file_path.relative_to(dir_path))
                    depth = len(file_path.parts) - base_depth
                    if depth <= max_depth:
                        hashes[rel_path] = self._hash_file(file_path)
        except (OSError, PermissionError) as e:
            self._log(f"  [!] Error hashing {dir_path}: {e}", "WARN")

        return hashes

    def get_mod_list_from_file(self, server: dict) -> List[str]:
        """Прочитать моды из mod_list.txt сервера"""
        server_dir = Path(server['path'])
        mod_list_file = server_dir / server.get('mods_file', 'mod_list.txt')

        if not mod_list_file.exists():
            self._log(f"mod_list.txt not found: {mod_list_file}", "WARN")
            return []

        mods = []
        with open(mod_list_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    mods.append(line)

        return mods

    def _get_legacy_mod_id_map(self, server: dict) -> Dict[str, str]:
        """Legacy mapping: ID из config.json по имени мода."""
        mapping = {}
        for item in server.get('mods', []) or []:
            if isinstance(item, dict) and item.get('name'):
                mod_id = str(item.get('id', '') or '').strip()
                if mod_id:
                    mapping[item['name']] = mod_id
        return mapping

    def _get_workshop_alias_root(self) -> Path:
        return Path(
            self.config.get(
                'steam.workshop_path',
                r'C:\Program Files (x86)\Steam\steamapps\common\DayZ\!Workshop'
            )
        )

    def _get_workshop_content_root(self) -> Path:
        """Путь к steamapps\workshop\content\221100."""
        workshop_alias_root = self._get_workshop_alias_root()
        candidates = []

        # Типичный путь: <Steam>\steamapps\common\DayZ\!Workshop
        try:
            candidates.append(workshop_alias_root.parent.parent.parent / 'workshop' / 'content' / WORKSHOP_APP_ID)
        except IndexError:
            pass

        dayz_install_path = self.config.get(
            'steam.dayz_install_path',
            r'C:\Program Files (x86)\Steam\steamapps\common\DayZ'
        )
        dayz_dir = Path(dayz_install_path)
        try:
            candidates.append(dayz_dir.parent.parent / 'workshop' / 'content' / WORKSHOP_APP_ID)
        except IndexError:
            pass

        for candidate in candidates:
            if candidate.exists():
                return candidate

        return candidates[0] if candidates else workshop_alias_root

    def _extract_workshop_id_from_path(self, path: Path) -> Optional[str]:
        """Вытащить Workshop ID из resolved пути вида ...\workshop\content\221100\<ID>."""
        try:
            resolved = path.resolve(strict=True)
        except Exception:
            return None

        parts = list(resolved.parts)
        for i in range(len(parts) - 2):
            if parts[i].lower() == 'content' and parts[i + 1] == WORKSHOP_APP_ID:
                candidate = str(parts[i + 2]).strip()
                if candidate.isdigit():
                    return candidate

        if resolved.name.isdigit() and resolved.parent.name == WORKSHOP_APP_ID:
            return resolved.name

        return None

    def _resolve_mod_id(self, server: dict, mod_name: str, legacy_map: Optional[Dict[str, str]] = None) -> tuple[str, str, str]:
        """Вернуть (id, source, reason) для мода из mod_list."""
        legacy_map = legacy_map or self._get_legacy_mod_id_map(server)
        server_dir = Path(server['path'])
        workshop_alias_root = self._get_workshop_alias_root()

        candidates = [
            ('server_symlink', server_dir / mod_name),
            ('workshop_alias', workshop_alias_root / mod_name),
        ]

        for source, candidate in candidates:
            mod_id = self._extract_workshop_id_from_path(candidate)
            if mod_id:
                return mod_id, source, ''

        legacy_id = legacy_map.get(mod_name, '')
        if legacy_id:
            return legacy_id, 'legacy_config', 'Workshop ID taken from servers[].mods legacy mapping'

        return '', 'unresolved', 'Workshop ID not found from local symlinks or legacy config'

    def get_effective_mods(self, server: dict) -> List[dict]:
        """Единый effective-список модов для запуска и отслеживания обновлений."""
        mod_names = self.get_mod_list_from_file(server)
        source = 'mod_list'

        if not mod_names:
            source = 'legacy_config'
            mod_names = [
                item['name']
                for item in (server.get('mods', []) or [])
                if isinstance(item, dict) and item.get('name')
            ]
            if mod_names:
                self._log(
                    f"{server['id']}: mod_list.txt is empty or missing, falling back to legacy servers[].mods",
                    "WARN"
                )

        legacy_map = self._get_legacy_mod_id_map(server)
        result = []
        for mod_name in mod_names:
            mod_id, id_source, reason = self._resolve_mod_id(server, mod_name, legacy_map)
            mod_id = str(mod_id or '').strip()
            result.append({
                'name': mod_name,
                'id': mod_id,
                'id_source': id_source,
                'list_source': source,
                'update_enabled': mod_id.isdigit(),
                'reason': reason,
            })

        return result

    def sync_mods(self, server: dict) -> str:
        """
        Синхронизировать моды:
        - Если симлинки в !Workshop и сервере уже есть — не трогать
        - Если нет — создать
        - Скопировать ключи .bikey
        """
        workshop_path = self.config.get('steam.workshop_path', r'C:\Program Files (x86)\Steam\steamapps\common\DayZ\!Workshop')
        server_dir = Path(server['path'])
        keys_dir = server_dir / server.get('keys_dir', 'keys')

        # Создать папку ключей
        keys_dir.mkdir(parents=True, exist_ok=True)

        # Получить список модов
        mods_with_ids = self.get_effective_mods(server)
        mod_strings = []

        for mod_entry in mods_with_ids:
            mod_name = mod_entry['name']

            workshop_mod = Path(workshop_path) / mod_name
            server_mod = server_dir / mod_name

            if not mod_entry.get('update_enabled'):
                self._log(
                    f"  [~] {mod_name} — no Workshop ID resolved, auto-update disabled ({mod_entry.get('reason')})",
                    "WARN"
                )

            # Если мод уже есть в папке сервера (симлинк или папка) — пропускаем
            if not server_mod.exists():
                # Попытаться создать симлинк из сервера в !Workshop
                if workshop_mod.exists():
                    self._create_symlink(mod_name, workshop_mod, server_mod)
                else:
                    self._log(f"  [!] {mod_name} — source not found in !Workshop, keeping launch entry as-is", "WARN")

            # Скопировать ключи
            if workshop_mod.exists():
                self._copy_keys(mod_name, workshop_mod, keys_dir)
            elif server_mod.exists():
                self._copy_keys(mod_name, server_mod, keys_dir)

            # Добавить в строку
            mod_strings.append(mod_name)

        result = ';'.join(mod_strings)
        self._log(f"Mods synced: {result}", "INFO")
        return result

    def _create_symlink(self, mod_name: str, source: Path, target: Path) -> bool:
        """Создать junction симлинк target → source"""
        if target.exists():
            return True

        try:
            cmd = f'mklink /J "{target}" "{source}"'
            result = subprocess.run(
                cmd,
                shell=True,
                check=True,
                capture_output=True,
                text=True
            )
            self._log(f"  [+] {mod_name} — symlink created", "DEBUG")
            return True
        except subprocess.CalledProcessError as e:
            self._log(f"  [!] {mod_name} — ERROR creating symlink: {e.stderr}", "ERROR")
            return False
        except Exception as e:
            self._log(f"  [!] {mod_name} — ERROR: {e}", "ERROR")
            return False

    def _get_mods_with_ids(self, server: dict) -> list:
        """Legacy alias for compatibility with existing call sites."""
        return self.get_effective_mods(server)

    def _ensure_workshop_symlink(self, mod_name: str, mod_id: str, workshop_mod: Path, workshop_content: Path):
        """Создать/проверить симлинк !Workshop\@ModName → steamapps\workshop\content\221100\<ID>"""
        if workshop_mod.exists():
            # Проверить что симлинк указывает на правильный ID
            try:
                target = workshop_mod.resolve()
                if str(mod_id) in str(target):
                    self._log(f"  [=] {mod_name} — Workshop symlink OK", "DEBUG")
                    return
                else:
                    self._log(f"  [~] {mod_name} — Workshop symlink points elsewhere, recreating", "WARN")
                    workshop_mod.unlink()
            except:
                pass  # Не симлинк, обычная папка — пропускаем

        # Найти папку с ID в workshop_content
        mod_source = workshop_content / mod_id
        if not mod_source.exists():
            self._log(f"  [!] {mod_name} ({mod_id}) — NOT FOUND in Workshop content!", "WARN")
            return

        try:
            # mklink /J "!Workshop\@ModName" "steamapps\workshop\content\221100\<ID>"
            cmd = f'mklink /J "{workshop_mod}" "{mod_source}"'
            result = subprocess.run(
                cmd,
                shell=True,
                check=True,
                capture_output=True,
                text=True
            )
            self._log(f"  [+] {mod_name} — Workshop symlink created → {mod_id}", "DEBUG")
        except subprocess.CalledProcessError as e:
            self._log(f"  [!] {mod_name} — ERROR creating symlink: {e.stderr}", "ERROR")
        except Exception as e:
            self._log(f"  [!] {mod_name} — ERROR: {e}", "ERROR")

    def _ensure_server_symlink(self, mod_name: str, workshop_mod: Path, server_mod: Path):
        """Создать/проверить симлинк папки сервера @ModName → !Workshop\@ModName"""
        if server_mod.exists():
            self._log(f"  [=] {mod_name} — Server symlink exists", "DEBUG")
            return

        if not workshop_mod.exists():
            self._log(f"  [!] {mod_name} — Workshop source not found, cannot create server symlink", "WARN")
            return

        try:
            # mklink /J "server\@ModName" "!Workshop\@ModName"
            cmd = f'mklink /J "{server_mod}" "{workshop_mod}"'
            result = subprocess.run(
                cmd,
                shell=True,
                check=True,
                capture_output=True,
                text=True
            )
            self._log(f"  [+] {mod_name} — Server symlink created", "DEBUG")
        except subprocess.CalledProcessError as e:
            self._log(f"  [!] {mod_name} — ERROR creating symlink: {e.stderr}", "ERROR")
        except Exception as e:
            self._log(f"  [!] {mod_name} — ERROR: {e}", "ERROR")

    def _create_junction(self, mod_name: str, workshop_mod: Path, server_mod: Path) -> bool:
        """Создать junction symlink (как mklink /J)"""
        if server_mod.exists():
            self._log(f"  [=] {mod_name} - exists", "DEBUG")
            return True

        if not workshop_mod.exists():
            self._log(f"  [!] {mod_name} - NOT FOUND in Workshop!", "WARN")
            return False

        try:
            # mklink /J "server\mod" "workshop\mod"
            cmd = f'mklink /J "{server_mod}" "{workshop_mod}"'
            result = subprocess.run(
                cmd,
                shell=True,
                check=True,
                capture_output=True,
                text=True
            )
            self._log(f"  [+] {mod_name} - junction created", "DEBUG")
            return True
        except subprocess.CalledProcessError as e:
            self._log(f"  [!] {mod_name} - ERROR creating junction: {e.stderr}", "ERROR")
            return False
        except Exception as e:
            self._log(f"  [!] {mod_name} - ERROR: {e}", "ERROR")
            return False

    def _copy_keys(self, mod_name: str, workshop_mod: Path, keys_dir: Path):
        """Копировать .bikey файлы"""
        # Папка keys в моде
        workshop_keys = workshop_mod / "keys"
        if workshop_keys.exists():
            for key_file in workshop_keys.glob("*.bikey"):
                target = keys_dir / key_file.name
                try:
                    shutil.copy2(key_file, target)
                    self._log(f"      Copied key: {key_file.name}", "DEBUG")
                except Exception as e:
                    self._log(f"      ERROR copying {key_file.name}: {e}", "ERROR")

        # Корень мода
        for key_file in workshop_mod.glob("*.bikey"):
            target = keys_dir / key_file.name
            try:
                shutil.copy2(key_file, target)
                self._log(f"      Copied key: {key_file.name}", "DEBUG")
            except Exception as e:
                self._log(f"      ERROR copying {key_file.name}: {e}", "ERROR")

    def check_mod_updates(self, server: dict) -> List[str]:
        """Современная проверка обновлений через Steam Web API для effective-списка модов."""
        status = self.get_mod_update_status(server)
        return status['updated_mods']

    def get_mod_update_status(self, server: dict) -> dict:
        """Детальный статус модов для API и планировщика."""
        from src.core.steamcmd import SteamCMD

        effective_mods = self.get_effective_mods(server)
        tracked_mods = []
        skipped_mods = []
        updated_mods = []
        updated_entries = []

        steamcmd = SteamCMD(self.config, self.logger)
        steamcmd_ready = steamcmd.is_installed()

        if not steamcmd_ready:
            self._log(f"SteamCMD not installed, cannot check updates for {server['id']}", "WARN")

        for entry in effective_mods:
            entry_copy = dict(entry)
            if not steamcmd_ready:
                entry_copy['reason'] = 'SteamCMD not installed'
                skipped_mods.append(entry_copy)
                continue

            mod_id = str(entry.get('id', '')).strip()
            if not entry.get('update_enabled') or not mod_id.isdigit():
                skipped_mods.append(entry_copy)
                continue

            has_update = steamcmd.has_mod_update(server['id'], mod_id, entry['name'])
            entry_copy['has_update'] = has_update
            tracked_mods.append(entry_copy)

            if has_update:
                updated_mods.append(entry['name'])
                updated_entries.append(entry_copy)

        return {
            'server_id': server['id'],
            'effective_mods': effective_mods,
            'tracked_mods': tracked_mods,
            'skipped_mods': skipped_mods,
            'updated_mods': updated_mods,
            'updated_entries': updated_entries,
            'steamcmd_installed': steamcmd_ready,
        }
