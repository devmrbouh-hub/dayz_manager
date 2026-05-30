"""Система хуков"""

import os
import sys
import importlib.util
from pathlib import Path
from typing import List


def get_project_base_dir() -> Path:
    """Корень установки (рядом с EXE в frozen-режиме)."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


class Hooks:
    """Система хуков для кастомной логики"""

    def __init__(self, config, logger=None):
        self.config = config
        self.logger = logger
        self.base_dir = get_project_base_dir()

    def _log(self, message: str, level: str = "INFO"):
        if self.logger:
            self.logger.log(message, level)
        else:
            print(f"[{level}] {message}")

    def _resolve_hook_path(self, hook_path: str) -> Path | None:
        path = Path(hook_path)
        if not path.is_absolute():
            path = self.base_dir / path

        resolved = path.resolve()
        try:
            resolved.relative_to(self.base_dir.resolve())
        except ValueError:
            self._log(f"Hook path is outside base directory and was skipped: {resolved}", "WARN")
            return None
        return resolved

    def execute_hook(self, server: dict, hook_name: str):
        """
        Выполнить хук для сервера.

        hook_name: 'beforeStart' или 'afterStop'
        """
        hooks = server.get('hooks', {}).get(hook_name, [])

        if not hooks:
            return

        self._log(f"Executing {hook_name} hooks for {server['id']}...", "INFO")

        for hook_path in hooks:
            resolved_path = self._resolve_hook_path(hook_path)
            if resolved_path is None:
                continue

            if not resolved_path.exists():
                self._log(f"Hook file not found: {resolved_path}", "WARN")
                continue

            try:
                # Загрузить модуль
                spec = importlib.util.spec_from_file_location("hook_module", resolved_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Выполнить функцию run
                if hasattr(module, 'run'):
                    module.run(server)
                    self._log(f"Hook executed: {resolved_path}", "INFO")
                else:
                    self._log(f"Hook has no 'run' function: {resolved_path}", "WARN")

            except Exception as e:
                self._log(f"Hook failed {resolved_path}: {e}", "ERROR")
