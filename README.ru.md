# DayZ Server Manager

**Languages:** [English](README.md) · [Русский](README.ru.md)

Надоели батники? Этот менеджер заменяет их удобным веб-интерфейсом.
Запускайте серверы, обновляйте моды, следите за игроками — всё из браузера.

> 👉 **Просто хотите запустить?** Скачайте EXE → распакуйте → отредактируйте config.json → запустите. [К быстрому старту ↓](#production-хост)

**Лицензия:** [MIT](LICENSE) · **Скачать:** [Releases](https://github.com/devmrbouh-hub/dayz_manager/releases)

## Скриншоты

![DayZ Manager — список серверов](docs/images/ui-servers-compact.png)
![DayZ Manager — карточка сервера](docs/images/ui-server-expanded.png)

## Что умеет

- Запуск / остановка / рестарт нескольких серверов из браузера
- WatchDog — автоперезапуск при падении
- Обновление модов через SteamCMD с предупреждениями игрокам (5 мин)
- Плановые рестарты с обратным отсчётом в игре (RU/EN)
- Live-статистика: FPS, список игроков с никами
- Игровой чат прямо в браузере
- RCON: say, kick, lock, graceful shutdown
- Один EXE для Windows — установка не нужна

## Быстрый старт (EXE — рекомендуется)

**Нужно:** DayZ Dedicated Server + SteamCMD + настроенный BattlEye RCON.

1. Скачайте архив **`dayz_manager-*-windows-x64.zip`** из [Releases](https://github.com/devmrbouh-hub/dayz_manager/releases)
2. Распакуйте на игровой хост
3. Скопируйте `config\config-host-template.json` → `config\config.json`
4. Отредактируйте `config.json` — укажите 4 параметра:

| Поле | Что указать |
|------|-------------|
| `auth.api_key` | Любой пароль на ваш выбор |
| `steam.steamcmd_path` | Путь к steamcmd.exe |
| `servers[].path` | Путь к папке DayZ сервера |
| `servers[].rcon_password` | Как в BEServer_*.cfg |

5. Запустите `DayZManager.exe`
6. Откройте **http://127.0.0.1:8000** и введите ваш api_key

Готово. Полный справочник конфига: [docs/ru/CONFIG.md](docs/ru/CONFIG.md)

## Production (хост)

### Вариант A — скачать Release (без сборки)

1. **[Releases](https://github.com/devmrbouh-hub/dayz_manager/releases)** → архив **`dayz_manager-*-windows-x64.zip`**
2. Распаковать; `config\config-host-template.json` → `config\config.json`, отредактировать
3. Запустить `DayZManager.exe` → http://127.0.0.1:8000

Инструкция: [docs/ru/RELEASES.md](docs/ru/RELEASES.md)

### Вариант B — собрать из исходников

1. `build.bat` → `dist\DayZManager.exe` (нужен `bercon-cli.exe` в корне проекта)
2. Скопировать EXE на хост; **не перезаписывать** рабочий `config.json`
3. Шаблоны: `config/config-host-template.json`, `config/config-host-nru90-template.json`

Подробно: [docs/ru/DEPLOY.md](docs/ru/DEPLOY.md), чеклист: [docs/ru/RUNBOOK.md](docs/ru/RUNBOOK.md).

## Структура

```
dayz_manager/
├── src/           # Python: core, api, notifications
├── web/           # UI
├── config/        # config.json (локально, в .gitignore)
├── hooks/         # Кастомные хуки
├── scripts/       # опциональные helper-скрипты
├── docs/          # документация (EN); docs/ru/ — русский
├── build.bat
└── README.md
```

## Ветка и релизы

Актуальная ветка: **`main`**. Фазы стабилизации и admin UI (planned restart, live stats, чат) влиты — см. [CHANGELOG.md](docs/ru/CHANGELOG.md) и [ROADMAP.md](docs/ru/ROADMAP.md).

Планы масштабирования (интернет, карта, магазин, SaaS): [docs/ru/PRODUCT_ARCHITECTURE.md](docs/ru/PRODUCT_ARCHITECTURE.md).

## Опциональные helper-скрипты

Не обязательны для первого запуска. Сервер: `DAYZ_MANAGER_SERVER` или первый в `config.json`.

```powershell
python scripts/test_stability_local.py
python scripts/start_server_direct.py   # sync + start без SteamCMD pre-download
```

См. [docs/ru/TESTING.md](docs/ru/TESTING.md).
