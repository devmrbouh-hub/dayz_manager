# GitHub Releases (pre-built EXE)

**Languages:** [English](RELEASES.md) · [Русский](ru/RELEASES.md)

If you do not want to install Python or run `build.bat`, use a **[GitHub Release](https://github.com/devmrbouh-hub/dayz_manager/releases)** asset.

## Download

1. Open [Releases](https://github.com/devmrbouh-hub/dayz_manager/releases).
2. Download **`dayz_manager-*-windows-x64.zip`** from the latest tag (e.g. `v1.0.0`).
3. Unzip to a folder on the game host, e.g. `C:\DayZManager\`.

## Contents of the ZIP

| File | Purpose |
|------|---------|
| `DayZManager.exe` | Manager (web UI + API) |
| `bercon-cli.exe` | RCON client (required next to EXE unless path set in config) |
| `config/config-host-template.json` | Copy to `config\config.json` and edit |
| `README-RELEASE.txt` | Short install steps |

## First run on the host

```powershell
cd C:\DayZManager
mkdir config -Force
copy config\config-host-template.json config\config.json
notepad config\config.json
```

Set at minimum: `auth.api_key`, Steam paths, `servers[].path`, ports, `rcon_password` (same as BattlEye).

Then:

```powershell
.\DayZManager.exe
```

Open **http://127.0.0.1:8000** and enter your API key.

Full checklist: [RUNBOOK.md](RUNBOOK.md), details: [DEPLOY.md](DEPLOY.md).

## Updating

1. Stop the old manager (`POST /api/shutdown` or close the process).
2. Replace `DayZManager.exe` (and `bercon-cli.exe` if the release includes a newer one).
3. **Do not overwrite** your working `config\config.json`.

## Building releases yourself (maintainers)

```powershell
.\scripts\package-release.ps1
# Upload dist\release\dayz_manager-*-windows-x64.zip to GitHub Releases
```

Requires `dist\DayZManager.exe` (run `build.bat` first) and `bercon-cli.exe` in the project root.
