# Roadmap — DayZ Server Manager

**Languages:** [English](ROADMAP.md) · [Русский](ru/ROADMAP.md)

**Updated:** 2026-06-21  
**Current stage:** **Stage 3 — Admin UI extensions** (Priority 1)

Phases 1–2 are merged into **`main`** — see [CHANGELOG.md](CHANGELOG.md).  
Architecture and product boundaries: [PRODUCT_ARCHITECTURE.md](PRODUCT_ARCHITECTURE.md).  
Planned restart, live stats, chat — verified on reference host (2026-05).

**Item numbering:** `stage.subitem` (e.g. **1.4**, **3.2.3**) — for references in commits and issues.

**Code audit (2026-06-21):** stages **0–2** are complete. Stage **3** is backlog; some related behavior already exists (see table below), but **3.x** items stay unchecked until the target UI/feature ships.

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
| **3.2.1** | Admin say: `POST /api/servers/{id}/chat/say` (item **1.21**) | General RCON preset panel, not chat-only |
| **3.3.1** | Game port on card (`:port`) | Query port on card |
| **3.5** | `restart()` waits for stop; planned restart has say/lock/kick | Single UI flow say → save → shutdown → verify → start |

### 3.1 Scheduler extensions

- [ ] **3.1.1** Weekdays and fixed time (in addition to interval from 00:00)
- [ ] **3.1.2** Multiple schedule templates per server

### 3.2 RCON preset commands

- [ ] **3.2.1** `say` from UI
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

- [ ] **3.5.1** RCON say (warning)
- [ ] **3.5.2** RCON save
- [ ] **3.5.3** RCON shutdown
- [ ] **3.5.4** Verified stop confirmation
- [ ] **3.5.5** Start after successful stop

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
