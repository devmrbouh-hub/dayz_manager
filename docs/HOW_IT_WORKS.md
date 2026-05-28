# How DayZ Manager works

**Languages:** [English](HOW_IT_WORKS.md) · [Русский](ru/HOW_IT_WORKS.md)

## Overview

```
DayZManager.exe (or python src/main.py)
├── FastAPI (web + REST + WebSocket)
├── ServerManager — start/stop/restart, PID, SERVER_LOCK
├── ServerRptWatcher — tail RPT, startup_phase, WS /ws/servers/{id}/logs
├── Scheduler (asyncio loop, not APScheduler)
│   ├── WatchDog
│   ├── ModCheck
│   ├── LogClean
│   ├── PlannedRestart (planned_restart + legacy restart_schedule)
│   └── CRON restart (restart_schedule)
├── ModSync — mod_list.txt → junction → Workshop ID
├── SteamCMD — download updates
└── RCON — say, shutdown
```

## WatchDog

Interval: `settings.watchdog_interval` (default 10 s).

For each server with `auto_restart: true`:

1. Check `SERVER_LOCK` — skip if present (restart or mod-update in progress).
2. `is_running`: PID file + process exe path under `servers[].path` (and cwd fallback); not any `DayZServer` on the host. Manual start from the server folder may restore PID. With multiple servers on one machine, each instance is matched by its own exe path.
3. If dead → `afterStop` → `prepare_server_for_start` → `beforeStart` → `start_server`.
4. If alive → refresh PID file.

File `.stopped` in server folder blocks auto-start until admin presses Start (or start clears flag on error).

## SERVER_LOCK

File `SERVER_LOCK` in server directory (`servers[].path`).

| Event | Lock |
|-------|------|
| Start of restart / mod-update / prepare | Created |
| Successful start | Released after running confirmed (`settings.start_confirm_timeout`, default 90 s) |
| Mod-update group | Held until all `start_server` in group |
| WatchDog | Skips server with lock |

If lock stuck after failure: delete `SERVER_LOCK` manually when sure DayZ and SteamCMD are idle.

## Starting a server

```
POST /api/servers/{id}/start
  → acquire_lock
  → prepare_server_for_start (sync mods, optional SteamCMD download)
  → beforeStart hooks
  → spawn DayZServer_x64.exe
  → wait_until_running (timeout start_confirm_timeout)
  → release_lock
```

On failed start `.stopped` is cleared so WatchDog can retry.

## Mod updates

**Active mods:** `mod_list.txt` in server folder.

**Workshop ID:** junction chain  
`server\@Mod` → `!Workshop\@Mod` → `steamapps\workshop\content\221100\<ID>`.  
Only **numeric** IDs get auto-update; otherwise mod is in launch but not updated via SteamCMD.

**ModCheck** (interval `scheduler.mod_check_interval`):

1. Compare `time_updated` via Steam Web API (`data/mod_versions.json`).
2. On updates: RCON warning → shutdown (or force-stop) → SteamCMD download → junction/keys → restart if was online.

**ModSync:** junction `server\@Mod` → `!Workshop\@Mod`, copy `.bikey` to `keys/`.

## Planned restart (recommended)

Config: `servers[].planned_restart` or **Restart** block on server card.

Scheduler checks slots **every 60 s** (`_planned_restart_job`).

| Field | Description |
|-------|-------------|
| `enabled` | Enable planned restart |
| `interval_minutes` | Interval from 00:00 (240 = every 4 h) |
| `test_mode` | Short interval 10–59 min for tests |

**Slots:** from midnight — 00:00, +interval, +interval …  
**Next restart:** API and UI show `next_restart_at` (ISO datetime).

**Stages** (skipped if smaller than interval, e.g. no T-30/T-15 at 15 min):

| Stage | Action |
|-------|--------|
| T-30, T-15, T-10 | RCON say RU, then EN |
| T-5 | say RU+EN → pause 5 s → `#lock` → kick all online |
| T-0 | `execute_planned_restart` (stop → prepare → start) |

Skipped on `SERVER_LOCK` or unavailable RCON (logged).  
**Auto restart** (WatchDog) and **Planned restart** are independent.

## CRON restarts (legacy)

`scheduler.restart_schedule` — checked **every 60 s**.

```json
{
  "server_id": "server1",
  "time": "04:00",
  "days": ["mon", "tue", "wed", "thu", "fri"]
}
```

- `time` — local `HH:MM`.
- `days` — `mon`…`sun` or `0`…`6` (`0` = Monday). Empty = every day.
- Alternative: `cron` field — 5 fields `minute hour * * *`.

Before restart: RCON `say` at `settings.restart_notify_minutes` (default 5), then `restart_server`.  
For new installs prefer **planned_restart**.

## RPT tail and READY

Module `ServerRptWatcher` — one background thread per server, reads `{path}/{profiles}/DayZServer_x64_*.RPT`.

| Phase | Condition |
|-------|-----------|
| `stopped` | No process |
| `starting` | PID exists, READY marker not seen in session |
| `ready` | `startup_ready_marker` found in RPT (default `[IdleMode] Entering IN - save processed`) |

- `running` (PID) and `ready` differ: PID in seconds, READY often ~30–60 s on a typical host.
- Repeated `Entering IN` after `Leaving OUT` does not reset phase.
- **Lazy attach:** DayZ already running — attach latest RPT on `GET /api/servers`.
- Console: `hide_console: true` → `CREATE_NO_WINDOW` + `SW_HIDE` (Windows); start only via manager.
- Live stats: FPS from RPT; players — RCON `players` every ~5 s; chat — Expansion ExpLog tail.

## Web UI

`http://127.0.0.1:8000` — enter API key in header.

| Element | Purpose |
|---------|---------|
| Server card | Start / Stop / Restart; STOPPED / STARTING / READY |
| **Server log (RPT)** | Live tail via WS, append lines; `syncServers` does not recreate card |
| **Restart** block | Auto restart, Planned restart, interval, Save, Next restart |
| Add Server | ID, name, path, port, RCON — no restart settings |
| Live Logs | **Manager** logs (not DayZ) |

After UI update: **Ctrl+F5** (cache `app.js`).

Cards sync via `syncServers()`: new — `createServerCard`, existing — `updateServerCard`. Log `<pre>` is not recreated on poll/WS.

**Tests:** `python -m pytest tests/ -v` — see [TESTING.md](TESTING.md).

## Hooks

| Hook | When |
|------|------|
| `beforeStart` | Before process spawn |
| `afterStop` | After stop |

In EXE, hook base path is next to `DayZManager.exe` (`sys.executable`).

Example: `hooks/before_start.py` → `run(server_config)`.

## Discord

Module `src/notifications/discord_bot.py` exists but is **not wired** in `main.py` — no automatic notifications.

## On-disk data

| Path | Purpose |
|------|---------|
| `data/mod_versions.json` | Workshop version cache |
| `data/mod_hashes.json` | Legacy/auxiliary cache |
| `logs/manager.log` | Manager log |
| `{server}/server.pid` | Process PID |
| `{server}/.stopped` | Block auto-start |
| `{server}/SERVER_LOCK` | Race lock |
