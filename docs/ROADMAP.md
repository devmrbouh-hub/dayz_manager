# Roadmap — phase 2 (admin UI)

**Languages:** [English](ROADMAP.md) · [Русский](ru/ROADMAP.md)

Phase 1 (stabilization) and phase 2 (admin UI) are merged into **`main`** — see [CHANGELOG.md](CHANGELOG.md).  
Planned restart, live stats, chat — verified on reference host (2026-05).

## Done

- **Planned restart** — interval from 00:00, stages T-30/15/10/5/0, RU+EN say, lock + kick at T-5
- **Web UI** — Restart block on server card (auto + planned, Save, Next restart)
- **API** — `planned_restart`, `next_restart_at`, interval / test_mode validation
- **RCON** — bercon-cli `players` parser, bilingual say, lock, kick_all
- **RPT tail + READY** — `ServerRptWatcher`, `startup_phase`, hidden console, WS `/ws/servers/{id}/logs`, Server log on card
- **Live stats on card** — FPS from RPT, players X/max and nicknames (RCON + `serverDZ.cfg`)
- **In-game chat** — ExpLog tail 24 h, WS `/ws/servers/{id}/chat`, `POST /chat/say`; wall-clock timestamps
- **Server log UI** — incremental DOM, append without flicker (`syncServers`, `app.js?v=12`)
- **Mod check** — Steam Web API via `certifi` on Windows

## Priority 1

### Scheduler extensions
- Weekdays and fixed time (in addition to interval from 00:00)
- Multiple schedule templates per server

### RCON preset commands
- `say`, `kick`, `ban`, `save`, `shutdown` from UI
- Mass warnings outside planned restart

### Extended server status
- Game-port / query-port
- RCON alive, uptime
- ~~READY from RPT~~ — done (`startup_phase`, IdleMode marker)
- ~~FPS, online players~~ — on card (`server_fps`, `players`, `max_players`)
- Current map / preset

### Config editor in UI
- `serverDZ.cfg`, `mod_list.txt`, launch args, BattlEye

### Safe restart flow
- Scenario: say → save → shutdown → verify stop → start

## Priority 2

- Backup / rollback for configs and mod_list
- Action audit (who start/stop/sync)
- Health dashboard (ports, keys, SteamCMD, conflicts)
- Pre-flight validation before start
- Telegram / Discord notifications (module exists, not connected)

## DayZ-specific

- Ban list / whitelist / priority queue
- Search server and BattlEye logs
- Launch profiles: prod / test / event
- Compare configs between servers

## Top 5 for next MVP

1. Config and mod_list editor
2. RCON preset commands
3. Backup / rollback
4. Audit + notifications
5. Health dashboard (ports, SteamCMD)

## Out of scope (discussed separately)

- Do not block WatchDog on failed SteamCMD download if sync OK
- Wait for `SERVER_LOCK` release in `prepare_server_for_start`
- Mark `mod_versions` when Steam API unavailable
