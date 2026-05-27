# REST API и WebSocket

Базовый URL: `http://<host>:<web.port>/` (по умолчанию `:8000`).

## Авторизация

Мутирующие запросы (**POST**, **PUT**, **DELETE**) требуют заголовок:

```
X-API-Key: <auth.api_key>
```

GET — без ключа. Роли `auth.users` в REST **не используются** (задел под будущий UI-login).

## Серверы

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/servers` | Список серверов и статус |
| GET | `/api/servers/{id}` | Один сервер |
| POST | `/api/servers/{id}/start` | Запуск |
| POST | `/api/servers/{id}/stop` | Остановка |
| POST | `/api/servers/{id}/restart` | Перезапуск |
| POST | `/api/servers/{id}/rcon/test` | Проверка RCON (`players`) |
| POST | `/api/servers` | Добавить сервер |
| PUT | `/api/servers/{id}` | Обновить сервер (в т.ч. `planned_restart`) |
| DELETE | `/api/servers/{id}` | Удалить сервер |
| GET | `/api/servers/{id}/logs/tail` | Последние N строк RPT из буфера (`lines`, max 500) |
| GET | `/api/servers/{id}/chat` | История игрового чата (`limit`, `since`) |
| POST | `/api/servers/{id}/chat/say` | Отправить текст всем игрокам (RCON `say -1`) |

Ответ `GET /api/servers` и `GET /api/servers/{id}` включает:

- `planned_restart` — `{ enabled, interval_minutes, test_mode }`
- `next_restart_at` — ISO datetime следующего слота (если enabled)
- `startup_phase` — `stopped` | `starting` | `ready`
- `ready_at`, `current_rpt`, `startup_warning` — см. [CONFIG.md](CONFIG.md)
- `server_fps` — последний FPS из RPT (`Average server FPS`, округлённо)
- `player_count`, `max_players`, `players` — онлайн через RCON poll (~5 с)
- `rcon_players_ok` — удалось ли получить список игроков
- `chat_available` — есть каталог Expansion `ExpLog`

В Web UI: блок **Restart**, статус **STARTING/READY**, **FPS / Игроки**, **Server log (RPT)**, **Игровой чат**.

## Моды

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/api/mods/check` | Проверка обновлений (+ `details` по серверам) |
| POST | `/api/mods/sync` | Синхронизация junction/keys |

## Логи и настройки

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/logs` | Последние записи лога |
| POST | `/api/logs/clean` | Очистка по `log_retention_days` |
| GET | `/api/settings` | Глобальные настройки |
| PUT | `/api/settings` | Обновление (см. hot-reload в CONFIG) |
| POST | `/api/shutdown` | Остановка процесса менеджера |

## WebSocket

| Путь | Описание |
|------|----------|
| `ws://host:port/ws/logs` | Логи менеджера в реальном времени |
| `ws://host:port/ws/servers/{id}/logs` | Лог RPT сервера (JSON-сообщения) |
| `ws://host:port/ws/servers/{id}/chat` | Игровой чат (Expansion ExpLog) |

До инициализации логгера — HTTP 503.

### WebSocket RPT (`/ws/servers/{id}/logs`)

| `t` | Поля | Описание |
|-----|------|----------|
| `s` | `phase`, `warning`, `rpt` | Статус сессии при подключении |
| `l` | `m`, `h` | Строка лога; `h=true` для READY-маркера |
| `r` | `at` | Событие перехода в READY |

При подключении сначала отправляется `s`, затем до 200 строк из буфера, затем live `l`.

### WebSocket chat (`/ws/servers/{id}/chat`)

| `t` | Поля | Описание |
|-----|------|----------|
| `c` | `ts`, `channel`, `player`, `text` | Строка чата |

При подключении replay до 200 сообщений из буфера (24 ч), затем live `c`.

## Примеры

```powershell
curl http://127.0.0.1:8000/api/servers

curl -X POST http://127.0.0.1:8000/api/servers/banov/start `
  -H "X-API-Key: YOUR_KEY"

curl -X POST http://127.0.0.1:8000/api/servers/banov/rcon/test `
  -H "X-API-Key: YOUR_KEY"

curl -X PUT http://127.0.0.1:8000/api/settings `
  -H "X-API-Key: YOUR_KEY" `
  -H "Content-Type: application/json" `
  -d "{\"mod_check_interval\": 600}"

curl -X PUT http://127.0.0.1:8000/api/servers/banov `
  -H "X-API-Key: YOUR_KEY" `
  -H "Content-Type: application/json" `
  -d "{\"planned_restart\": {\"enabled\": true, \"interval_minutes\": 240, \"test_mode\": false}}"
```

```javascript
const ws = new WebSocket('ws://127.0.0.1:8000/ws/logs');
ws.onmessage = (e) => console.log(e.data);
```

## Ответ mods/check

- `updates` — краткий список модов с обновлениями
- `details.<server_id>.effective_mods` — полный список
- `details.<server_id>.tracked_mods` / `skipped_mods` — с Workshop ID и без

## Ответ rcon/test

- `success`, `message`
- `diagnostics`: `client_path`, `host`, `port`, `timeout`, `error_type`
