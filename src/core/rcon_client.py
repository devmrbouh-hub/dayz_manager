"""BattlEye RCON клиент для DayZ серверов (через bercon-cli.exe)"""

import subprocess
import asyncio
import concurrent.futures
import os
import re
import time
from typing import Callable, List, Optional, Tuple


MOD_NAMES_MAX_LEN = 120
MESSAGE_PAUSE_SECONDS = 2


DEFAULT_BERCON_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    'bercon-cli.exe'
)


class RconClient:
    """BattlEye RCON клиент для DayZ через bercon-cli.exe"""

    def __init__(self, config=None, logger=None):
        self.config = config
        self.logger = logger
        self._chat_inject: Optional[Callable[..., None]] = None

    def set_chat_inject(self, callback: Callable[..., None]):
        """callback(server, text, player=..., channel=...) after successful say."""
        self._chat_inject = callback

    def _inject_chat(self, server: dict, text: str, player: str = "Server", channel: str = "Broadcast"):
        if not self._chat_inject or not text.strip():
            return
        try:
            self._chat_inject(server, text, player=player, channel=channel)
        except Exception as exc:
            self._log(f"Chat inject failed for {server.get('id')}: {exc}", "DEBUG")

    def _log(self, message: str, level: str = "INFO"):
        if self.logger:
            self.logger.log(message, level)
        else:
            print(f"[{level}] {message}")

    def _get_bercon_path(self) -> str:
        if self.config:
            configured_path = self.config.get('rcon.client_path')
            if configured_path:
                return configured_path
        return DEFAULT_BERCON_PATH

    def _get_server_rcon_config(self, server: dict) -> dict:
        rcon_cfg = server.get('rcon', {}) or {}
        enabled = rcon_cfg.get('enabled', True)
        host = rcon_cfg.get('host') or server.get('rcon_host') or '127.0.0.1'
        port = int(rcon_cfg.get('port', server.get('rcon_port', 2305)))
        password = rcon_cfg.get('password', server.get('rcon_password', ''))
        mode = rcon_cfg.get('mode', 'preferred')
        timeout = int(rcon_cfg.get('timeout', 10))

        return {
            'enabled': enabled,
            'host': host,
            'port': port,
            'password': password,
            'mode': mode,
            'timeout': timeout,
        }

    def _classify_error(self, message: str) -> str:
        lowered = (message or '').lower()
        if 'not found' in lowered or 'client not found' in lowered:
            return 'client_missing'
        if 'login deadline timeout' in lowered or 'timeout' in lowered or 'deadline' in lowered:
            return 'timeout'
        if 'access denied' in lowered or 'auth' in lowered or 'password' in lowered:
            return 'auth_failed'
        return 'endpoint_unavailable'

    def _normalize_success_output(self, command: str, output: str) -> str:
        """Убрать шум bercon-cli из успешных ответов."""
        raw_lines = [line.rstrip() for line in (output or '').splitlines() if line.strip()]
        if not raw_lines:
            return ''

        filtered_lines = [line for line in raw_lines if line.strip().lower() != 'unknown command']
        if filtered_lines:
            return '\n'.join(filtered_lines).strip()

        # Для say/#shutdown bercon-cli иногда печатает только "Unknown command",
        # хотя сервер принял команду и выполнил её.
        if command.startswith('say ') or command.startswith('#'):
            return 'RCON command accepted'

        return '\n'.join(raw_lines).strip()

    def _safe_log_text(self, text: str) -> str:
        """Сделать текст безопасным для Windows-консоли."""
        return (text or '').encode('ascii', 'replace').decode('ascii')

    def _execute(self, host: str, port: int, password: str, command: str, timeout: int = 10) -> Tuple[bool, str, str]:
        bercon_path = self._get_bercon_path()

        if not os.path.exists(bercon_path):
            message = f"RCON client not found at {bercon_path}"
            self._log(message, "ERROR")
            return False, message, 'client_missing'

        try:
            cmd = [
                bercon_path,
                '-i', host,
                '-p', str(port),
                '-P', password,
                'exec', '--', command
            ]

            self._log(f"RCON exec: host={host} port={port} command={command}", "DEBUG")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding='utf-8',
                errors='replace'
            )

            output = (result.stdout or '') + (result.stderr or '')
            clean_output = re.sub(r'\x1b\[[0-9;]*m', '', output).strip()

            if result.returncode == 0:
                normalized_output = self._normalize_success_output(command, clean_output)
                if normalized_output:
                    first_line = normalized_output.splitlines()[0].strip()
                    if first_line:
                        self._log(
                            f"RCON [{command}]: {self._safe_log_text(first_line[:200])}",
                            "DEBUG"
                        )
                return True, normalized_output, ''

            details = clean_output or f"Process exited with code {result.returncode}"
            error_type = self._classify_error(details)
            self._log(f"RCON command failed [{command}] ({error_type}): {details[:500]}", "WARN")
            return False, details, error_type

        except subprocess.TimeoutExpired:
            message = f"RCON timeout for command: {command}"
            self._log(message, "ERROR")
            return False, message, 'timeout'
        except Exception as e:
            message = f"RCON error: {e}"
            self._log(message, "ERROR")
            return False, message, 'endpoint_unavailable'

    def send_command(self, host: str, port: int, password: str, command: str, timeout: int = 10) -> bool:
        """Отправить RCON команду через bercon-cli.exe"""
        success, _, _ = self._execute(host, port, password, command, timeout)
        return success

    async def send_command_async(self, host: str, port: int, password: str, command: str) -> bool:
        """Отправить RCON команду (асинхронно)"""
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            return await loop.run_in_executor(
                executor,
                self.send_command,
                host, port, password, command
            )

    def send_message(self, host: str, port: int, password: str, message: str, timeout: int = 10) -> bool:
        """Отправить сообщение всем игрокам (say -1)"""
        # Без кавычек — bercon сам экранирует
        return self.send_command(host, port, password, f'say -1 {message}', timeout)

    def send_shutdown(self, host: str, port: int, password: str, timeout: int = 10) -> bool:
        """Выключить сервер (#shutdown)"""
        return self.send_command(host, port, password, '#shutdown', timeout)

    def send_players(self, host: str, port: int, password: str, timeout: int = 10) -> Optional[str]:
        """Получить список игроков"""
        success, output, _ = self._execute(host, port, password, 'players', timeout)
        return output if success else None

    @staticmethod
    def parse_player_ids(players_output: str) -> List[int]:
        """Извлечь ID игроков из вывода команды players.

        bercon-cli печатает таблицу с box-drawing символами, например:
        │ 0 │ 192.168.0.225 │ 55281 │ ... │ Mr_BOUH │ ...
        Старый/plain формат: "0 192.168.0.1:1234 Name"
        """
        if not players_output:
            return []

        ids = []
        seen = set()
        decoration_chars = set('│|─━┌┐└┘├┤┬┴┼╭╮╰╯')

        for line in players_output.splitlines():
            stripped = line.strip()
            if not stripped:
                continue

            lowered = stripped.lower()
            if lowered.startswith('players') or lowered.startswith('unknown command'):
                continue

            # Строки-разделители таблицы без данных игрока
            if not any(ch.isalnum() for ch in stripped):
                continue
            if all(ch in decoration_chars or ch.isspace() for ch in stripped):
                continue

            player_id = None
            box_match = re.match(r'^[│|]\s*(\d+)\s*[│|]', stripped)
            if box_match:
                player_id = int(box_match.group(1))
            else:
                plain_match = re.match(r'^(\d+)\s', stripped)
                if plain_match:
                    player_id = int(plain_match.group(1))

            if player_id is not None and player_id not in seen:
                seen.add(player_id)
                ids.append(player_id)

        return ids

    @staticmethod
    def _is_player_row_metadata(token: str) -> bool:
        """IP, port, ping, BE GUID — not the display name."""
        t = token.strip()
        if not t:
            return True
        if t.lower() in ("true", "false"):
            return True
        if re.match(r"^\d+$", t):
            return True
        if re.match(r"^\d+\.\d+\.\d+\.\d+(:\d+)?$", t):
            return True
        if re.match(r"^[0-9a-fA-F=+-]+$", t) and len(t) >= 8:
            return True
        return False

    @classmethod
    def _pick_player_name_from_row_parts(cls, parts: List[str]) -> Optional[str]:
        """Name from bercon table row; last column may be admin true/false."""
        if len(parts) < 2:
            return None

        tokens = parts[1:]
        while tokens and tokens[-1].strip().lower() in ("true", "false"):
            tokens.pop()
        while tokens and cls._is_player_row_metadata(tokens[0]):
            tokens.pop(0)

        if tokens:
            return tokens[-1].strip()

        for token in reversed(parts[1:]):
            cleaned = token.strip()
            if cleaned.lower() in ("true", "false"):
                continue
            if cls._is_player_row_metadata(cleaned):
                continue
            return cleaned
        return None

    @staticmethod
    def _clean_plain_player_name(name: str) -> str:
        name = name.strip()
        if name.lower().endswith(" true"):
            return name[:-5].rstrip()
        if name.lower().endswith(" false"):
            return name[:-6].rstrip()
        return name

    @classmethod
    def parse_players(cls, players_output: str) -> List[dict]:
        """Извлечь ID и ники игроков из вывода команды players."""
        if not players_output:
            return []

        decoration_chars = set('│|─━┌┐└┘├┤┬┴┼╭╮╰╯')
        players = []
        seen = set()

        for line in players_output.splitlines():
            stripped = line.strip()
            if not stripped:
                continue

            lowered = stripped.lower()
            if lowered.startswith('players') or lowered.startswith('unknown command'):
                continue
            if not any(ch.isalnum() for ch in stripped):
                continue
            if all(ch in decoration_chars or ch.isspace() for ch in stripped):
                continue

            player_id = None
            name = None

            box_match = re.match(r'^[│|]\s*(\d+)\s*[│|]', stripped)
            if box_match:
                player_id = int(box_match.group(1))
                parts = [p.strip() for p in re.split(r'[│|]', stripped) if p.strip()]
                if len(parts) >= 2:
                    name = cls._pick_player_name_from_row_parts(parts)
            else:
                plain_match = re.match(r'^(\d+)\s+\S+\s+(.+)$', stripped)
                if plain_match:
                    player_id = int(plain_match.group(1))
                    name = cls._clean_plain_player_name(plain_match.group(2))

            if player_id is None or player_id in seen:
                continue

            seen.add(player_id)
            players.append({
                'id': player_id,
                'name': name or f'Player {player_id}',
            })

        return players

    def lock_server(self, server: dict) -> bool:
        """Заблокировать сервер для новых подключений (#lock)."""
        rcon_cfg = self._get_server_rcon_config(server)
        if not rcon_cfg['enabled']:
            return False
        success, _, _ = self._execute(
            rcon_cfg['host'],
            rcon_cfg['port'],
            rcon_cfg['password'],
            '#lock',
            rcon_cfg['timeout'],
        )
        if success:
            self._log(f"Server {server['id']} locked for new connections", "INFO")
        return success

    def unlock_server(self, server: dict) -> bool:
        """Снять блокировку новых подключений (#unlock)."""
        rcon_cfg = self._get_server_rcon_config(server)
        if not rcon_cfg['enabled']:
            return False
        success, _, _ = self._execute(
            rcon_cfg['host'],
            rcon_cfg['port'],
            rcon_cfg['password'],
            '#unlock',
            rcon_cfg['timeout'],
        )
        if success:
            self._log(f"Server {server['id']} unlocked for new connections", "INFO")
        return success

    def kick_player(self, server: dict, player_id: int, reason: str = 'Planned restart') -> bool:
        """Кикнуть игрока по ID."""
        rcon_cfg = self._get_server_rcon_config(server)
        if not rcon_cfg['enabled']:
            return False
        command = f'kick {player_id} {reason}'
        return self.send_command(
            rcon_cfg['host'],
            rcon_cfg['port'],
            rcon_cfg['password'],
            command,
            rcon_cfg['timeout'],
        )

    def kick_all_players(self, server: dict, reason: str = 'Planned restart') -> int:
        """Кикнуть всех онлайн-игроков. Возвращает число успешных kick."""
        rcon_cfg = self._get_server_rcon_config(server)
        if not rcon_cfg['enabled']:
            return 0

        success, output, _ = self._execute(
            rcon_cfg['host'],
            rcon_cfg['port'],
            rcon_cfg['password'],
            'players',
            rcon_cfg['timeout'],
        )
        if not success:
            self._log(
                f"Failed to list players for kick on {server['id']}: {output[:300]}",
                "WARN",
            )
            return 0

        player_ids = self.parse_player_ids(output)
        if not player_ids:
            self._log(f"No players online to kick on {server['id']}", "DEBUG")
            return 0

        kicked = 0
        for player_id in player_ids:
            if self.kick_player(server, player_id, reason):
                kicked += 1
            else:
                self._log(f"Failed to kick player {player_id} on {server['id']}", "WARN")

        self._log(f"Kicked {kicked}/{len(player_ids)} players on {server['id']}", "INFO")
        return kicked

    def send_bilingual_say(self, server: dict, ru_message: str, en_message: str) -> bool:
        """Отправить RU и EN сообщения всем игрокам (say -1)."""
        rcon_cfg = self._get_server_rcon_config(server)
        if not rcon_cfg['enabled']:
            self._log(f"RCON disabled for server {server['id']}, skipping bilingual say", "INFO")
            return False

        all_success = True
        for index, message in enumerate((ru_message, en_message)):
            success, output, error_type = self._execute(
                rcon_cfg['host'],
                rcon_cfg['port'],
                rcon_cfg['password'],
                f'say -1 {message}',
                rcon_cfg['timeout'],
            )
            if success:
                lang = 'RU' if index == 0 else 'EN'
                self._log(f"Bilingual say sent ({lang}) to {server['id']}", "DEBUG")
                self._inject_chat(server, message, player="Server", channel="Global")
            else:
                all_success = False
                self._log(
                    f"Failed bilingual say for {server['id']} ({error_type}): {output[:300]}",
                    "WARN",
                )

            if index == 0:
                time.sleep(MESSAGE_PAUSE_SECONDS)

        return all_success

    def test_server(self, server: dict) -> dict:
        """Проверить доступность RCON для сервера"""
        rcon_cfg = self._get_server_rcon_config(server)
        bercon_path = self._get_bercon_path()

        result = {
            'enabled': rcon_cfg['enabled'],
            'client_path': bercon_path,
            'client_exists': os.path.exists(bercon_path),
            'host': rcon_cfg['host'],
            'port': rcon_cfg['port'],
            'mode': rcon_cfg['mode'],
            'success': False,
            'message': '',
            'error_type': '',
            'timeout': rcon_cfg['timeout'],
        }

        if not rcon_cfg['enabled']:
            result['message'] = 'RCON disabled in config'
            return result

        if not rcon_cfg['password']:
            result['message'] = 'RCON password is empty'
            return result

        success, output, error_type = self._execute(
            rcon_cfg['host'],
            rcon_cfg['port'],
            rcon_cfg['password'],
            'players',
            rcon_cfg['timeout']
        )
        result['success'] = success
        result['message'] = output or ('RCON test OK' if success else 'RCON test failed')
        result['error_type'] = error_type
        return result

    @staticmethod
    def _display_mod_name(name: str) -> str:
        """Убрать ведущий @ из имени мода для отображения игрокам."""
        stripped = (name or '').strip()
        if stripped.startswith('@'):
            return stripped[1:]
        return stripped

    def _format_mod_names_list(self, mod_names: Optional[List[str]]) -> str:
        """Сформировать список имён модов без @, с обрезкой при превышении лимита."""
        if not mod_names:
            return ''

        display_names = [
            self._display_mod_name(name)
            for name in mod_names
            if name and name.strip()
        ]
        if not display_names:
            return ''

        joined = ', '.join(display_names)
        if len(joined) <= MOD_NAMES_MAX_LEN:
            return joined

        truncated = joined[:MOD_NAMES_MAX_LEN].rstrip(', ')
        self._log(
            f"Mod names list truncated for RCON message ({len(joined)} > {MOD_NAMES_MAX_LEN} chars)",
            "WARN"
        )
        return f"{truncated}..."

    def _build_restart_messages(self, minutes: int, mod_names: Optional[List[str]] = None) -> List[str]:
        """Сформировать RU и EN сообщения о предстоящем рестарте."""
        mods_list = self._format_mod_names_list(mod_names)
        has_mods = bool(mods_list)

        if has_mods:
            mod_count = len([n for n in (mod_names or []) if n and n.strip()])
            if mod_count == 1:
                ru = (
                    f"[INFO] Сервер будет перезагружен через {minutes} мин. "
                    f"для обновления мода: {mods_list}. Завершите игру."
                )
                en = (
                    f"[INFO] Server will restart in {minutes} minutes "
                    f"to update mod: {mods_list}. Please finish your activities."
                )
            else:
                ru = (
                    f"[INFO] Сервер будет перезагружен через {minutes} мин. "
                    f"для обновления модов: {mods_list}. Завершите игру."
                )
                en = (
                    f"[INFO] Server will restart in {minutes} minutes "
                    f"to update mods: {mods_list}. Please finish your activities."
                )
        else:
            ru = f"[INFO] Сервер будет перезагружен через {minutes} мин. Завершите игру."
            en = f"[INFO] Server will restart in {minutes} minutes. Please finish your activities."

        return [ru, en]

    def notify_restart(
        self,
        server: dict,
        minutes: int = 5,
        mod_names: Optional[List[str]] = None,
    ) -> bool:
        """Уведомить игроков о рестарте (RU, затем EN)."""
        rcon_cfg = self._get_server_rcon_config(server)
        if not rcon_cfg['enabled']:
            self._log(f"RCON disabled for server {server['id']}, skipping restart notification", "INFO")
            return False

        messages = self._build_restart_messages(minutes, mod_names)
        notified = self.send_bilingual_say(server, messages[0], messages[1])
        if notified:
            self._log(f"Players notified about restart in {minutes} minutes", "INFO")
        return notified

    def shutdown_server(self, server: dict) -> bool:
        """Выключить сервер через RCON"""
        rcon_cfg = self._get_server_rcon_config(server)
        if not rcon_cfg['enabled']:
            self._log(f"RCON disabled for server {server['id']}, skipping graceful shutdown", "INFO")
            return False

        success, output, error_type = self._execute(
            rcon_cfg['host'],
            rcon_cfg['port'],
            rcon_cfg['password'],
            '#shutdown',
            rcon_cfg['timeout']
        )
        if success:
            self._log(f"Server {server['id']} shutdown via RCON", "INFO")
        else:
            self._log(
                f"Failed to shutdown {server['id']} via RCON ({error_type}): {output[:300]}",
                "WARN"
            )
        return success

    def get_server_mode(self, server: dict) -> str:
        return self._get_server_rcon_config(server)['mode']
