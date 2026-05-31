# Testing

**Languages:** [English](TESTING.md) · [Русский](ru/TESTING.md)

**Last updated:** 2026-05-30
**Branch:** `main` (local host manager / future host agent)

Use your `servers[].id` in API paths (examples use `server1`).

## Prerequisites

- [ ] Manager running (`python src/main.py` or `DayZManager.exe`)
- [ ] `bercon.exe` / `bercon-cli.exe` available (see `rcon.client_path`)
- [ ] SteamCMD configured; with `credentials` — env or manual login
- [ ] BattlEye in profile (`Instance_X\BattlEye\`)
- [ ] RCON in `config.json` matches BattlEye cfg
- [ ] For T1/T6/T4b — DayZ **running**

---

## Automated RPT / READY tests

No DayZ required — pytest covers watcher, server_mgr, API/WS, UI helpers.

```powershell
cd dayz_manager
pip install -r requirements-dev.txt
python -m pytest tests/ -v
node --test tests/test_server_status.mjs
```

| Suite | File | Checks |
|-------|------|--------|
| Watcher | `tests/test_server_rpt_watcher.py` | phases, marker, FPS, lazy attach, late RPT attach, `_find_rpt_for_session`, … |
| SteamCMD cache | `tests/test_steamcmd_mod_cache.py` | shared `w:` cache, legacy key migration, skip download, accept local content after failed SteamCMD |
| Chat | `tests/test_server_chat_watcher.py` | ExpLog parse, history, tail |
| Live stats | `tests/test_live_stats.py` | FPS, maxPlayers, parse_players |
| ServerManager | `tests/test_server_mgr_rpt.py` | session begin/end, hide console, failed-start cleanup, safe restart |
| API/WS | `tests/test_api_rpt.py`, `tests/test_api_chat.py` | RPT/READY, chat/say |
| Validation | `tests/test_api_validation.py` | invalid settings/server payloads rejected without partial writes |
| Static/UI routing | `tests/test_main_static.py` | path traversal blocked, SPA fallback preserved |
| Scheduler locks | `tests/test_scheduler_locks.py` | shared mod update respects existing locks and releases owned locks safely |
| Runtime paths | `tests/test_runtime_paths.py` | frozen EXE writes data cache next to external install |
| UI | `tests/test_server_status.mjs` | STOPPED/STARTING/READY, WEAPON filter |

**Last run (2026-05-31):** `pytest` — 87 passed; `node --test tests/test_server_status.mjs` — 10 passed.

**CI:** GitHub Actions runs both `pytest` and `node --test tests/test_server_status.mjs`.

**Reference (2026-05-25, manual):** OK — live stats, in-game chat, Steam mod check, hidden console.

---

## UI — Restart block on server card

1. Open `http://127.0.0.1:8000`, enter API key, **Refresh**.
2. Card shows status, Start/Stop/Restart, **Restart** block.
3. **Auto restart** — toggle sends `PUT` (`auto_restart`).
4. **Planned restart** — toggle, Interval (2/3/4/6 h, Custom, Test mode), **Save planned restart**.
5. After Save — **Next:** shows `next_restart_at`; matches `GET /api/servers/{id}`.
6. Add Server — basic fields only; new card has Restart defaults (planned off, 4 h).

**Reference (2026-05-24):** OK — planned restart test mode 15 min, kick at T-5.

---

## T7 — RPT log and READY

**Goal:** hidden console, STOPPED → STARTING → READY, live RPT on card.

### Basic flow

1. **Ctrl+F5** on Web UI.
2. **Start** — no separate DayZ window (`hide_console: true`).
3. Status **STARTING** → **READY**; **FPS** and **Players X/Y** update (~5 s).
4. Expand **Players online** — nicknames (not `true`/`false`).
5. Expand **Server log (RPT)** — live tail; READY marker highlighted.
6. **Stop** → **STOPPED**.

## T7b — In-game chat

1. Server **READY**, Expansion: `LogsSettings.json` → `"Chat": 1`.
2. Expand **In-game chat** — 24 h history, live lines; timestamps match local time.
3. Type text → **Send** — appears in game (RCON `say -1`); FPS/player metrics not duplicated in chat.
4. Write in global chat in game — line appears in UI.
5. Planned restart — RU/EN say and pre-kick message visible in feed.

**Reference (2026-05-25):** OK.

## T-console — hidden window

| # | Action | Expected |
|---|--------|----------|
| 1 | Start from UI | No `DayZServer_x64.exe` console window |
| 2 | Start via `.bat` / exe manually | Window may appear (outside manager) |

### API

```powershell
curl http://127.0.0.1:8000/api/servers/server1

curl "http://127.0.0.1:8000/api/servers/server1/logs/tail?lines=50"
```

### Edge cases

| # | Action | Expected |
|---|--------|----------|
| 4 | Kill `DayZServer_x64.exe` during STARTING | STOPPED, tail thread stopped |
| 5 | Kill after READY | STOPPED, not stuck STARTING |
| 6 | Restart | STARTING → READY again |
| 7 | Open log → close | WS disconnected; READY on card remains |
| 8 | Restart manager only while DayZ alive | lazy attach → READY without Start |
| 9 | Wrong `profiles` in config | `startup_warning: rpt_not_found` |

### Performance (smoke)

| # | Check |
|---|--------|
| 10 | Tail under load: UI responsive, tail CPU < ~5% one core |
| 11 | Two UI tabs — both receive WS lines |

**Reference (2026-05-25):** OK — STARTING → READY, Server log, WEAPON filter.

### Server log without flicker

1. **Ctrl+F5**.
2. Server **stopped** — open **Server log (RPT)**: no flicker.
3. **Start** with log open: lines **append**; `<pre>` **not cleared** on poll.
4. **Hide WEAPON** — toggle without reload.
5. **Refresh** in header — card updates, log lines preserved.

**Reference (2026-05-25):** OK.

---

## T1 — WatchDog after killing PID

1. Start via UI/API.
2. Wait 5 s, end `DayZServer_x64.exe` in Task Manager.
3. After 10–15 s check logs.

**Expected:**

```
[WatchDog] server1 is down, auto restarting...
Server server1 started with PID: ...
```

**Reference host (2026-05-23):** WatchDog **fired**, full restart **failed** — `Pre-start mod download failed` (SteamCMD timeout). Workaround: `scripts/start_server_direct.py`.

---

## T2 — Mod update without race

1. `POST /api/mods/check` with API key.
2. If updates exist — wait for ModCheck cycle or `POST /api/mods/sync`.
3. During update no parallel WatchDog restart on same server (`SERVER_LOCK`).

**Checks:**

- `details.<server>.tracked_mods` / `skipped_mods`
- Junction: `dir D:\Servers\MyServer\@* /AL`
- `data/mod_versions.json` updated

---

## T3 — Failed start + WatchDog

1. Simulate start error (wrong exe or port in use).
2. `.stopped` **cleared** after error.
3. Fix condition — WatchDog should restart with `auto_restart: true`.

---

## T4 — CRON restart (legacy)

Add slot in `config.json` for nearest minute:

```json
"restart_schedule": [
  { "server_id": "server1", "time": "14:37", "days": ["sat"] }
]
```

**Expected:** restart in due slot (no multi-stage warnings).

**Reference:** not run (`restart_schedule: []`).

---

## T4b — Planned restart (interval from 00:00)

1. On card **Restart** or via API enable test mode, `interval_minutes: 15`.
2. RCON works: `POST /api/servers/server1/rcon/test`.
3. Wait for T-10, T-5, T-0 (T-30/T-15 skipped at 15 min interval).

**Expected:**

- T-10 / T-5: two says (RU, then EN) in chat
- T-5: say → 5 s pause → `#lock` → kick all online
- T-0: server restarted, new PID

**Reference (2026-05-24):** OK.

```powershell
curl -X PUT http://127.0.0.1:8000/api/servers/server1 `
  -H "X-API-Key: YOUR_KEY" `
  -H "Content-Type: application/json" `
  -d "{\"planned_restart\": {\"enabled\": true, \"interval_minutes\": 15, \"test_mode\": true}}"
```

---

## T5 — PUT mod_check_interval (hot-reload)

```powershell
curl -X PUT http://127.0.0.1:8000/api/settings `
  -H "X-API-Key: YOUR_KEY" `
  -H "Content-Type: application/json" `
  -d "{\"mod_check_interval\": 601}"
```

**Expected:** `GET /api/settings` → 601; ModCheck task restarted without manager restart.

**Reference:** OK.

---

## T6 — RCON test

```powershell
curl -X POST http://127.0.0.1:8000/api/servers/server1/rcon/test `
  -H "X-API-Key: YOUR_KEY"
```

**Expected:** `"success": true`, `"message": "RCON test OK"`.

**If fail:**

- DayZ running, BattlEye initialized (1–2 min after start)
- Port/password = `BEServer_x64.cfg`
- `netstat -ano -p udp | findstr <rcon_port>`

**Reference:** OK after BattlEye/RCON setup (2026-05-24).

---

## Additional scenarios

| # | Scenario | Summary |
|---|----------|---------|
| 4 | Graceful Stop | UI Stop → RCON shutdown or taskkill in `preferred` |
| 5 | Player notify | Mod update / CRON — two says (RU, then EN) |
| 7 | SteamCMD session | Empty credentials + saved session |

---

## Helper scripts

```powershell
cd dayz_manager
# optional: set DAYZ_MANAGER_SERVER=your_server_id
python scripts/test_stability_local.py
python scripts/start_server_direct.py
```

### `test_system.bat` (curl smoke)

```powershell
set API_KEY=your_api_key_from_config
set SERVER_ID=server1
test_system.bat
```

---

## Reference verification results

| Check | 2026-05-23 | 2026-05-24 | 2026-05-25 |
|-------|------------|------------|------------|
| lock acquire/release | OK | OK | OK |
| effective_mods | OK | OK | OK |
| PUT mod_check_interval | OK | OK | OK |
| GET /api/servers | OK | OK | OK |
| WatchDog after kill | Partial (SteamCMD) | — | — |
| RCON test | Fail (timeout) | OK | OK |
| Planned restart T4b | — | OK | OK |
| UI Restart block | — | OK | OK |
| Live stats + nicknames | — | — | OK |
| In-game chat | — | — | OK |
| Steam mod check (certifi) | — | — | OK |

---

## Checklist

| Test | Status | Note |
|------|--------|------|
| UI Restart block | Done | ref 2026-05-24 |
| T4b Planned restart | Done | ref 2026-05-24 |
| T6 RCON | Done | ref 2026-05-24 |
| T1 WatchDog | Open | |
| T2 Mod update / lock | Open | |
| T3 Failed start | Open | |
| T4 CRON (legacy) | Open | |
| T5 Settings hot-reload | Done | ref 2026-05-23 |
| T7 RPT + READY | Done | ref 2026-05-25 |
| T7b In-game chat | Done | ref 2026-05-25 |
| T7c Live stats | Done | ref 2026-05-25 |
| Log no flicker | Done | ref 2026-05-25 |
| Mod check Steam API | Done | ref 2026-05-25 |
| pytest RPT/chat/stats | Done | 80 passed, 2026-05-30 |
| node server_status | Done | 10 passed, 2026-05-30 |

## Logs

- UI: **Server log (RPT)** on card / `ws://host:8000/ws/servers/{id}/logs`
- UI: Live Logs (manager) / `ws://host:8000/ws/logs`
- File: `logs/manager.log`
- API: `GET /api/logs`, `GET /api/servers/{id}/logs/tail`
- DayZ: `{path}/{profiles}/DayZServer_x64_*.RPT`, BattlEye logs
