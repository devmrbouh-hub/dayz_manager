# Roadmap — фаза 2 (admin UI)

Фаза 1 (стабилизация) и фаза 2 (admin UI) влиты в **`main`** — см. [CHANGELOG.md](CHANGELOG.md).  
Planned restart, live stats, чат — проверено на Banov (2026-05).

## Сделано

- **Planned restart** — интервал от 00:00, этапы T-30/15/10/5/0, RU+EN say, lock + kick на T-5
- **Web UI** — блок Restart на карточке сервера (auto + planned, Save, Next restart)
- **API** — `planned_restart`, `next_restart_at`, валидация interval / test_mode
- **RCON** — парсер bercon-cli `players`, bilingual say, lock, kick_all
- **RPT tail + READY** — `ServerRptWatcher`, фазы `startup_phase`, скрытая консоль, WS `/ws/servers/{id}/logs`, Server log на карточке
- **Live stats на карточке** — FPS из RPT, игроки X/max и список ников (RCON + `serverDZ.cfg`)
- **Игровой чат** — ExpLog tail 24 ч, WS `/ws/servers/{id}/chat`, `POST /chat/say`; wall-clock timestamps; RCON inject для broadcast
- **Server log UI** — инкрементальный DOM, append лога без моргания (`syncServers`, `app.js?v=12`)
- **Проверка модов** — Steam Web API через `certifi` на Windows

## Приоритет 1

### Расширение планировщика
- Дни недели и фиксированное время (дополнение к интервалу от 00:00)
- Несколько шаблонов расписания на сервер

### Preset-команды RCON
- `say`, `kick`, `ban`, `save`, `shutdown` из UI
- Массовые предупреждения вне planned restart

### Расширенный статус сервера
- Game-port / query-port
- RCON alive, uptime
- ~~READY по RPT~~ — сделано (`startup_phase`, маркер IdleMode)
- ~~FPS, игроки онлайн~~ — на карточке (`server_fps`, `players`, `max_players`)
- Текущая карта / preset

### Редактор конфигов в UI
- `serverDZ.cfg`, `mod_list.txt`, launch args, BattlEye

### Безопасный restart flow
- Сценарий: say → save → shutdown → проверка stop → start

## Приоритет 2

- Backup / rollback конфигов и mod_list
- Аудит действий (кто start/stop/sync)
- Health dashboard (порты, ключи, SteamCMD, конфликты)
- Pre-flight валидация перед start
- Telegram / Discord уведомления (модуль есть, не подключён)

## DayZ-специфика

- Ban list / whitelist / priority queue
- Поиск по логам сервера и BattlEye
- Профили запуска: prod / test / event
- Сравнение конфигов между серверами

## Топ-5 для следующего MVP

1. Редактор конфигов и mod_list
2. Preset RCON-команды
3. Backup / rollback
4. Аудит + уведомления
5. Health dashboard (порты, SteamCMD)

## Вне scope (обсуждалось отдельно)

- Не блокировать WatchDog при failed SteamCMD download, если sync OK
- Ожидание снятия `SERVER_LOCK` в `prepare_server_for_start`
- Пометка `mod_versions` при недоступном Steam API
