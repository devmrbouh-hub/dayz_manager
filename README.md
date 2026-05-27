# DayZ Server Manager

Единый менеджер DayZ-серверов: веб-UI, REST API, WatchDog, автообновление модов через SteamCMD, плановые и CRON-рестарты.

**Документация:** [docs/INDEX.md](docs/INDEX.md) · **Лицензия:** [MIT](LICENSE)

## Требования

- Windows, Python 3.10+
- [SteamCMD](https://developer.valvesoftware.com/wiki/SteamCMD) и установка DayZ Server
- **bercon-cli.exe** — в корне проекта или путь в `rcon.client_path` в `config.json` (см. [CONFIG.md](docs/CONFIG.md))

## Возможности

- Несколько серверов: start / stop / restart
- WatchDog — автоперезапуск при падении (`auto_restart`, интервал `settings.watchdog_interval`, по умолчанию 10 с)
- **Planned restart** — рестарт по интервалу от 00:00 с RU/EN предупреждениями, lock и kick на T-5 (настройка на карточке сервера)
- Проверка и синхронизация модов (`mod_list.txt`, junction, Steam Web API)
- CRON-рестарты (legacy) по `scheduler.restart_schedule`
- RCON: say, lock, kick, graceful shutdown
- Web UI, REST API, WebSocket логов
- **Live stats** на карточке: FPS, игроки X/max, список ников
- **Игровой чат** на карточке: ExpLog + admin say (24 ч история)
- Хуки `beforeStart` / `afterStop`
- Сборка в один EXE (`build.bat`)

## Быстрый старт

### 1. Клонировать и зависимости

```powershell
git clone https://github.com/<user>/dayz_manager.git
cd dayz_manager
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. RCON-клиент

Скачайте [bercon-cli](https://github.com/WoozyMasta/bercon-cli) и положите `bercon-cli.exe` в корень проекта  
или укажите путь в `config.json` → `rcon.client_path` (см. шаблон).

### 3. Конфиг

```powershell
copy config\config-host-template.json config\config.json
```

В `config\config.json` обязательно задайте:

| Поле | Что указать |
|------|-------------|
| `auth.api_key` | Свой ключ (не `change_this_api_key` — иначе менеджер не стартует) |
| `steam.steamcmd_path`, `steam.workshop_path` | Пути к SteamCMD и Workshop |
| `servers[].path`, порты | Папка и порты вашего dedicated server |
| `servers[].rcon_password` | Как в BattlEye `BEServer_*.cfg` |

Пароль Steam — через `DAYZ_STEAM_USERNAME` / `DAYZ_STEAM_PASSWORD` или поля `steam.*` (см. [CONFIG.md](docs/CONFIG.md)).

`config/config.json` **не в git** — только на вашей машине.

### 4. Запуск

```powershell
python src/main.py
```

Откройте **http://127.0.0.1:8000** → введите тот же `auth.api_key` в поле API Key (сохранится в браузере).

### 5. Проверка

```powershell
pytest
# или smoke (менеджер должен быть запущен):
set API_KEY=ваш_ключ_из_config
test_system.bat
```

Дальше: [RUNBOOK.md](docs/RUNBOOK.md) (BattlEye, firewall), [DEPLOY.md](docs/DEPLOY.md) (EXE на хост).

## Production (хост)

На сервере обычно только **EXE** и локальный `config/config.json` (не в git).

1. Собрать: `build.bat` → `dist\DayZManager.exe`
2. Скопировать EXE на хост; **не перезаписывать** рабочий `config.json`
3. Шаблоны: `config/config-host-template.json`, `config/config-host-nru90-template.json`

Подробно: [docs/DEPLOY.md](docs/DEPLOY.md), чеклист: [docs/RUNBOOK.md](docs/RUNBOOK.md).

## Структура

```
dayz_manager/
├── src/           # Python: core, api, notifications
├── web/           # UI
├── config/        # config.json (локально, в .gitignore)
├── hooks/         # Кастомные хуки
├── scripts/       # test_stability_banov.py, start_banov_direct.py
├── docs/          # Актуальная документация
├── build.bat
└── README.md
```

## Ветка и релизы

Актуальная ветка: **`main`**. Фазы стабилизации и admin UI (planned restart, live stats, чат) влиты — см. [CHANGELOG.md](docs/CHANGELOG.md) и [ROADMAP.md](docs/ROADMAP.md).

Планы масштабирования (интернет, карта, магазин, SaaS): [docs/PRODUCT_ARCHITECTURE.md](docs/PRODUCT_ARCHITECTURE.md).

## Скрипты проверки (Banov)

```powershell
python scripts/test_stability_banov.py
python scripts/start_banov_direct.py   # sync + start без SteamCMD pre-download
```

См. [docs/TESTING.md](docs/TESTING.md).
