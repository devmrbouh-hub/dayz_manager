"""Загрузка и валидация конфигурации"""

import json
import os
import sys
from typing import Optional

from src.core.planned_restart import normalize_planned_restart, validate_planned_restart


def get_external_config_path() -> str:
    """Получить путь только к внешнему config.json."""
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

    return os.path.join(base_dir, 'config', 'config.json')


CONFIG_PATH = get_external_config_path()
REQUIRED_SERVER_FIELDS = ['id', 'name', 'path', 'exe', 'port', 'query_port', 'rcon_port', 'rcon_password']
PORT_FIELDS = ['port', 'query_port', 'rcon_port']
SETTINGS_RULES = {
    'settings.watchdog_interval': {'type': int, 'min': 1, 'max': 3600},
    'settings.restart_notify_minutes': {'type': int, 'min': 0, 'max': 1440},
    'settings.log_retention_days': {'type': int, 'min': 1, 'max': 3650},
    'settings.start_confirm_timeout': {'type': int, 'min': 10, 'max': 3600},
    'scheduler.mod_check_interval': {'type': int, 'min': 60, 'max': 86400},
    'settings.startup_ready_timeout_sec': {'type': int, 'min': 10, 'max': 7200},
    'settings.rpt_tail_buffer_lines': {'type': int, 'min': 10, 'max': 10000},
    'settings.rpt_poll_interval_ms': {'type': int, 'min': 50, 'max': 10000},
}


class Config:
    """Управление конфигурацией"""

    def __init__(self, config_path: str = CONFIG_PATH):
        self.config_path = config_path
        self._config = None

    def load(self) -> dict:
        """Загрузить конфигурацию из файла"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(
                f"External config file not found: {self.config_path}. "
                "Create config\\config.json before startup."
            )

        with open(self.config_path, 'r', encoding='utf-8') as f:
            self._config = json.load(f)

        self._validate()
        return self._config

    def save(self):
        """Сохранить конфигурацию в файл"""
        if self._config is None:
            raise ValueError("Config not loaded")

        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self._config, f, indent=2, ensure_ascii=False)

    def get(self, key: str, default=None):
        """Получить значение по ключу (поддержка вложенных ключей через точку)"""
        if self._config is None:
            self.load()

        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return default
        return value

    def set(self, key: str, value):
        """Установить значение по ключу"""
        if self._config is None:
            self.load()

        self.validate_setting_value(key, value)

        keys = key.split('.')
        obj = self._config
        for k in keys[:-1]:
            if k not in obj:
                obj[k] = {}
            obj = obj[k]
        obj[keys[-1]] = value
        self.save()

    @property
    def servers(self) -> list:
        """Получить список серверов"""
        if self._config is None:
            self.load()
        return self._config.get('servers', [])

    def get_server(self, server_id: str) -> Optional[dict]:
        """Получить сервер по ID"""
        for server in self.servers:
            if server['id'] == server_id:
                return server
        return None

    def add_server(self, server: dict):
        """Добавить сервер"""
        if self._config is None:
            self.load()

        self.validate_server_payload(server)

        # Проверить дубликат
        for s in self._config['servers']:
            if s['id'] == server['id']:
                raise ValueError(f"Server with ID '{server['id']}' already exists")

        self._config['servers'].append(server)
        self.save()

    def get_server_planned_restart(self, server_id: str) -> dict:
        """Получить planned_restart для сервера с дефолтами."""
        server = self.get_server(server_id)
        if not server:
            raise ValueError(f"Server '{server_id}' not found")
        return normalize_planned_restart(server.get('planned_restart'))

    def remove_server(self, server_id: str):
        """Удалить сервер"""
        if self._config is None:
            self.load()

        self._config['servers'] = [
            s for s in self._config['servers'] if s['id'] != server_id
        ]
        self.save()

    def update_server(self, server_id: str, updates: dict):
        """Обновить настройки сервера"""
        if self._config is None:
            self.load()

        for i, server in enumerate(self._config['servers']):
            if server['id'] == server_id:
                self.validate_server_payload(updates, existing_server=server)
                self._config['servers'][i].update(updates)
                self.save()
                return

        raise ValueError(f"Server '{server_id}' not found")

    def validate_setting_value(self, key: str, value):
        """Проверить runtime-настройку, если для нее есть ограничения."""
        rule = SETTINGS_RULES.get(key)
        if not rule:
            return

        if isinstance(value, bool) or not isinstance(value, rule['type']):
            raise ValueError(f"{key} must be an integer")

        if value < rule['min'] or value > rule['max']:
            raise ValueError(f"{key} must be between {rule['min']} and {rule['max']}")

    def validate_server_payload(self, payload: dict, existing_server: Optional[dict] = None):
        """Проверить payload сервера для add/update."""
        if not isinstance(payload, dict):
            raise ValueError("Server payload must be an object")

        if existing_server is not None:
            if 'id' in payload and payload['id'] != existing_server['id']:
                raise ValueError("Server id cannot be changed")
            candidate = dict(existing_server)
            candidate.update(payload)
        else:
            candidate = dict(payload)

        self._validate_server_entry(candidate)

    def _require_string(self, server_id: str, field: str, value, *, allow_empty: bool = False):
        if not isinstance(value, str):
            raise ValueError(f"Server '{server_id}' field '{field}' must be a string")
        if not allow_empty and not value.strip():
            raise ValueError(f"Server '{server_id}' field '{field}' must not be empty")

    def _require_bool(self, server_id: str, field: str, value):
        if not isinstance(value, bool):
            raise ValueError(f"Server '{server_id}' field '{field}' must be a boolean")

    def _require_port(self, server_id: str, field: str, value):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"Server '{server_id}' field '{field}' must be an integer")
        if value < 1 or value > 65535:
            raise ValueError(f"Server '{server_id}' field '{field}' must be between 1 and 65535")

    def _validate_hook_list(self, server_id: str, hook_name: str, value):
        if not isinstance(value, list):
            raise ValueError(f"Server '{server_id}' hook '{hook_name}' must be an array")
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"Server '{server_id}' hook '{hook_name}' entries must be non-empty strings")

    def _validate_server_entry(self, server: dict):
        server_id = server.get('id', 'unknown')
        for field in REQUIRED_SERVER_FIELDS:
            if field not in server:
                raise ValueError(f"Server '{server_id}' missing field: {field}")

        for field in ['id', 'name', 'path', 'exe', 'rcon_password']:
            self._require_string(server_id, field, server.get(field))

        for field in PORT_FIELDS:
            self._require_port(server_id, field, server.get(field))

        optional_string_fields = ['profiles', 'config_file', 'mods_file', 'keys_dir', 'server_mods', 'startup_ready_marker']
        for field in optional_string_fields:
            if field in server and server.get(field) is not None:
                self._require_string(server_id, field, server.get(field), allow_empty=(field == 'server_mods'))

        for field in ['auto_restart', 'hide_console']:
            if field in server:
                self._require_bool(server_id, field, server.get(field))

        launch_args = server.get('launch_args')
        if launch_args is not None:
            if not isinstance(launch_args, list):
                raise ValueError(f"Server '{server_id}' field 'launch_args' must be an array")
            for item in launch_args:
                if not isinstance(item, str) or not item.strip():
                    raise ValueError(f"Server '{server_id}' launch_args entries must be non-empty strings")

        hooks = server.get('hooks')
        if hooks is not None:
            if not isinstance(hooks, dict):
                raise ValueError(f"Server '{server_id}' field 'hooks' must be an object")
            for hook_name in ['beforeStart', 'afterStop']:
                if hook_name in hooks:
                    self._validate_hook_list(server_id, hook_name, hooks.get(hook_name))

        rcon_cfg = server.get('rcon')
        if rcon_cfg is not None:
            if not isinstance(rcon_cfg, dict):
                raise ValueError(f"Server '{server_id}' field 'rcon' must be an object")
            if 'enabled' in rcon_cfg:
                self._require_bool(server_id, 'rcon.enabled', rcon_cfg.get('enabled'))
            if 'host' in rcon_cfg and rcon_cfg.get('host') is not None:
                self._require_string(server_id, 'rcon.host', rcon_cfg.get('host'))
            if 'port' in rcon_cfg and rcon_cfg.get('port') is not None:
                self._require_port(server_id, 'rcon.port', rcon_cfg.get('port'))
            if 'password' in rcon_cfg and rcon_cfg.get('password') is not None:
                self._require_string(server_id, 'rcon.password', rcon_cfg.get('password'))
            if 'timeout' in rcon_cfg:
                timeout = rcon_cfg.get('timeout')
                if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout < 1 or timeout > 300:
                    raise ValueError(f"Server '{server_id}' field 'rcon.timeout' must be between 1 and 300")
            if 'mode' in rcon_cfg:
                mode = rcon_cfg.get('mode')
                allowed_modes = {'preferred', 'required'}
                if mode not in allowed_modes:
                    raise ValueError(f"Server '{server_id}' field 'rcon.mode' must be one of: preferred, required")

        battleye_cfg = server.get('battleye')
        if battleye_cfg is not None:
            if not isinstance(battleye_cfg, dict):
                raise ValueError(f"Server '{server_id}' field 'battleye' must be an object")
            if battleye_cfg.get('path') is not None:
                self._require_string(server_id, 'battleye.path', battleye_cfg.get('path'))

        planned = server.get('planned_restart')
        if planned is not None:
            if not isinstance(planned, dict):
                raise ValueError(
                    f"Server '{server_id}' field 'planned_restart' must be an object"
                )
            validate_planned_restart(planned)

    def _validate(self):
        """Валидировать конфигурацию"""
        required = ['steam', 'servers', 'auth', 'web', 'scheduler', 'settings']
        for key in required:
            if key not in self._config:
                raise ValueError(f"Missing required config key: {key}")

        # Проверить серверы
        for server in self._config['servers']:
            self._validate_server_entry(server)

        rcon_root = self._config.get('rcon')
        if rcon_root is not None and not isinstance(rcon_root, dict):
            raise ValueError("Root config key 'rcon' must be an object")
