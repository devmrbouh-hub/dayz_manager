# Конфигурация

**Languages:** [English](../CONFIG.md) · [Русский](CONFIG.md)


Файл: `config/config.json` (локально, **не в git** — см. `.gitignore`).  
Шаблоны: `config/config-host-template.json`, `config/config-host-nru90-template.json`.

Текущая модель развёртывания: **локальный host manager / будущий host agent**. Встроенный UI/API стоит держать на доверенном хосте или в приватной админ-сети; публичный доступ из интернета этим репозиторием не поддерживается.

## Переменные окружения Steam

Не храните пароль в репозитории. Поддерживаются:

- `DAYZ_STEAM_USERNAME`
- `DAYZ_STEAM_PASSWORD`
- `DAYZ_STEAM_GUARD_CODE`

Если `steam.username` / `steam.password` пустые, менеджер читает env.

## Пример структуры

```json
{
  "steam": {
    "username": "",
    "password": "",
    "guard_code": null,
    "auth_mode": "credentials",
    "steamcmd_path": "C:\\steamcmd\\steamcmd.exe",
    "workshop_path": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\DayZ\\!Workshop"
  },
  "servers": [
    {
      "id": "server1",
      "name": "My DayZ Server",
      "path": "D:\\Servers\\MyServer",
      "exe": "DayZServer_x64.exe",
      "port": 2302,
      "query_port": 2303,
      "rcon_port": 2305,
      "rcon_password": "***",
      "config_file": "serverDZ.cfg",
      "profiles": "Instance_1",
      "mods_file": "mod_list.txt",
      "mods": [],
      "server_mods": "",
      "launch_args": ["-noupdate", "-netlog"],
      "auto_restart": true,
      "planned_restart": {
        "enabled": false,
        "interval_minutes": 240,
        "test_mode": false
      },
      "hooks": {
        "beforeStart": ["hooks/before_start.py"],
        "afterStop": []
      }
    }
  ],
  "scheduler": {
    "mod_check_interval": 600,
    "log_clean_interval": 86400,
    "restart_schedule": []
  },
  "auth": {
    "api_key": "change_this_api_key",
    "users": []
  },
  "web": { "host": "0.0.0.0", "port": 8000 },
  "settings": {
    "watchdog_interval": 10,
    "restart_notify_minutes": 5,
    "log_retention_days": 2,
    "start_confirm_timeout": 90
  }
}
```

## Поля

| Раздел | Поле | Описание | Обязательно |
|--------|------|----------|-------------|
| **steam** | steamcmd_path | Путь к `steamcmd.exe` | ✅ |
| | workshop_path | Корень Workshop content | ✅ |
| | auth_mode | `credentials` или `session` | ❌ |
| | username/password | Или через env | ❌ |
| **servers** | id | Уникальный ID | ✅ |
| | path | Папка dedicated server | ✅ |
| | port, query_port | Игровые порты | ✅ |
| | rcon_port, rcon_password | BattlEye RCON | ✅ |
| | profiles | Напр. `Instance_1` | ✅ |
| | mods_file | Список модов | ❌ (`mod_list.txt`) |
| | mods | Legacy `{name,id}` fallback | ❌ |
| | auto_restart | WatchDog | ❌ (false) |
| | hide_console | Скрыть окно консоли DayZ (Windows) | ❌ (true) |
| | chat_history_hours | История чата в памяти, ч | ❌ (24) |
| | chat_buffer_max | Макс. сообщений чата в буфере | ❌ (5000) |
| | startup_ready_marker | Строка READY в RPT | ❌ (IdleMode IN) |
| | planned_restart | Плановый рестарт по интервалу от 00:00 | ❌ |
| | launch_args | Без `-BEpath` при profiles | ❌ |
| **scheduler** | mod_check_interval | Сек между проверками модов | ❌ (600) |
| | log_clean_interval | Очистка логов | ❌ (86400) |
| | restart_schedule | CRON-рестарты | ❌ |
| **auth** | api_key | Заголовок `X-API-Key` для локальных админ-операций | ✅ |
| | users | Задел под UI-login; REST только api_key | ❌ |
| **settings** | watchdog_interval | WatchDog, сек | ❌ (10) |
| | restart_notify_minutes | Предупреждение перед CRON | ❌ (5) |
| | log_retention_days | Хранение логов | ❌ (2) |
| | start_confirm_timeout | PID жив после start, сек | ❌ (90) |
| | startup_ready_timeout_sec | WARN если нет READY в RPT | ❌ (180) |
| | rpt_tail_buffer_lines | Буфер строк RPT в памяти | ❌ (500) |
| | rpt_poll_interval_ms | Интервал опроса tail | ❌ (200) |
| | live_stats_interval_sec | RCON poll игроков для карточки | ❌ (5) |
| | chat_poll_interval_ms | Интервал tail ExpLog | ❌ (500) |

## Старт сервера и READY

| Поле | Описание |
|------|----------|
| `hide_console` | `true` — без отдельного окна `DayZServer_x64.exe` (Windows: `CREATE_NO_WINDOW` + `SW_HIDE`) |
| `startup_ready_marker` | Подстрока в `.RPT` для фазы **READY** (по умолчанию `[IdleMode] Entering IN - save processed`) |

**Live stats на карточке:** FPS из RPT; игроки и `maxPlayers` из RCON + `serverDZ.cfg`. Метрики **не** отправляются в in-game чат.

**Игровой чат:** tail `{path}/{profiles}/ExpansionMod/Logs/ExpLog_*.log` (Expansion, `"Chat": 1` в LogsSettings). Админ пишет только через `POST /chat/say` (ручной текст).

**Фазы в API/UI:** `stopped` → `starting` (PID есть) → `ready` (маркер найден в текущей сессии).

| Поле ответа | Значение |
|-------------|----------|
| `startup_phase` | `stopped` \| `starting` \| `ready` |
| `startup_warning` | `rpt_not_found` \| `ready_timeout` \| null |
| `ready_at` | ISO время первого READY |
| `current_rpt` | Имя файла `DayZServer_x64_*.RPT` |
| `server_fps` | int \| null |
| `player_count`, `max_players`, `players` | Онлайн / слоты / `[{id,name}]` |

Логи сервера: tail `{path}/{profiles}/DayZServer_x64_*.RPT`, WebSocket `/ws/servers/{id}/logs`.

Cleanup failed-start: если процесс сервера успел стартовать, но не дошёл до подтверждённого `running`, менеджер завершает этот процесс, очищает `server.pid` и закрывает временные watcher-сессии перед возвратом ошибки.

## planned_restart

Плановый рестарт сервера по интервалу от полуночи (00:00). Настраивается на карточке сервера (блок **Restart**) или через `PUT /api/servers/{id}`.

```json
"planned_restart": {
  "enabled": true,
  "interval_minutes": 240,
  "test_mode": false
}
```

| Поле | Описание |
|------|----------|
| enabled | Включить плановый рестарт |
| interval_minutes | Интервал в минутах (240 = каждые 4 ч: 00:00, 04:00, 08:00 …) |
| test_mode | Разрешить короткий интервал 10–59 мин для тестов |

**Этапы (RCON):** T-30, T-15, T-10 — say RU+EN; T-5 — say RU+EN, пауза 5 с, `#lock`, kick всех; T-0 — restart.

В обычном режиме `interval_minutes` — 60–1440; в `test_mode` — 10–59.

### Web UI

На карточке сервера (секция **Servers**), блок **Restart**:

| Элемент | Поле конфига |
|---------|--------------|
| Auto restart | `auto_restart` (сохраняется сразу при toggle) |
| Planned restart | `planned_restart.enabled` |
| Interval / Custom / Test mode | `interval_minutes`, `test_mode` |
| Save planned restart | `PUT /api/servers/{id}` |
| Next: … | `next_restart_at` из API |

Модалка **Add Server** не содержит настроек рестарта; новый сервер получает дефолты (`planned_restart` выключен, 240 мин).

## restart_schedule (legacy)

Проверка каждые 60 с. Формат записи:

```json
{
  "server_id": "server1",
  "time": "04:00",
  "days": ["mon", "tue", "wed", "thu", "fri"]
}
```

Альтернатива: `"cron": "0 4 * * *"` (5 полей).

## mod_list.txt

Главный список модов для launch и ModCheck. Workshop ID определяется по junction; без ID мод запускается, но **не** обновляется через SteamCMD.

## RCON (опционально в конфиге)

Глобально: `rcon.client_path` — путь к `bercon.exe` / `bercon-cli.exe`.  
На сервер: блок `servers[].rcon` с `enabled`, `host`, `port`, `password`, `mode` (`preferred` | `required`), `timeout`.

Для production на одном хосте с DayZ предпочтителен `127.0.0.1`.

## Hooks

`servers[].hooks.beforeStart` / `afterStop` запускают Python-файлы из директории установки. Считайте hooks доверенным выполнением кода. В EXE-режиме пути считаются относительно каталога с `DayZManager.exe`; пути вне базовой директории пропускаются.

## Hot-reload настроек

`PUT /api/settings` с `mod_check_interval` обновляет `scheduler.mod_check_interval` и перезапускает задачу ModCheck без рестарта менеджера. См. [API.md](API.md).

Для runtime-обновлений менеджер валидирует числовые настройки и отклоняет некорректные диапазоны до записи в `config.json` (например нулевой watchdog или слишком маленький mod-check interval).

## Предупреждение портов

При старте менеджер сравнивает `port` / `query_port` с `serverDZ.cfg` и пишет warning при расхождении.

## Файлы данных

Кэши Workshop/hash лежат в `data/`. В frozen EXE-сборке эти файлы находятся рядом с `DayZManager.exe` во внешней директории установки, а не внутри временного PyInstaller bundle.

- **`data/mod_versions.json`** — кэш `time_updated` Workshop. Ключи **`w:{workshop_id}`** (общий для всех `servers[]` на хосте). При загрузке legacy `server_id:mod_id` сливаются в `w:` (максимальный timestamp на mod id). Не коммитить в git; править вручную только если понимаете логику ModCheck.
- **`data/mod_hashes.json`** — вспомогательный/legacy кэш хэшей (не используется для решений ModCheck).
