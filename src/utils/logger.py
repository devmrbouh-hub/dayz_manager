"""Логирование"""

import os
import logging
from datetime import datetime
from pathlib import Path
import asyncio
from typing import List


class LoggerManager:
    """Управление логами"""

    def __init__(self, log_dir: str = None):
        if log_dir is None:
            log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')

        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "manager.log"

        # Настроить file logger
        self.file_logger = logging.getLogger('manager')
        self.file_logger.setLevel(logging.INFO)

        if not self.file_logger.handlers:
            handler = logging.FileHandler(self.log_file, encoding='utf-8')
            handler.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s'))
            self.file_logger.addHandler(handler)

        # WebSocket подписчики
        self._subscribers: List[asyncio.Queue] = []

    def log(self, message: str, level: str = "INFO"):
        """Записать лог"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}"

        # Записать в файл
        if level == "ERROR":
            self.file_logger.error(message)
        elif level == "WARN":
            self.file_logger.warning(message)
        elif level == "DEBUG":
            self.file_logger.debug(message)
        else:
            self.file_logger.info(message)

        # Отправить подписчикам WebSocket
        for queue in self._subscribers:
            try:
                queue.put_nowait(log_entry)
            except:
                pass

        # Вывести в консоль (без цветов для Windows)
        try:
            colors = {
                "INFO": "\033[92m",
                "WARN": "\033[93m",
                "ERROR": "\033[91m",
                "DEBUG": "\033[94m",
            }
            color = colors.get(level, "\033[0m")
            reset = "\033[0m"
            print(f"{color}{log_entry}{reset}", flush=True)
        except UnicodeEncodeError:
            # Windows fallback
            print(log_entry, flush=True)

    def info(self, message: str):
        self.log(message, "INFO")

    def warn(self, message: str):
        self.log(message, "WARN")

    def error(self, message: str):
        self.log(message, "ERROR")

    def debug(self, message: str):
        self.log(message, "DEBUG")

    def subscribe(self) -> asyncio.Queue:
        """Подписаться на логи (для WebSocket)"""
        queue = asyncio.Queue()
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        """Отписаться от логов"""
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    def get_recent_logs(self, count: int = 100) -> List[str]:
        """Получить последние N логов"""
        if not self.log_file.exists():
            return []

        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            return lines[-count:] if len(lines) > count else lines
        except:
            return []

    def clean_old_logs(self, days: int = 2):
        """Удалить логи старше N дней"""
        from datetime import datetime, timedelta

        if not self.log_file.exists():
            return

        cutoff = datetime.now() - timedelta(days=days)
        file_mtime = datetime.fromtimestamp(self.log_file.stat().st_mtime)

        if file_mtime < cutoff:
            # Архивировать старые логи
            archive = self.log_dir / f"manager_{file_mtime.strftime('%Y%m%d')}.log"
            self.log_file.rename(archive)
            self.info(f"Old logs archived: {archive.name}")

        # Удалить старые архивы
        for old_log in self.log_dir.glob("manager_*.log"):
            old_mtime = datetime.fromtimestamp(old_log.stat().st_mtime)
            if old_mtime < cutoff and old_log != self.log_file:
                old_log.unlink()
                self.info(f"Deleted old log: {old_log.name}")


# Глобальный логгер
logger = LoggerManager()
