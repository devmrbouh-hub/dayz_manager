# GitHub Releases (готовый EXE)

**Languages:** [English](../RELEASES.md) · [Русский](RELEASES.md)

Если не хотите ставить Python и собирать `build.bat`, скачайте архив с **[GitHub Releases](https://github.com/devmrbouh-hub/dayz_manager/releases)**.

## Скачать

1. Откройте [Releases](https://github.com/devmrbouh-hub/dayz_manager/releases).
2. Скачайте **`dayz_manager-*-windows-x64.zip`** у последнего тега (например `v1.0.0`).
3. Распакуйте на хост с DayZ, например `C:\DayZManager\`.

## Что внутри ZIP

| Файл | Назначение |
|------|------------|
| `DayZManager.exe` | Менеджер (веб + API) |
| `bercon-cli.exe` | RCON (рядом с EXE или путь в config) |
| `config/config-host-template.json` | Скопировать в `config\config.json` и отредактировать |
| `README-RELEASE.txt` | Краткая установка |

## Первый запуск

```powershell
cd C:\DayZManager
mkdir config -Force
copy config\config-host-template.json config\config.json
notepad config\config.json
```

Минимум: `auth.api_key`, пути Steam, `servers[].path`, порты, `rcon_password` (как в BattlEye).

```powershell
.\DayZManager.exe
```

Браузер: **http://127.0.0.1:8000** → ввести API key.

Чеклист: [RUNBOOK.md](RUNBOOK.md), деплой: [DEPLOY.md](DEPLOY.md).

## Обновление

1. Остановить старый менеджер.
2. Заменить `DayZManager.exe` (и при необходимости `bercon-cli.exe`).
3. **Не перезаписывать** рабочий `config\config.json`.

## Сборка релиза (для себя)

```powershell
.\scripts\package-release.ps1
# Загрузить dist\release\dayz_manager-*-windows-x64.zip в GitHub Releases
```

Нужны `dist\DayZManager.exe` (`build.bat`) и `bercon-cli.exe` в корне проекта.
