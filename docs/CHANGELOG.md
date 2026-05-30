# Changelog

**Languages:** [English](CHANGELOG.md) · [Русский](ru/CHANGELOG.md)

## 2026-05-30 — Host hardening on `main`

- Static file serving now rejects traversal outside `web/` while keeping SPA fallback behavior.
- Failed DayZ start now cleans up `server.pid`, watcher sessions, and the spawned child process instead of leaving an orphan instance behind.
- Restart now aborts if stop could not be confirmed, avoiding accidental double-starts.
- Shared mod-update locks are acquired/released as owned locks, without deleting pre-existing foreign `SERVER_LOCK` files.
- Runtime validation was tightened for server/settings payloads, and frozen EXE data caches now resolve to the external install directory next to `DayZManager.exe`.
- Docs updated to describe the current host-local manager model and the future agent/cloud split more clearly.

---

## 2026-05-25 — Admin UI in `main` (verified on reference host)

**Status:** scenarios below verified on a reference deployment.

### Live stats, chat, console

- **Console:** `hide_console` — no DayZ window when starting via manager.
- **Card:** FPS from RPT; players `X/max`; expandable **nicknames** (RCON `players` ~5 s).
- **In-game chat:** only `[Chat - *]` from ExpLog + RCON broadcast (`say -1`, planned restart); 24 h history; WS + poll; admin say from UI.
- **Chat timestamps:** ExpLog wall-clock; RCON inject local time.
- **Player parser:** bercon table with admin `true`/`false` column — correct nicknames.
- **Mod check:** Steam Web API via `certifi` (Windows without `Common Files\SSL\cert.pem`).
- UI: `app.js?v=12`.

### Server log UI (no flicker)

- `syncServers` / `updateServerCard` — incremental updates without `innerHTML = ''`.
- RPT log: append only via WebSocket; STARTING/READY updated in place.
- WEAPON filter — hide lines in DOM without reloading tail.
- Static: `app.js?v=6`, `min-height` on `.server-log-view`.

### RPT logs and READY

- `ServerRptWatcher` — tail `{profiles}/DayZServer_x64_*.RPT`, ring buffer, lazy attach.
- **STARTING / READY** via `[IdleMode] Entering IN - save processed` (configurable).
- `hide_console` — start without console window (Windows).
- WebSocket `/ws/servers/{id}/logs`, `GET /api/servers/{id}/logs/tail`.
- Card: **Server log (RPT)**, WEAPON filter, poll until READY.

### Planned restart

- Restart on interval from midnight: slots 00:00, 04:00, 08:00 … at `interval_minutes: 240`.
- RCON stages: T-30/15/10 — say RU+EN; T-5 — say → 5 s pause → `#lock` → kick all; T-0 — restart.
- `servers[].planned_restart`: `{ enabled, interval_minutes, test_mode }`; test mode 10–59 min.
- API: `GET/PUT /api/servers/{id}` returns `planned_restart` and `next_restart_at`.
- bercon-cli table parser for kick at T-5.

### Web UI

- **Restart** block per server: auto restart, planned restart, interval, Save, Next restart.
- Separate Scheduled Restart section removed; Add Server modal without restart fields (defaults on POST).
- **Auto restart** (WatchDog) and **Planned restart** (scheduler) are independent.

---

## 2026-05 — Stabilization (`feature/stability`)

### SERVER_LOCK and start

- Lock held until running confirmed (`settings.start_confirm_timeout`, default 90 s).
- Unified lock model for `prepare_server_for_start` and WatchDog.
- Mod-update lock released only after all `start_server` in group.

### PID and `.stopped`

- `is_running` checks process name/exe, not only PID file.
- PID recovery on manual DayZ start.
- `.stopped` cleared on Start/Restart and failed start.

### Mods and SteamCMD

- Workshop ID: numeric only; invalid IDs skipped.
- `+workshop_download_item` — separate SteamCMD argv.

### Scheduler and API

- `scheduler.restart_schedule` wired (check every 60 s).
- `PUT /api/settings`: hot-reload `mod_check_interval`.

### Other

- Hooks in EXE: base path next to `DayZManager.exe`.
- WebSocket `/ws/logs`: 503 until logger ready.
- Warning on `port` / `query_port` mismatch with `serverDZ.cfg`.
- Documentation in `docs/`.

---

## Earlier (pre-stabilization)

Summary from [archive/CHANGES_RU.md](archive/CHANGES_RU.md) if present:

- RCON: `rcon.client_path`, per-server `servers[].rcon`, `preferred` / `required`, `POST .../rcon/test`.
- `stop_server()` respects RCON mode.
- Mod sync/check via `mod_list.txt` + effective mods + junction.
- SteamCMD: force-stop on mod-update, skip notify if server offline.
- API mods/check with `details` (tracked/skipped).
- `mod_list.txt` as primary mod source.
