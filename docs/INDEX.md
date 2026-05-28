# DayZ Manager documentation

**Languages:** [English](INDEX.md) · [Русский](ru/INDEX.md)

Project documentation (English). Russian mirror: [docs/ru/](ru/INDEX.md).

## Documentation sync

When you change docs, update **both** [docs/](.) and [docs/ru/](ru/) in the same PR (or open a follow-up issue). Facts follow code and `config/*.json` templates.

## Getting started

| Document | Contents |
|----------|----------|
| [RUNBOOK.md](RUNBOOK.md) | Checklist: BattlEye, Steam, firewall, smoke tests |
| [DEPLOY.md](DEPLOY.md) | New host, EXE, service, merge → build → deploy workflow |
| [CONFIG.md](CONFIG.md) | `config.json`, `planned_restart`, environment variables |

## Operations

| Document | Contents |
|----------|----------|
| [HOW_IT_WORKS.md](HOW_IT_WORKS.md) | WatchDog, SERVER_LOCK, mods, planned restart, Web UI |
| [API.md](API.md) | REST, WebSocket, `planned_restart`, auth |
| [RUNBOOK.md](RUNBOOK.md) | Common issues and quick checks |

## Development and releases

| Document | Contents |
|----------|----------|
| [CHANGELOG.md](CHANGELOG.md) | History: phase 1 stabilization, phase 2 planned restart |
| [TESTING.md](TESTING.md) | Plan T1–T6, T4b planned restart, checklist |
| [ROADMAP.md](ROADMAP.md) | Phase 2: done and backlog |
| [PRODUCT_ARCHITECTURE.md](PRODUCT_ARCHITECTURE.md) | Scaling: Cloud, Agent, Bridge, shop, SaaS |

## Config templates

- `config/config-host-template.json` — single server
- `config/config-host-nru90-template.json` — multiple servers on one host (example)
