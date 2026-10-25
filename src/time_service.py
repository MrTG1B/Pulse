"""Model-specific quota schedules derived from current provider announcements."""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, Sequence

import config_manager
import provider_updates

# No global quota windows: unlimited and suspended models have no countdown.
RELEASE_HOURS_UTC = ()
DEFAULT_USER_TZ = timezone(timedelta(hours=5, minutes=30), name="IST")
BEIJING_TZ = timezone(timedelta(hours=8), name="CST")


def get_timezone_from_offset(offset_minutes: int) -> timezone:
    sign = "+" if offset_minutes >= 0 else "-"
    abs_mins = abs(offset_minutes)
    name = f"UTC{sign}{abs_mins // 60:02d}:{abs_mins % 60:02d}"
    return timezone(timedelta(minutes=offset_minutes), name=name)


def calculate_next_release(
    now_utc: Optional[datetime] = None,
    release_minutes_utc: Optional[Sequence[int]] = None,
) -> Dict[str, Any]:
    """Calculate a countdown only for explicitly published UTC release slots."""
    now_utc = now_utc or datetime.now(timezone.utc)
    now_utc = now_utc.replace(tzinfo=timezone.utc) if now_utc.tzinfo is None else now_utc.astimezone(timezone.utc)
    slots = sorted(set(release_minutes_utc or []))
    if not slots:
        return {
            "enabled": False, "now_utc": now_utc.isoformat(), "next_slot_utc": None,
            "prev_slot_utc": None, "batch_number": None, "batch_title": None,
            "seconds_remaining": None, "hours_remaining": None, "minutes_remaining": None,
            "seconds_part": None, "countdown_formatted": "", "cycle_progress_percent": 0,
        }
    if any(not isinstance(slot, int) or not 0 <= slot < 1440 for slot in slots):
        raise ValueError("Invalid UTC release minute")
    candidates = []
    for day_delta in (-1, 0, 1, 2):
        day = now_utc.date() + timedelta(days=day_delta)
        for slot in slots:
            candidates.append(datetime(day.year, day.month, day.day, slot // 60, slot % 60, tzinfo=timezone.utc))
    candidates.sort()
    next_slot = next(c for c in candidates if c > now_utc)
    prev_slot = max(c for c in candidates if c <= now_utc)
    total_seconds = max(0, int((next_slot - now_utc).total_seconds()))
    hours = total_seconds // 3600
    minutes = total_seconds % 3600 // 60
    seconds = total_seconds % 60
    cycle_total = (next_slot - prev_slot).total_seconds()
    progress_pct = (now_utc - prev_slot).total_seconds() / cycle_total * 100
    batch_num = slots.index(next_slot.hour * 60 + next_slot.minute) + 1
    return {
        "enabled": True, "now_utc": now_utc.isoformat(),
        "next_slot_utc": next_slot.isoformat(), "prev_slot_utc": prev_slot.isoformat(),
        "batch_number": batch_num, "batch_title": f"Batch {batch_num}",
        "seconds_remaining": total_seconds, "hours_remaining": hours,
        "minutes_remaining": minutes, "seconds_part": seconds,
        "countdown_formatted": f"{hours:02d}h {minutes:02d}m {seconds:02d}s",
        "cycle_progress_percent": round(min(100.0, max(0.0, progress_pct)), 1),
    }


def format_release_info(
    now_utc: Optional[datetime] = None,
    user_offset_minutes: Optional[int] = None,
    model_id: Optional[str] = None,
    release_minutes_utc: Optional[Sequence[int]] = None,
) -> Dict[str, Any]:
    """Describe the selected model's supply and any published quota schedule."""
    now_utc = now_utc or datetime.now(timezone.utc)
    now_utc = now_utc.replace(tzinfo=timezone.utc) if now_utc.tzinfo is None else now_utc.astimezone(timezone.utc)
    cfg = config_manager.load_config()
    model_id = model_id or cfg.get("selected_model", "gpt-6.1-sol")
    model = provider_updates.get_model(model_id) or {}
    status = model.get("provider_status", "unknown")
    if user_offset_minutes is None:
        user_offset_minutes = cfg.get("user_timezone_offset", 330)
    user_tz = get_timezone_from_offset(user_offset_minutes)
    if release_minutes_utc is None:
        release_minutes_utc = model.get("release_minutes_utc", []) if status == "limited" and model.get("available_in_account") is not False else []
    slots = sorted(set(release_minutes_utc))
    schedule = calculate_next_release(now_utc, slots)
    notices = provider_updates.get_snapshot()["announcements"]
    notice = notices[0]["content"] if notices else ""
    info = {
        **schedule, "model_id": model.get("id", model_id), "supply_status": status,
        "user_timezone": user_tz.tzname(None), "user_offset_minutes": user_offset_minutes,
        "release_minutes_utc": slots, "official_notice": notice,
        "official_notice_cn": notice.split("📢 Important Notice")[0].strip(),
        "official_notice_en": notice.split("📢 Important Notice")[-1].strip(),
    }
    if not schedule["enabled"]:
        labels = {"unlimited": "Unlimited · all day", "unavailable": "Temporarily unavailable", "limited": "Release time not announced"}
        messages = {
            "unlimited": "No scheduled quota refill is needed. Supply is available all day; test your token to confirm access.",
            "unavailable": "AgentRouter has not announced a restoration time.",
            "limited": "Limited supply. Wait for AgentRouter to publish a release time.",
        }
        label = labels.get(status, "No published schedule")
        message = messages.get(status, "No quota release schedule has been announced for this model.")
        return {
            **info, "availability_title": label, "schedule_message": message,
            "local_display": label, "local_time": "", "local_day": "",
            "time_left_human": message, "quota_replenishment_notice": message,
            "beijing_time": "", "utc_time": "", "daily_schedule_local": "No scheduled refill",
            "daily_schedule_beijing": "", "daily_schedule_utc": "",
        }
    next_slot = datetime.fromisoformat(schedule["next_slot_utc"])
    local_slot = next_slot.astimezone(user_tz)
    local_now = now_utc.astimezone(user_tz)
    day_str = "Today" if local_slot.date() == local_now.date() else "Tomorrow"
    local_time = local_slot.strftime("%I:%M %p")
    local_full = f"{day_str}, {local_time} ({user_tz.tzname(None)})"
    midnight = datetime(now_utc.year, now_utc.month, now_utc.day, tzinfo=timezone.utc)
    daily = [midnight + timedelta(minutes=slot) for slot in slots]
    return {
        **info, "availability_title": "Next quota release", "schedule_message": "Published by AgentRouter",
        "local_display": local_full, "local_time": local_time, "local_day": day_str,
        "time_left_human": f"{schedule['hours_remaining']}h {schedule['minutes_remaining']}m remaining",
        "quota_replenishment_notice": f"Quota will replenish at {local_full} (in {schedule['countdown_formatted']})",
        "beijing_time": next_slot.astimezone(BEIJING_TZ).strftime("%H:%M CST (UTC+8)"),
        "utc_time": next_slot.strftime("%H:%M UTC"),
        "daily_schedule_local": " & ".join(slot.astimezone(user_tz).strftime("%I:%M %p") for slot in daily) + f" ({user_tz.tzname(None)})",
        "daily_schedule_beijing": " & ".join(slot.astimezone(BEIJING_TZ).strftime("%H:%M") for slot in daily) + " CST (UTC+8)",
        "daily_schedule_utc": " & ".join(slot.strftime("%H:%M") for slot in daily) + " UTC",
    }
