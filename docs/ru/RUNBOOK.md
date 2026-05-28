# Runbook — быстрый чеклист

**Languages:** [English](../) · [Русский]()


## Перед запуском

- [ ] Python 3.10+ **или** готовый `DayZManager.exe`
- [ ] SteamCMD и DayZ server на месте
- [ ] `config/config.json`: `api_key` ≠ `change_this_api_key`
- [ ] `steam.steamcmd_path` корректен
- [ ] `servers[].path`, порты, `profiles`, `mods_file`
- [ ] BattlEye cfg в `Instance_X\BattlEye\` совпадает с RCON в конфиге
- [ ] `mod_list.txt` заполнен
- [ ] Steam: `DAYZ_STEAM_*` env или успешный ручной login в SteamCMD

## Запуск

```powershell
cd D:\dayz_manager
python src/main.py
# или
.\dist\DayZManager.exe
```

UI: `http://127.0.0.1:8000` — ввести API key в шапке. На карточке сервера — блок **Restart** (auto restart, planned restart).

После обновления кода UI: **Ctrl+F5** (кэш `app.js`).

## Smoke tests

```powershell
curl http://127.0.0.1:8000/api/servers

curl -X POST http://127.0.0.1:8000/api/servers/server1/rcon/test `
  -H "X-API-Key: YOUR_KEY"

curl -X POST http://127.0.0.1:8000/api/mods/check `
  -H "X-API-Key: YOUR_KEY"
```

Ожидания:

- `/api/mods/check` → `details.<id>.tracked_mods` / `skipped_mods`
- `/rcon/test` → `"success": true` (нужен **запущенный** DayZ + BattlEye)
- Planned restart: на карточке сервера включить test mode 15 мин → Save → в UI **Next:** показывает ближайший слот
- В консоли DayZ: `BattlEye Server: Config entry: RConPort ...`
- `netstat -ano -p udp | findstr 2305` — UDP слушает RCON-порт

## Остановка менеджера

```powershell
curl -X POST http://127.0.0.1:8000/api/shutdown -H "X-API-Key: YOUR_KEY"
```

## Зависший SERVER_LOCK

1. Убедиться, что нет `DayZServer_x64.exe` и активного SteamCMD update.
2. Удалить `D:\Servers\MyServer\SERVER_LOCK` (или `{servers[].path}\SERVER_LOCK`).
3. Перезапустить сервер через UI/API.

## Planned restart не срабатывает

- На карточке: **Planned restart** включён, **Save planned restart** нажат
- `GET /api/servers/server1` → `planned_restart.enabled: true`, `next_restart_at` не null
- RCON test OK; сервер **running**, нет `SERVER_LOCK`
- Лог: `Planned restart stage T-...` или `RCON unavailable`
- Test mode: `interval_minutes` 10–59; обычный режим: 60–1440

## WatchDog не поднимает сервер

- Проверить `auto_restart: true`
- Нет ли `.stopped` (нужен явный Start)
- Лог: `Pre-start mod download failed` → SteamCMD (см. [TESTING.md](TESTING.md))
- Временный обход: `python scripts/start_server_direct.py`

## Сборка EXE

```powershell
cmd /c "echo.|build.bat"
```

## Полное тестирование

[TESTING.md](TESTING.md) — сценарии T1–T6, T4b (planned restart).
