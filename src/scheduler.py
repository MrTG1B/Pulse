"""
Release Scheduler — follows the selected model's current published quota slots.
"""

import logging
from typing import Optional, Callable

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    HAS_APSCHEDULER = True
except ImportError:
    HAS_APSCHEDULER = False
    BackgroundScheduler = None  # type: ignore
    CronTrigger = None          # type: ignore

import focus_trigger
import config_manager
import provider_updates

logger = logging.getLogger(__name__)

_scheduler: Optional["BackgroundScheduler"] = None
_ui_callback: Optional[Callable[[dict], None]] = None


def _release_minutes(cfg):
    model = provider_updates.get_model(cfg.get("selected_model", "gpt-6.1-sol")) or {}
    if model.get("provider_status") != "limited" or model.get("available_in_account") is False:
        return []
    return model.get("release_minutes_utc", [])


def refresh_jobs() -> None:
    """Remove obsolete jobs and register only currently published release slots."""
    if not _scheduler:
        return
    slots = _release_minutes(config_manager.load_config())
    desired = {f"release_{slot // 60:02d}{slot % 60:02d}": slot for slot in slots}
    existing = {job.id for job in _scheduler.get_jobs() if job.id.startswith("release_")}
    for job_id in existing - desired.keys():
        _scheduler.remove_job(job_id)
    for job_id, slot in desired.items():
        if job_id not in existing:
            _scheduler.add_job(
                _on_release, CronTrigger(hour=slot // 60, minute=slot % 60, timezone="UTC"),
                args=[slot], id=job_id, name=f"Quota release {slot // 60:02d}:{slot % 60:02d} UTC",
                replace_existing=True, misfire_grace_time=300,
            )


def _on_release(release_minute=None) -> None:
    """
    Invoked by APScheduler at each quota release time.
    Reads fresh config, builds an optional Gemini 3.8 AI gate, fires the
    focus trigger, optionally narrates the result, then calls the UI callback.
    """
    cfg = config_manager.load_config()

    if not cfg.get("scheduler_enabled", True):
        logger.info("[Scheduler] Scheduler disabled in config — skipping release.")
        return

    slots = _release_minutes(cfg)
    if not slots or (release_minute is not None and release_minute not in slots):
        logger.info("[Scheduler] No current quota release for the selected model — skipping.")
        return

    press_enter: bool = cfg.get("scheduler_press_enter", True)
    gemini_key: str = cfg.get("gemini_api_key", "").strip()
    gemini_on: bool = cfg.get("gemini_enabled", False) and bool(gemini_key)

    # Build optional Gemini 3.8 gate function (with visual screenshot verification)
    ai_gate: Optional[Callable] = None
    if gemini_on:
        try:
            from gemini_helper import ai_verify_window_from_screenshot
            ai_gate = lambda hwnd, title: ai_verify_window_from_screenshot(hwnd, title, gemini_key)
        except Exception as exc:
            logger.warning("[Scheduler] Gemini gate unavailable: %s", exc)

    logger.info("[Scheduler] 🔔 Quota release — running focus trigger...")
    results = focus_trigger.trigger_all_targets(
        press_enter=press_enter,
        ai_gate_fn=ai_gate,
    )
    logger.info("[Scheduler] %s", results["message"])

    # Optional Gemini 3.8 narration for the UI notification
    if gemini_on:
        try:
            from gemini_helper import ai_narrate_trigger
            results["ai_message"] = ai_narrate_trigger(results, gemini_key)
        except Exception as exc:
            logger.warning("[Scheduler] Gemini narration error: %s", exc)

    if _ui_callback:
        try:
            _ui_callback(results)
        except Exception as exc:
            logger.warning("[Scheduler] UI callback error: %s", exc)


def start(ui_callback: Optional[Callable[[dict], None]] = None) -> None:
    """
    Start the scheduler and keep its release jobs in sync with provider metadata.
    Safe to call multiple times — will skip if already running.

    Args:
        ui_callback: Optional callable(results_dict) invoked after each trigger.
                     Useful for pushing a notification to the Pulse widget UI.
    """
    global _scheduler, _ui_callback

    if not HAS_APSCHEDULER:
        logger.error(
            "[Scheduler] APScheduler not installed — scheduler disabled. "
            "Install with: pip install apscheduler"
        )
        return

    if _scheduler and _scheduler.running:
        logger.debug("[Scheduler] Already running — skipping start.")
        return

    _ui_callback = ui_callback
    _scheduler = BackgroundScheduler(timezone="UTC")

    refresh_jobs()
    _scheduler.add_job(refresh_jobs, "interval", seconds=30, id="provider_schedule_sync", replace_existing=True)
    _scheduler.start()
    logger.info("[Scheduler] Started — following the selected model's published schedule.")


def stop() -> None:
    """Gracefully stop the scheduler if it is running."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[Scheduler] Stopped.")


def is_running() -> bool:
    """Return True if the APScheduler is currently running."""
    return bool(_scheduler and _scheduler.running)


def get_jobs_info() -> list:
    """Return a serialisable list of scheduled jobs for the API status endpoint."""
    if not _scheduler:
        return []
    return [
        {
            "id": j.id,
            "name": j.name,
            "next_run_utc": str(j.next_run_time) if j.next_run_time else None,
        }
        for j in _scheduler.get_jobs()
        if j.id.startswith("release_")
    ]
