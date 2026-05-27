"""Discord бот для уведомлений"""

import asyncio
from typing import Optional


class DiscordBot:
    """Discord бот"""

    def __init__(self, config: dict, logger=None):
        self.config = config
        self.logger = logger
        self.enabled = config.get('notifications.discord.enabled', False)
        self.token = config.get('notifications.discord.token', '')
        self.channel_id = config.get('notifications.discord.channel_id', '')

        self.client = None
        self._task = None

    def _log(self, message: str, level: str = "INFO"):
        if self.logger:
            self.logger.log(message, level)
        else:
            print(f"[{level}] {message}")

    async def start(self):
        """Запустить бота"""
        if not self.enabled:
            self._log("Discord bot disabled", "INFO")
            return

        if not self.token:
            self._log("Discord token not configured", "WARN")
            return

        try:
            import discord

            intents = discord.Intents.default()
            intents.message_content = True

            self.client = discord.Client(intents=intents)

            @self.client.event
            async def on_ready():
                self._log(f"Discord bot logged in as {self.client.user}", "INFO")

            @self.client.event
            async def on_message(message):
                if message.author == self.client.user:
                    return

                # Команды
                if message.content.startswith('!'):
                    await self._handle_command(message)

            # Запустить в фоне
            self._task = asyncio.create_task(self.client.start(self.token))
            self._log("Discord bot started", "INFO")

        except ImportError:
            self._log("discord.py not installed. Run: pip install discord.py", "ERROR")
        except Exception as e:
            self._log(f"Failed to start Discord bot: {e}", "ERROR")

    async def stop(self):
        """Остановить бота"""
        if self._task:
            self._task.cancel()
        if self.client:
            await self.client.close()
        self._log("Discord bot stopped", "INFO")

    async def send_message(self, message: str):
        """Отправить сообщение в канал"""
        if not self.client or not self.client.is_ready():
            return

        try:
            channel = self.client.get_channel(int(self.channel_id))
            if channel:
                await channel.send(message)
        except Exception as e:
            self._log(f"Failed to send Discord message: {e}", "ERROR")

    async def notify_server_start(self, server_id: str, server_name: str, pid: int):
        """Уведомление о запуске сервера"""
        message = f"✅ **{server_name}** (`{server_id}`) started!\nPID: `{pid}`"
        await self.send_message(message)

    async def notify_server_stop(self, server_id: str, server_name: str):
        """Уведомление об остановке сервера"""
        message = f"🛑 **{server_name}** (`{server_id}`) stopped."
        await self.send_message(message)

    async def notify_server_crash(self, server_id: str, server_name: str):
        """Уведомление о падении сервера"""
        message = f"⚠️ **{server_name}** (`{server_id}`) crashed! Auto-restarting..."
        await self.send_message(message)

    async def notify_mod_update(self, server_id: str, server_name: str, mods: list):
        """Уведомление об обновлении модов"""
        mods_list = ", ".join(mods)
        message = f"🔄 **{server_name}** (`{server_id}`) mods updated:\n{mods_list}"
        await self.send_message(message)

    async def _handle_command(self, message):
        """Обработать команду"""
        content = message.content.strip()
        parts = content.split()
        command = parts[0].lower()

        if command == '!status':
            await self._cmd_status(message)
        elif command == '!help':
            await self._cmd_help(message)

    async def _cmd_status(self, message):
        """Команда !status"""
        from src.core.config import Config
        config = Config()
        config.load()

        servers = config.servers
        status_lines = ["📊 **Server Status:**\n"]

        for server in servers:
            running = "✅" if self._is_running(server) else "❌"
            status_lines.append(f"{running} **{server['name']}** (`:{server['port']}`)")

        await message.channel.send("\n".join(status_lines))

    def _is_running(self, server: dict) -> bool:
        """Проверить запущен ли сервер"""
        import psutil
        from pathlib import Path

        pid_file = Path(server['path']) / "server.pid"
        if not pid_file.exists():
            return False

        try:
            pid = int(pid_file.read_text().strip())
            process = psutil.Process(pid)
            return process.is_running()
        except:
            return False

    async def _cmd_help(self, message):
        """Команда !help"""
        help_text = """📖 **Available Commands:**

`!status` - Show server status
`!help` - Show this help message

More commands coming soon!"""
        await message.channel.send(help_text)
