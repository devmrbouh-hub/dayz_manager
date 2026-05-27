# Как устроен DayZ Manager

## Общая схема

```
DayZManager.exe (или python src/main.py)
├── FastAPI (web + REST + WebSocket)
├── ServerManager — start/stop/restart, PID, SERVER_LOCK
├── ServerRptWatcher — tail RPT, startup_phase, WS /ws/servers/{id}/logs
├── Scheduler (asyncio loop, не APScheduler)
│   ├── WatchDog
│   ├── ModCheck
│   ├── LogClean
│   ├── PlannedRestart (planned_restart + legacy restart_schedule)
│   └── CRON restart (restart_schedule)
├── ModSync — mod_list.txt → junction → Workshop ID
├── SteamCMD — загрузка обновлений
└── RCON — say, shutdown
```

## WatchDog

Интервал: `settings.watchdog_interval` (по умолчанию 10 с).

Для каждого сервера с `auto_restart: true`:

1. Проверить `SERVER_LOCK` — если есть, пропуск (идёт рестарт или mod-update).
2. `is_running`: PID-файл + проверка процесса по имени/exe; при ручном запуске DayZ PID может восстановиться.
3. Если процесс мёртв → `afterStop` → `prepare_server_for_start` → `beforeStart` → `start_server`.
4. Если жив → обновить PID-файл.

Файл `.stopped` в папке сервера блокирует автозапуск, пока админ явно не нажмёт Start (или пока старт не снимет флаг при ошибке).

## SERVER_LOCK

Файл `SERVER_LOCK` в каталоге сервера (`servers[].path`).

| Событие | Lock |
|---------|------|
| Начало restart / mod-update / prepare | Создаётся |
| Успешный start | Снимается после подтверждения running (`settings.start_confirm_timeout`, по умолчанию 90 с) |
| Mod-update группы | Держится до всех `start_server` в группе |
| WatchDog | Не трогает сервер с lock |

При зависшем lock после сбоя: удалить `SERVER_LOCK` вручную, когда убедились, что DayZ не запускается и нет активного SteamCMD.

## Запуск сервера

```
POST /api/servers/{id}/start
  → acquire_lock
  → prepare_server_for_start (sync mods, optional SteamCMD download)
  → beforeStart hooks
  → spawn DayZServer_x64.exe
  → wait_until_running (timeout start_confirm_timeout)
  → release_lock
```

При неудачном старте `.stopped` снимается, чтобы WatchDog мог повторить попытку.

## Обновление модов

**Источник активных модов:** `mod_list.txt` в папке сервера.

**Workshop ID:** цепочка junction  
`server\@Mod` → `!Workshop\@Mod` → `steamapps\workshop\content\221100\<ID>`.  
Только **цифровые** ID участвуют в автообновлении; иначе мод в launch, но без SteamCMD update.

**ModCheck** (интервал `scheduler.mod_check_interval`):

1. Сравнить `time_updated` через Steam Web API (`data/mod_versions.json`).
2. При обновлениях: RCON-предупреждение → shutdown (или force-stop) → SteamCMD download → junction/keys → перезапуск, если сервер был online.

**ModSync:** junction `server\@Mod` → `!Workshop\@Mod`, копирование `.bikey` в `keys/`.

## Planned restart (рекомендуемый способ)

Настройка: `servers[].planned_restart` или блок **Restart** на карточке сервера в Web UI.

Планировщик проверяет слоты **каждые 60 с** (`_planned_restart_job`).

| Поле | Описание |
|------|----------|
| `enabled` | Включить плановый рестарт |
| `interval_minutes` | Интервал от 00:00 (240 = каждые 4 ч) |
| `test_mode` | Короткий интервал 10–59 мин для тестов |

**Слоты:** от полуночи — 00:00, +interval, +interval …  
**Next restart:** API и UI показывают `next_restart_at` (ISO datetime).

**Этапы** (если этап меньше интервала — пропускается, напр. при 15 мин нет T-30/T-15):

| Этап | Действие |
|------|----------|
| T-30, T-15, T-10 | RCON say RU, затем EN |
| T-5 | say RU+EN → пауза 5 с → `#lock` → kick всех онлайн |
| T-0 | `execute_planned_restart` (stop → prepare → start) |

При `SERVER_LOCK` или недоступном RCON этап пропускается с записью в лог.  
**Auto restart** (WatchDog) и **Planned restart** работают независимо.

## CRON-рестарты (legacy)

`scheduler.restart_schedule` — проверка **каждые 60 с**.

```json
{
  "server_id": "banov",
  "time": "04:00",
  "days": ["mon", "tue", "wed", "thu", "fri"]
}
```

- `time` — локальное `HH:MM`.
- `days` — `mon`…`sun` или `0`…`6` (`0` = понедельник). Пусто = каждый день.
- Альтернатива: поле `cron` — 5 полей `минута час * * *`.

Перед рестартом: RCON `say` за `settings.restart_notify_minutes` (по умолчанию 5), затем `restart_server`.  
Для новых установок предпочтительнее **planned_restart** — см. выше.

## RPT tail и READY

Модуль `ServerRptWatcher` — один фоновый поток на сервер, читает `{path}/{profiles}/DayZServer_x64_*.RPT`.

| Фаза | Условие |
|------|---------|
| `stopped` | Процесса нет |
| `starting` | PID есть, маркер READY ещё не встречен в сессии |
| `ready` | В RPT появилась `startup_ready_marker` (по умолчанию `[IdleMode] Entering IN - save processed`) |

- `running` (PID) и `ready` — разные вещи: PID появляется за секунды, READY — через ~30–60 с на Banov.
- Повторный `Entering IN` после `Leaving OUT` не сбрасывает фазу.
- **Lazy attach:** DayZ уже запущен (ручной старт / рестарт менеджера) — подхват последнего RPT при `GET /api/servers`.
- Консоль: `hide_console: true` → `CREATE_NO_WINDOW` + `SW_HIDE` (Windows); старт только через менеджер.
- Live stats: FPS из RPT tail; игроки — RCON `players` каждые ~5 с; чат — Expansion ExpLog tail.

## Web UI

`http://127.0.0.1:8000` — ввести API key в шапке.

| Элемент | Назначение |
|---------|------------|
| Карточка сервера | Start / Stop / Restart; статус STOPPED / STARTING / READY |
| **Server log (RPT)** | Live tail по WS, append строк; `syncServers` не пересоздаёт карточку |
| Блок **Restart** | Auto restart, Planned restart, интервал, Save, Next restart |
| Add Server | ID, имя, path, port, RCON — без настроек рестарта |
| Live Logs | Логи **менеджера** (не DayZ) |

После обновления UI: **Ctrl+F5** (кэш `app.js`, сейчас `?v=6`).

Карточки серверов синхронизируются через `syncServers()`: новые — `createServerCard`, существующие — `updateServerCard` (статус, PID, warning). Блок лога и `<pre>` при poll и WS-сообщениях `s`/`r` не пересоздаются.

**Автотесты:** `python -m pytest tests/ -v` из каталога `dayz_manager` — см. [TESTING.md](TESTING.md).

## Хуки

| Хук | Когда |
|-----|--------|
| `beforeStart` | Перед spawn процесса |
| `afterStop` | После остановки |

В EXE базовый каталог для путей хуков — рядом с `DayZManager.exe` (`sys.executable`).

Пример: `hooks/before_start.py` → функция `run(server_config)`.

## Discord

Модуль `src/notifications/discord_bot.py` есть, в `main.py` **не подключён** — автоматических уведомлений нет.

## Данные на диске

| Путь | Назначение |
|------|------------|
| `data/mod_versions.json` | Кэш версий Workshop |
| `data/mod_hashes.json` | Legacy/вспомогательный кэш |
| `logs/manager.log` | Лог менеджера |
| `{server}/server.pid` | PID процесса |
| `{server}/.stopped` | Запрет автозапуска |
| `{server}/SERVER_LOCK` | Блокировка гонок |
