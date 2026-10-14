# Roadmap — DayZ Server Manager

**Languages:** [English](ROADMAP.md) · [Русский](ru/ROADMAP.md)

**Updated:** 2026-10-14  
**Current stage:** **Stage 3 — Admin UI extensions** (Priority 1)

Phases 1–2 are merged into **`main`** — see [CHANGELOG.md](CHANGELOG.md).  
Architecture and product boundaries: [PRODUCT_ARCHITECTURE.md](PRODUCT_ARCHITECTURE.md).  
Planned restart, live stats, chat — verified on reference host (2026-05).

**Item numbering:** `stage.subitem` (e.g. **1.4**, **3.2.3**) — for references in commits and issues.

**Code audit (2026-10-14):** stages **0–2** are complete. In stage **3**, items already in the code are checked: chat `say`, the game port on the card, `#shutdown`, a confirmed stop, and start after that stop. The query port and RCON `save` are still open.

---

## Development path

| Phase | Stages | Status | Outcome |
|-------|--------|--------|---------|
| Stabilization | 0 | ✅ | SERVER_LOCK, multi-instance, mod sync |
| Admin UI MVP | 1 | ✅ | planned restart, RPT, chat, live stats |
| Host hardening | 2 | ✅ | shared `w:` cache, late RPT, frozen EXE, UI v1.0.2 |
| UI extensions | 3 | **now** | scheduler, RCON presets, config editor |
| Operations | 4 | — | backup, audit, health, notifications |
| DayZ-specific | 5 | — | ban list, log search, launch profiles |
| Admin PC panel | 6 | later | VPN, login, Windows service, restore after a crash |

### Top 5 for next MVP

1. Config and mod_list editor (**3.4**)
2. RCON preset commands (**3.2**)
3. Backup / rollback (**4.1**)
4. Audit + notifications (**4.2**, **4.5**)
5. Health dashboard (**4.3**)

---

## Stage 0 — Stabilization ✅

See [CHANGELOG.md](CHANGELOG.md) — `feature/stability` section.

- [x] **0.1** SERVER_LOCK and safe start/stop (`start_confirm_timeout`)
- [x] **0.2** Unified lock model for `prepare_server_for_start` and WatchDog
- [x] **0.3** Multiple instances on one host
- [x] **0.4** ModSync: junction `server\@Mod` → `!Workshop` + `.bikey` copy
- [x] **0.5** ModCheck via Steam Web API; Workshop ID digits only
- [x] **0.6** `+workshop_download_item` — separate SteamCMD argv
- [x] **0.7** CRON (`scheduler.restart_schedule`), WatchDog, hooks
- [x] **0.8** `PUT /api/settings`: hot-reload `mod_check_interval`
- [x] **0.9** PID / `.stopped`: exe check, recovery on manual DayZ start
- [x] **0.10** Hooks and frozen EXE: base path next to `DayZManager.exe`

---

## Stage 1 — Admin UI MVP ✅

Verified on reference host (2026-05). See [CHANGELOG.md](CHANGELOG.md).

### Planned restart

- [x] **1.1** Interval from 00:00 (`interval_minutes`)
- [x] **1.2** Stages T-30 / T-15 / T-10 / T-5 / T-0
- [x] **1.3** RU + EN say at each stage
- [x] **1.4** Lock + kick all at T-5

### Web UI and API

- [x] **1.5** Restart block on server card (auto + planned)
- [x] **1.6** Save restart settings from card
- [x] **1.7** Next restart display (`next_restart_at`)
- [x] **1.8** API: `planned_restart`, interval / test_mode validation

### RCON

- [x] **1.9** bercon-cli `players` parser (admin column)
- [x] **1.10** Bilingual say (RU + EN)
- [x] **1.11** Lock and kick_all for planned restart

### RPT tail + READY

- [x] **1.12** `ServerRptWatcher`, RPT tail, ring buffer
- [x] **1.13** `startup_phase`, IdleMode marker (READY)
- [x] **1.14** `hide_console` — start without DayZ window
- [x] **1.15** WebSocket `/ws/servers/{id}/logs`, Server log on card

### Live stats on card

- [x] **1.16** FPS from RPT (`server_fps`)
- [x] **1.17** Players X/max (`players`, `max_players` from `serverDZ.cfg`)
- [x] **1.18** Expandable nickname list (RCON `players` ~5 s)

### In-game chat

- [x] **1.19** ExpLog tail 24 h, `[Chat - *]` only
- [x] **1.20** WebSocket `/ws/servers/{id}/chat`
- [x] **1.21** `POST /chat/say` — admin say from UI
- [x] **1.22** Wall-clock timestamps; RCON inject for broadcast

### Server log UI

- [x] **1.23** Incremental DOM (`syncServers`, `updateServerCard`)
- [x] **1.24** WebSocket log append without flicker (`app.js?v=12`)

### Mod check

- [x] **1.25** Steam Web API via `certifi` (Windows without `Common Files\SSL\cert.pem`)

---

## Stage 2 — Host hardening and v1.0.2 ✅

See [CHANGELOG.md](CHANGELOG.md) — v1.0.2 and host hardening sections.

- [x] **2.1** Shared cache `w:{workshop_id}` + legacy `server_id:mod_id` migration
- [x] **2.2** Skip SteamCMD when remote version matches cache and Workshop folder is non-empty
- [x] **2.3** Fallback: accept existing Workshop folder on SteamCMD failure (WARN)
- [x] **2.4** Late RPT attach until `max(60, settings.startup_ready_timeout_sec)`
- [x] **2.5** Frozen EXE: `data/mod_versions.json` next to `DayZManager.exe`
- [x] **2.6** Owned SERVER_LOCK on shared mod update (no deleting foreign locks)
- [x] **2.7** Orphan process and `server.pid` cleanup on failed start
- [x] **2.8** Restart aborts if stop is not confirmed
- [x] **2.9** Static files: traversal protection outside `web/`
- [x] **2.10** Manager logs panel collapsed by default (`<details>`)
- [x] **2.11** **Open folder** button on card header (`POST .../open-folder`)

---

## Stage 3 — Admin UI extensions

**Focus:** former Priority 1 backlog.

### Partially in code (stage 3 not done)

| Item | Already exists | Missing for `[x]` |
|------|----------------|-------------------|
| **3.1.1** | Legacy `scheduler.restart_schedule`: `time`, `days`, `cron` — see [CONFIG.md](CONFIG.md) | UI and unified model with `planned_restart` (interval from 00:00) |
| **3.3.1** | Game port on the card (`:port`) | Query port on the card |
| **3.5.2** | `#shutdown` and a dead-process check exist on Stop and Restart | No separate RCON `save` command in the code |

### 3.1 Scheduler extensions

- [ ] **3.1.1** Weekdays and fixed time (in addition to interval from 00:00)
- [ ] **3.1.2** Multiple schedule templates per server

### 3.2 RCON preset commands

- [x] **3.2.1** `say` from UI (card chat, `POST /api/servers/{id}/chat/say`)
- [ ] **3.2.2** `kick`, `ban` from UI
- [ ] **3.2.3** `save`, `shutdown` from UI
- [ ] **3.2.4** Mass warnings outside planned restart

### 3.3 Extended server status

- [ ] **3.3.1** Game-port / query-port on card
- [ ] **3.3.2** RCON alive, uptime
- [ ] **3.3.3** Current map / preset

### 3.4 Config editor in UI

- [ ] **3.4.1** `serverDZ.cfg`
- [ ] **3.4.2** `mod_list.txt`
- [ ] **3.4.3** Launch args
- [ ] **3.4.4** BattlEye (`BEServer_*.cfg`)

### 3.5 Safe restart flow

- [x] **3.5.1** RCON say (warning on planned-restart stages; the card Restart button does not send it)
- [ ] **3.5.2** RCON save
- [x] **3.5.3** RCON shutdown (`#shutdown` in `stop_server`, otherwise taskkill)
- [x] **3.5.4** Verified stop (Restart does not continue while the process is alive)
- [x] **3.5.5** Start after a successful stop

---

## Stage 4 — Operations and monitoring

- [ ] **4.1** Backup / rollback for configs and mod_list
- [ ] **4.2** Action audit (who start/stop/sync)
- [ ] **4.3** Health dashboard (ports, keys, SteamCMD, conflicts)
- [ ] **4.4** Pre-flight validation before start
- [ ] **4.5** Telegram / Discord notifications (module exists, not connected)

---

## Stage 5 — DayZ-specific

- [ ] **5.1** Ban list / whitelist / priority queue
- [ ] **5.2** Search server and BattlEye logs
- [ ] **5.3** Launch profiles: prod / test / event
- [ ] **5.4** Compare configs between servers

---

## Stage 6 — Panel from the admin PC

**Later, not the current stage.** Recorded 2026-10-14.

The manager runs on its own VDS. The panel is open in a browser on the VDS desktop, and the admin sees it through Remote Desktop. The VDS network does not accept the panel port from outside, even though the process listens on `0.0.0.0:8000`.

Target:

- The panel port is not published to the internet. The process listens on `127.0.0.1` only. The VDS firewall has no inbound rule for TCP `8000`. Player game ports stay as they are. RCON is not added to the public internet.
- The admin reaches the panel only through a VPN between their computer and the VDS (WireGuard or Tailscale). The bookmark is the panel address inside that network, not the public VDS IP. Remote Desktop is not how they open the panel. The VPN encrypts the path.
- Login is a username and password. The password is stored as a hash. After login the browser gets a cookie with `HttpOnly`, `Secure`, and `SameSite=Strict`. The API-key field leaves the page and `localStorage`. Repeated failed logins are blocked for a while.
- Without a session everything is closed: the page, static files, server list, logs, chat, settings, and both WebSockets. Today some GET routes and the sockets are open without a key, and CORS is `allow_origins=*`.
- The manager runs as a Windows service under its own account and starts without an open desktop. A sketch already exists: `install_service.bat` (NSSM), see [DEPLOY.md](DEPLOY.md).
- Each server has one config field, "should be running". Start sets it and starts the process. Stop clears it and stops the process. A Windows or manager crash does not clear it. After boot the service starts servers with the field set. The same field replaces `.stopped` and the auto-restart toggle.

This does not close player game ports: those stay open for players. An admin computer that is already on the VPN can open the panel until the VPN key or the session is revoked. A logged-in admin can still run local hooks on the VDS.

- [ ] **6.1** Login: username and password, password stored as a hash, cookie `HttpOnly` / `Secure` / `SameSite=Strict`, lockout after repeated failures
- [ ] **6.2** Session on every request: page, static files, API, WebSocket. Remove CORS `*`. Remove the API key from the browser
- [ ] **6.3** Panel bound to `127.0.0.1` only. Do not add TCP `8000` to the firewall. The admin bookmark goes through the VPN
- [ ] **6.4** Manager as a Windows service, without a Remote Desktop session
- [ ] **6.5** "Should be running" field: Start/Stop change it, a crash does not clear it, the service and WatchDog start those servers

---

## Out of scope (discussed separately)

Improvements without a dedicated stage; do not block Stage 3:

- Do not block WatchDog on failed SteamCMD download if sync OK
- Wait for `SERVER_LOCK` release in `prepare_server_for_start`
- Mark `mod_versions` when Steam API unavailable

---

## How to maintain this roadmap

1. Mark `[x]` after a commit with the completed item; reference the number in commits or issues (**e.g. `roadmap 3.4.2`**).
2. Log blockers in [CHANGELOG.md](CHANGELOG.md) or a GitHub issue.
3. Do not duplicate API, schemas, or ModCheck details here — see [HOW_IT_WORKS.md](HOW_IT_WORKS.md), [API.md](API.md).
4. When deprioritizing, mark the item «deferred» with a short reason.
5. Keep ru and en versions in sync; do not renumber completed items.
