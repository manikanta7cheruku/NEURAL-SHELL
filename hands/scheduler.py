"""
=============================================================================
PROJECT SEVEN - hands/scheduler.py (The Scheduler)
Version: 1.8

Handles: Alarms, Reminders, Timers, Events, Recurring schedules.
Storage: JSON file persistence (seven_data/schedules.json)
Background: Daemon thread checks every 15 seconds, fires on time.
Speaker: Per-speaker schedules with voice profile support.

ARCHITECTURE:
    brain.py detects scheduler intent → builds ###SCHED: tag
    main.py extracts tag → calls manage_schedule()
    Background thread monitors → fires mouth.speak() on time

TAG FORMAT:
    ###SCHED: action=reminder time=2025-06-15T17:00 message=call Mom
    ###SCHED: action=timer duration=600 message=timer done
    ###SCHED: action=list
    ###SCHED: action=cancel match=5pm reminder
=============================================================================
"""

import json
import os
import re
import time
import threading
import calendar
from datetime import datetime, timedelta
from colorama import Fore

# =========================================================================
# STORAGE
# =========================================================================

SCHEDULE_FILE = os.path.join("seven_data", "schedules.json")
_schedules = []
_lock = threading.Lock()
_next_id = 1
_background_thread = None
_speak_callback = None  # Set by main.py — function to call when schedule fires
_running = False


def _load():
    """Load schedules from disk."""
    global _schedules, _next_id
    if os.path.exists(SCHEDULE_FILE):
        try:
            with open(SCHEDULE_FILE, 'r') as f:
                _schedules = json.load(f)
            if _schedules:
                _next_id = max(s.get("id", 0) for s in _schedules) + 1
            print(Fore.GREEN + f"[SCHEDULER] Loaded {len(_schedules)} schedules.")
        except Exception as e:
            print(Fore.RED + f"[SCHEDULER] Load error: {e}")
            _schedules = []
    else:
        _schedules = []


def _save():
    """Persist schedules to disk."""
    try:
        os.makedirs(os.path.dirname(SCHEDULE_FILE), exist_ok=True)
        with open(SCHEDULE_FILE, 'w') as f:
            json.dump(_schedules, f, indent=2)
    except Exception as e:
        print(Fore.RED + f"[SCHEDULER] Save error: {e}")


# Load on import
_load()


# =========================================================================
# TIME PARSING — Pure Python, zero dependencies
# =========================================================================

def _parse_time(time_str, ref_time=None):
    """
    Parse natural language time into datetime object.
    Returns datetime or None if unparseable.
    
    Supports:
        "5pm", "5:30pm", "17:00", "7am", "6:30"
        "in 30 minutes", "in 2 hours", "in 1 hour"
        "tomorrow at 9", "tomorrow at 9am", "tomorrow 3pm"
        "next friday", "next monday at 2pm"
        "on june 20 at 3pm", "on friday at 3pm"
        "10 minutes", "2 hours" (bare durations for timers)
    """
    if not time_str:
        return None
    
    now = ref_time or datetime.now()
    clean = time_str.lower().strip()
    
    # Normalize "after" to "in" for uniform parsing
    clean = re.sub(r'^after\s+', 'in ', clean)
    
    # --- RELATIVE: "in X minutes/hours/seconds" ---
    rel_match = re.match(r'in\s+(\d+)\s+(second|seconds|sec|minute|minutes|min|mins|hour|hours|hr|hrs)', clean)
    if rel_match:
        amount = int(rel_match.group(1))
        unit = rel_match.group(2)
        if unit.startswith("sec"):
            return now + timedelta(seconds=amount)
        elif unit.startswith("min"):
            return now + timedelta(minutes=amount)
        elif unit.startswith("h"):
            return now + timedelta(hours=amount)
    
    # --- BARE DURATION (for timers): "30 minutes", "2 hours", "90 seconds" ---
    dur_match = re.match(r'^(\d+)\s+(second|seconds|sec|minute|minutes|min|mins|hour|hours|hr|hrs)$', clean)
    if dur_match:
        amount = int(dur_match.group(1))
        unit = dur_match.group(2)
        if unit.startswith("sec"):
            return now + timedelta(seconds=amount)
        elif unit.startswith("min"):
            return now + timedelta(minutes=amount)
        elif unit.startswith("h"):
            return now + timedelta(hours=amount)
    
    # --- EXTRACT TIME COMPONENT (Xpm, Xam, X:XX, XX:XX) ---
    def _extract_clock(text):
        """Extract hour and minute from text containing time."""
        # "5pm", "5:30pm", "5:30 pm", "17:00"
        clock_match = re.search(r'(\d{1,2}):?(\d{2})?\s*(am|pm)?', text)
        if clock_match:
            hour = int(clock_match.group(1))
            minute = int(clock_match.group(2)) if clock_match.group(2) else 0
            ampm = clock_match.group(3)
            
            if ampm == "pm" and hour < 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0
            elif ampm is None and hour <= 12:
                # Ambiguous — guess PM if hour <= 12 and it's a small number
                # "at 5" probably means 5 PM, "at 7" could be either
                # Heuristic: if the time would be in the past for today AM, use PM
                if hour < 12:
                    test_am = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if test_am < now:
                        hour += 12  # Assume PM if AM already passed
            
            return hour, minute
        return None, None
    
    # --- "tomorrow at X" ---
    if "tomorrow" in clean:
        tomorrow = now + timedelta(days=1)
        hour, minute = _extract_clock(clean)
        if hour is not None:
            return tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)
        # "tomorrow" with no time — default 9am
        return tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)
    
    # --- "next [weekday]" ---
    days_of_week = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6,
        "mon": 0, "tue": 1, "wed": 2, "thu": 3,
        "fri": 4, "sat": 5, "sun": 6
    }
    
    next_match = re.search(r'next\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|wed|thu|fri|sat|sun)', clean)
    if next_match:
        target_day = days_of_week[next_match.group(1)]
        days_ahead = target_day - now.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        target_date = now + timedelta(days=days_ahead)
        hour, minute = _extract_clock(clean)
        if hour is not None:
            return target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return target_date.replace(hour=9, minute=0, second=0, microsecond=0)
    
    # --- "on [weekday]" (this week or next) ---
    on_day_match = re.search(r'(?:on\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)', clean)
    if on_day_match and "every" not in clean:
        target_day = days_of_week[on_day_match.group(1)]
        days_ahead = target_day - now.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        target_date = now + timedelta(days=days_ahead)
        hour, minute = _extract_clock(clean)
        if hour is not None:
            return target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return target_date.replace(hour=9, minute=0, second=0, microsecond=0)
    
    # --- "on [month] [day]" ---
    months = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
        "jan": 1, "feb": 2, "mar": 3, "apr": 4,
        "jun": 6, "jul": 7, "aug": 8, "sep": 9,
        "oct": 10, "nov": 11, "dec": 12
    }
    
    for month_name, month_num in months.items():
        if month_name in clean:
            day_match = re.search(r'(\d{1,2})', clean.split(month_name)[1] if month_name in clean else "")
            if day_match:
                day = int(day_match.group(1))
                year = now.year
                target_date = datetime(year, month_num, day)
                if target_date < now:
                    target_date = datetime(year + 1, month_num, day)
                hour, minute = _extract_clock(clean)
                if hour is not None:
                    return target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                return target_date.replace(hour=9, minute=0, second=0, microsecond=0)
            break
    
    # --- BARE TIME: "5pm", "7:30am", "17:00" (today or tomorrow) ---
    hour, minute = _extract_clock(clean)
    if hour is not None:
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)  # If time passed today, schedule for tomorrow
        return target
    
    return None


def _parse_duration_seconds(time_str):
    """
    Parse duration string into seconds (for timers).
    "10 minutes" → 600, "2 hours" → 7200, "90 seconds" → 90
    "in 30 minutes" → 1800
    """
    if not time_str:
        return None
    
    clean = time_str.lower().strip()
    clean = clean.replace("in ", "")  # "in 30 minutes" → "30 minutes"
    
    match = re.match(r'(\d+)\s*(second|seconds|sec|secs|s|minute|minutes|min|mins|m|hour|hours|hr|hrs|h)', clean)
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        if unit.startswith("s"):
            return amount
        elif unit.startswith("m"):
            return amount * 60
        elif unit.startswith("h"):
            return amount * 3600
    
    # Bare number — assume minutes for timers
    if clean.isdigit():
        return int(clean) * 60
    
    return None


def _parse_recurrence(recur_str):
    """
    Parse recurrence pattern.
    Returns: "daily", "weekly_N" (N=weekday 0-6), "weekdays", or None.
    """
    if not recur_str:
        return None
    
    clean = recur_str.lower().strip()
    
    if clean in ["daily", "every day", "everyday"]:
        return "daily"
    
    if clean in ["weekdays", "every weekday", "weekday"]:
        return "weekdays"
    
    days = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6
    }
    
    for day_name, day_num in days.items():
        if day_name in clean:
            return f"weekly_{day_num}"
    
    if clean in ["weekly", "every week"]:
        # Default to current weekday
        return f"weekly_{datetime.now().weekday()}"
    
    return None


def _next_recurrence(schedule):
    """Calculate the next occurrence for a recurring schedule."""
    recur = schedule.get("recur", "")
    last_time = datetime.fromisoformat(schedule["time"])
    now = datetime.now()
    
    if recur == "daily":
        next_time = last_time + timedelta(days=1)
        while next_time <= now:
            next_time += timedelta(days=1)
        return next_time
    
    if recur == "weekdays":
        next_time = last_time + timedelta(days=1)
        while next_time <= now or next_time.weekday() >= 5:  # Skip weekends
            next_time += timedelta(days=1)
        return next_time
    
    if recur.startswith("weekly_"):
        target_day = int(recur.split("_")[1])
        next_time = last_time + timedelta(days=7)
        # Adjust to correct weekday
        while next_time.weekday() != target_day or next_time <= now:
            next_time += timedelta(days=1)
        return next_time
    
    return None


def _format_time_natural(dt):
    """Format datetime into natural speech. '5:00 PM today' or 'Friday at 3:00 PM'"""
    now = datetime.now()
    time_str = dt.strftime("%-I:%M %p") if os.name != 'nt' else dt.strftime("%#I:%M %p")
    
    if dt.date() == now.date():
        return f"{time_str} today"
    elif dt.date() == (now + timedelta(days=1)).date():
        return f"tomorrow at {time_str}"
    else:
        day_name = dt.strftime("%A")
        month_day = dt.strftime("%B %d") if os.name != 'nt' else dt.strftime("%B %#d")
        # If within this week, just say day name
        days_ahead = (dt.date() - now.date()).days
        if days_ahead <= 7:
            return f"{day_name} at {time_str}"
        return f"{day_name}, {month_day} at {time_str}"


def _format_duration_natural(seconds):
    """Format seconds into natural speech. '10 minutes', '1 hour 30 minutes'"""
    if seconds < 60:
        return f"{seconds} second{'s' if seconds != 1 else ''}"
    elif seconds < 3600:
        mins = seconds // 60
        secs = seconds % 60
        result = f"{mins} minute{'s' if mins != 1 else ''}"
        if secs > 0:
            result += f" {secs} second{'s' if secs != 1 else ''}"
        return result
    else:
        hours = seconds // 3600
        mins = (seconds % 3600) // 60
        result = f"{hours} hour{'s' if hours != 1 else ''}"
        if mins > 0:
            result += f" {mins} minute{'s' if mins != 1 else ''}"
        return result


def _format_remaining(target_dt):
    """Format time remaining until target. '6 minutes', '2 hours 15 minutes'"""
    now = datetime.now()
    diff = target_dt - now
    total_secs = int(diff.total_seconds())
    if total_secs <= 0:
        return "now"
    return _format_duration_natural(total_secs)


# =========================================================================
# SCHEDULE MANAGEMENT
# =========================================================================

def add_schedule(stype, message, time_str=None, duration=None, recur=None, speaker_id="default"):
    """
    Add a new schedule.
    
    Args:
        stype: "alarm", "reminder", "timer", "event"
        message: What to say when it fires
        time_str: Natural language time (parsed internally)
        duration: Seconds (for timers, already parsed)
        recur: Recurrence pattern string
        speaker_id: Who set this
    
    Returns: (success, speech, schedule_dict)
    """
    global _next_id
    
    now = datetime.now()
    
    with _lock:
        schedule = {
            "id": _next_id,
            "type": stype,
            "message": message,
            "status": "active",
            "speaker_id": speaker_id,
            "created": now.isoformat()
        }
        
        # --- TIMER: duration-based ---
        if stype == "timer":
            if duration:
                secs = duration
            elif time_str:
                secs = _parse_duration_seconds(time_str)
            else:
                return False, "How long should I set the timer for?", None
            
            if not secs:
                return False, "I didn't catch the duration. Try something like '10 minutes'.", None
            
            fire_time = now + timedelta(seconds=secs)
            schedule["time"] = fire_time.isoformat()
            schedule["duration"] = secs
            schedule["recur"] = "none"
            
            duration_speech = _format_duration_natural(secs)
            import random as _rand
            if message:
                speech = _rand.choice([
                    f"Got it. {duration_speech} on the clock for {message}.",
                    f"{duration_speech} timer for {message}. Starting now.",
                    f"Counting down {duration_speech}. I'll let you know.",
                ])
            else:
                speech = _rand.choice([
                    f"{duration_speech}. Starting now.",
                    f"Got it. {duration_speech} on the clock.",
                    f"Counting down {duration_speech}. I'll let you know.",
                    f"{duration_speech}, clock's ticking.",
                ])
            
        # --- ALARM / REMINDER / EVENT: time-based ---
        else:
            if time_str:
                fire_time = _parse_time(time_str)
            else:
                return False, "When should I set that for?", None
            
            if not fire_time:
                return False, "I couldn't understand that time. Try something like 'at 5pm' or 'in 30 minutes'.", None
            
            schedule["time"] = fire_time.isoformat()
            
            # Handle recurrence
            if recur:
                parsed_recur = _parse_recurrence(recur)
                schedule["recur"] = parsed_recur if parsed_recur else "none"
            else:
                schedule["recur"] = "none"
            
            time_speech = _format_time_natural(fire_time)
            
            import random as _rand2
            if stype == "alarm":
                if schedule["recur"] != "none":
                    speech = _rand2.choice([
                        f"Recurring alarm locked in. {schedule['recur'].replace('_', ' ')} at {fire_time.strftime('%I:%M %p')}.",
                        f"You'll hear from me {schedule['recur'].replace('_', ' ')} at {fire_time.strftime('%I:%M %p')}.",
                    ])
                else:
                    speech = _rand2.choice([
                        f"Alarm set. {time_speech}.",
                        f"I'll wake you at {time_speech}.",
                        f"You're waking up {time_speech}. Alarm set.",
                    ])
            elif stype == "reminder":
                if schedule["recur"] != "none":
                    recur_label = schedule["recur"].replace("weekly_", "every ")
                    if recur_label.startswith("every "):
                        day_num = schedule["recur"].split("_")[-1]
                        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                        try:
                            recur_label = f"every {day_names[int(day_num)]}"
                        except:
                            pass
                    speech = _rand2.choice([
                        f"I'll remind you {recur_label}. {message}.",
                        f"Recurring. {recur_label} — {message}.",
                    ])
                else:
                    speech = _rand2.choice([
                        f"I'll remind you {time_speech}. {message}.",
                        f"Noted. {time_speech} — {message}.",
                        f"You got it. {message}, {time_speech}.",
                    ])
            elif stype == "event":
                speech = _rand2.choice([
                    f"On the calendar. {message}, {time_speech}.",
                    f"Locked in. {message} — {time_speech}.",
                    f"You've got {message} {time_speech}.",
                ])
            else:
                speech = f"Got it. Set for {time_speech}."
        
        _next_id += 1
        _schedules.append(schedule)
        _save()
        
        print(Fore.GREEN + f"[SCHEDULER] Added: {schedule}")
        return True, speech, schedule


def cancel_schedule(match_str=None, schedule_id=None, cancel_type=None, speaker_id=None):
    """
    Cancel schedule(s) by ID, match string, or type.
    
    Returns: (success, speech)
    """
    with _lock:
        if schedule_id is not None:
            # Cancel by exact ID
            for s in _schedules:
                if s["id"] == schedule_id and s["status"] == "active":
                    s["status"] = "cancelled"
                    _save()
                    return True, f"Cancelled — {s['message']}."
            return False, f"No active schedule with ID {schedule_id}."
        
        if cancel_type == "all":
            # Cancel everything
            count = 0
            for s in _schedules:
                if s["status"] == "active":
                    s["status"] = "cancelled"
                    count += 1
            _save()
            if count > 0:
                return True, f"All schedules cleared. {count} item{'s' if count != 1 else ''} removed."
            return True, "Nothing to cancel. Schedule is empty."
        
        if cancel_type in ["alarm", "alarms", "timer", "timers", "reminder", "reminders", "event", "events"]:
            # Cancel all of a specific type
            base_type = cancel_type.rstrip("s")  # "timers" → "timer"
            count = 0
            for s in _schedules:
                if s["status"] == "active" and s["type"] == base_type:
                    if speaker_id and s.get("speaker_id") != speaker_id and s.get("speaker_id") != "default":
                        continue
                    s["status"] = "cancelled"
                    count += 1
            _save()
            if count > 0:
                return True, f"All {base_type}s cleared. {count} removed."
            return True, f"No active {base_type}s to cancel."
        
        if match_str:
            # Fuzzy match by message content or time
            match_lower = match_str.lower()
            best = None
            for s in _schedules:
                if s["status"] != "active":
                    continue
                if speaker_id and s.get("speaker_id") != speaker_id and s.get("speaker_id") != "default":
                    continue
                # Match by message content
                if match_lower in s.get("message", "").lower():
                    best = s
                    break
                # Match by type
                if match_lower in s.get("type", ""):
                    best = s
                    break
                # Match by time fragment
                if match_lower in s.get("time", "").lower():
                    best = s
                    break
            
            if best:
                best["status"] = "cancelled"
                _save()
                return True, f"Cancelled — {best['message']}."
            return False, f"Couldn't find a schedule matching '{match_str}'."
        
        return False, "What should I cancel?"


def list_schedules(speaker_id=None, list_type=None):
    """
    List active schedules.
    
    Returns: (success, speech)
    """
    with _lock:
        active = [s for s in _schedules if s["status"] == "active"]
        
        # Filter by speaker if specified
        if speaker_id and speaker_id not in ("default", "unknown"):
            active = [s for s in active if s.get("speaker_id") in (speaker_id, "default")]
        
        # Filter by type if specified
        if list_type:
            base_type = list_type.rstrip("s")
            active = [s for s in active if s["type"] == base_type]
        
        if not active:
            if list_type:
                return True, f"No active {list_type}."
            return True, "No active schedules."
        
        # Sort by time
        def _sort_key(s):
            try:
                return datetime.fromisoformat(s["time"])
            except:
                return datetime.max
        
        active.sort(key=_sort_key)
        
        lines = []
        now = datetime.now()
        
        for s in active:
            stype = s["type"].capitalize()
            message = s.get("message", "")
            
            try:
                fire_time = datetime.fromisoformat(s["time"])
                
                if s["type"] == "timer":
                    remaining = _format_remaining(fire_time)
                    lines.append(f"{stype} — {remaining} remaining. {message}")
                else:
                    time_str = _format_time_natural(fire_time)
                    recur = s.get("recur", "none")
                    if recur != "none":
                        recur_label = recur.replace("weekly_", "every ")
                        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                        for i, d in enumerate(days):
                            recur_label = recur_label.replace(f"every {i}", f"every {d}")
                        lines.append(f"{stype} — {recur_label} at {fire_time.strftime('%I:%M %p')}. {message}")
                    else:
                        lines.append(f"{stype} at {time_str}. {message}")
            except:
                lines.append(f"{stype}. {message}")
        
        count = len(active)
        header = f"You have {count} active item{'s' if count != 1 else ''}. "
        body = " ".join(lines)
        
        return True, header + body


def get_timer_remaining(speaker_id=None):
    """Get remaining time on active timer(s)."""
    with _lock:
        timers = [s for s in _schedules if s["status"] == "active" and s["type"] == "timer"]
        if speaker_id and speaker_id not in ("default", "unknown"):
            timers = [s for s in timers if s.get("speaker_id") in (speaker_id, "default")]
        
        if not timers:
            return True, "No active timers."
        
        lines = []
        for t in timers:
            try:
                fire_time = datetime.fromisoformat(t["time"])
                remaining = _format_remaining(fire_time)
                msg = t.get("message", "")
                if msg:
                    lines.append(f"{remaining} left on your {msg} timer.")
                else:
                    lines.append(f"{remaining} remaining.")
            except:
                lines.append("Timer active, time unclear.")
        
        return True, " ".join(lines)


# =========================================================================
# MANAGE_SCHEDULE — Main dispatcher (called from main.py)
# =========================================================================

def manage_schedule(params):
    """
    Execute a schedule command from ###SCHED: tag params.
    
    Args:
        params: dict with action, time, message, duration, recur, match, cancel_type, speaker_id
    
    Returns: (success: bool, message: str)
    """
    action = params.get("action", "")
    message = params.get("message", "").replace("_", " ")
    time_str = params.get("time", "").replace("_", " ")
    duration = params.get("duration", "")
    recur = params.get("recur", "").replace("_", " ") if params.get("recur") else None
    speaker_id = params.get("speaker_id", "default")
    match_str = params.get("match", "").replace("_", " ")
    cancel_type = params.get("cancel_type", "")
    list_type = params.get("list_type", "")
    
    if action in ["alarm", "reminder", "timer", "event"]:
        dur_secs = None
        if action == "timer" and duration:
            try:
                dur_secs = int(duration)
            except:
                dur_secs = _parse_duration_seconds(duration)
        
        success, speech, _ = add_schedule(
            stype=action,
            message=message,
            time_str=time_str if time_str else None,
            duration=dur_secs,
            recur=recur if recur and recur != "none" else None,
            speaker_id=speaker_id
        )
        return success, speech
    
    elif action == "cancel":
        sched_id = None
        if params.get("id"):
            try:
                sched_id = int(params["id"])
            except:
                pass
        
        return cancel_schedule(
            match_str=match_str if match_str else None,
            schedule_id=sched_id,
            cancel_type=cancel_type if cancel_type else None,
            speaker_id=speaker_id
        )
    
    elif action == "list":
        return list_schedules(speaker_id=speaker_id, list_type=list_type if list_type else None)
    
    elif action == "timer_remaining":
        return get_timer_remaining(speaker_id=speaker_id)
    
    return False, "I didn't understand that schedule command."


# =========================================================================
# BACKGROUND THREAD — Monitors and fires schedules
# =========================================================================

def _fire_schedule(schedule):
    """Fire a schedule — speak the message."""
    stype = schedule["type"]
    message = schedule.get("message", "")
    speaker_id = schedule.get("speaker_id", "default")
    
    # Build natural fire message based on type
    # Try to get speaker's name
    speaker_name = speaker_id.title() if speaker_id not in ("default", "unknown") else ""
    name_prefix = f"{speaker_name}, " if speaker_name else ""
    
    import random as _rand3
    
    if stype == "alarm":
        now = datetime.now()
        time_str = now.strftime("%I:%M %p").lstrip("0")
        if message and message != "Time to wake up.":
            fire_msg = _rand3.choice([
                f"Hey {speaker_name}. It's {time_str}. {message}.",
                f"{speaker_name}, rise and shine. {time_str}. {message}.",
                f"{speaker_name}. {time_str}. {message}.",
            ]) if speaker_name else f"It's {time_str}. {message}."
        else:
            fire_msg = _rand3.choice([
                f"Hey {speaker_name}. It's {time_str}. Time to get up.",
                f"{speaker_name}, {time_str}. Your alarm.",
                f"Rise and shine, {speaker_name}. {time_str}.",
            ]) if speaker_name else f"It's {time_str}. Time to wake up."
    elif stype == "timer":
        duration = schedule.get("duration", 0)
        dur_str = _format_duration_natural(duration) if duration else ""
        custom_msg = message.strip() if message else ""
        
        if custom_msg:
            # Has custom message like "the oven"
            if speaker_name:
                fire_msg = _rand3.choice([
                    f"Hey {speaker_name}. Time's up. {custom_msg}.",
                    f"{speaker_name}, {dur_str} is up. Don't forget — {custom_msg}.",
                    f"That's {dur_str}, {speaker_name}. {custom_msg}.",
                ])
            else:
                fire_msg = _rand3.choice([
                    f"Time's up. {custom_msg}.",
                    f"Your {dur_str} timer is done. {custom_msg}.",
                ])
        else:
            if speaker_name:
                fire_msg = _rand3.choice([
                    f"Hey {speaker_name}. Your {dur_str} timer is done.",
                    f"{speaker_name}, that's {dur_str}. Timer's up.",
                    f"Time's up, {speaker_name}. {dur_str}.",
                ])
            else:
                fire_msg = f"Your {dur_str} timer is up."
    elif stype == "reminder":
        if message:
            if speaker_name:
                fire_msg = _rand3.choice([
                    f"Hey {speaker_name}. Quick reminder — {message}.",
                    f"{speaker_name}. Don't forget — {message}.",
                    f"Heads up, {speaker_name}. {message}.",
                    f"{speaker_name}. Just a nudge — {message}.",
                    f"Hey. {message}. That's your reminder, {speaker_name}.",
                ])
            else:
                fire_msg = _rand3.choice([
                    f"Quick reminder — {message}.",
                    f"Don't forget — {message}.",
                    f"Heads up. {message}.",
                ])
        else:
            fire_msg = f"Hey {speaker_name}, you have a reminder." if speaker_name else "You have a reminder."
    elif stype == "event":
        if message:
            fire_msg = _rand3.choice([
                f"{speaker_name}, you've got {message} right now.",
                f"Hey {speaker_name}. {message} is starting.",
                f"{speaker_name}. Time for {message}.",
            ]) if speaker_name else f"You have {message} right now."
        else:
            fire_msg = f"{speaker_name}, you have something scheduled right now." if speaker_name else "You have an event right now."
    else:
        fire_msg = f"{speaker_name}, {message}." if speaker_name and message else (message if message else "Schedule alert.")
    
    print(Fore.YELLOW + f"[SCHEDULER] 🔔 FIRING: {fire_msg}")
    
    # Speak through callback (set by main.py)
    if _speak_callback:
        try:
            _speak_callback(fire_msg)
        except Exception as e:
            print(Fore.RED + f"[SCHEDULER] Speech error: {e}")
    else:
        print(Fore.YELLOW + f"[SCHEDULER] No speak callback set. Message: {fire_msg}")


def _background_checker():
    """Background thread that checks schedules every 15 seconds."""
    global _running
    
    print(Fore.GREEN + "[SCHEDULER] Background thread started.")
    
    while _running:
        try:
            now = datetime.now()
            
            with _lock:
                for schedule in _schedules:
                    if schedule["status"] != "active":
                        continue
                    
                    try:
                        fire_time = datetime.fromisoformat(schedule["time"])
                    except:
                        continue
                    
                    if now >= fire_time:
                        # FIRE!
                        recur = schedule.get("recur", "none")
                        
                        if recur != "none":
                            # Recurring — advance to next occurrence
                            next_time = _next_recurrence(schedule)
                            if next_time:
                                schedule["time"] = next_time.isoformat()
                            else:
                                schedule["status"] = "fired"
                        else:
                            schedule["status"] = "fired"
                        
                        _save()
                        
                        # Fire outside the lock to avoid deadlock with speak
                        threading.Thread(
                            target=_fire_schedule,
                            args=(schedule.copy(),),
                            daemon=True
                        ).start()
        
        except Exception as e:
            print(Fore.RED + f"[SCHEDULER] Background error: {e}")
        
        # Sleep 15 seconds, but check _running every second for clean shutdown
        for _ in range(15):
            if not _running:
                break
            time.sleep(1)
    
    print(Fore.YELLOW + "[SCHEDULER] Background thread stopped.")


def start_background(speak_fn):
    """Start the background scheduler thread. Called from main.py."""
    global _speak_callback, _running, _background_thread
    
    _speak_callback = speak_fn
    
    if _background_thread and _background_thread.is_alive():
        print(Fore.YELLOW + "[SCHEDULER] Background already running.")
        return
    
    _running = True
    _background_thread = threading.Thread(target=_background_checker, daemon=True)
    _background_thread.start()


def stop_background():
    """Stop the background scheduler thread."""
    global _running
    _running = False


def get_all_schedules():
    """Return all schedules (for dev console)."""
    with _lock:
        return list(_schedules)


def get_active_count():
    """Return count of active schedules."""
    with _lock:
        return sum(1 for s in _schedules if s["status"] == "active")