# DayZ Server Manager

**Languages:** [English](README.md) · [Русский](README.ru.md)

Tired of batch files? This manager replaces them with a clean web UI.
Start/stop servers, auto-update mods, monitor players — all from a browser.

> 👉 **Just want to run it?** Download EXE → unzip → prepare the server folder → edit config.json → run. [Where to start ↓](#where-to-start)

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

The manager starts a folder that already contains `DayZServer_x64.exe` and `serverDZ.cfg`. Downloading the DayZ Server, choosing mods, the economy, `types.xml`, and the mission stay outside this README.

## Where to start

Both paths end at one `mod_list.txt` in the server folder and one Start button.

### Mods and bat

The manager does not read the bat. Use `mod_list.txt` instead of the bat `-mod=` line: the same `@Name` values, one per line, order matters.

On every Start, ModSync builds the `-mod=` string from that list. If an `@Name` folder already sits next to `DayZServer_x64.exe`, the manager leaves it alone, uses it for launch, and copies `.bikey` files into `keys/`. If the folder is missing and a Workshop id is known, it creates junctions `server\@Name` → `!Workshop\@Name` → `content\221100\<id>`.

The numeric id comes from a junction (path into `content\221100\<id>`), from `servers[].mods` in `config.json` (`name` and `id`), not from a lone line in `mod_list.txt`. A plain copied `@Mod` folder does not provide an id for auto-update. Load order in `-mod=` comes only from `mod_list.txt`, not from `servers[].mods`.

If a name is listed but there is no folder next to the exe and no Workshop chain, the name still appears in `-mod=`, but the mod will not load in game — check WARN lines in `logs/manager.log`.

**First time on the machine:** subscribe and download mods with the **DayZ client launcher** (or Steam) into the **same library** as `steam.dayz_install_path` and `steam.workshop_path`. The manager does not replace the launcher: without files under `steamapps\workshop\content\221100\<id>` there is nothing to junction. After the download, Start links each `@Name` to that content and builds `-mod=`. **Later updates** go through SteamCMD and ModCheck when `steam.*`, `servers[].mods` with ids, and SteamCMD are configured (before start the manager may fetch outstanding mod updates once if ModCheck sees them).

Details: [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md) (ModSync and junctions).

### You have never launched a server

1. In Steam, open the library, Tools, and install **DayZ Server** into its own folder. The manager does not install into that folder.
2. Create `mod_list.txt`: mod names with `@`, as on the Workshop page or in your guide, one per line, in load order.
3. Subscribe to the same mods in the **launcher** and wait until they finish downloading (`@Name` as in `mod_list.txt`). Then set `steam.*` paths in `config.json` and, if needed, `name`/`id` pairs in `servers[].mods` so the manager links mods on Start and **updates** them via SteamCMD.
4. You do **not** need to copy gigabytes of mods into the server folder — that is only for legacy bat setups.
5. Set the hostname in `serverDZ.cfg` if you want. A password for players joining the game is optional in that file.

### You already have a folder and a bat

Leave the folder as it is; do not move mods. Open the bat, find `-mod=@CF;@Community-Online-Tools;...`, and copy those names into `mod_list.txt`, one per line, in the same order. The manager picks up `@Mod` folders that already sit next to the exe.

## config.json

1. Download **`dayz_manager-*-windows-x64.zip`** from [Releases](https://github.com/devmrbouh-hub/dayz_manager/releases) and unzip it.
2. Copy `config\config-host-template.json` → `config\config.json`.

The template is an example of a host that is already laid out. For one new folder, change it like this:

| Field | What to set |
|-------|-------------|
| `servers` | Keep one object. Delete the second server from the template |
| `servers[].path` | The folder that contains `DayZServer_x64.exe` |
| `servers[].config_file` | Path to the `serverDZ.cfg` that exists on disk. The template says `Instance_1\\serverDZ.cfg`. A fresh Steam install usually has `serverDZ.cfg` in the server root |
| `servers[].server_mods` | Clear it if there is no `@ServerMod` folder. Otherwise the launch line includes `-servermod=@ServerMod` |
| `servers[].mods_file` | Leave `mod_list.txt` |
| `servers[].mods` | Optional: `{ "name": "@CF", "id": "123456789" }` for Workshop id when no junction exists yet. Does not change launch order |
| `auth.api_key` | Your own string instead of `change_this_api_key`. The manager refuses to start with the template value. Type it on http://127.0.0.1:8000. It is not the player password and not the BattlEye password. The page does not ask for `auth.users` |
| `servers[].rcon_password`, `rcon.password`, `rcon.port`, `rcon_port` | The same `RConPassword` and `RConPort` as in your `BEServer_*.cfg`. The template uses port 2304; yours may differ |

**Minimum for Start** when `@Mod` folders already sit next to the exe (as after a bat): `servers[].path`, `auth.api_key`, RCON, correct `config_file`.

**For junctions and ModCheck:** `steam.steamcmd_path`, `steam.dayz_install_path`, `steam.workshop_path`, and `servers[].mods` with ids (or junctions after the launcher). SteamCMD is for **updates**, not the first subscribe; the launcher fills the library first. Paths: [docs/CONFIG.md](docs/CONFIG.md). Junctions: [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md).

On Start the manager copies `.bikey` from the server `@Mod` folder or from `!Workshop` when a junction points there.

3. Run `DayZManager.exe`.
4. Open **http://127.0.0.1:8000** and enter `auth.api_key`.

BattlEye, ports, and the firewall: [docs/DEPLOY.md](docs/DEPLOY.md). Full field reference: [docs/CONFIG.md](docs/CONFIG.md).

## Production (host)

### Option A — Download release (recommended if you do not build)

1. Open **[Releases](https://github.com/devmrbouh-hub/dayz_manager/releases)** → latest **`dayz_manager-*-windows-x64.zip`**
2. Unzip on the host; copy `config\config-host-template.json` → `config\config.json` and fill it in as in [config.json](#configjson)
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
