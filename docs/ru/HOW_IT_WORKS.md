# Как устроен DayZ Manager

**Languages:** [English](../HOW_IT_WORKS.md) · [Русский](HOW_IT_WORKS.md)


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

## Trust model

Сейчас DayZ Manager рассчитан на **локальное администрирование на хосте**. Встроенный UI/API следует считать интерфейсом для доверенного хоста или приватной сети, а не публичной панелью для интернета. Hooks запускают локальные Python-файлы и по сути равны исполнению доверенного кода оператором.

## WatchDog

Интервал: `settings.watchdog_interval` (по умолчанию 10 с).

Первый опрос после старта менеджера только запоминает, запущен ли процесс. Уже остановленный сервер сам не включается. Дальше для каждого сервера с `auto_restart: true`:

1. Проверить `SERVER_LOCK` — если есть, пропуск (идёт рестарт или mod-update).
2. `is_running`: PID-файл + путь к exe в каталоге `servers[].path` (при необходимости cwd); не любой процесс DayZ на хосте. При ручном запуске из папки сервера PID может восстановиться. Несколько серверов на одной машине различаются по своему exe. Пока идёт остановка, этот PID обратно не записывается.
3. Если в этой сессии сервер уже был запущен и процесс пропал → `afterStop` → `prepare_server_for_start` → `beforeStart` → `start_server`.
4. Если жив → обновить PID-файл.

Файл `.stopped` пишут только кнопка Stop и кнопка **Выключить** в шапке менеджера. Плановый рестарт и обновление модов его не создают. Флаг блокирует автозапуск, пока Start или Restart не подтвердят запуск. Закрытие окна менеджера игровые серверы не останавливает. **Выключить** сначала останавливает планировщик, затем серверы, затем сам процесс. Второй `DayZManager.exe` выходит, если первый ещё жив (`data/manager.pid`).

## SERVER_LOCK

Файл `SERVER_LOCK` в каталоге сервера (`servers[].path`).

| Событие | Lock |
|---------|------|
| Начало restart / mod-update / prepare | Создаётся с контекстом операции |
| Успешный start | Снимается после подтверждения running (`settings.start_confirm_timeout`, по умолчанию 90 с) |
| Mod-update группы | Держится до всех `start_server` в группе |
| WatchDog | Не трогает сервер с lock |

Групповой mod-update теперь создаёт только свои lock-файлы и не удаляет уже существующие чужие lock-и. При зависшем lock после crash/power loss: удалить `SERVER_LOCK` вручную, когда убедились, что DayZ не запускается и нет активного SteamCMD.

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

Неудачный старт не снимает `.stopped`. Флаг снимается только после успешного `wait_until_running`. Если процесс успел стартовать, но не дошёл до подтверждённого `running`, менеджер завершает этот процесс, очищает `server.pid` и завершает временные watcher-сессии.

## Обновление модов

**Источник активных модов:** `mod_list.txt` в папке сервера.

**Workshop ID:** цепочка junction  
`server\@Mod` → `!Workshop\@Mod` → `steamapps\workshop\content\221100\<ID>`.  
Только **цифровые** ID участвуют в автообновлении; иначе мод в launch, но без SteamCMD update.

**ModCheck** (интервал `scheduler.mod_check_interval`):

1. Сравнить `time_updated` через Steam Web API (`data/mod_versions.json`). Ключи кэша — **`w:{workshop_id}`** (одна запись на Workshop-айтем для всех серверов на хосте, общая папка `content/221100/<id>`). Legacy `server_id:mod_id` мигрируются при загрузке (**минимальная** метка на мод).
2. Детекция сравнивает `time_updated` из API с общим кэшем (без хэшей PBO; mtime файлов не используется).
3. При обновлениях менеджер записывает время группового рестарта (`restart_notify_minutes`). `say` в чат это время не сдвигает и `taskkill` не выбирает. В срок `SERVER_LOCK` держится на остановку, одну загрузку SteamCMD и старт тех серверов, что были online. Если загрузка сорвалась, эти серверы запускаются снова, пока lock ещё держится. Успешный модовый рестарт снимает долг планового T-0, чтобы тот же слот не перезапустил сервер второй раз.
4. **Skip / fallback:** SteamCMD не вызывается, если кэш совпадает с Workshop и папка content не пуста; при сбое SteamCMD, но наличии папки — принимается локальный контент (WARN) **без** обновления кэша, чтобы ModCheck повторил загрузку.
5. Если админ обновил моды **клиентским Steam**, ModCheck может запланировать цикл, пока успешный SteamCMD не обновит кэш.

**Пути Steam:** `steam.dayz_install_path` = `…\\steamapps\\common\\DayZ` (не корень `…\\Steam`). См. [CONFIG.md](CONFIG.md). Неверный путь давал `force_install_dir: C:\\` и mismatch у игроков при «успешном» скачивании.

**ModSync:** при sync проверяется junction `!Workshop\\@Mod` → `content\\221100\\<ID>`, junction `server\\@Mod` → `!Workshop`, копирование `.bikey` в `keys/`.

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
| T-30, T-15, T-10 | RCON say RU, затем EN (отметка этапа только после успешного RCON) |
| T-5…T-3 | **Окно кика:** первый заход — say RU+EN → пауза 5 с → `#lock` → kick всех онлайн; повтор каждые 60 с, пока в окне, если RCON/список/кик не удались или кик частичный (в логе менеджера `Kicked N/M`) |
| T-0 | `execute_planned_restart` (stop → prepare → start); страховочный `kick_all`, если кик для слота не завершён |

При активном `SERVER_LOCK` весь planned job для сервера пропускается (кика в окне не будет). Сбой RCON в окне — WARN в логе и повтор на следующем тике.  
**Auto restart** (WatchDog) и **Planned restart** работают независимо.

## CRON-рестарты (legacy)

`scheduler.restart_schedule` — проверка **каждые 60 с**.

```json
{
  "server_id": "server1",
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

- `running` (PID) и `ready` — разные вещи: PID появляется за секунды, READY — через ~30–60 с на reference-хосте (дольше при тяжёлом списке модов).
- Повторный `Entering IN` после `Leaving OUT` не сбрасывает фазу.
- **Поиск RPT:** не обрывается на 30 с; на 30 с в UI может быть `rpt_not_found`, watcher ищет до `max(60, settings.startup_ready_timeout_sec)`. Поздний RPT подключается, предупреждение снимается. Fallback — newest RPT в grace window (~120 с mtime), если файл появился с задержкой.
- **Lazy attach:** DayZ уже запущен (ручной старт / рестарт менеджера) — подхват последнего RPT при `GET /api/servers`.
- Консоль: `hide_console: true` → `CREATE_NO_WINDOW` + `SW_HIDE` (Windows); старт только через менеджер.
- Live stats: FPS из RPT tail; игроки — RCON `players` каждые ~5 с (успешный опрос без строк в логе менеджера). Ответ `players` читается как cp866, cp1251 и UTF-8; берётся расшифровка с большим числом строк (при равенстве — cp866). На хосте 2026-10-14 проверено: счётчик на карточке снова совпадает с онлайном. Кнопка **Обновить список** на карточке — принудительный опрос; чат — Expansion ExpLog tail.

## Web UI

`http://127.0.0.1:8000` — ввести API key в шапке.

| Элемент | Назначение |
|---------|------------|
| Карточка сервера | Start / Stop / Restart; игровой порт; статус STOPPED / STARTING / READY. Restart идёт дальше только после подтверждённой остановки |
| Чат | Текст в игру: `POST /api/servers/{id}/chat/say` |
| **Server log (RPT)** | Live tail по WS, append строк; `syncServers` не пересоздаёт карточку |
| Блок **Restart** | Auto restart, Planned restart, интервал, Save, Next restart |
| **Игроки онлайн** | Список + кнопка обновления (POST players/refresh) |
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

В EXE базовый каталог для путей хуков — рядом с `DayZManager.exe` (`sys.executable`). Выполняются только hook-файлы внутри этого каталога установки; пути наружу пропускаются.

Пример: `hooks/before_start.py` → функция `run(server_config)`.

## Discord

Модуль `src/notifications/discord_bot.py` есть, в `main.py` **не подключён** — автоматических уведомлений нет.

## Данные на диске

| Путь | Назначение |
|------|------------|
| `data/mod_versions.json` | Кэш версий Workshop, ключи `w:{workshop_id}` (общий для всех серверов; в frozen-сборке рядом с EXE) |
| `data/mod_hashes.json` | Legacy/вспомогательный кэш (в frozen-сборке рядом с EXE) |
| `logs/manager.log` | Лог менеджера (рядом с EXE в frozen-сборке; пишется DEBUG) |
| `{server}/server.pid` | PID процесса |
| `{server}/.stopped` | Запрет автозапуска |
| `{server}/SERVER_LOCK` | Блокировка гонок |
