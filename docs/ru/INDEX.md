# Документация DayZ Manager

**Languages:** [English](../INDEX.md) · [Русский](INDEX.md)

Актуальная документация проекта (русский). English: [docs/](../INDEX.md).

## Синхронизация документации

При изменении документации обновляйте **оба** каталога — [docs/ru/](.) и [docs/](../INDEX.md) — в одном PR (или отдельный issue). Источник истины по фактам — код и шаблоны `config/*.json`.

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
| [RELEASES.md](RELEASES.md) | Скачать готовый EXE с GitHub Releases |
| [ROADMAP.md](ROADMAP.md) | Фаза 2: сделано и backlog |
| [PRODUCT_ARCHITECTURE.md](PRODUCT_ARCHITECTURE.md) | Масштабирование: Cloud, Agent, Bridge, магазин, SaaS |

## Шаблоны конфигурации

- `config/config-host-template.json` — один сервер
- `config/config-host-nru90-template.json` — несколько серверов на одном хосте (пример)
