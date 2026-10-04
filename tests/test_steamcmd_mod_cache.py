"""Workshop mod version cache is shared across servers (same Steam content path)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.core import steamcmd as steamcmd_module
from src.core.steamcmd import SteamCMD


@pytest.fixture
def steamcmd(tmp_path, monkeypatch):
    cache_file = tmp_path / "data" / "mod_versions.json"
    monkeypatch.setattr("src.core.steamcmd.MOD_VERSIONS_FILE", cache_file)
    config = MagicMock()
    config.get.side_effect = lambda key, default=None: {
        "steam.steamcmd_path": str(tmp_path / "steamcmd.exe"),
        "steam.dayz_install_path": str(tmp_path / "DayZ"),
        "steam.workshop_path": str(tmp_path / "DayZ" / "!Workshop"),
        "steam.auth_mode": "anonymous",
    }.get(key, default)
    (tmp_path / "steamcmd.exe").write_text("", encoding="utf-8")
    return SteamCMD(config)


def write_mod_cache(data: dict):
    import src.core.steamcmd as live_steamcmd

    cache_file = Path(live_steamcmd.MOD_VERSIONS_FILE)
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(data), encoding="utf-8")


def test_migrate_legacy_per_server_keys_to_workshop_cache(steamcmd, tmp_path):
    cache_file = steamcmd_module.MOD_VERSIONS_FILE
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(
        json.dumps(
            {
                "banov:2116157322": 1780062106,
                "Cherno:2116157322": 1775590039,
            }
        ),
        encoding="utf-8",
    )

    reloaded = SteamCMD(steamcmd.config)
    assert reloaded._get_cached_mod_time("2116157322") == 1775590039


def test_has_mod_update_after_shared_cache_merge_when_remote_newer(steamcmd):
    """Min merge keeps cache low enough to detect Workshop updates."""
    write_mod_cache({"w:2116157322": 1775590039})
    with patch.object(steamcmd, "_get_remote_mod_update_time", return_value=1780062106):
        with patch.object(steamcmd, "is_mod_present_locally", return_value=True):
            assert steamcmd.has_mod_update("banov", "2116157322", "@Licensed") is True


def test_has_mod_update_detects_stale_files_without_cache(steamcmd, tmp_path):
    mod_dir = steamcmd.get_mod_path("2116157322")
    mod_dir.mkdir(parents=True)
    mod_file = mod_dir / "meta.cpp"
    mod_file.write_text("// mod", encoding="utf-8")
    old_mtime = 1_600_000_000
    import os

    os.utime(mod_file, (old_mtime, old_mtime))
    remote = 1_780_062_106
    with patch.object(steamcmd, "_get_remote_mod_update_time", return_value=remote):
        assert steamcmd.has_mod_update("banov", "2116157322", "@Licensed") is True


def test_has_mod_update_uses_shared_cache_when_current(steamcmd):
    write_mod_cache({"w:2793893086": 1780062122})
    with patch.object(steamcmd, "_get_remote_mod_update_time", return_value=1780062122):
        assert steamcmd.has_mod_update("Cherno", "2793893086", "@Expansion") is False


def test_mark_mod_version_synced_updates_workshop_key(steamcmd):
    with patch.object(steamcmd, "_get_remote_mod_update_time", return_value=1780062106):
        steamcmd.mark_mod_version_synced("banov", "2116157322")
    assert steamcmd.mod_versions["w:2116157322"] == 1780062106


def test_has_mod_update_when_shared_cache_inflated_but_files_stale(steamcmd, tmp_path):
    mod_dir = steamcmd.get_mod_path("2116157322")
    mod_dir.mkdir(parents=True, exist_ok=True)
    mod_file = mod_dir / "meta.cpp"
    mod_file.write_text("// mod", encoding="utf-8")
    import os

    remote = 1_780_062_106
    os.utime(mod_file, (1_600_000_000, 1_600_000_000))
    write_mod_cache({"w:2116157322": remote})
    with patch.object(steamcmd, "_get_remote_mod_update_time", return_value=remote):
        assert steamcmd.has_mod_update("banov", "2116157322", "@Licensed") is True


def test_download_mod_skips_when_workshop_folder_exists_and_cache_current(steamcmd, tmp_path):
    mod_dir = steamcmd.get_mod_path("2793893086")
    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / "meta.cpp").write_text("// mod", encoding="utf-8")
    write_mod_cache({"w:2793893086": 1780062122})

    with patch.object(steamcmd, "_get_remote_mod_update_time", return_value=1780062122):
        with patch.object(steamcmd, "_append_login_args") as login:
            assert steamcmd.download_mod("2793893086", "@Expansion") is True
            login.assert_not_called()


def test_download_mod_accepts_existing_content_after_failed_steamcmd(steamcmd, tmp_path):
    mod_dir = steamcmd.get_mod_path("2993279164")
    mod_dir.mkdir(parents=True)
    (mod_dir / "meta.cpp").write_text("// mod", encoding="utf-8")

    with patch.object(steamcmd, "_get_remote_mod_update_time", return_value=1777465480):
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(
                stdout="ERROR",
                stderr="not logged on",
                returncode=0,
            )
            assert steamcmd.download_mod("2993279164", "@FutureLand_ServerPack") is True
    assert steamcmd._get_cached_mod_time("2993279164") is None
    assert steamcmd.should_sync_mod_cache_after_download() is False


def test_download_mod_success_syncs_cache_flag(steamcmd, tmp_path):
    mod_dir = steamcmd.get_mod_path("2993279164")
    mod_dir.mkdir(parents=True, exist_ok=True)
    with patch.object(steamcmd, "_get_remote_mod_update_time", return_value=1777465480):
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(
                stdout="Success. Item downloaded.",
                stderr="",
                returncode=0,
            )
            assert steamcmd.download_mod("2993279164", "@FutureLand_ServerPack") is True
    assert steamcmd.should_sync_mod_cache_after_download() is True
