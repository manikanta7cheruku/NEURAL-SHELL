"""
main_modules/startup/morning_brief.py

Builds and speaks Seven's startup briefing.
Includes: greeting, tasks, schedules, battery, noise floor.
"""

import random
from colorama import Fore


def build_morning_brief(ctx, config):
    """Build the full morning brief string."""
    parts = []

    from datetime import datetime as _dt
    _hour = _dt.now().hour

    # Name resolution
    _name = ""
    try:
        _name = config.KEY.get("identity", {}).get("user_name", "").strip()
    except Exception:
        pass

    if not _name or _name.lower() in ("admin", "there", "user", ""):
        try:
            if ctx.brain and hasattr(ctx.brain, 'USER_NAME'):
                if ctx.brain.USER_NAME.lower() not in ("admin", "there", ""):
                    _name = ctx.brain.USER_NAME
        except Exception:
            pass

    _greeting_word = (
        "Good morning"   if _hour < 12 else
        "Good afternoon" if _hour < 17 else
        "Good evening"
    )

    if _name:
        _name_variants = [_name, "boss", _name, _name, "boss"]
        _chosen = random.choice(_name_variants)
    else:
        _chosen = "boss"

    parts.append(f"{_greeting_word}, {_chosen}.")
    print(Fore.CYAN + f"[BRIEF] {_greeting_word}, {_chosen} | hour={_hour}")

    # Tasks
    try:
        from backend.routes.tasks import db_get_due_today, db_get_overdue, db_get_stats
        _td = db_get_due_today()
        _od = db_get_overdue()
        _stats = db_get_stats()
        _total_pending = _stats.get("pending", 0)
        print(Fore.CYAN + f"[BRIEF] tasks today={len(_td)} overdue={len(_od)} total_pending={_total_pending}")

        if _od:
            _oc = len(_od)
            parts.append(f"You have {_oc} overdue task{'s' if _oc != 1 else ''}.")
            if _td:
                parts.append(f"Plus {len(_td)} due today.")
        elif _td:
            _pm  = {"high": 3, "medium": 2, "low": 1}
            _top = max(_td, key=lambda t: _pm.get(t.get("priority", "medium"), 2))
            if len(_td) == 1:
                parts.append(f"One task on your plate today: {_top['text']}.")
            else:
                parts.append(f"{len(_td)} tasks today. Priority is {_top['text'][:40]}.")
        elif _total_pending > 0:
            parts.append(
                f"You have {_total_pending} pending task{'s' if _total_pending != 1 else ''}, "
                f"nothing due today."
            )
        else:
            parts.append(random.choice([
                "Your plate is clear.",
                "No tasks on the list.",
                "Nothing pending. Clear day ahead.",
                "All caught up.",
            ]))
    except Exception as _te:
        print(Fore.YELLOW + f"[BRIEF] tasks failed: {_te}")

    # Schedules
    try:
        _sc = ctx.scheduler_mod.get_active_count()
        if _sc == 1:
            parts.append("One reminder active.")
        elif _sc > 1:
            parts.append(f"{_sc} reminders active.")
    except Exception as _se:
        print(Fore.YELLOW + f"[BRIEF] schedules failed: {_se}")

    # Battery
    try:
        import psutil as _pb
        _bat = _pb.sensors_battery()
        if _bat is not None and not _bat.power_plugged:
            _pct = int(_bat.percent)
            parts.append(f"Battery at {_pct} percent.")
    except Exception:
        pass

    # Voice level
    try:
        from ears.core import _noise_floor as _nf
        if _nf < 300:
            parts.append("Very quiet today.")
        elif _nf >= 600:
            parts.append("Noisy environment. Speak clearly.")
    except Exception:
        pass

    result = " ".join(parts)
    print(Fore.GREEN + f"[BRIEF] Full: {result}")
    return result


def speak_morning_brief(ctx, config):
    """Build and speak the morning brief. Called once at startup."""
    try:
        _brief = build_morning_brief(ctx, config)
        if _brief:
            ctx.mouth.speak(_brief)
    except Exception as _brief_err:
        print(Fore.YELLOW + f"[BRIEF] failed: {_brief_err}")
        try:
            ctx.mouth.speak("Seven online.")
        except Exception:
            pass