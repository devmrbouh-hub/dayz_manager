# Roadmap — DayZ Server Manager

**Languages:** [English](../ROADMAP.md) · [Русский](ROADMAP.md)

**Обновлено:** 2026-06-21  
**Текущий этап:** **Этап 3 — Расширение admin UI** (Приоритет 1)

Фазы 1–2 влиты в **`main`** — см. [CHANGELOG.md](CHANGELOG.md).  
Архитектура и границы продукта: [PRODUCT_ARCHITECTURE.md](PRODUCT_ARCHITECTURE.md).  
Planned restart, live stats, чат — проверено на reference-хосте (2026-05).

**Нумерация пунктов:** `этап.подпункт` (например **1.4**, **3.2.3**) — для ссылок в коммитах и issue.

**Сверка с кодом (2026-06-21):** этапы **0–2** закрыты. Этап **3** — в backlog; часть смежного функционала уже есть (см. таблицу ниже), но пункты **3.x** не отмечены выполненными, пока нет целевого UI/фичи.

---

## Путь развития

| Фаза | Этапы | Статус | Результат |
|------|-------|--------|-----------|
| Стабилизация | 0 | ✅ | SERVER_LOCK, multi-instance, mod sync |
| Admin UI MVP | 1 | ✅ | planned restart, RPT, chat, live stats |
| Host hardening | 2 | ✅ | общий кэш `w:`, поздний RPT, frozen EXE, UI v1.0.2 |
| Расширение UI | 3 | **сейчас** | scheduler, RCON presets, config editor |
| Операции | 4 | — | backup, audit, health, notifications |
| DayZ-специфика | 5 | — | ban list, поиск логов, профили запуска |

### Топ-5 для следующего MVP

1. Редактор конфигов и mod_list (**3.4**)
2. Preset RCON-команды (**3.2**)
3. Backup / rollback (**4.1**)
4. Аудит + уведомления (**4.2**, **4.5**)
5. Health dashboard (**4.3**)

---

## Этап 0 — Стабилизация ✅

См. [CHANGELOG.md](CHANGELOG.md) — секция `feature/stability`.

- [x] **0.1** SERVER_LOCK и безопасный start/stop (`start_confirm_timeout`)
- [x] **0.2** Единая модель lock для `prepare_server_for_start` и WatchDog
- [x] **0.3** Несколько инстансов на одном хосте
- [x] **0.4** ModSync: junction `server\@Mod` → `!Workshop` + копирование `.bikey`
- [x] **0.5** ModCheck через Steam Web API; Workshop ID только цифровые
- [x] **0.6** `+workshop_download_item` — отдельные argv SteamCMD
- [x] **0.7** CRON (`scheduler.restart_schedule`), WatchDog, hooks
- [x] **0.8** `PUT /api/settings`: hot-reload `mod_check_interval`
- [x] **0.9** PID / `.stopped`: проверка exe, восстановление при ручном запуске
- [x] **0.10** Хуки и frozen EXE: базовый путь рядом с `DayZManager.exe`

---

## Этап 1 — Admin UI MVP ✅

Проверено на reference-хосте (2026-05). См. [CHANGELOG.md](CHANGELOG.md).

### Planned restart

- [x] **1.1** Интервал от 00:00 (`interval_minutes`)
- [x] **1.2** Этапы T-30 / T-15 / T-10 / T-5 / T-0
- [x] **1.3** RU + EN say на каждом этапе
- [x] **1.4** Lock + kick all на T-5

### Web UI и API

- [x] **1.5** Блок Restart на карточке сервера (auto + planned)
- [x] **1.6** Save настроек рестарта с карточки
- [x] **1.7** Отображение Next restart (`next_restart_at`)
- [x] **1.8** API: `planned_restart`, валидация interval / test_mode

### RCON

- [x] **1.9** Парсер bercon-cli `players` (колонка admin)
- [x] **1.10** Bilingual say (RU + EN)
- [x] **1.11** Lock и kick_all для planned restart

### RPT tail + READY

- [x] **1.12** `ServerRptWatcher`, tail RPT, ring buffer
- [x] **1.13** Фазы `startup_phase`, маркер IdleMode (READY)
- [x] **1.14** `hide_console` — старт без окна DayZ
- [x] **1.15** WebSocket `/ws/servers/{id}/logs`, Server log на карточке

### Live stats на карточке

- [x] **1.16** FPS из RPT (`server_fps`)
- [x] **1.17** Игроки X/max (`players`, `max_players` из `serverDZ.cfg`)
- [x] **1.18** Раскрывающийся список ников (RCON `players` ~5 с)

### Игровой чат

- [x] **1.19** ExpLog tail 24 ч, только `[Chat - *]`
- [x] **1.20** WebSocket `/ws/servers/{id}/chat`
- [x] **1.21** `POST /chat/say` — admin say из UI
- [x] **1.22** Wall-clock timestamps; RCON inject для broadcast

### Server log UI

- [x] **1.23** Инкрементальный DOM (`syncServers`, `updateServerCard`)
- [x] **1.24** Append лога по WebSocket без моргания (`app.js?v=12`)

### Mod check

- [x] **1.25** Steam Web API через `certifi` (Windows без `Common Files\SSL\cert.pem`)

---

## Этап 2 — Host hardening и v1.0.2 ✅

См. [CHANGELOG.md](CHANGELOG.md) — секции v1.0.2 и host hardening.

- [x] **2.1** Общий кэш `w:{workshop_id}` + миграция legacy `server_id:mod_id`
- [x] **2.2** Skip SteamCMD, если remote-версия совпадает с кэшем и папка Workshop не пуста
- [x] **2.3** Fallback: при сбое SteamCMD принять существующую папку Workshop (WARN)
- [x] **2.4** Поздний RPT attach до `max(60, settings.startup_ready_timeout_sec)`
- [x] **2.5** Frozen EXE: `data/mod_versions.json` рядом с `DayZManager.exe`
- [x] **2.6** Owned SERVER_LOCK при shared mod update (без удаления чужих lock)
- [x] **2.7** Очистка orphan-процесса и `server.pid` при неудачном старте
- [x] **2.8** Restart прерывается, если stop не подтверждён
- [x] **2.9** Статика: защита от traversal за пределы `web/`
- [x] **2.10** Панель логов менеджера свёрнута по умолчанию (`<details>`)
- [x] **2.11** Кнопка **Открыть папку** в шапке карточки (`POST .../open-folder`)

---

## Этап 3 — Расширение admin UI

**Фокус:** Приоритет 1 из прежнего backlog.

### Частично в коде (этап 3 не закрыт)

| Пункт | Уже есть | Чего не хватает для `[x]` |
|-------|----------|-------------------------|
| **3.1.1** | Legacy `scheduler.restart_schedule`: `time`, `days`, `cron` — см. [CONFIG.md](CONFIG.md) | UI и единая модель с `planned_restart` (интервал от 00:00) |
| **3.2.1** | Admin say: `POST /api/servers/{id}/chat/say` (п. **1.21**) | Общая RCON preset-панель, не только чат |
| **3.3.1** | Game-port на карточке (`:port`) | Query-port на карточке |
| **3.5** | `restart()` ждёт stop; planned restart — say/lock/kick | Единый сценарий say → save → shutdown → verify → start из UI |

### 3.1 Расширение планировщика

- [ ] **3.1.1** Дни недели и фиксированное время (дополнение к интервалу от 00:00)
- [ ] **3.1.2** Несколько шаблонов расписания на сервер

### 3.2 Preset-команды RCON

- [ ] **3.2.1** `say` из UI
- [ ] **3.2.2** `kick`, `ban` из UI
- [ ] **3.2.3** `save`, `shutdown` из UI
- [ ] **3.2.4** Массовые предупреждения вне planned restart

### 3.3 Расширенный статус сервера

- [ ] **3.3.1** Game-port / query-port на карточке
- [ ] **3.3.2** RCON alive, uptime
- [ ] **3.3.3** Текущая карта / preset

### 3.4 Редактор конфигов в UI

- [ ] **3.4.1** `serverDZ.cfg`
- [ ] **3.4.2** `mod_list.txt`
- [ ] **3.4.3** Launch args
- [ ] **3.4.4** BattlEye (`BEServer_*.cfg`)

### 3.5 Безопасный restart flow

- [ ] **3.5.1** RCON say (предупреждение)
- [ ] **3.5.2** RCON save
- [ ] **3.5.3** RCON shutdown
- [ ] **3.5.4** Проверка подтверждённого stop
- [ ] **3.5.5** Start после успешного stop

---

## Этап 4 — Операции и мониторинг

- [ ] **4.1** Backup / rollback конфигов и mod_list
- [ ] **4.2** Аудит действий (кто start/stop/sync)
- [ ] **4.3** Health dashboard (порты, ключи, SteamCMD, конфликты)
- [ ] **4.4** Pre-flight валидация перед start
- [ ] **4.5** Telegram / Discord уведомления (модуль есть, не подключён)

---

## Этап 5 — DayZ-специфика

- [ ] **5.1** Ban list / whitelist / priority queue
- [ ] **5.2** Поиск по логам сервера и BattlEye
- [ ] **5.3** Профили запуска: prod / test / event
- [ ] **5.4** Сравнение конфигов между серверами

---

## Вне scope (обсуждалось отдельно)

Улучшения без отдельного этапа; не блокируют Этап 3:

- Не блокировать WatchDog при failed SteamCMD download, если sync OK
- Ожидание снятия `SERVER_LOCK` в `prepare_server_for_start`
- Пометка `mod_versions` при недоступном Steam API

---

## Как вести roadmap

1. Ставить `[x]` после коммита с готовым пунктом; в коммите или issue указывать номер (**например `roadmap 3.4.2`**).
2. Блокеры — в [CHANGELOG.md](CHANGELOG.md) или issue на GitHub.
3. Не дублировать сюда API, схемы и детали ModCheck — см. [HOW_IT_WORKS.md](HOW_IT_WORKS.md), [API.md](API.md).
4. При смене приоритета помечать пункт «отложено» и кратко почему.
5. Обновлять ru и en версии синхронно; не менять номера уже закрытых пунктов.
