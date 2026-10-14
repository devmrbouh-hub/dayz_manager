"""Планировщик задач на чистом asyncio (без APScheduler)"""

import asyncio
import functools
from datetime import datetime, timedelta
from typing import Optional, Set

from src.core.planned_restart import (
    KICK_WARN_DELAY_SECONDS,
    LOCK_KICK_STAGE,
    RESTART_STAGE,
    applicable_warning_stages,
    get_stage_messages,
    in_kick_window,
    is_planned_restart_enabled,
    minutes_until_next_restart,
    normalize_planned_restart,
    restart_slot_key,
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
        self._planned_kick_state: dict = {}
        # Долг слота T-0, если в его минуту сервер был занят. Не путать с окном кика.
        self._owed_planned: dict = {}
        # Групповое обновление модов: время рестарта не зависит от say.
        self._mod_groups: list = []

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
            planned = normalize_planned_restart(server.get('planned_restart'))
            interval = int(planned['interval_minutes'])
            if minutes_until_next_restart(interval, now) != RESTART_STAGE:
                continue
            slot_key = restart_slot_key(interval, now)
            if slot_key:
                self._owed_planned[server['id']] = slot_key

        # Модовый рестарт в этот же тик закрывает долг T-0, чтобы не рестартовать дважды.
        await self._service_mod_restarts()

        for server in self.config.servers:
            if not is_planned_restart_enabled(server):
                continue

            planned = normalize_planned_restart(server.get('planned_restart'))
            interval = int(planned['interval_minutes'])
            server_id = server['id']
            minutes_until = minutes_until_next_restart(interval, now)

            if self.server_mgr.is_locked(server):
                if server_id in self._owed_planned:
                    self._log(
                        f"Planned restart for {server_id} waits: SERVER_LOCK active",
                        "WARN",
                    )
                else:
                    self._log(
                        f"Planned restart stage skipped for {server_id}: SERVER_LOCK active",
                        "WARN",
                    )
                continue

            for stage in applicable_warning_stages(interval):
                if minutes_until == stage:
                    await self._run_planned_stage(server, stage, now)

            if LOCK_KICK_STAGE < interval and in_kick_window(minutes_until):
                await self._run_planned_kick_window(server, interval, minutes_until, now)

            if server_id in self._owed_planned:
                restarted = await self.execute_planned_restart(server_id)
                if restarted:
                    self._owed_planned.pop(server_id, None)

        await self._cron_restart_job()

    def _kick_state_for_slot(self, server_id: str, slot_key: Optional[str]) -> dict:
        if not slot_key:
            return {'slot': None, 'say_done': False, 'kick_done': False}
        state = self._planned_kick_state.get(server_id)
        if not state or state.get('slot') != slot_key:
            state = {'slot': slot_key, 'say_done': False, 'kick_done': False}
            self._planned_kick_state[server_id] = state
        return state

    async def _run_planned_kick_window(
        self,
        server: dict,
        interval: int,
        minutes_until: int,
        now: datetime,
    ):
        server_id = server['id']
        slot_key = restart_slot_key(interval, now)
        state = self._kick_state_for_slot(server_id, slot_key)
        if state.get('kick_done'):
            return

        loop = asyncio.get_event_loop()
        if not self.rcon or not self.server_mgr.is_running(server):
            return

        rcon_status = await loop.run_in_executor(None, self.rcon.test_server, server)
        if not rcon_status.get('success'):
            self._log(
                f"Planned kick window ({minutes_until} min): RCON unavailable for {server_id}",
                "WARN",
            )
            return

        try:
            if not state.get('say_done'):
                self._log(
                    f"Planned restart kick window for {server_id} ({minutes_until} min to restart)",
                    "INFO",
                )
                ru, en = get_stage_messages(LOCK_KICK_STAGE)
                await loop.run_in_executor(
                    None,
                    functools.partial(self.rcon.send_bilingual_say, server, ru, en),
                )
                await asyncio.sleep(KICK_WARN_DELAY_SECONDS)
                state['say_done'] = True

            locked = await loop.run_in_executor(None, self.rcon.lock_server, server)
            if locked:
                self._planned_locked_servers.add(server_id)

            kicked, total = await loop.run_in_executor(
                None,
                functools.partial(self.rcon.kick_all_players, server, 'Planned restart'),
            )
            if total < 0:
                return
            if total == 0 or kicked == total:
                state['kick_done'] = True
            else:
                self._log(
                    f"Planned kick incomplete for {server_id}: {kicked}/{total}, will retry",
                    "WARN",
                )
        except Exception as e:
            self._log(f"Planned kick window failed for {server_id}: {e}", "ERROR")

    async def _run_planned_stage(self, server: dict, stage: int, now: datetime):
        server_id = server['id']
        loop = asyncio.get_event_loop()

        try:
            if stage == RESTART_STAGE:
                # T-0 идёт через _owed_planned, отметка только после успешного рестарта.
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

            if not self._mark_stage_fired(now, server_id, stage):
                return

            self._log(f"Planned restart stage T-{stage} for {server_id}", "INFO")
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

        planned = normalize_planned_restart(server.get('planned_restart'))
        if planned.get('enabled') and self.rcon and self.server_mgr.is_running(server):
            interval = int(planned['interval_minutes'])
            slot_key = restart_slot_key(interval)
            state = self._planned_kick_state.get(server_id) or {}
            if (
                slot_key
                and state.get('slot') == slot_key
                and not state.get('kick_done')
            ):
                self._log(
                    f"Planned restart T-0 safety kick for {server_id} (kick window was incomplete)",
                    "WARN",
                )
                kicked, total = await loop.run_in_executor(
                    None,
                    functools.partial(self.rcon.kick_all_players, server, 'Planned restart'),
                )
                if total >= 0 and (total == 0 or kicked == total):
                    state['kick_done'] = True

        restarted = False
        try:
            mods_string = await loop.run_in_executor(None, self.mod_sync.sync_mods, server)
            restarted = await loop.run_in_executor(
                None,
                self.server_mgr.restart_server,
                server,
                mods_string,
            )
            if restarted:
                self._log(f"Planned restart completed for {server_id}", "INFO")
            else:
                self._log(f"Planned restart failed for {server_id}", "ERROR")
        except Exception as e:
            self._log(f"Planned restart failed for {server_id}: {e}", "ERROR")
            restarted = False
        if not restarted and unlock_needed and self.rcon and self.server_mgr.is_running(server):
            await loop.run_in_executor(None, self.rcon.unlock_server, server)
        if restarted:
            self._planned_locked_servers.discard(server_id)
        return bool(restarted)

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

            server = self.config.get_server(server_id)
            if server and is_planned_restart_enabled(server):
                self._cron_fired.add(fired_key)
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
                await self._schedule_update_group(group, server_by_id, notify_minutes)
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

    def _clear_planned_debt(self, server_id: str):
        """Модовый stop/start уже перезапустил сервер: плановый долг этого слота не повторять."""
        if server_id in self._owed_planned:
            self._owed_planned.pop(server_id, None)
            self._log(f"Planned restart debt cleared for {server_id} after mod restart", "INFO")

    async def _schedule_update_group(self, group: dict, server_by_id: dict, notify_minutes: int):
        """Записать групповой рестарт. Паузу здесь не спать и SERVER_LOCK не держать."""
        from src.core.steamcmd import SteamCMD

        servers = [server_by_id[server_id] for server_id in group['server_ids']]
        group_label = ', '.join(group['server_ids'])
        mod_names = [group['mods'][mod_id] for mod_id in sorted(group['mods'])]
        self._log(
            f"Mod updates found for {group_label}: {', '.join(mod_names)}",
            "WARN",
        )

        steamcmd = SteamCMD(self.config, self.logger)
        if not steamcmd.is_installed():
            self._log(f"SteamCMD not installed, skipping mod check for {group_label}", "WARN")
            return

        pending_ids = set()
        for existing in self._mod_groups:
            pending_ids.update(existing['server_ids'])
        if any(server_id in pending_ids for server_id in group['server_ids']):
            self._log(f"Mod restart already scheduled for {group_label}", "INFO")
            return

        loop = asyncio.get_event_loop()
        was_running = {}
        any_running = False
        for server in servers:
            running = await loop.run_in_executor(None, self.server_mgr.is_running, server)
            was_running[server['id']] = bool(running)
            if running:
                any_running = True
            else:
                self._log(
                    f"Server {server['id']} is offline, it will stay offline after shared mod update",
                    "INFO",
                )
        if not any_running:
            return

        minutes = max(int(notify_minutes), 0)
        restart_at = datetime.now() + timedelta(minutes=minutes)
        self._mod_groups.append({
            'server_ids': list(group['server_ids']),
            'mods': dict(group['mods']),
            'server_mod_ids': {
                server_id: set(mod_ids)
                for server_id, mod_ids in group['server_mod_ids'].items()
            },
            'was_running': was_running,
            'restart_at': restart_at,
            'say_sent': False,
            'say_ok': set(),
            'notify_minutes': minutes,
        })
        self._log(
            f"Mod restart scheduled for {group_label} at {restart_at.strftime('%Y-%m-%d %H:%M')}",
            "INFO",
        )

    async def _service_mod_restarts(self):
        """Тик: say не сдвигает restart_at. В срок один stop/start под SERVER_LOCK."""
        if not self._mod_groups or not self.server_mgr:
            return

        now = datetime.now()
        server_by_id = {server['id']: server for server in self.config.servers}
        pending = []
        for group in self._mod_groups:
            if not group.get('say_sent') and now < group['restart_at']:
                if await self._say_mod_group(group, server_by_id):
                    group['say_sent'] = True
            if now >= group['restart_at']:
                done = await self._process_update_group(
                    group,
                    server_by_id,
                    {},
                    group.get('notify_minutes', 0),
                )
                if not done:
                    pending.append(group)
            else:
                pending.append(group)
        self._mod_groups = pending

    async def _say_mod_group(self, group: dict, server_by_id: dict) -> bool:
        """Предупреждение в чат. Неудача не меняет время рестарта и не включает taskkill."""
        if not self.rcon:
            return False

        say_ok = group.setdefault('say_ok', set())
        names = [group['mods'][mod_id] for mod_id in sorted(group['mods'])]
        loop = asyncio.get_event_loop()
        all_ok = True
        for server_id in group['server_ids']:
            if not group.get('was_running', {}).get(server_id):
                continue
            if server_id in say_ok:
                continue
            server = server_by_id.get(server_id)
            if not server:
                continue
            notified = await loop.run_in_executor(
                None,
                functools.partial(
                    self.rcon.notify_restart,
                    server,
                    group.get('notify_minutes', 0),
                    names,
                ),
            )
            if notified:
                say_ok.add(server_id)
            else:
                all_ok = False
                self._log(
                    f"RCON notify failed for {server_id}; mod restart time unchanged",
                    "WARN",
                )
        return all_ok

    async def _stop_for_mods(self, server: dict) -> bool:
        """Остановка ради обновления модов: режим restart, без .stopped."""
        loop = asyncio.get_event_loop()
        stop_ok = await loop.run_in_executor(
            None,
            functools.partial(self.server_mgr.stop_server, server, "restart"),
        )
        if stop_ok:
            return True
        self._log(
            f"Controlled stop failed for {server['id']}, forcing stop before shared mod download",
            "WARN",
        )
        return await loop.run_in_executor(
            None,
            functools.partial(self.server_mgr.stop_server, server, "force"),
        )

    async def _restore_stopped_servers(self, servers: list, was_running: dict, stopped_ids: set) -> None:
        loop = asyncio.get_event_loop()
        for server in servers:
            server_id = server['id']
            if server_id not in stopped_ids:
                continue
            mods_string = await loop.run_in_executor(None, self.mod_sync.sync_mods, server)
            started = await loop.run_in_executor(
                None,
                functools.partial(self.server_mgr.start_server_lock_held, server, mods_string),
            )
            if started:
                self._log(f"Server {server_id} restored after failed mod update", "WARN")
            else:
                self._log(f"Failed to restore server {server_id} after failed mod update", "ERROR")

    async def _process_update_group(self, group: dict, server_by_id: dict, status_map: dict, notify_minutes: int) -> bool:
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
            return True

        locked_servers = [server['id'] for server in servers if self.server_mgr.is_locked(server)]
        if locked_servers:
            self._log(
                f"Skipping shared mod update for {group_label}: SERVER_LOCK active on {', '.join(locked_servers)}",
                "WARN"
            )
            return False

        locked_for_update = []
        for server in servers:
            if not self.server_mgr.acquire_lock(server, reason="shared_mod_update"):
                self._log(
                    f"Skipping shared mod update for {group_label}: failed to acquire SERVER_LOCK for {server['id']}",
                    "WARN"
                )
                for locked_server in locked_for_update:
                    self.server_mgr.release_lock(locked_server)
                return False
            locked_for_update.append(server)

        try:
            recorded = group.get('was_running')
            server_was_running = {}
            for server in servers:
                server_id = server['id']
                if recorded is not None:
                    server_was_running[server_id] = bool(recorded.get(server_id))
                else:
                    server_was_running[server_id] = bool(await loop.run_in_executor(
                        None,
                        self.server_mgr.is_running,
                        server,
                    ))

            stopped_ids = set()
            abort_download = False
            for server in servers:
                server_id = server['id']
                if not server_was_running.get(server_id):
                    continue
                if await self._stop_for_mods(server):
                    still_running = await loop.run_in_executor(
                        None,
                        self.server_mgr.is_running,
                        server,
                    )
                    if still_running:
                        abort_download = True
                    else:
                        stopped_ids.add(server_id)
                else:
                    abort_download = True

            if abort_download:
                self._log(
                    f"Server group {group_label} is still running. Abort shared mod download to avoid file lock.",
                    "ERROR",
                )
                await self._restore_stopped_servers(servers, server_was_running, stopped_ids)
                return True

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
                if success and steamcmd.should_sync_mod_cache_after_download():
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
                await self._restore_stopped_servers(servers, server_was_running, stopped_ids)
                return True

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
                    started = await loop.run_in_executor(
                        None,
                        functools.partial(
                            self.server_mgr.start_server_lock_held,
                            server,
                            mods_by_server[server_id],
                        ),
                    )
                    if started:
                        self._clear_planned_debt(server_id)
                        self._log(f"Server {server_id} restarted with updated mods", "INFO")
                    else:
                        self._log(f"Server {server_id} failed to restart with updated mods", "ERROR")
                else:
                    self._log(f"Mods updated for offline server {server_id}", "INFO")
            return True
        finally:
            for locked_server in locked_for_update:
                self.server_mgr.release_lock(locked_server)

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
