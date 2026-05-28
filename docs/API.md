# REST API and WebSocket

**Languages:** [English](API.md) · [Русский](ru/API.md)

Base URL: `http://<host>:<web.port>/` (default `:8000`).

## Authentication

Mutating requests (**POST**, **PUT**, **DELETE**) require header:

```
X-API-Key: <auth.api_key>
```

GET — no key. Roles in `auth.users` are **not used** in REST (reserved for future UI login).

## Servers

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/servers` | List servers and status |
| GET | `/api/servers/{id}` | One server |
| POST | `/api/servers/{id}/start` | Start |
| POST | `/api/servers/{id}/stop` | Stop |
| POST | `/api/servers/{id}/restart` | Restart |
| POST | `/api/servers/{id}/rcon/test` | RCON test (`players`) |
| POST | `/api/servers` | Add server |
| PUT | `/api/servers/{id}` | Update server (incl. `planned_restart`) |
| DELETE | `/api/servers/{id}` | Remove server |
| GET | `/api/servers/{id}/logs/tail` | Last N RPT lines from buffer (`lines`, max 500) |
| GET | `/api/servers/{id}/chat` | Chat history (`limit`, `since`) |
| POST | `/api/servers/{id}/chat/say` | Broadcast text to players (RCON `say -1`) |

`GET /api/servers` and `GET /api/servers/{id}` include:

- `planned_restart` — `{ enabled, interval_minutes, test_mode }`
- `next_restart_at` — ISO datetime of next slot (if enabled)
- `startup_phase` — `stopped` | `starting` | `ready`
- `ready_at`, `current_rpt`, `startup_warning` — see [CONFIG.md](CONFIG.md)
- `server_fps` — last FPS from RPT (`Average server FPS`, rounded)
- `player_count`, `max_players`, `players` — online via RCON poll (~5 s)
- `rcon_players_ok` — whether player list was fetched
- `chat_available` — Expansion `ExpLog` directory exists

Web UI: **Restart** block, **STARTING/READY**, **FPS / Players**, **Server log (RPT)**, **In-game chat**.

## Mods

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/mods/check` | Check updates (+ per-server `details`) |
| POST | `/api/mods/sync` | Sync junctions/keys |

## Logs and settings

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/logs` | Recent log entries |
| POST | `/api/logs/clean` | Clean by `log_retention_days` |
| GET | `/api/settings` | Global settings |
| PUT | `/api/settings` | Update (see hot-reload in CONFIG) |
| POST | `/api/shutdown` | Stop manager process |

## WebSocket

| Path | Description |
|------|-------------|
| `ws://host:port/ws/logs` | Manager logs in real time |
| `ws://host:port/ws/servers/{id}/logs` | Server RPT log (JSON messages) |
| `ws://host:port/ws/servers/{id}/chat` | In-game chat (Expansion ExpLog) |

HTTP 503 until logger is initialized.

### WebSocket RPT (`/ws/servers/{id}/logs`)

| `t` | Fields | Description |
|-----|--------|-------------|
| `s` | `phase`, `warning`, `rpt` | Session status on connect |
| `l` | `m`, `h` | Log line; `h=true` for READY marker |
| `r` | `at` | READY transition event |

On connect: `s`, then up to 200 buffered lines, then live `l`.

### WebSocket chat (`/ws/servers/{id}/chat`)

| `t` | Fields | Description |
|-----|--------|-------------|
| `c` | `ts`, `channel`, `player`, `text` | Chat line |

On connect: replay up to 200 messages (24 h), then live `c`.

## Examples

```powershell
curl http://127.0.0.1:8000/api/servers

curl -X POST http://127.0.0.1:8000/api/servers/server1/start `
  -H "X-API-Key: YOUR_KEY"

curl -X POST http://127.0.0.1:8000/api/servers/server1/rcon/test `
  -H "X-API-Key: YOUR_KEY"

curl -X PUT http://127.0.0.1:8000/api/settings `
  -H "X-API-Key: YOUR_KEY" `
  -H "Content-Type: application/json" `
  -d "{\"mod_check_interval\": 600}"

curl -X PUT http://127.0.0.1:8000/api/servers/server1 `
  -H "X-API-Key: YOUR_KEY" `
  -H "Content-Type: application/json" `
  -d "{\"planned_restart\": {\"enabled\": true, \"interval_minutes\": 240, \"test_mode\": false}}"
```

```javascript
const ws = new WebSocket('ws://127.0.0.1:8000/ws/logs');
ws.onmessage = (e) => console.log(e.data);
```

## mods/check response

- `updates` — short list of mods with updates
- `details.<server_id>.effective_mods` — full list
- `details.<server_id>.tracked_mods` / `skipped_mods` — with/without Workshop ID

## rcon/test response

- `success`, `message`
- `diagnostics`: `client_path`, `host`, `port`, `timeout`, `error_type`
