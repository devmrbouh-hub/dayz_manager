"""Resolve Steam library and Workshop content paths from config."""

from __future__ import annotations

from pathlib import Path

WORKSHOP_APP_ID = "221100"


def resolve_steam_library_path(workshop_path: str, dayz_install_path: str) -> Path:
    """
    Folder passed to SteamCMD +force_install_dir (parent of steamapps/).
    Prefer deriving from steam.workshop_path (.../common/DayZ/!Workshop).
    """
    wp = Path(workshop_path or "")
    if wp.name.lower() == "!workshop":
        dayz_dir = wp.parent
        if dayz_dir.name.lower() == "dayz":
            steamapps = dayz_dir.parent.parent
            if steamapps.name.lower() == "steamapps":
                return steamapps.parent

    dayz_dir = Path(dayz_install_path or "")
    if dayz_dir.name.lower() == "dayz":
        steamapps = dayz_dir.parent.parent
        if steamapps.name.lower() == "steamapps":
            return steamapps.parent

    try:
        return dayz_dir.parent.parent.parent
    except IndexError:
        return dayz_dir


def resolve_workshop_content_root(workshop_path: str, dayz_install_path: str) -> Path:
    """steamapps/workshop/content/221100 (first existing candidate)."""
    workshop_alias_root = Path(
        workshop_path or r"C:\Program Files (x86)\Steam\steamapps\common\DayZ\!Workshop"
    )
    candidates: list[Path] = []

    try:
        candidates.append(
            workshop_alias_root.parent.parent.parent / "workshop" / "content" / WORKSHOP_APP_ID
        )
    except IndexError:
        pass

    dayz_dir = Path(dayz_install_path or r"C:\Program Files (x86)\Steam\steamapps\common\DayZ")
    try:
        candidates.append(dayz_dir.parent.parent / "workshop" / "content" / WORKSHOP_APP_ID)
    except IndexError:
        pass

    library = resolve_steam_library_path(workshop_path, dayz_install_path)
    candidates.append(library / "steamapps" / "workshop" / "content" / WORKSHOP_APP_ID)

    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        if candidate.exists():
            return candidate

    return candidates[0] if candidates else workshop_alias_root


def workshop_download_dir(workshop_path: str, dayz_install_path: str, mod_id: str) -> Path:
    """Target folder SteamCMD should populate for a Workshop item."""
    return resolve_workshop_content_root(workshop_path, dayz_install_path) / str(mod_id)


def is_suspicious_steam_library(path: Path) -> bool:
    """Drive root or too-shallow path — likely misconfigured dayz_install_path."""
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    parts = [p for p in resolved.parts if p not in ("/", "\\")]
    if len(parts) <= 1:
        return True
    if len(parts) == 2 and parts[0].endswith(":"):
        return True
    return False
