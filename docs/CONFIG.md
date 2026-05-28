# Configuration

**Languages:** [English](CONFIG.md) · [Русский](ru/CONFIG.md)

File: `config/config.json` (local, **not in git** — see `.gitignore`).  
Templates: `config/config-host-template.json`, `config/config-host-nru90-template.json`.

## Steam environment variables

Do not store passwords in the repo. Supported:

- `DAYZ_STEAM_USERNAME`
- `DAYZ_STEAM_PASSWORD`
- `DAYZ_STEAM_GUARD_CODE`

If `steam.username` / `steam.password` are empty, the manager reads env vars.

## Example structure

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

## Fields

| Section | Field | Description | Required |
|---------|-------|-------------|----------|
| **steam** | steamcmd_path | Path to `steamcmd.exe` | Yes |
| | workshop_path | Workshop content root | Yes |
| | auth_mode | `credentials` or `session` | No |
| | username/password | Or via env | No |
| **servers** | id | Unique ID | Yes |
| | path | Dedicated server folder | Yes |
| | port, query_port | Game ports | Yes |
| | rcon_port, rcon_password | BattlEye RCON | Yes |
| | profiles | e.g. `Instance_1` | Yes |
| | mods_file | Mod list file | No (`mod_list.txt`) |
| | mods | Legacy `{name,id}` fallback | No |
| | auto_restart | WatchDog | No (false) |
| | hide_console | Hide DayZ console window (Windows) | No (true) |
| | chat_history_hours | In-memory chat history, hours | No (24) |
| | chat_buffer_max | Max chat messages in buffer | No (5000) |
| | startup_ready_marker | READY substring in RPT | No (IdleMode IN) |
| | planned_restart | Planned restart from 00:00 | No |
| | launch_args | No `-BEpath` when using profiles | No |
| **scheduler** | mod_check_interval | Seconds between mod checks | No (600) |
| | log_clean_interval | Log cleanup | No (86400) |
| | restart_schedule | CRON restarts | No |
| **auth** | api_key | `X-API-Key` for POST/PUT/DELETE | Yes |
| | users | Placeholder for UI login; REST uses api_key only | No |
| **settings** | watchdog_interval | WatchDog, seconds | No (10) |
| | restart_notify_minutes | Warning before CRON restart | No (5) |
| | log_retention_days | Log retention | No (2) |
| | start_confirm_timeout | PID alive after start, seconds | No (90) |
| | startup_ready_timeout_sec | WARN if no READY in RPT | No (180) |
| | rpt_tail_buffer_lines | RPT ring buffer lines | No (500) |
| | rpt_poll_interval_ms | Tail poll interval | No (200) |
| | live_stats_interval_sec | RCON player poll for card | No (5) |
| | chat_poll_interval_ms | ExpLog tail interval | No (500) |

## Server start and READY

| Field | Description |
|-------|-------------|
| `hide_console` | `true` — no separate `DayZServer_x64.exe` window (Windows: `CREATE_NO_WINDOW` + `SW_HIDE`) |
| `startup_ready_marker` | Substring in `.RPT` for **READY** phase (default `[IdleMode] Entering IN - save processed`) |

**Live stats on card:** FPS from RPT; players and `maxPlayers` from RCON + `serverDZ.cfg`. Metrics are **not** sent to in-game chat.

**In-game chat:** tail `{path}/{profiles}/ExpansionMod/Logs/ExpLog_*.log` (Expansion, `"Chat": 1` in LogsSettings). Admin text only via `POST /chat/say`.

**API/UI phases:** `stopped` → `starting` (PID exists) → `ready` (marker found in current session).

| Response field | Value |
|----------------|-------|
| `startup_phase` | `stopped` \| `starting` \| `ready` |
| `startup_warning` | `rpt_not_found` \| `ready_timeout` \| null |
| `ready_at` | ISO time of first READY |
| `current_rpt` | `DayZServer_x64_*.RPT` filename |
| `server_fps` | int \| null |
| `player_count`, `max_players`, `players` | Online / slots / `[{id,name}]` |

Server logs: tail `{path}/{profiles}/DayZServer_x64_*.RPT`, WebSocket `/ws/servers/{id}/logs`.

## planned_restart

Planned server restart on interval from midnight (00:00). Configure on server card (**Restart** block) or `PUT /api/servers/{id}`.

```json
"planned_restart": {
  "enabled": true,
  "interval_minutes": 240,
  "test_mode": false
}
```

| Field | Description |
|-------|-------------|
| enabled | Enable planned restart |
| interval_minutes | Minutes from 00:00 (240 = every 4 h: 00:00, 04:00, 08:00 …) |
| test_mode | Allow short interval 10–59 min for tests |

**Stages (RCON):** T-30, T-15, T-10 — say RU+EN; T-5 — say RU+EN, pause 5 s, `#lock`, kick all; T-0 — restart.

Normal mode: `interval_minutes` 60–1440; test mode: 10–59.

### Web UI

On server card (**Servers** section), **Restart** block:

| UI element | Config field |
|------------|--------------|
| Auto restart | `auto_restart` (saved on toggle) |
| Planned restart | `planned_restart.enabled` |
| Interval / Custom / Test mode | `interval_minutes`, `test_mode` |
| Save planned restart | `PUT /api/servers/{id}` |
| Next: … | `next_restart_at` from API |

**Add Server** modal has no restart settings; new servers get defaults (planned off, 240 min).

## restart_schedule (legacy)

Checked every 60 s. Entry format:

```json
{
  "server_id": "server1",
  "time": "04:00",
  "days": ["mon", "tue", "wed", "thu", "fri"]
}
```

Alternative: `"cron": "0 4 * * *"` (5 fields).

## mod_list.txt

Primary mod list for launch and ModCheck. Workshop ID from junction; without ID the mod launches but is **not** updated via SteamCMD.

## RCON (optional in config)

Global: `rcon.client_path` — path to `bercon.exe` / `bercon-cli.exe`.  
Per server: `servers[].rcon` with `enabled`, `host`, `port`, `password`, `mode` (`preferred` | `required`), `timeout`.

On production host with DayZ on same machine, prefer `127.0.0.1`.

## Settings hot-reload

`PUT /api/settings` with `mod_check_interval` updates `scheduler.mod_check_interval` and restarts ModCheck without restarting the manager. See [API.md](API.md).

## Port warning

On start the manager compares `port` / `query_port` with `serverDZ.cfg` and logs a warning on mismatch.
