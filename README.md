# DayZ Server Manager

**Languages:** [English](README.md) · [Русский](README.ru.md)

Tired of batch files? This manager replaces them with a clean web UI.
Start/stop servers, auto-update mods, monitor players — all from a browser.

> 👉 **Just want to run it?** Download EXE → unzip → edit config.json → run. [Jump to Quick Start ↓](#production-host)

**License:** [MIT](LICENSE) · **Downloads:** [Releases](https://github.com/devmrbouh-hub/dayz_manager/releases)

## Screenshots

![DayZ Manager — compact server list](docs/images/ui-servers-compact.png)
![DayZ Manager — expanded server card](docs/images/ui-server-expanded.png)

## What it does

- Start / stop / restart multiple servers from a browser
- WatchDog — auto-restart on crash
- Mod updates via SteamCMD with in-game player warnings (5 min countdown)
- Planned restarts with RU/EN in-game countdown
- Live stats: FPS, player count, nicknames
- In-game chat visible in the browser
- RCON: say, kick, lock, graceful shutdown
- Single EXE for Windows — no install needed

## Quick Start (EXE — recommended)

**You need:** DayZ Dedicated Server + SteamCMD + BattlEye RCON configured.

1. Download latest **`dayz_manager-*-windows-x64.zip`** from [Releases](https://github.com/devmrbouh-hub/dayz_manager/releases)
2. Unzip anywhere on your game server host
3. Copy `config\config-host-template.json` → `config\config.json`
4. Edit `config.json` — set these 4 things:

| Field | What to set |
|-------|-------------|
| `auth.api_key` | Any password you choose |
| `steam.steamcmd_path` | Path to steamcmd.exe |
| `servers[].path` | Path to your DayZ server folder |
| `servers[].rcon_password` | Same as in BEServer_*.cfg |

5. Run `DayZManager.exe`
6. Open **http://127.0.0.1:8000** and enter your api_key

That's it. Full config reference: [docs/CONFIG.md](docs/CONFIG.md)

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
