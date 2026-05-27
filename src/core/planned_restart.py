"""Плановый рестарт: интервал от 00:00, этапы предупреждений, расчёт следующего слота."""

from datetime import datetime, timedelta
from typing import Optional, Tuple


DEFAULT_PLANNED_RESTART = {
    'enabled': False,
    'interval_minutes': 240,
    'test_mode': False,
}

WARNING_STAGES = (30, 15, 10)
LOCK_KICK_STAGE = 5
RESTART_STAGE = 0
# Пауза после say на T-5, чтобы игрок успел прочитать перед kick
KICK_WARN_DELAY_SECONDS = 5


def normalize_planned_restart(raw: Optional[dict]) -> dict:
    """Вернуть planned_restart с дефолтами."""
    if not raw or not isinstance(raw, dict):
        return dict(DEFAULT_PLANNED_RESTART)
    result = dict(DEFAULT_PLANNED_RESTART)
    result.update(raw)
    return result


def validate_planned_restart(planned: dict) -> dict:
    """Валидировать и нормализовать planned_restart. ValueError при ошибке."""
    if not isinstance(planned, dict):
        raise ValueError('planned_restart must be an object')

    enabled = bool(planned.get('enabled', False))
    test_mode = bool(planned.get('test_mode', False))

    try:
        interval_minutes = int(planned.get('interval_minutes', DEFAULT_PLANNED_RESTART['interval_minutes']))
    except (TypeError, ValueError) as exc:
        raise ValueError('interval_minutes must be an integer') from exc

    if not enabled:
        return {
            'enabled': False,
            'interval_minutes': interval_minutes,
            'test_mode': test_mode,
        }

    if test_mode:
        if interval_minutes < 10 or interval_minutes > 59:
            raise ValueError('test_mode interval_minutes must be between 10 and 59')
    else:
        if interval_minutes < 60 or interval_minutes > 1440:
            raise ValueError('interval_minutes must be between 60 and 1440 (1–24 hours)')

    return {
        'enabled': True,
        'interval_minutes': interval_minutes,
        'test_mode': test_mode,
    }


def minutes_since_midnight(now: datetime) -> int:
    return now.hour * 60 + now.minute


def minutes_until_next_restart(interval_minutes: int, now: Optional[datetime] = None) -> int:
    """Минут до следующего слота рестарта от 00:00."""
    if interval_minutes <= 0:
        return 0

    now = now or datetime.now()
    current = minutes_since_midnight(now)
    remainder = current % interval_minutes
    if remainder == 0:
        return 0
    return interval_minutes - remainder


def compute_next_restart_at(interval_minutes: int, now: Optional[datetime] = None) -> Optional[datetime]:
    """Вычислить datetime следующего рестарта."""
    if interval_minutes <= 0:
        return None

    now = now or datetime.now()
    until = minutes_until_next_restart(interval_minutes, now)
    return (now + timedelta(minutes=until)).replace(second=0, microsecond=0)


def applicable_warning_stages(interval_minutes: int) -> Tuple[int, ...]:
    """Этапы say-предупреждений, которые помещаются в интервал."""
    return tuple(m for m in WARNING_STAGES if m < interval_minutes)


def get_stage_messages(minutes_before: int) -> Tuple[str, str]:
    """RU/EN тексты для этапа planned restart."""
    if minutes_before == 10:
        ru = (
            '[INFO] Плановая перезагрузка через 10 мин. '
            'Через 5 мин. сервер закроется для входа и всех отключат. Завершите дела.'
        )
        en = (
            '[INFO] Scheduled restart in 10 minutes. '
            'In 5 minutes the server will lock and all players will be kicked. Please wrap up.'
        )
        return ru, en

    if minutes_before == 5:
        ru = (
            '[INFO] Сейчас всех отключат для плановой перезагрузки. '
            'Рестарт сервера через 5 мин.'
        )
        en = (
            '[INFO] Disconnecting all players now for scheduled restart. '
            'Server restarts in 5 minutes.'
        )
        return ru, en

    ru = (
        f'[INFO] Плановая перезагрузка через {minutes_before} мин. Завершите дела.'
    )
    en = (
        f'[INFO] Scheduled restart in {minutes_before} minutes. Please wrap up.'
    )
    return ru, en


def is_planned_restart_enabled(server: dict) -> bool:
    planned = normalize_planned_restart(server.get('planned_restart'))
    return bool(planned.get('enabled')) and int(planned.get('interval_minutes', 0)) > 0
