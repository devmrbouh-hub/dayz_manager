"""Planned restart kick window and slot keys."""

from datetime import datetime

from src.core.planned_restart import (
    in_kick_window,
    restart_slot_key,
    minutes_until_next_restart,
    compute_next_restart_at,
    KICK_WINDOW_MIN_MINUTES,
    KICK_WINDOW_MAX_MINUTES,
)


def test_in_kick_window_bounds():
    assert in_kick_window(KICK_WINDOW_MIN_MINUTES - 1) is False
    assert in_kick_window(KICK_WINDOW_MIN_MINUTES) is True
    assert in_kick_window(KICK_WINDOW_MAX_MINUTES) is True
    assert in_kick_window(KICK_WINDOW_MAX_MINUTES + 1) is False


def test_restart_slot_key_stable_within_minute():
    now = datetime(2026, 10, 4, 11, 55, 42)
    interval = 240
    assert restart_slot_key(interval, now) == "2026-10-04 12:00"
    assert minutes_until_next_restart(interval, now) == 5


def test_restart_slot_key_changes_after_restart_minute():
    interval = 240
    before = datetime(2026, 10, 4, 11, 59, 0)
    at = datetime(2026, 10, 4, 12, 0, 0)
    assert restart_slot_key(interval, before) == "2026-10-04 12:00"
    assert restart_slot_key(interval, at) == "2026-10-04 12:00"
    after = datetime(2026, 10, 4, 12, 1, 0)
    assert restart_slot_key(interval, after) == "2026-10-04 16:00"


def test_compute_next_restart_at_aligns_with_slot_key():
    now = datetime(2026, 10, 4, 11, 55, 0)
    interval = 240
    target = compute_next_restart_at(interval, now)
    assert target is not None
    assert restart_slot_key(interval, now) == target.strftime("%Y-%m-%d %H:%M")
