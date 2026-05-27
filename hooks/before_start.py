"""Пример хука beforeStart"""

def run(server_config):
    """
    Вызывается перед запуском сервера.

    Args:
        server_config (dict): Конфигурация сервера
    """
    server_id = server_config['id']
    server_name = server_config['name']

    print(f"[HOOK] beforeStart для {server_name} ({server_id})")

    # Пример: создать бэкап конфига
    # import shutil
    # from pathlib import Path
    # from datetime import datetime
    #
    # server_dir = Path(server_config['path'])
    # config_file = server_dir / server_config.get('config_file', 'serverDZ.cfg')
    #
    # if config_file.exists():
    #     backup_dir = server_dir / "config_backups"
    #     backup_dir.mkdir(exist_ok=True)
    #
    #     timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    #     backup = backup_dir / f"serverDZ_{timestamp}.cfg"
    #     shutil.copy2(config_file, backup)
    #     print(f"[HOOK] Config backup created: {backup.name}")

    # Пример: проверить наличие модов
    # mods = server_config.get('mods', [])
    # print(f"[HOOK] Mods to load: {len(mods)}")

    print(f"[HOOK] beforeStart завершён для {server_name}")
