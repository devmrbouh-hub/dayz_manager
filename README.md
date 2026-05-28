# DayZ Server Manager

**Languages:** [English](README.md) · [Русский](README.ru.md)

Unified DayZ server manager for Windows: web UI, REST API, WatchDog, SteamCMD mod updates, planned and CRON restarts. **Any map and mod set** — configured only via `config.json` (server path, `mod_list.txt`, launch args). Multiple instances on one host.

**Docs:** [docs/INDEX.md](docs/INDEX.md) · **License:** [MIT](LICENSE) · **Downloads:** [Releases](https://github.com/devmrbouh-hub/dayz_manager/releases) (ready-made EXE, no build)

> **GitHub About (description):** `DayZ dedicated server manager for Windows — web UI, multi-server, SteamCMD mods, RCON, WatchDog, planned restarts`

## Prerequisites

Before quick start: **DayZ Dedicated Server** and **SteamCMD** installed, BattlEye RCON configured on the game server.

Field `servers[].id` is any name you choose (`server1`, `chernarus`, …). Examples in docs use `server1`; use your id from `config.json`.

**Manager won't start?** Check `auth.api_key`, Steam paths, and [RUNBOOK.md](docs/RUNBOOK.md).

## Requirements

- Windows, Python 3.10+
- [SteamCMD](https://developer.valvesoftware.com/wiki/SteamCMD) and DayZ Server installation
- **bercon-cli.exe** — project root or `rcon.client_path` in `config.json` (see [CONFIG.md](docs/CONFIG.md))

## Features

- Multiple servers: start / stop / restart
- WatchDog — auto-restart on crash (`auto_restart`, `settings.watchdog_interval`, default 10 s)
- **Planned restart** — interval from 00:00 with RU/EN warnings, lock and kick at T-5 (server card)
- Mod check and sync (`mod_list.txt`, junctions, Steam Web API)
- CRON restarts (legacy) via `scheduler.restart_schedule`
- RCON: say, lock, kick, graceful shutdown
- Web UI, REST API, log WebSockets
- **Live stats** on card: FPS, players X/max, nicknames
- **In-game chat** on card: ExpLog + admin say (24 h history)
- Hooks `beforeStart` / `afterStop`
- Single-file EXE build (`build.bat`)

## Screenshots

Compact server list — several instances on one host:

![DayZ Manager — compact server list](docs/images/ui-servers-compact.png)

Expanded server card — restart settings, RPT log, in-game chat:

![DayZ Manager — expanded server card](docs/images/ui-server-expanded.png)

## Quick start

### 1. Clone and dependencies

```powershell
git clone https://github.com/devmrbouh-hub/dayz_manager.git
cd dayz_manager
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. RCON client

Download [bercon-cli](https://github.com/WoozyMasta/bercon-cli) and place `bercon-cli.exe` in the project root  
or set `rcon.client_path` in `config.json` (see template).

### 3. Config

```powershell
copy config\config-host-template.json config\config.json
```

In `config\config.json` set at minimum:

| Field | Value |
|-------|--------|
| `auth.api_key` | Your key (not `change_this_api_key` — manager refuses default) |
| `steam.steamcmd_path`, `steam.workshop_path` | SteamCMD and Workshop paths |
| `servers[].path`, ports | Dedicated server folder and ports |
| `servers[].rcon_password` | Same as BattlEye `BEServer_*.cfg` |

Steam password via `DAYZ_STEAM_USERNAME` / `DAYZ_STEAM_PASSWORD` or `steam.*` fields (see [CONFIG.md](docs/CONFIG.md)).

`config/config.json` is **not in git** — local only.

### 4. Run

```powershell
python src/main.py
```

Open **http://127.0.0.1:8000** → enter the same `auth.api_key` in the API Key field (stored in browser).

### 5. Verify

```powershell
pytest
# optional smoke (manager must be running):
set API_KEY=your_key_from_config
set SERVER_ID=server1
test_system.bat
```

Next: [RUNBOOK.md](docs/RUNBOOK.md) (BattlEye, firewall), [DEPLOY.md](docs/DEPLOY.md) (EXE on host).

## Production (host)

### Option A — Download release (recommended if you do not build)

1. Open **[Releases](https://github.com/devmrbouh-hub/dayz_manager/releases)** → latest **`dayz_manager-*-windows-x64.zip`**
2. Unzip on the host; copy `config\config-host-template.json` → `config\config.json` and edit
3. Run `DayZManager.exe` → http://127.0.0.1:8000

Step-by-step: [docs/RELEASES.md](docs/RELEASES.md)

### Option B — Build from source

1. `build.bat` → `dist\DayZManager.exe` (requires `bercon-cli.exe` in project root)
2. Copy EXE to host; **do not overwrite** working `config.json`
3. Templates: `config/config-host-template.json`, `config/config-host-nru90-template.json`

Details: [docs/DEPLOY.md](docs/DEPLOY.md), checklist: [docs/RUNBOOK.md](docs/RUNBOOK.md).

## Layout

```
dayz_manager/
├── src/           # Python: core, api, notifications
├── web/           # UI
├── config/        # config.json (local, .gitignore)
├── hooks/         # Custom hooks
├── scripts/       # Optional helper scripts
├── docs/          # Documentation (EN); docs/ru/ — Russian
├── build.bat
└── README.md
```

## Branch and releases

Active branch: **`main`**. Stabilization and admin UI (planned restart, live stats, chat) are merged — see [CHANGELOG.md](docs/CHANGELOG.md) and [ROADMAP.md](docs/ROADMAP.md).

Scaling plans (internet, map, shop, SaaS): [docs/PRODUCT_ARCHITECTURE.md](docs/PRODUCT_ARCHITECTURE.md).

## Optional helper scripts

Not required for first run. Target server: `DAYZ_MANAGER_SERVER` env or first entry in `config.json`.

```powershell
python scripts/test_stability_local.py
python scripts/start_server_direct.py   # sync + start without SteamCMD pre-download
```

See [docs/TESTING.md](docs/TESTING.md).
