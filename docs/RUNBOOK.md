# Runbook — quick checklist

**Languages:** [English](RUNBOOK.md) · [Русский](ru/RUNBOOK.md)

## Before first run

- [ ] Python 3.10+ **or** built `DayZManager.exe`
- [ ] SteamCMD and DayZ server installed
- [ ] `config/config.json`: `api_key` ≠ `change_this_api_key`
- [ ] `steam.steamcmd_path` is correct
- [ ] `servers[].path`, ports, `profiles`, `mods_file`
- [ ] BattlEye cfg in `Instance_X\BattlEye\` matches RCON in config
- [ ] `mod_list.txt` filled in
- [ ] Steam: `DAYZ_STEAM_*` env or successful manual SteamCMD login

## Start

```powershell
cd D:\dayz_manager
python src/main.py
# or
.\dist\DayZManager.exe
```

UI: `http://127.0.0.1:8000` — enter API key in header. Server card — **Restart** block (auto restart, planned restart).

After code updates: **Ctrl+F5** (cache `app.js`).

## Smoke tests

```powershell
curl http://127.0.0.1:8000/api/servers

curl -X POST http://127.0.0.1:8000/api/servers/server1/rcon/test `
  -H "X-API-Key: YOUR_KEY"

curl -X POST http://127.0.0.1:8000/api/mods/check `
  -H "X-API-Key: YOUR_KEY"
```

Expect:

- `/api/mods/check` → `details.<id>.tracked_mods` / `skipped_mods`
- `/rcon/test` → `"success": true` (requires **running** DayZ + BattlEye)
- Planned restart: enable test mode 15 min on card → Save → UI **Next:** shows nearest slot
- DayZ console: `BattlEye Server: Config entry: RConPort ...`
- `netstat -ano -p udp | findstr 2305` — UDP listening on RCON port

## Stop manager

```powershell
curl -X POST http://127.0.0.1:8000/api/shutdown -H "X-API-Key: YOUR_KEY"
```

## Stuck SERVER_LOCK

1. Ensure no `DayZServer_x64.exe` and no active SteamCMD update.
2. Delete `D:\Servers\MyServer\SERVER_LOCK` (or `{servers[].path}\SERVER_LOCK`).
3. Restart server via UI/API.

## Planned restart not firing

- Card: **Planned restart** on, **Save planned restart** clicked
- `GET /api/servers/server1` → `planned_restart.enabled: true`, `next_restart_at` not null
- RCON test OK; server **running**, no `SERVER_LOCK`
- Log: `Planned restart stage T-...` or `RCON unavailable`
- Test mode: `interval_minutes` 10–59; normal mode: 60–1440

## WatchDog not restarting

- Check `auto_restart: true`
- No `.stopped` (needs explicit Start)
- Log: `Pre-start mod download failed` → SteamCMD (see [TESTING.md](TESTING.md))
- Workaround: `python scripts/start_server_direct.py`

## Build EXE

```powershell
cmd /c "echo.|build.bat"
```

## Full testing

[TESTING.md](TESTING.md) — scenarios T1–T6, T4b (planned restart).
