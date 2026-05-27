"""Загрузка и валидация конфигурации"""

import json
import os
import sys
from pathlib import Path
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

        if 'planned_restart' in updates:
            updates = dict(updates)
            updates['planned_restart'] = validate_planned_restart(updates['planned_restart'])

        for i, server in enumerate(self._config['servers']):
            if server['id'] == server_id:
                self._config['servers'][i].update(updates)
                self.save()
                return

        raise ValueError(f"Server '{server_id}' not found")

    def _validate(self):
        """Валидировать конфигурацию"""
        required = ['steam', 'servers', 'auth', 'web', 'scheduler', 'settings']
        for key in required:
            if key not in self._config:
                raise ValueError(f"Missing required config key: {key}")

        # Проверить серверы
        for server in self._config['servers']:
            for field in ['id', 'name', 'path', 'exe', 'port', 'query_port', 'rcon_port', 'rcon_password']:
                if field not in server:
                    raise ValueError(f"Server '{server.get('id', 'unknown')}' missing field: {field}")

            rcon_cfg = server.get('rcon')
            if rcon_cfg is not None and not isinstance(rcon_cfg, dict):
                raise ValueError(f"Server '{server.get('id', 'unknown')}' field 'rcon' must be an object")

            battleye_cfg = server.get('battleye')
            if battleye_cfg is not None and not isinstance(battleye_cfg, dict):
                raise ValueError(f"Server '{server.get('id', 'unknown')}' field 'battleye' must be an object")

            if battleye_cfg and battleye_cfg.get('path') is not None and not isinstance(battleye_cfg.get('path'), str):
                raise ValueError(f"Server '{server.get('id', 'unknown')}' battleye.path must be a string")

            planned = server.get('planned_restart')
            if planned is not None:
                if not isinstance(planned, dict):
                    raise ValueError(
                        f"Server '{server.get('id', 'unknown')}' field 'planned_restart' must be an object"
                    )
                validate_planned_restart(planned)

        rcon_root = self._config.get('rcon')
        if rcon_root is not None and not isinstance(rcon_root, dict):
            raise ValueError("Root config key 'rcon' must be an object")
