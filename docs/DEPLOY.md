# Deployment

**Languages:** [English](DEPLOY.md) · [Русский](ru/DEPLOY.md)

## Two modes

| Mode | Where | How to run |
|------|-------|------------|
| Development | Machine with sources | `pip install -r requirements.txt`, `python src/main.py` |
| Production | Game host | `DayZManager.exe` + local `config/config.json` only |

Production does **not** need Python sources. After code changes: merge → `build.bat` → replace EXE on host.

The built-in web UI/API is intended for **local host administration**. If you open TCP `8000`, keep it on localhost, trusted LAN, VPN, or behind a separate gateway. Do not expose the raw manager UI directly to the public internet.

## New host (step by step)

### 1. Software

- Windows Server / Windows 10+
- DayZ Dedicated Server
- SteamCMD (e.g. `D:\Servers\MyServer\SteamCMD\steamcmd.exe`)
- For EXE build: Python 3.10+ on build machine

```powershell
python --version
Test-Path "D:\Servers\MyServer\SteamCMD\steamcmd.exe"
Test-Path "D:\Servers\MyServer\DayZServer_x64.exe"
```

### 2. BattlEye / RCON

Server profile, e.g. `D:\Servers\MyServer\Instance_1\BattlEye\BEServer_x64.cfg`:

```cfg
RConPassword YOUR_PASSWORD
RConPort 2305
RConIP 0.0.0.0
RestrictRCon 0
```

In `config.json`:

- `servers[].profiles` = `Instance_1`
- `servers[].rcon_port` / `rcon_password` match BattlEye
- No `-BEpath=BattlEye` in `launch_args` (use `-profiles=Instance_1`)

### 3. config.json

```powershell
copy config\config-host-template.json config\config.json
# edit path, ports, api_key, steamcmd_path
```

Steam login via env (see [CONFIG.md](CONFIG.md)):

```powershell
setx DAYZ_STEAM_USERNAME "your_login"
setx DAYZ_STEAM_PASSWORD "your_password"
```

Restart terminal after `setx`. Log in to SteamCMD once manually for session.

### 4. mod_list.txt

In server folder (`D:\Servers\MyServer\mod_list.txt`) — order and `@Mod` names. Workshop ID from junction (see [HOW_IT_WORKS.md](HOW_IT_WORKS.md)).

### 5. Firewall

```powershell
netsh advfirewall firewall add rule name="DayZ UDP 2302 IN" dir=in action=allow protocol=UDP localport=2302
netsh advfirewall firewall add rule name="DayZ UDP 2303 IN" dir=in action=allow protocol=UDP localport=2303
netsh advfirewall firewall add rule name="DayZ RCON UDP 2305 IN" dir=in action=allow protocol=UDP localport=2305
netsh advfirewall firewall add rule name="DayZ Manager TCP 8000 IN" dir=in action=allow protocol=TCP localport=8000
```

Use your ports from `serverDZ.cfg`. Only open TCP `8000` if you intentionally need access from a trusted admin network.

### 6. Verify

See [RUNBOOK.md](RUNBOOK.md) — smoke tests.

## Build EXE

```powershell
cd D:\dayz_manager
cmd /c "echo.|build.bat"
```

Output:

- `dist\DayZManager.exe`
- `dist\web\` (copied by script)
- `dist\config\config.json` — **sample**; do not overwrite host config

`build.bat` bundles `bercon-cli.exe` when present.

## Deploy to host

1. Stop old manager (`POST /api/shutdown` or kill process).
2. Replace `DayZManager.exe` (and `web/`, `bercon-cli.exe` next to EXE if needed).
3. **Do not touch** host `config/config.json` if paths and keys are already set.
4. Run EXE from folder containing `config\`, `hooks\`, `data\`, `logs\`.

Layout next to EXE:

```
C:\DayZManager\
├── DayZManager.exe
├── bercon-cli.exe
├── web\              # required — EXE serves static files from here
├── config\config.json
├── hooks\
├── data\
└── logs\
```

## Windows service (optional)

```powershell
install_service.bat
```

Requires `nssm` in PATH.

## Release workflow (recommended)

1. Finish phase on branch (`feature/stability` → merge to `main`).
2. On build machine: `build.bat`.
3. Copy `dist\DayZManager.exe` to host.
4. Smoke: `GET /api/servers`, `POST .../rcon/test`, `POST /api/mods/check`.

## Multiple servers on one host

Example: `config/config-host-nru90-template.json`.

## Common issues

| Symptom | Action |
|---------|--------|
| SteamCMD `Not logged on` / Timeout | Manual steamcmd login; check env and `auth_mode` |
| `Access Denied` on mod | Friend-only mod — account with access |
| RCON timeout | BattlEye up? `netstat -ano -p udp \| findstr <rcon_port>` |
| Stuck `SERVER_LOCK` | Delete manually after all operations stopped |
| `POST /start` → 500, pre-download failed | Fix Steam; workaround: `scripts/start_server_direct.py` |
