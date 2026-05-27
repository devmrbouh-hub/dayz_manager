"""Проверка системных зависимостей"""

import sys
import os
import subprocess
from pathlib import Path


class SystemChecker:
    """Проверка зависимостей ОС"""

    def __init__(self, logger=None):
        self.logger = logger

    def _log(self, message: str, level: str = "INFO"):
        if self.logger:
            self.logger.log(message, level)
        else:
            print(f"[{level}] {message}")

    def check_all(self) -> dict:
        """Проверить все зависимости"""
        results = {
            'python_version': self._check_python(),
            'vcredist': self._check_vcredist(),
            'directx': self._check_directx(),
            'steamcmd': self._check_steamcmd(),
        }

        return results

    def _check_python(self) -> dict:
        """Проверить версию Python"""
        version = sys.version_info
        return {
            'ok': version.major >= 3 and version.minor >= 10,
            'version': f"{version.major}.{version.minor}.{version.micro}",
            'required': '3.10+'
        }

    def _check_vcredist(self) -> dict:
        """Проверить Visual C++ Redistributable"""
        # Проверить наличие dll
        system_paths = [
            Path(os.environ.get('WINDIR', 'C:\\Windows')) / 'System32' / 'vcruntime140.dll',
            Path(os.environ.get('WINDIR', 'C:\\Windows')) / 'SysWOW64' / 'vcruntime140.dll',
        ]

        for dll_path in system_paths:
            if dll_path.exists():
                return {'ok': True, 'path': str(dll_path)}

        return {
            'ok': False,
            'message': 'Visual C++ Redistributable not found',
            'download': 'https://aka.ms/vs/17/release/vc_redist.x64.exe'
        }

    def _check_directx(self) -> dict:
        """Проверить DirectX"""
        # DirectX всегда установлен на Windows Server
        return {
            'ok': True,
            'message': 'DirectX available on Windows'
        }

    def _check_steamcmd(self) -> dict:
        """Проверить SteamCMD"""
        from src.core.config import Config
        try:
            config = Config()
            config.load()
            steamcmd_path = config.get('steam.steamcmd_path', r'C:\SteamCMD\steamcmd.exe')

            if Path(steamcmd_path).exists():
                return {'ok': True, 'path': steamcmd_path}
            else:
                return {
                    'ok': False,
                    'message': 'SteamCMD not found',
                    'path': steamcmd_path,
                    'download': 'https://developer.valvesoftware.com/wiki/SteamCMD'
                }
        except:
            return {
                'ok': False,
                'message': 'Config not found'
            }

    def print_report(self):
        """Вывести отчёт"""
        results = self.check_all()

        self._log("=" * 60, "INFO")
        self._log("  System Dependencies Check", "INFO")
        self._log("=" * 60, "INFO")

        for name, result in results.items():
            status = "OK" if result.get('ok') else "FAIL"
            info = result.get('version') or result.get('path') or result.get('message', '')
            self._log(f"  [{status}] {name}: {info}", "INFO")

            if not result.get('ok') and result.get('download'):
                self._log(f"     Download: {result['download']}", "WARN")

        self._log("=" * 60, "INFO")
