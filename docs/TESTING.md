# Тестирование

**Последнее обновление:** 2026-05-25  
**Ветка:** `master` (admin UI: live stats, игровой чат, скрытая консоль)

## Предварительные условия

- [ ] Менеджер запущен (`python src/main.py` или `DayZManager.exe`)
- [ ] `bercon.exe` / `bercon-cli.exe` доступен (см. `rcon.client_path`)
- [ ] SteamCMD настроен; при `credentials` — env или ручной login
- [ ] BattlEye в профиле (`Instance_X\BattlEye\`)
- [ ] RCON в `config.json` совпадает с BattlEye cfg
- [ ] Для T1/T6/T4b — DayZ **запущен**

---

## Автотесты RPT / READY

Без запуска DayZ — pytest покрывает §6–§7 плана (watcher, server_mgr, API/WS, UI helpers).

```powershell
cd dayz_manager
pip install -r requirements-dev.txt
python -m pytest tests/ -v
node --test tests/test_server_status.mjs
```

| Набор | Файл | Что проверяет |
|-------|------|----------------|
| Watcher | `tests/test_server_rpt_watcher.py` | фазы, маркер, FPS, lazy attach, … |
| Chat | `tests/test_server_chat_watcher.py` | парс ExpLog, history, tail |
| Live stats | `tests/test_live_stats.py` | FPS, maxPlayers, parse_players |
| ServerManager | `tests/test_server_mgr_rpt.py` | begin/end session, hide console (STARTUPINFO) |
| API/WS | `tests/test_api_rpt.py`, `tests/test_api_chat.py` | RPT/READY, chat/say |
| UI | `tests/test_server_status.mjs` | STOPPED/STARTING/READY, фильтр WEAPON |

**Последний прогон (2026-05-25):** `pytest` — 56+ passed; `node --test tests/test_server_status.mjs` — 9 passed.

**Banov (2026-05-25, ручная проверка):** OK — live stats (FPS, ники игроков), игровой чат (ExpLog + say + planned restart T-5/T-10), проверка модов Steam API, скрытая консоль.

---

## UI — блок Restart на карточке сервера

1. Открыть `http://127.0.0.1:8000`, ввести API key, **Refresh**.
2. На карточке сервера видны: статус, кнопки Start/Stop/Restart, блок **Restart**.
3. **Auto restart** — переключатель сразу шлёт `PUT` (поле `auto_restart`).
4. **Planned restart** — toggle, Interval (2/3/4/6 h, Custom, Test mode), **Save planned restart**.
5. После Save — **Next:** показывает `next_restart_at`; значение совпадает с `GET /api/servers/{id}`.
6. Add Server — только базовые поля; после добавления на карточке есть блок Restart с дефолтами (planned off, 4 h).

**Banov (2026-05-24):** OK — planned restart test mode 15 мин, kick на T-5, UI на карточке.

---

## T7 — RPT log и READY

**Цель:** скрытая консоль, фазы STOPPED → STARTING → READY, live RPT на карточке.

### Базовый сценарий

1. **Ctrl+F5** на Web UI (`app.js?v=12`).
2. **Start** — отдельного окна DayZ нет (`hide_console: true`, только старт через менеджер).
3. Статус: **STARTING** → **READY**; на карточке **FPS** и **Игроки X/Y** обновляются (~5 с).
4. Раскрыть **Игроки онлайн** — список **ников** (не `true`/`false`); или «Никого онлайн».
5. Раскрыть **Server log (RPT)** — live tail; READY-маркер подсвечен.
6. **Stop** → **STOPPED**.

## T7b — Игровой чат

1. Сервер **READY**, Expansion: `LogsSettings.json` → `"Chat": 1`.
2. Раскрыть **Игровой чат** — история за 24 ч (если есть в ExpLog), live новые строки; **время** совпадает с локальным.
3. Ввести текст → **Отправить** — сообщение в игре (RCON `say -1`); в UI метрики FPS/игроков **не** дублируются в чат.
4. Написать в global chat в игре — строка появляется в блоке чата.
5. Planned restart — say RU/EN и сообщение перед kick (T-5) видны в ленте.

**Banov (2026-05-25):** OK.

## T-console — скрытое окно

| # | Действие | Ожидание |
|---|----------|----------|
| 1 | Start из UI | Нет окна консоли `DayZServer_x64.exe` |
| 2 | Запуск через `.bat` / exe вручную | Окно может появиться (вне менеджера) |

### API

```powershell
curl http://127.0.0.1:8000/api/servers/banov
# startup_phase, ready_at, current_rpt, startup_warning

curl "http://127.0.0.1:8000/api/servers/banov/logs/tail?lines=50"
```

### Пограничные

| # | Действие | Ожидание |
|---|----------|----------|
| 4 | Kill `DayZServer_x64.exe` во время STARTING | STOPPED, tail-thread остановлен |
| 5 | Kill после READY | STOPPED, не зависает STARTING |
| 6 | Restart | STARTING → READY снова |
| 7 | Открыть log → закрыть | WS отключён; READY на карточке остаётся |
| 8 | Рестарт только менеджера при живом DayZ | lazy attach → READY без Start |
| 9 | Неверный `profiles` в config | `startup_warning: rpt_not_found` |

### Производительность (smoke)

| # | Проверка |
|---|----------|
| 10 | Tail при загрузке: UI отзывчив, CPU tail-thread < ~5% одного ядра |
| 11 | Две вкладки UI — обе получают строки по WS |

**Banov (2026-05-25):** OK — Start → STARTING → READY, Server log, WEAPON filter.

### T7b — Server log без моргания

1. **Ctrl+F5** (`app.js?v=6`).
2. Сервер **остановлен** — открыть **Server log (RPT)**: панель не мигает, пустой лог или статус stopped.
3. **Start** — лог открыт: строки **добавляются вниз**, блок `<pre>` **не очищается** при poll каждые 3 с.
4. Toggle **Hide WEAPON** — строки скрываются/показываются **без** перезагрузки лога.
5. **Refresh** в шапке Servers — карточка обновляется, открытый лог и накопленные строки сохраняются.

**Banov (2026-05-25):** OK — без моргания при открытии лога и во время STARTING.

---

## T1 — WatchDog после kill PID

1. Start через UI/API.
2. Подождать 5 с, завершить `DayZServer_x64.exe` в диспетчере задач.
3. Через 10–15 с проверить логи.

**Ожидание:**

```
[WatchDog] banov is down, auto restarting...
Server banov started with PID: ...
```

**На Banov (2026-05-23):** WatchDog **сработал**, полный рестарт **не завершился** — `Pre-start mod download failed` (SteamCMD login timeout). Обход: `scripts/start_banov_direct.py`.

---

## T2 — Mod update без гонки

1. `POST /api/mods/check` с API key.
2. При наличии обновлений — дождаться цикла ModCheck или `POST /api/mods/sync`.
3. Во время update не должно быть параллельного WatchDog restart на том же сервере (`SERVER_LOCK`).

**Проверки:**

- `details.<server>.tracked_mods` / `skipped_mods`
- Junction: `dir D:\Banov\@* /AL` (ссылки на !Workshop)
- `data/mod_versions.json` обновляется

---

## T3 — Failed start + WatchDog

1. Симулировать ошибку старта (неверный exe или занятый порт).
2. Убедиться, что `.stopped` **снят** после ошибки.
3. Исправить условие — WatchDog должен снова поднять сервер при `auto_restart: true`.

---

## T4 — CRON restart (legacy)

В `config.json` добавить слот на ближайшую минуту:

```json
"restart_schedule": [
  { "server_id": "banov", "time": "14:37", "days": ["sat"] }
]
```

**Ожидание:** немедленный restart в due-слот (без многоэтапных предупреждений).

**Banov:** не прогонялся (`restart_schedule: []`).

---

## T4b — Planned restart (интервал от 00:00)

1. На карточке сервера в блоке **Restart** или через API включить test mode, `interval_minutes: 15`.
2. Убедиться, что RCON работает: `POST /api/servers/banov/rcon/test`.
3. Дождаться этапов T-10, T-5, T-0 (для interval 15 пропускаются T-30 и T-15).

**Ожидание:**

- T-10 / T-5: два say подряд (RU, затем EN) в игровом чате
- T-5: say → пауза 5 с → `#lock` → kick всех онлайн (сообщение успевают прочитать)
- T-0: сервер перезапущен, PID обновился

**Banov (2026-05-24):** OK — T-10/T-5 say, lock + kick, restart на T-0; bercon-cli table parse для kick.

```powershell
curl -X PUT http://127.0.0.1:8000/api/servers/banov `
  -H "X-API-Key: YOUR_KEY" `
  -H "Content-Type: application/json" `
  -d "{\"planned_restart\": {\"enabled\": true, \"interval_minutes\": 15, \"test_mode\": true}}"
```

---

## T5 — PUT mod_check_interval (hot-reload)

```powershell
curl -X PUT http://127.0.0.1:8000/api/settings `
  -H "X-API-Key: YOUR_KEY" `
  -H "Content-Type: application/json" `
  -d "{\"mod_check_interval\": 601}"
```

**Ожидание:** `GET /api/settings` → 601; в логе перезапуск задачи ModCheck без рестарта менеджера.

**Banov:** OK.

---

## T6 — RCON test

```powershell
curl -X POST http://127.0.0.1:8000/api/servers/banov/rcon/test `
  -H "X-API-Key: YOUR_KEY"
```

**Ожидание:** `"success": true`, `"message": "RCON test OK"`.

**Если fail:**

- DayZ запущен, BattlEye инициализирован (1–2 мин после старта)
- Порт/пароль = `BEServer_x64.cfg`
- `netstat -ano -p udp | findstr <rcon_port>`

**Banov:** OK после настройки BattlEye/RCON (2026-05-24).

---

## Дополнительные сценарии (из базового плана)

| # | Сценарий | Кратко |
|---|----------|--------|
| 4 | Graceful Stop | UI Stop → RCON shutdown или taskkill в `preferred` |
| 5 | Notify игроков | При mod update / CRON — два say подряд (RU, затем EN); при mod update — имена модов без `@` |
| 7 | SteamCMD session | Пустые credentials + сохранённая сессия |

---

## Автоматические скрипты

```powershell
cd dayz_manager
python scripts/test_stability_banov.py
python scripts/start_banov_direct.py
```

### `test_system.bat` (smoke через curl)

Перед запуском задайте API-ключ из `config/config.json`:

```powershell
set API_KEY=your_api_key_from_config
test_system.bat
```

---

## Результаты Banov

| Проверка | 2026-05-23 | 2026-05-24 | 2026-05-25 |
|----------|------------|------------|------------|
| lock acquire/release | OK | OK | OK |
| effective_mods | OK (22 мода) | OK | OK |
| PUT mod_check_interval | OK | OK | OK |
| GET /api/servers | OK | OK | OK |
| WatchDog после kill | Частично (SteamCMD) | — | — |
| RCON test | Fail (timeout) | OK | OK |
| Planned restart T4b | — | OK | OK |
| UI Restart block | — | OK | OK |
| Live stats + ники | — | — | OK |
| Игровой чат | — | — | OK |
| Steam mod check (certifi) | — | — | OK |

**Действия на хосте:** починить SteamCMD login; проверить BattlEye RCON; удалить зависший `SERVER_LOCK` при сбое mod-update.

---

## Чек-лист

| Тест | Статус | Примечание |
|------|--------|------------|
| UI Restart block | ✅ | Banov 2026-05-24 |
| T4b Planned restart | ✅ | Banov 2026-05-24 |
| T6 RCON | ✅ | Banov 2026-05-24 |
| T1 WatchDog | ⬜ | |
| T2 Mod update / lock | ⬜ | |
| T3 Failed start | ⬜ | |
| T4 CRON (legacy) | ⬜ | |
| T5 Settings hot-reload | ✅ | Banov 2026-05-23 |
| T7 RPT + READY | ✅ | Banov 2026-05-25 |
| T7b Игровой чат | ✅ | Banov 2026-05-25 |
| T7c Live stats / ники | ✅ | Banov 2026-05-25 |
| T7b Log без моргания | ✅ | Banov 2026-05-25 |
| Mod check Steam API | ✅ | Banov 2026-05-25 |
| pytest RPT/chat/stats | ✅ | 56+ passed, 2026-05-25 |
| node server_status | ✅ | 9 passed, 2026-05-25 |

## Логи

- UI: **Server log (RPT)** на карточке / `ws://host:8000/ws/servers/{id}/logs`
- UI: Live Logs (менеджер) / `ws://host:8000/ws/logs`
- Файл: `logs/manager.log`
- API: `GET /api/logs`, `GET /api/servers/{id}/logs/tail`
- DayZ: `{path}/{profiles}/DayZServer_x64_*.RPT`, BattlEye logs
