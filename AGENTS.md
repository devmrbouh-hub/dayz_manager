# Карта для агента

Инструкция агенту, который правит этот репозиторий. Учебник админа здесь не дублируется: человеку в [README.ru.md](README.ru.md) два входа к одному Start, DayZ Server менеджер не ставит, подробности хоста в [docs/ru/DEPLOY.md](docs/ru/DEPLOY.md).

## Кто чем владеет

- `ServerManager` в [src/core/server_mgr.py](src/core/server_mgr.py) владеет процессом, pid и `.stopped`.
- `Scheduler` в [src/core/scheduler.py](src/core/scheduler.py) владеет расписанием и группой модов.
- `RconClient` в [src/core/rcon_client.py](src/core/rcon_client.py) владеет очередью команд одного host:port.
- Слоты планового рестарта считает [src/core/planned_restart.py](src/core/planned_restart.py). HTTP-вызовы в [src/api/routes.py](src/api/routes.py). **ModSync** в [src/core/mod_sync.py](src/core/mod_sync.py): список имён — `mod_list.txt`; существующие `@Мод` в `servers[].path` не заменяет; без них junction при известном Workshop id.

Новые классы и интерфейсы ради одного вызова не вводить.

## Правила, которые из соседних строк не читаются

- `.stopped` пишут только кнопка Stop и кнопка «Выключить». Плановый рестарт и моды файл не ставят.
- WatchDog на первом опросе только запоминает baseline и никого не стартует.
- `say` не сдвигает время рестарта и не выбирает вид остановки.
- Файловый `SERVER_LOCK` берётся раньше lock процесса.
- Команды одного host:port идут по одной. Опрос игроков сначала берёт свой poll-lock, потом RCON.

## Что не трогать без просьбы

Парсеры игроков, RPT, чат и пути Steam не переписывать. Discord из [src/main.py](src/main.py) не подключать, пока об этом не попросили.

Не коммитить `config/config.json`, `.ci_venv/`, `.ci_logs.zip` и секреты. Документы править парой [docs/](docs/INDEX.md) и [docs/ru/](docs/ru/INDEX.md).

Проверка: `python -m pytest tests`.
