# Changelog

**Languages:** [English](CHANGELOG.md) · [Русский](ru/CHANGELOG.md)

## 2026-10-14 — Onboarding

- **README** has two ways into the same Start: a first DayZ Server folder, or an existing folder and bat file. `mod_list.txt` is that mod list. First mod download is via the client launcher into the same Steam library; ModSync on Start and SteamCMD handle linking and updates. The host template is not filled in with only a path and an API key.

---

## 2026-10-14 — Process control

- **WatchDog** restarts a server only after this manager session has seen it running. The first poll does not start a server that is already stopped. `.stopped` is written only by Stop and by manager Shutdown.
- **Shutdown** stops the scheduler, then the game servers, then the process. Closing the window leaves game servers running. A second manager process exits while the first is alive.
- **Mod updates and planned T-0** do not depend on chat `say`. A missed T-0 stays owed until it succeeds, and a successful mod restart clears that debt. RCON commands for one host:port run one at a time.

---

## 2026-10-14 — v1.0.8 Player list encoding

- **RCON `players`:** try cp866, cp1251, and UTF-8 and keep the decoding that yields the most player rows (cp866 on a tie). One WARN with a raw-byte snippet when a non-empty reply still parses to nobody.
- **Verified on the host (2026-10-14):** the server card shows the online player count again after upgrading to v1.0.8.

---

## 2026-10-11 — v1.0.7 Players refresh and planned kick window

- **Live stats:** shared `_poll_one_server`, per-server RCON lock; `POST /api/servers/{id}/players/refresh` via `asyncio.to_thread`; UI refresh button on each server card.
- **Planned restart:** kick in **3–5 min** window before slot with per-slot state and 60 s retries; say stages marked only after RCON; safety kick at T-0 if kick did not complete; `kick_all_players` returns `(kicked, total)`.

---

## 2026-10-04 — v1.0.6 Steam library paths and Workshop junction sync

- **Docs / config:** `steam.dayz_install_path` must be the **DayZ client folder** (`…\\steamapps\\common\\DayZ`), not the Steam library root; host template and CONFIG/RUNBOOK updated (fixes `force_install_dir: C:\\` and mod updates not reaching the server).
- **Steam paths:** `steam_paths.py` resolves the Steam library from `workshop_path` first; log ERROR when `force_install_dir` looks like a drive root; verify download target after SteamCMD success.
- **ModSync:** recreate `!Workshop\\@Mod` junctions to `content\\221100\\<ID>` during sync when the alias points elsewhere.
- **ModCheck:** version detection uses shared cache vs Steam API only (removed file-mtime loop that could repeat download without fixing player mismatches).

---

- Stop logging every RCON `players` poll (live stats); failures still log as WARN.
- Read bercon-cli output as **cp866** on Windows so player tables parse correctly (no `????` lines in file logs).
- Collapse repeated `.bikey` copy lines into one DEBUG summary per mod during ModSync.

---

## 2026-05-31 — v1.0.4 Manager log path (frozen EXE)

- **`logs/manager.log`** is written next to `DayZManager.exe` (same install root as `data/` and `config/`), not PyInstaller’s temporary `_MEI*` folder that disappears on exit.
- Startup logs the full path: `Manager log file: …`
- DEBUG-level lines from ModCheck/SteamCMD are included in the log file (not only INFO+).

---

## 2026-05-31 — v1.0.3 Shared mod cache fix

- **ModCheck / SteamCMD:** legacy per-server cache migration now uses **minimum** `time_updated` per Workshop ID (not max), so one server’s inflated cache entry no longer blocks updates for all hosts sharing `content/221100/<id>`.
- **Stale content detection:** compares Steam `time_updated` with newest file mtime in the Workshop folder; triggers download when cache looks current but files are older.
- **Failed SteamCMD fallback:** accepts existing on-disk Workshop folder for junction/sync (WARN) but **does not** bump `mod_versions.json`; scheduler/pre-start skip `mark_mod_version_synced` on that path so ModCheck can retry.
- **Cache I/O:** thread lock on `mod_versions.json`; reload from disk before mod checks and downloads (safe with parallel ModCheck per server).

---

## 2026-05-31 — v1.0.2 UI and host fixes

- Manager logs panel collapsed by default (`<details>`); expand on click.
- **Open folder** button on server card header (visible when collapsed); opens `servers[].path` in Windows Explorer via `POST /api/servers/{id}/open-folder`.
- Release **v1.0.2** also ships all changes since v1.0.1: host hardening, shared `w:{workshop_id}` mod cache, late RPT watcher (see sections below).

---

## 2026-05-31 — Shared Workshop cache and late RPT

- `data/mod_versions.json` now uses shared keys `w:{workshop_id}` (not per-server); legacy `server_id:mod_id` entries are migrated on load (**minimum** `time_updated` per mod — conservative merge for shared Workshop folders).
- ModCheck / `download_mod` skip SteamCMD when the remote version matches the cache, the content folder is non-empty, **and** local files are not older than Workshop metadata (newest file mtime).
- If SteamCMD fails but the Workshop content folder exists on disk, the download is treated as success with WARN **without** updating the version cache (ModCheck retries until SteamCMD succeeds).
- `ServerRptWatcher` keeps searching for RPT until `max(60, settings.startup_ready_timeout_sec)`; warns at 30s but continues; attaches late RPT and clears `rpt_not_found` when the file appears.

---

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
