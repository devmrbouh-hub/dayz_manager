# Развёртывание

**Languages:** [English](../DEPLOY.md) · [Русский](DEPLOY.md)


## Два режима

| Режим | Где | Как запускать |
|-------|-----|----------------|
| Разработка | Машина с исходниками | `pip install -r requirements.txt`, `python src/main.py` |
| Production | Игровой хост | Только `DayZManager.exe` + локальный `config/config.json` |

На production **не нужны** исходники Python. После изменений в коде: merge → `build.bat` → заменить EXE на хосте.

Встроенный web UI/API рассчитан на **локальное администрирование на хосте**. Порт панели в интернет не открывать. Будущий вход админа со своего компьютера — VPN до ВДС, панель слушает только `127.0.0.1` (этап **6** в [ROADMAP.md](ROADMAP.md)). Правило брандмауэра на TCP `8000` ниже — только для доверенной сети на время настройки, не для постоянного доступа из интернета.

## Новый хост (пошагово)

Папка сервера и `mod_list.txt` — по [README](../../README.ru.md#с-чего-начать). На новом хосте моды **сначала** качают клиентским лаунчером в ту же библиотеку Steam, что в конфиге; SteamCMD подключают для обновлений (см. [Моды и bat](../../README.ru.md#моды-и-bat)). Копировать моды в папку сервера вручную не обязательно, если настроены пути Workshop и id, либо рядом с exe уже лежат папки после bat. Здесь пароль BattlEye, порты и firewall.

### 1. ПО

- Windows Server / Windows 10+
- DayZ Dedicated Server
- SteamCMD (например `D:\Servers\MyServer\SteamCMD\steamcmd.exe`) — обновления модов и ModCheck после загрузки лаунчером; на первом Start с `@Мод` от bat или уже скачанным Workshop content не обязателен
- Для сборки EXE: Python 3.10+ на машине разработчика

```powershell
python --version
Test-Path "D:\Servers\MyServer\SteamCMD\steamcmd.exe"
Test-Path "D:\Servers\MyServer\DayZServer_x64.exe"
```

### 2. BattlEye / RCON

Профиль сервера, например `D:\Servers\MyServer\Instance_1\BattlEye\BEServer_x64.cfg`:

```cfg
RConPassword YOUR_PASSWORD
RConPort 2305
RConIP 0.0.0.0
RestrictRCon 0
```

Число 2305 в примере замените на `RConPort` своего сервера. В шаблоне менеджера порт равен 2304, пока вы его не изменили.

В `config.json`:

- `servers[].profiles` = `Instance_1`
- `servers[].rcon_port` / `rcon_password` совпадают с BattlEye
- В `launch_args` **нет** `-BEpath=BattlEye` (используйте `-profiles=Instance_1`)

### 3. config.json

```powershell
copy config\config-host-template.json config\config.json
# отредактировать path, порты, api_key, steamcmd_path
```

Steam-логин через env (см. [CONFIG.md](CONFIG.md)):

```powershell
setx DAYZ_STEAM_USERNAME "your_login"
setx DAYZ_STEAM_PASSWORD "your_password"
```

Перезапустить терминал после `setx`. Один раз войти в SteamCMD вручную для сессии.

### 4. mod_list.txt

В папке сервера (`D:\Servers\MyServer\mod_list.txt`) — порядок и имена `@Mod` для строки `-mod=`. Из bat перепишите строку после `-mod=`, по одному имени на строку. Раскладку папок и junction на Start делает ModSync: существующие `@Мод` у exe не заменяются, иначе создаются junction к `!Workshop` при известном Workshop id. Id — в `servers[].mods` или из junction (см. [HOW_IT_WORKS.md](HOW_IT_WORKS.md)).

### 5. Firewall

```powershell
netsh advfirewall firewall add rule name="DayZ UDP 2302 IN" dir=in action=allow protocol=UDP localport=2302
netsh advfirewall firewall add rule name="DayZ UDP 2303 IN" dir=in action=allow protocol=UDP localport=2303
netsh advfirewall firewall add rule name="DayZ RCON UDP 2305 IN" dir=in action=allow protocol=UDP localport=2305
netsh advfirewall firewall add rule name="DayZ Manager TCP 8000 IN" dir=in action=allow protocol=TCP localport=8000
```

Подставьте свои порты из `serverDZ.cfg`. TCP `8000` открывайте только если он нужен доверенной админ-сети.

### 6. Проверка

См. [RUNBOOK.md](RUNBOOK.md) — smoke tests.

## Сборка EXE

```powershell
cd D:\dayz_manager
cmd /c "echo.|build.bat"
```

Результат:

- `dist\DayZManager.exe`
- `dist\web\` (копируется скриптом)
- `dist\config\config.json` — **пример**; на хосте не перезаписывать рабочий конфиг

`build.bat` также подключает `bercon-cli.exe` в bundle.

## Выкладка на хост

1. Остановить старый менеджер (`POST /api/shutdown` или завершить процесс).
2. Заменить `DayZManager.exe` (и при необходимости `web/`, `bercon-cli.exe` рядом с EXE).
3. **Не трогать** `config/config.json` на хосте, если пути и ключи уже настроены.
4. Запустить EXE из папки, где лежат `config\`, `hooks\`, `data\`, `logs\`.

Структура рядом с EXE:

```
C:\DayZManager\
├── DayZManager.exe
├── config\config.json
├── hooks\
├── data\
├── logs\
└── web\          # если не встроено в onefile — см. фактическую сборку
```

## Служба Windows (опционально)

```powershell
install_service.bat
```

Требуется `nssm` в PATH.

## Workflow релиза (рекомендуется)

1. Завершить фазу на ветке (`feature/stability` → merge в `main`).
2. На машине сборки: `build.bat`.
3. Скопировать `dist\DayZManager.exe` на хост.
4. Smoke: `GET /api/servers`, `POST .../rcon/test`, `POST /api/mods/check`.
5. Следующие feature-ветки ответвлять от актуальной `main`.

## Несколько серверов на одном хосте

Пример: `config/config-host-nru90-template.json`.

## Частые проблемы

| Симптом | Действие |
|---------|----------|
| SteamCMD `Not logged on` / Timeout | Ручной login в steamcmd; проверить env и `auth_mode` |
| `Access Denied` на мод | Friend-only мод — аккаунт с доступом |
| RCON timeout | BattlEye поднят? `netstat -ano -p udp \| findstr <rcon_port>` |
| Зависший `SERVER_LOCK` | Удалить вручную после остановки всех операций |
| `POST /start` → 500, pre-download failed | Починить Steam; обход: `scripts/start_server_direct.py` |
