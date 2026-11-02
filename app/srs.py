"""Pure SM-2 scheduling helpers for the private notebook."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

VIETNAM = ZoneInfo("Asia/Ho_Chi_Minh")


def vietnam_today(now: datetime | None = None) -> date:
    return (now or datetime.now(VIETNAM)).astimezone(VIETNAM).date()


def schedule(
    level: int,
    ease: float,
    interval_days: int,
    quality: int,
    today: date,
) -> dict:
    """Return the next SM-2 state for a self-rated answer from 0 to 5."""
    next_ease = max(1.3, ease + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    if quality < 3:
        next_level = 0
        next_interval = 1
    else:
        next_level = min(level + 1, 5)
        if level == 0:
            next_interval = 1
        elif level == 1:
            next_interval = 6
        else:
            next_interval = max(1, round(interval_days * next_ease))
    return {
        "level": next_level,
        "ease": round(next_ease, 2),
        "interval_days": next_interval,
        "next_review": today + timedelta(days=next_interval),
    }
