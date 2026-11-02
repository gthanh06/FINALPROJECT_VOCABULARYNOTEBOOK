# app/ratelimit.py — how many AI requests one user may make.
#
# Counted in the ai_usage table, so the limit holds across restarts and several workers.
# Only calls that really reach the AI count; answers served from the cache are free.
#   AI_LIMIT_PER_MINUTE  default 5
#   AI_LIMIT_PER_DAY     default 50, the day is Vietnam's (UTC+7, no daylight saving)
import os
from datetime import UTC, datetime, timedelta, timezone

from fastapi import HTTPException

VN = timezone(timedelta(hours=7))


def limits() -> tuple[int, int]:
    return (
        int(os.environ.get("AI_LIMIT_PER_MINUTE", "5")),
        int(os.environ.get("AI_LIMIT_PER_DAY", "50")),
    )


def start_of_day(now: datetime) -> datetime:
    return now.astimezone(VN).replace(hour=0, minute=0, second=0, microsecond=0)


def used_today(repo, user_id: int) -> int:
    return repo.usage_since(user_id, start_of_day(datetime.now(UTC)))


def check_and_count(repo, user_id: int, feature: str) -> None:
    """Raises 429 when the user is over a limit, otherwise records one AI call."""
    per_minute, per_day = limits()
    now = datetime.now(UTC)
    if repo.usage_since(user_id, now - timedelta(minutes=1)) >= per_minute:
        raise HTTPException(
            status_code=429,
            detail=f"Bạn gửi yêu cầu AI hơi nhanh (tối đa {per_minute} lần/phút)."
            " Đợi 1 phút rồi thử lại.",
            headers={"Retry-After": "60"},
        )
    if repo.usage_since(user_id, start_of_day(now)) >= per_day:
        raise HTTPException(
            status_code=429,
            detail=f"Bạn đã dùng hết {per_day} lượt AI hôm nay. Hãy quay lại vào ngày mai nhé.",
        )
    repo.add_usage(user_id, feature)
