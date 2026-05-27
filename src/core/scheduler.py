"""Планировщик задач на чистом asyncio (без APScheduler)"""

import asyncio
import functools
from datetime import datetime
from pathlib import Path
from typing import Optional, Set

from src.core.planned_restart import (
    KICK_WARN_DELAY_SECONDS,
    LOCK_KICK_STAGE,
    RESTART_STAGE,
    applicable_warning_stages,
    get_stage_messages,
    is_planned_restart_enabled,
    minutes_until_next_restart,
    normalize_planned_restart,
)


WEEKDAY_ALIASES = {
    'mon': 0, 'monday': 0,
    'tue': 1, 'tuesday': 1,
    'wed': 2, 'wednesday': 2,
    'thu': 3, 'thursday': 3,
    'fri': 4, 'friday': 4,
    'sat': 5, 'saturday': 5,
    'sun': 6, 'sunday': 6,
}


class Scheduler:
    """Планировщик задач"""

    def __init__(self, config, logger=None):
        self.config = config
        self.logger = logger

        # Компоненты (будут установлены из main.py)
        self.server_mgr = None
        self.mod_sync = None
        self.rcon = None

        # Задачи
        self._tasks = []
        self._mod_check_task = None
        self._mod_check_interval = 600
        self._cron_fired: Set[str] = set()
        self._running = False
        self._planned_locked_servers: Set[str] = set()

    def _log(self, message: str, level: str = "INFO"):
        if self.logger:
            self.logger.log(message, level)
        else:
            print(f"[{level}] {message}")

    def setup_jobs(self):
        """Настроить все задачи (но не запускать)"""
        settings = self.config.get('settings', {})
        scheduler_config = self.config.get('scheduler', {})

        # WatchDog (проверка серверов каждые N секунд)
        watchdog_interval = settings.get('watchdog_interval', 10)
        self._tasks.append(asyncio.create_task(
            self._periodic_job(self._watchdog_job, watchdog_interval, 'WatchDog')
        ))
        self._log(f"WatchDog scheduled: every {watchdog_interval}s")

        # Проверка обновлений модов
        self._mod_check_interval = scheduler_config.get('mod_check_interval', 600)
        self._mod_check_task = asyncio.create_task(
            self._periodic_job(self._mod_check_job, self._mod_check_interval, 'ModCheck')
        )
        self._tasks.append(self._mod_check_task)
        self._log(f"Mod check scheduled: every {self._mod_check_interval}s")

        # Плановые рестарты (интервал от 00:00) + legacy restart_schedule
        self._tasks.append(asyncio.create_task(
            self._periodic_job(self._planned_restart_job, 60, 'PlannedRestart')
        ))
        self._log("Planned restart job scheduled: every 60s")

        # Очистка логов
        log_clean_interval = scheduler_config.get('log_clean_interval', 86400)
        self._tasks.append(asyncio.create_task(
            self._periodic_job(self._log_clean_job, log_clean_interval, 'LogClean')
        ))
        self._log(f"Log cleanup scheduled: every {log_clean_interval}s")

    async def start(self):
        """Запустить планировщик"""
        self._running = True
        self.setup_jobs()
        self._log("Scheduler started", "INFO")

    async def stop(self):
        """Остановить планировщик"""
        self._running = False

        # Отменить все задачи
        for task in self._tasks:
            task.cancel()

        # Подождать завершения
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        self._mod_check_task = None
        self._tasks.clear()
        self._log("Scheduler stopped", "INFO")

    async def reschedule_mod_check(self, interval: int):
        """Перезапустить задачу ModCheck с новым интервалом (после PUT /api/settings)."""
        interval = int(interval)
        if interval < 60:
            interval = 60

        if self._mod_check_task and not self._mod_check_task.done():
            self._mod_check_task.cancel()
            try:
                await self._mod_check_task
            except asyncio.CancelledError:
                pass
            if self._mod_check_task in self._tasks:
                self._tasks.remove(self._mod_check_task)

        self._mod_check_interval = interval
        self._mod_check_task = asyncio.create_task(
            self._periodic_job(self._mod_check_job, interval, 'ModCheck')
        )
        if self._running:
            self._tasks.append(self._mod_check_task)
        self._log(f"Mod check rescheduled: every {interval}s", "INFO")

    def _normalize_weekdays(self, days) -> set:
        if not days:
            return set(range(7))
        normalized = set()
        for item in days:
            if isinstance(item, int):
                normalized.add(int(item) % 7)
            elif isinstance(item, str):
                key = item.strip().lower()
                if key.isdigit():
                    normalized.add(int(key) % 7)
                elif key[:3] in WEEKDAY_ALIASES:
                    normalized.add(WEEKDAY_ALIASES[key[:3]])
                elif key in WEEKDAY_ALIASES:
                    normalized.add(WEEKDAY_ALIASES[key])
        return normalized if normalized else set(range(7))

    def _cron_expression_due(self, cron_expr: str, now: datetime) -> bool:
        """Простой matcher для 5-полевого cron: minute hour dom month dow."""
        parts = cron_expr.strip().split()
        if len(parts) != 5:
            return False

        minute_f, hour_f, dom_f, month_f, dow_f = parts
        checks = [
            (minute_f, now.minute, 0, 59),
            (hour_f, now.hour, 0, 23),
            (dom_f, now.day, 1, 31),
            (month_f, now.month, 1, 12),
            (dow_f, now.weekday(), 0, 6),
        ]

        for field, value, min_v, max_v in checks:
            if field == '*':
                continue
            if field.isdigit():
                if int(field) != value:
                    return False
                continue
            if '/' in field:
                base, step = field.split('/', 1)
                if not step.isdigit():
                    return False
                step_n = int(step)
                if base == '*':
                    if value % step_n != 0:
                        return False
                elif base.isdigit():
                    if value < int(base) or (value - int(base)) % step_n != 0:
                        return False
                continue
            if ',' in field:
                allowed = {int(x) for x in field.split(',') if x.isdigit()}
                if value not in allowed:
                    return False
                continue
            return False
        return True

    def _schedule_entry_due(self, entry: dict, now: datetime) -> bool:
        cron_expr = entry.get('cron')
        if cron_expr:
            return self._cron_expression_due(str(cron_expr), now)

        time_str = entry.get('time')
        if not time_str:
            return False

        try:
            hour_str, minute_str = str(time_str).strip().split(':', 1)
            hour = int(hour_str)
            minute = int(minute_str)
        except (ValueError, AttributeError):
            self._log(f"Invalid restart_schedule time: {time_str}", "WARN")
            return False

        if now.hour != hour or now.minute != minute:
            return False

        allowed_days = self._normalize_weekdays(entry.get('days'))
        return now.weekday() in allowed_days

    def _prune_cron_fired(self, now: datetime):
        today_prefix = now.strftime('%Y-%m-%d')
        self._cron_fired = {k for k in self._cron_fired if k.startswith(today_prefix)}

    def _stage_fired_key(self, now: datetime, server_id: str, stage: int) -> str:
        return f"{now.strftime('%Y-%m-%d %H:%M')}:{server_id}:stage{stage}"

    def _mark_stage_fired(self, now: datetime, server_id: str, stage: int) -> bool:
        key = self._stage_fired_key(now, server_id, stage)
        if key in self._cron_fired:
            return False
        self._cron_fired.add(key)
        return True

    async def _planned_restart_job(self):
        """Интервальные плановые рестарты и legacy restart_schedule."""
        if not self.server_mgr:
            return

        now = datetime.now()
        self._prune_cron_fired(now)

        for server in self.config.servers:
            if not is_planned_restart_enabled(server):
                continue

            if self.server_mgr.is_locked(server):
                self._log(
                    f"Planned restart stage skipped for {server['id']}: SERVER_LOCK active",
                    "WARN",
                )
                continue

            planned = normalize_planned_restart(server.get('planned_restart'))
            interval = int(planned['interval_minutes'])
            server_id = server['id']
            minutes_until = minutes_until_next_restart(interval, now)

            for stage in applicable_warning_stages(interval):
                if minutes_until == stage:
                    await self._run_planned_stage(server, stage, now)

            if LOCK_KICK_STAGE < interval and minutes_until == LOCK_KICK_STAGE:
                await self._run_planned_stage(server, LOCK_KICK_STAGE, now)

            if minutes_until == RESTART_STAGE:
                await self._run_planned_stage(server, RESTART_STAGE, now)

        await self._cron_restart_job()

    async def _run_planned_stage(self, server: dict, stage: int, now: datetime):
        server_id = server['id']
        if not self._mark_stage_fired(now, server_id, stage):
            return

        self._log(f"Planned restart stage T-{stage} for {server_id}", "INFO")
        loop = asyncio.get_event_loop()

        try:
            if stage == RESTART_STAGE:
                await self.execute_planned_restart(server_id)
                return

            if not self.rcon or not self.server_mgr.is_running(server):
                return

            rcon_status = await loop.run_in_executor(None, self.rcon.test_server, server)
            if not rcon_status.get('success'):
                self._log(
                    f"Planned restart T-{stage}: RCON unavailable for {server_id}",
                    "WARN",
                )
                return

            if stage == LOCK_KICK_STAGE:
                ru, en = get_stage_messages(stage)
                await loop.run_in_executor(
                    None,
                    functools.partial(self.rcon.send_bilingual_say, server, ru, en),
                )
                await asyncio.sleep(KICK_WARN_DELAY_SECONDS)
                locked = await loop.run_in_executor(None, self.rcon.lock_server, server)
                if locked:
                    self._planned_locked_servers.add(server_id)
                await loop.run_in_executor(
                    None,
                    functools.partial(self.rcon.kick_all_players, server, 'Planned restart'),
                )
                return

            ru, en = get_stage_messages(stage)
            await loop.run_in_executor(
                None,
                functools.partial(self.rcon.send_bilingual_say, server, ru, en),
            )
        except Exception as e:
            self._log(f"Planned restart stage T-{stage} failed for {server_id}: {e}", "ERROR")

    async def execute_planned_restart(self, server_id: str):
        """Выполнить рестарт сервера (T-0 планового цикла или legacy CRON)."""
        if not self.server_mgr or not self.mod_sync:
            return

        server = self.config.get_server(server_id)
        if not server:
            self._log(f"Server not found for planned restart: {server_id}", "ERROR")
            return

        if self.server_mgr.is_locked(server):
            self._log(
                f"Planned restart skipped for {server_id}: SERVER_LOCK active",
                "WARN",
            )
            return

        self._log(f"Executing planned restart for {server_id}...", "INFO")
        loop = asyncio.get_event_loop()
        unlock_needed = server_id in self._planned_locked_servers

        try:
            mods_string = await loop.run_in_executor(None, self.mod_sync.sync_mods, server)
            await loop.run_in_executor(
                None,
                self.server_mgr.restart_server,
                server,
                mods_string,
            )
            self._log(f"Planned restart completed for {server_id}", "INFO")
        except Exception as e:
            self._log(f"Planned restart failed for {server_id}: {e}", "ERROR")
            if unlock_needed and self.rcon and self.server_mgr.is_running(server):
                await loop.run_in_executor(None, self.rcon.unlock_server, server)
        finally:
            self._planned_locked_servers.discard(server_id)

    async def _cron_restart_job(self):
        """Проверить restart_schedule и запустить cron_restart для due-слотов."""
        entries = self.config.get('scheduler.restart_schedule', []) or []
        if not entries:
            return

        now = datetime.now()
        slot_key = now.strftime('%Y-%m-%d %H:%M')
        today_prefix = now.strftime('%Y-%m-%d')

        for entry in entries:
            server_id = entry.get('server_id')
            if not server_id:
                continue
            if not self._schedule_entry_due(entry, now):
                continue

            fired_key = f"{today_prefix} {now.strftime('%H:%M')}:{server_id}"
            if fired_key in self._cron_fired:
                continue

            self._cron_fired.add(fired_key)
            self._log(f"Legacy CRON restart triggered for {server_id} at {slot_key}", "INFO")
            try:
                await self.execute_planned_restart(server_id)
            except Exception as e:
                self._log(f"Legacy CRON restart failed for {server_id}: {e}", "ERROR")

    async def _periodic_job(self, coro_func, interval: int, name: str):
        """Периодическое выполнение задачи"""
        self._log(f"Periodic job {name} started (every {interval}s)", "DEBUG")

        while self._running:
            try:
                await coro_func()
            except asyncio.CancelledError:
                self._log(f"Periodic job {name} cancelled", "DEBUG")
                break
            except Exception as e:
                self._log(f"Periodic job {name} error: {e}", "ERROR")

            # Спать интервал
            try:
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break

    async def _watchdog_job(self):
        """WatchDog: проверить все серверы с автоперезапуском"""
        if not self.server_mgr:
            return

        servers = self.config.servers
        for server in servers:
            try:
                # Запускать в executor чтобы не блокировать
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    self.server_mgr.check_and_auto_restart,
                    server
                )
            except Exception as e:
                self._log(f"WatchDog error for {server['id']}: {e}", "ERROR")

    async def _mod_check_job(self):
        """Проверить обновления модов для всех серверов"""
        if not self.mod_sync or not self.server_mgr or not self.rcon:
            return

        settings = self.config.get('settings', {})
        notify_minutes = settings.get('restart_notify_minutes', 5)

        servers = self.config.servers
        loop = asyncio.get_event_loop()
        status_tasks = [
            loop.run_in_executor(None, self.mod_sync.get_mod_update_status, server)
            for server in servers
        ]
        status_results = await asyncio.gather(*status_tasks, return_exceptions=True)

        status_map = {}
        server_by_id = {server['id']: server for server in servers}
        for server, result in zip(servers, status_results):
            server_id = server['id']
            if isinstance(result, Exception):
                self._log(f"Mod check error for {server_id}: {result}", "ERROR")
                continue

            status_map[server_id] = result
            self._log_mod_status(server_id, result)

        update_groups = self._build_update_groups(servers, status_map)
        for group in update_groups:
            try:
                await self._process_update_group(group, server_by_id, status_map, notify_minutes)
            except Exception as e:
                group_label = ', '.join(group['server_ids'])
                self._log(f"Shared mod update group error for {group_label}: {e}", "ERROR")

    def _log_mod_status(self, server_id: str, mod_status: dict):
        skipped_mods = mod_status.get('skipped_mods', [])
        tracked_mods = mod_status.get('tracked_mods', [])
        updated_mods = mod_status.get('updated_mods', [])

        if skipped_mods:
            skipped_names = ', '.join(
                f"{item['name']} ({item.get('reason') or 'auto-update disabled'})"
                for item in skipped_mods
            )
            self._log(f"Mods without auto-update for {server_id}: {skipped_names}", "DEBUG")

        if not tracked_mods:
            self._log(f"No trackable mods resolved from mod_list for {server_id}", "DEBUG")
            return

        if not updated_mods:
            self._log(f"No mod updates for {server_id}", "DEBUG")

    def _build_update_groups(self, servers: list, status_map: dict) -> list:
        server_order = {server['id']: index for index, server in enumerate(servers)}
        updated_server_ids = []
        mod_to_server_ids = {}

        for server in servers:
            server_id = server['id']
            mod_status = status_map.get(server_id) or {}
            updates = mod_status.get('updated_entries', [])
            if not updates:
                continue

            updated_server_ids.append(server_id)
            for mod in updates:
                mod_id = str(mod.get('id', '')).strip()
                if not mod_id:
                    continue
                mod_to_server_ids.setdefault(mod_id, set()).add(server_id)

        if not updated_server_ids:
            return []

        adjacency = {server_id: set() for server_id in updated_server_ids}
        for server_ids in mod_to_server_ids.values():
            for server_id in server_ids:
                adjacency[server_id].update(other_id for other_id in server_ids if other_id != server_id)

        groups = []
        visited = set()
        for server_id in updated_server_ids:
            if server_id in visited:
                continue

            stack = [server_id]
            component = []
            while stack:
                current_id = stack.pop()
                if current_id in visited:
                    continue
                visited.add(current_id)
                component.append(current_id)
                stack.extend(sorted(adjacency.get(current_id, ())))

            component.sort(key=lambda item: server_order.get(item, 0))
            component_mods = {}
            server_mod_ids = {}

            for component_server_id in component:
                updates = (status_map.get(component_server_id) or {}).get('updated_entries', [])
                server_mod_ids[component_server_id] = set()
                for mod in updates:
                    mod_id = str(mod.get('id', '')).strip()
                    if not mod_id:
                        continue
                    component_mods[mod_id] = mod.get('name') or mod_id
                    server_mod_ids[component_server_id].add(mod_id)

            groups.append({
                'server_ids': component,
                'mods': component_mods,
                'server_mod_ids': server_mod_ids,
            })

        return groups

    async def _process_update_group(self, group: dict, server_by_id: dict, status_map: dict, notify_minutes: int):
        from src.core.hooks import Hooks
        from src.core.steamcmd import SteamCMD

        loop = asyncio.get_event_loop()
        servers = [server_by_id[server_id] for server_id in group['server_ids']]
        group_label = ', '.join(group['server_ids'])
        mod_names = [group['mods'][mod_id] for mod_id in sorted(group['mods'])]

        if len(servers) > 1:
            self._log(
                f"Shared mod updates found for {group_label}: {', '.join(mod_names)}",
                "WARN"
            )
        else:
            self._log(
                f"Mod updates found for {group_label}: {', '.join(mod_names)}",
                "WARN"
            )

        steamcmd = SteamCMD(self.config, self.logger)
        if not steamcmd.is_installed():
            self._log(f"SteamCMD not installed, skipping mod check for {group_label}", "WARN")
            return

        update_locks = [Path(server['path']) / "SERVER_LOCK" for server in servers]
        for update_lock in update_locks:
            update_lock.touch()

        try:
            server_was_running = {}
            rcon_available = {}
            any_notified = False
            any_running = False

            for server in servers:
                server_id = server['id']
                was_running = await loop.run_in_executor(
                    None,
                    self.server_mgr.is_running,
                    server
                )
                server_was_running[server_id] = was_running

                if not was_running:
                    self._log(
                        f"Server {server_id} is offline, it will stay offline after shared mod update",
                        "INFO"
                    )
                    continue

                any_running = True
                rcon_status = await loop.run_in_executor(
                    None,
                    self.rcon.test_server,
                    server
                )
                rcon_available[server_id] = bool(rcon_status.get('success'))

                if not rcon_available[server_id]:
                    self._log(
                        f"RCON unavailable for {server_id}, using force-stop path: {rcon_status.get('message', 'unknown error')}",
                        "WARN"
                    )
                    continue

                server_mod_names = [
                    entry.get('name', '')
                    for entry in (status_map.get(server_id) or {}).get('updated_entries', [])
                ]
                notified = await loop.run_in_executor(
                    None,
                    functools.partial(
                        self.rcon.notify_restart,
                        server,
                        notify_minutes,
                        server_mod_names,
                    )
                )
                if notified:
                    any_notified = True
                else:
                    rcon_available[server_id] = False
                    self._log(
                        f"RCON notify failed for {server_id}, using force-stop path without wait",
                        "WARN"
                    )

            if any_running and any_notified:
                self._log(
                    f"Waiting {notify_minutes} minutes before shared restart for {group_label}...",
                    "INFO"
                )
                await asyncio.sleep(notify_minutes * 60)

            for server in servers:
                server_id = server['id']
                if not server_was_running.get(server_id):
                    continue

                stop_ok = await loop.run_in_executor(
                    None,
                    self.server_mgr.stop_server,
                    server,
                    not rcon_available.get(server_id, False)
                )
                if not stop_ok:
                    self._log(
                        f"Controlled stop failed for {server_id}, forcing stop before shared mod download",
                        "WARN"
                    )
                    await loop.run_in_executor(
                        None,
                        self.server_mgr.stop_server,
                        server,
                        True
                    )
                await asyncio.sleep(5)

            for server in servers:
                server_id = server['id']
                if not server_was_running.get(server_id):
                    continue

                still_running = await loop.run_in_executor(
                    None,
                    self.server_mgr.is_running,
                    server
                )
                if still_running:
                    self._log(
                        f"Server {server_id} is still running, forcing stop before shared mod download",
                        "WARN"
                    )
                    await loop.run_in_executor(
                        None,
                        self.server_mgr.stop_server,
                        server,
                        True
                    )
                    await asyncio.sleep(5)

                still_running = await loop.run_in_executor(
                    None,
                    self.server_mgr.is_running,
                    server
                )
                if still_running:
                    self._log(
                        f"Server {server_id} is still running. Abort shared mod download to avoid file lock.",
                        "ERROR"
                    )
                    return

            self._log(
                f"Downloading updated mods for {group_label} via SteamCMD...",
                "INFO"
            )
            failed_downloads = []
            for mod_id, mod_name in group['mods'].items():
                success = await loop.run_in_executor(
                    None,
                    steamcmd.download_mod,
                    mod_id,
                    mod_name
                )
                if success:
                    for server_id in group['server_ids']:
                        if mod_id in group['server_mod_ids'].get(server_id, set()):
                            await loop.run_in_executor(
                                None,
                                steamcmd.mark_mod_version_synced,
                                server_id,
                                mod_id
                            )
                else:
                    failed_downloads.append(mod_name or mod_id)

            if failed_downloads:
                self._log(
                    f"Failed to download updated mods for {group_label}: {', '.join(failed_downloads)}",
                    "ERROR"
                )
                for update_lock in update_locks:
                    if update_lock.exists():
                        update_lock.unlink()

                for server in servers:
                    server_id = server['id']
                    if not server_was_running.get(server_id):
                        continue

                    mods_string = await loop.run_in_executor(
                        None,
                        self.mod_sync.sync_mods,
                        server
                    )
                    await loop.run_in_executor(
                        None,
                        self.server_mgr.start_server,
                        server,
                        mods_string
                    )
                    self._log(
                        f"Server {server_id} restored after failed mod update",
                        "WARN"
                    )
                return

            hooks = Hooks(self.config, self.logger)
            mods_by_server = {}
            for server in servers:
                await loop.run_in_executor(
                    None,
                    hooks.execute_hook,
                    server,
                    'afterStop'
                )
                mods_by_server[server['id']] = await loop.run_in_executor(
                    None,
                    self.mod_sync.sync_mods,
                    server
                )
                await loop.run_in_executor(
                    None,
                    hooks.execute_hook,
                    server,
                    'beforeStart'
                )

            for server in servers:
                server_id = server['id']
                if server_was_running.get(server_id):
                    await loop.run_in_executor(
                        None,
                        self.server_mgr.start_server_lock_held,
                        server,
                        mods_by_server[server_id]
                    )
                    self._log(f"Server {server_id} restarted with updated mods", "INFO")
                else:
                    self._log(f"Mods updated for offline server {server_id}", "INFO")
        finally:
            for update_lock in update_locks:
                if update_lock.exists():
                    update_lock.unlink()

    async def _log_clean_job(self):
        """Очистить старые логи"""
        if not self.logger:
            return

        days = self.config.get('settings.log_retention_days', 2)
        self.logger.clean_old_logs(days)
        self._log(f"Log cleanup completed (older than {days} days)", "INFO")

    async def cron_restart(self, server_id: str):
        """Перезапуск сервера по запросу (legacy alias)."""
        await self.execute_planned_restart(server_id)
