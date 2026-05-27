# Документация DayZ Manager

Актуальная документация проекта.

## Начало работы

| Документ | Содержание |
|----------|------------|
| [RUNBOOK.md](RUNBOOK.md) | Чеклист: BattlEye, Steam, firewall, smoke tests |
| [DEPLOY.md](DEPLOY.md) | Новый хост, EXE, служба, workflow merge → build → хост |
| [CONFIG.md](CONFIG.md) | `config.json`, `planned_restart`, переменные окружения |

## Эксплуатация

| Документ | Содержание |
|----------|------------|
| [HOW_IT_WORKS.md](HOW_IT_WORKS.md) | WatchDog, SERVER_LOCK, моды, planned restart, Web UI |
| [API.md](API.md) | REST, WebSocket, `planned_restart`, авторизация |
| [RUNBOOK.md](RUNBOOK.md) | Типовые проблемы и быстрые проверки |

## Разработка и релизы

| Документ | Содержание |
|----------|------------|
| [CHANGELOG.md](CHANGELOG.md) | История: стабилизация фазы 1, planned restart фазы 2 |
| [TESTING.md](TESTING.md) | План T1–T6, T4b planned restart, чек-лист |
| [ROADMAP.md](ROADMAP.md) | Фаза 2: сделано и backlog |
| [PRODUCT_ARCHITECTURE.md](PRODUCT_ARCHITECTURE.md) | Масштабирование: Cloud, Agent, Bridge, магазин, SaaS |

## Шаблоны конфигурации

- `config/config-host-template.json` — один сервер
- `config/config-host-nru90-template.json` — несколько серверов (пример multi-host)
