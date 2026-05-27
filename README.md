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

## Быстрый старт (разработка)

```powershell
cd dayz_manager
pip install -r requirements.txt
copy config\config-host-template.json config\config.json
# Отредактировать config\config.json (пути, порты, auth.api_key)
python src/main.py
# http://127.0.0.1:8000
```

`config/config.json` не коммитится в git — секреты и пути хоста только локально.

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

## Ветки и релизы

| Ветка | Назначение |
|-------|------------|
| `master` | Стабильная база |
| `feature/stability` | Фаза 1: lock, PID, CRON, settings API |
| `feature/admin-ui` | Фаза 2: planned restart, UI на карточке сервера — см. [CHANGELOG.md](docs/CHANGELOG.md) |

История изменений: [docs/CHANGELOG.md](docs/CHANGELOG.md).

Планы масштабирования (интернет, карта, магазин, SaaS): [docs/PRODUCT_ARCHITECTURE.md](docs/PRODUCT_ARCHITECTURE.md).

## Скрипты проверки (Banov)

```powershell
python scripts/test_stability_banov.py
python scripts/start_banov_direct.py   # sync + start без SteamCMD pre-download
```

См. [docs/TESTING.md](docs/TESTING.md).
