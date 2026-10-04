from pathlib import Path

from src.core.steam_paths import (
    is_suspicious_steam_library,
    resolve_steam_library_path,
    resolve_workshop_content_root,
    workshop_download_dir,
)


def test_resolve_steam_library_from_workshop_path():
    workshop = r"C:\Program Files (x86)\Steam\steamapps\common\DayZ\!Workshop"
    dayz_wrong = "C:\\"
    lib = resolve_steam_library_path(workshop, dayz_wrong)
    assert lib == Path(r"C:\Program Files (x86)\Steam")


def test_resolve_steam_library_from_dayz_install():
    workshop = r"C:\fake\!Workshop"
    dayz = r"D:\SteamLibrary\steamapps\common\DayZ"
    lib = resolve_steam_library_path(workshop, dayz)
    assert lib == Path(r"D:\SteamLibrary")


def test_suspicious_steam_library_detects_drive_root():
    assert is_suspicious_steam_library(Path("C:\\")) is True
    assert is_suspicious_steam_library(Path(r"C:\Program Files (x86)\Steam")) is False


def test_workshop_download_dir_matches_content_root(tmp_path):
    steam = tmp_path / "Steam"
    content = steam / "steamapps" / "workshop" / "content" / "221100" / "3726105026"
    content.mkdir(parents=True)
    workshop = steam / "steamapps" / "common" / "DayZ" / "!Workshop"
    workshop.mkdir(parents=True)
    dayz = steam / "steamapps" / "common" / "DayZ"
    root = resolve_workshop_content_root(str(workshop), str(dayz))
    assert root == steam / "steamapps" / "workshop" / "content" / "221100"
    assert workshop_download_dir(str(workshop), str(dayz), "3726105026") == content
