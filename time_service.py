"""
Time Service for AgentRouter Quota Releases.

Schedule based on official AgentRouter announcement:
"为保障服务稳定，8月27日起 Claude / GPT 改为每日限量供应，新的投放时间为🕙北京时间10:00和19:00（对应UTC时间02:00和11:00）"
"The new allocation times are 10:00 AM and 7:00 PM Beijing Time (corresponding to 02:00 and 11:00 UTC)."
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional


# Daily release hours in UTC
RELEASE_HOURS_UTC = (2, 11)  # 02:00 UTC (10:00 Beijing), 11:00 UTC (19:00 Beijing)

# Default user local timezone: UTC+05:30 (India Standard Time)
DEFAULT_LOCAL_OFFSET_HOURS = 5
DEFAULT_LOCAL_OFFSET_MINUTES = 30
DEFAULT_USER_TZ = timezone(timedelta(hours=DEFAULT_LOCAL_OFFSET_HOURS, minutes=DEFAULT_LOCAL_OFFSET_MINUTES), name="IST")
BEIJING_TZ = timezone(timedelta(hours=8), name="CST")


def get_timezone_from_offset(offset_minutes: int) -> timezone:
    """Create a timezone object from an offset in minutes."""
    sign = "+" if offset_minutes >= 0 else "-"
    abs_mins = abs(offset_minutes)
    hours = abs_mins // 60
    mins = abs_mins % 60
    name = f"UTC{sign}{hours:02d}:{mins:02d}"
    return timezone(timedelta(minutes=offset_minutes), name=name)


def calculate_next_release(now_utc: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Calculates the next release time, countdown, and previous release time.
    All calculations are done in UTC for exactness.
    """
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)
    elif now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)

    # Candidate release slots across yesterday, today, and tomorrow
    today_date = now_utc.date()
    candidates = []
    for day_delta in (-1, 0, 1, 2):
        target_date = today_date + timedelta(days=day_delta)
        for hour in RELEASE_HOURS_UTC:
            dt = datetime(
                target_date.year, target_date.month, target_date.day,
                hour, 0, 0, tzinfo=timezone.utc
            )
            candidates.append(dt)

    candidates.sort()

    # Find the next future slot and the previous passed slot
    future_slots = [c for c in candidates if c > now_utc]
    past_slots = [c for c in candidates if c <= now_utc]

    next_slot = future_slots[0]
    prev_slot = past_slots[-1] if past_slots else (next_slot - timedelta(hours=9))

    diff = next_slot - now_utc
    total_seconds = max(0, int(diff.total_seconds()))

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    countdown_formatted = f"{hours:02d}h {minutes:02d}m {seconds:02d}s"

    # Cycle progress calculation (how far between prev_slot and next_slot)
    cycle_total = (next_slot - prev_slot).total_seconds()
    elapsed = (now_utc - prev_slot).total_seconds()
    progress_pct = min(100.0, max(0.0, (elapsed / cycle_total) * 100.0)) if cycle_total > 0 else 0.0

    # Determine batch label (Batch 1 = 02:00 UTC / 10:00 Beijing; Batch 2 = 11:00 UTC / 19:00 Beijing)
    batch_num = 1 if next_slot.hour == 2 else 2
    batch_title = "Morning Release (Batch 1)" if batch_num == 1 else "Evening Release (Batch 2)"

    return {
        "now_utc": now_utc.isoformat(),
        "next_slot_utc": next_slot.isoformat(),
        "prev_slot_utc": prev_slot.isoformat(),
        "batch_number": batch_num,
        "batch_title": batch_title,
        "seconds_remaining": total_seconds,
        "hours_remaining": hours,
        "minutes_remaining": minutes,
        "seconds_part": seconds,
        "countdown_formatted": countdown_formatted,
        "cycle_progress_percent": round(progress_pct, 1),
    }


def format_release_info(
    now_utc: Optional[datetime] = None,
    user_offset_minutes: Optional[int] = None
) -> Dict[str, Any]:
    """
    Returns full human-readable release information formatted in user local time,
    Beijing time, and UTC.
    """
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)
    elif now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)

    # Determine user timezone
    if user_offset_minutes is not None:
        user_tz = get_timezone_from_offset(user_offset_minutes)
    else:
        user_tz = DEFAULT_USER_TZ

    schedule_data = calculate_next_release(now_utc)
    next_slot_utc = datetime.fromisoformat(schedule_data["next_slot_utc"])
    now_local = now_utc.astimezone(user_tz)
    next_slot_local = next_slot_utc.astimezone(user_tz)
    next_slot_beijing = next_slot_utc.astimezone(BEIJING_TZ)

    # Relative day indicator for local time
    if next_slot_local.date() == now_local.date():
        day_str = "Today"
    elif next_slot_local.date() == now_local.date() + timedelta(days=1):
        day_str = "Tomorrow"
    else:
        day_str = next_slot_local.strftime("%b %d")

    local_time_str = next_slot_local.strftime("%I:%M %p")
    local_full_str = f"{day_str}, {local_time_str} ({user_tz.tzname(None)})"

    beijing_time_str = next_slot_beijing.strftime("%H:%M CST (UTC+8)")
    utc_time_str = next_slot_utc.strftime("%H:%M UTC")

    # The 2 daily drop schedules formatted for user timezone
    today = now_utc.date()
    slot1_local = datetime(today.year, today.month, today.day, 2, 0, 0, tzinfo=timezone.utc).astimezone(user_tz).strftime("%I:%M %p")
    slot2_local = datetime(today.year, today.month, today.day, 11, 0, 0, tzinfo=timezone.utc).astimezone(user_tz).strftime("%I:%M %p")

    tz_name = user_tz.tzname(None)
    time_left_human = f"{schedule_data['hours_remaining']}h {schedule_data['minutes_remaining']}m remaining"
    quota_replenishment_notice = f"Quota will replenish at {local_full_str} (in {schedule_data['countdown_formatted']})"

    return {
        **schedule_data,
        "user_timezone": tz_name,
        "user_offset_minutes": int(user_tz.utcoffset(None).total_seconds() // 60),
        "local_display": local_full_str,
        "local_time": local_time_str,
        "local_day": day_str,
        "time_left_human": time_left_human,
        "quota_replenishment_notice": quota_replenishment_notice,
        "beijing_time": beijing_time_str,
        "utc_time": utc_time_str,
        "daily_schedule_local": f"{slot1_local} & {slot2_local} ({tz_name})",
        "daily_schedule_beijing": "10:00 & 19:00 (Beijing Time / UTC+8)",
        "daily_schedule_utc": "02:00 & 11:00 UTC",
        "official_notice_cn": (
            "为保障服务稳定，8月27日起 Claude / GPT 改为每日限量供应，"
            "新的投放时间为🕙北京时间10:00和19:00（对应UTC时间02:00和11:00）。"
            "额度用尽后会报错 402 Budget pool quota has been exhausted，等下一批次即可；"
            "也可随时切换 DeepSeek / GLM 正常使用。"
        ),
        "official_notice_en": (
            "To ensure service stability, Claude / GPT are limited to daily quotas. "
            "The new allocation times are 10:00 AM and 7:00 PM Beijing Time (02:00 and 11:00 UTC). "
            "Once exhausted, returns HTTP 402 Budget pool quota has been exhausted until next release. "
            "Switch to DeepSeek / GLM anytime for uninterrupted use."
        )
    }
