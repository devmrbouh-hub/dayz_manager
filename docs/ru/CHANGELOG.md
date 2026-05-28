# История изменений

**Languages:** [English](../) · [Русский]()


## 2026-05-25 — Admin UI в `master` (проверено на reference-хосте)

**Статус:** все сценарии ниже проверены на reference-хосте, работает.

### Live stats, чат, консоль

- **Консоль:** `hide_console` — без окна DayZ при старте из менеджера.
- **Карточка:** FPS из RPT; игроки `X/max`; раскрывающийся список **ников** (RCON `players` ~5 с).
- **Игровой чат:** только `[Chat - *]` из ExpLog + RCON broadcast (`say -1`, planned restart); история 24 ч; WS + poll; admin say из UI.
- **Время в чате:** ExpLog — wall-clock (не elapsed); inject RCON — локальное время; без рассинхрона.
- **Парсер игроков:** bercon-таблица с колонкой admin `true`/`false` — ник берётся корректно.
- **Проверка модов:** Steam Web API через `certifi` (Windows без `Common Files\SSL\cert.pem`).
- UI: `app.js?v=12`.

### Server log UI (без моргания)

- `syncServers` / `updateServerCard` — инкрементальное обновление карточек без `innerHTML = ''`.
- Лог RPT: только append по WebSocket; статус STARTING/READY обновляется точечно.
- Фильтр WEAPON — скрытие строк в DOM без перезагрузки tail.
- Статика: `app.js?v=6`, `min-height` у `.server-log-view`.

### RPT logs и READY

- `ServerRptWatcher` — tail `{profiles}/DayZServer_x64_*.RPT`, ring buffer, lazy attach.
- Статус **STARTING / READY** по маркеру `[IdleMode] Entering IN - save processed` (настраивается).
- `hide_console` — запуск без окна консоли (Windows).
- WebSocket `/ws/servers/{id}/logs`, `GET /api/servers/{id}/logs/tail`.
- Карточка сервера: **Server log (RPT)**, фильтр WEAPON, poll до READY.

### Planned restart

- Рестарт по интервалу от полуночи (00:00): слоты 00:00, 04:00, 08:00 … при `interval_minutes: 240`.
- Этапы RCON: T-30 / T-15 / T-10 — say RU+EN; T-5 — say → пауза 5 с → `#lock` → kick всех; T-0 — restart.
- Поле `servers[].planned_restart`: `{ enabled, interval_minutes, test_mode }`; test mode — интервал 10–59 мин.
- API: `GET/PUT /api/servers/{id}` возвращает `planned_restart` и `next_restart_at`.
- Парсер bercon-cli: табличный вывод `players` для kick на T-5.

### Web UI

- Блок **Restart** на карточке каждого сервера: auto restart, planned restart, интервал, Save, Next restart.
- Отдельная секция Scheduled Restart удалена; модалка Add Server без полей рестарта (дефолты при POST).
- Независимость **Auto restart** (WatchDog) и **Planned restart** (планировщик).

---

## 2026-05 — Стабилизация (ветка `feature/stability`)

### SERVER_LOCK и старт

- Lock держится до подтверждения running (`settings.start_confirm_timeout`, по умолчанию 90 с).
- Единая модель lock для `prepare_server_for_start` и WatchDog.
- При mod-update lock снимается только после всех `start_server` в группе.

### PID и `.stopped`

- `is_running` проверяет имя/exe процесса, не только PID из файла.
- Восстановление PID при ручном запуске DayZ.
- `.stopped` снимается при Start/Restart и при неудачном старте.

### Моды и SteamCMD

- Workshop ID: только цифровые; невалидные пропускаются.
- `+workshop_download_item` — отдельные argv SteamCMD.

### Планировщик и API

- `scheduler.restart_schedule` подключён (проверка каждые 60 с).
- `PUT /api/settings`: hot-reload `mod_check_interval`.

### Прочее

- Хуки в EXE: базовый путь рядом с `DayZManager.exe`.
- WebSocket `/ws/logs`: 503 до готовности логгера.
- Warning при расхождении `port` / `query_port` с `serverDZ.cfg`.
- Документация в `docs/`.

---

## Ранее (до стабилизации)

Кратко по архиву [archive/CHANGES_RU.md](archive/CHANGES_RU.md):

- RCON: `rcon.client_path`, per-server `servers[].rcon`, режимы `preferred` / `required`, `POST .../rcon/test`.
- `stop_server()` с учётом режима RCON.
- Синхронизация и проверка модов через `mod_list.txt` + effective mods + junction.
- SteamCMD: force-stop при mod-update, пропуск notify если сервер offline.
- API mods/check с `details` (tracked/skipped).
- Переход на `mod_list.txt` как основной источник модов.

Полный текст старых пунктов — в архивном файле.
