"""
=============================================================================
LAYER 4.5c: SCHEDULER DETECTION

Catches:
    "remind me at 5pm to X"
    "set alarm for 7am"
    "timer 10 minutes"
    "cancel my reminder"
    "show my schedules"

Emits ###SCHED: tag with parsed parameters.

Uses existing brain_modules/command_router.py _build_sched_tag().
=============================================================================
"""

import re
import random
from brain_modules.layer_result import LayerResult
from brain_modules.command_router import _build_sched_tag


SCHED_TRIGGER_PHRASES = [
    "remind me", "remember me to", "reminder to", "reminder for",
    "dont let me forget", "don't let me forget", "remind me to",
    "remind me about", "tell me to", "let me know when", "let me know to",
    "alert me", "notify me", "ping me", "wake me up", "wake me at",
    "set a timer", "set an alarm", "set timer", "set alarm", "start a timer",
    "schedule a meeting", "add meeting", "add event", "cancel my",
    "cancel the", "cancel all", "delete the alarm", "delete the timer",
    "delete the reminder", "remove the alarm", "remove the timer",
    "remove the reminder", "clear all timers", "clear all reminders",
    "clear all alarms", "what reminders", "what alarms", "what timers",
    "show my schedule", "show schedule", "any alarms", "any reminders",
    "any timers", "whats scheduled", "how much time left", "time remaining",
    "timer status", "list reminders", "list alarms", "list timers",
    "my schedule", "my reminders", "my alarms", "cancel everything",
    "clear all schedules", "how long left", "time left on timer",
]

_SCHED_ACKS = {
    "reminder":        ["On it.", "Locked in.", "I have it.",
                        "Leave it with me.", "Got it. I will remind you."],
    "timer":           ["Clock is running.", "Counting down.",
                        "Timer set.", "On the clock."],
    "alarm":           ["Alarm set.", "I will wake you.", "Set."],
    "event":           ["On the calendar.", "Locked in.", "Noted."],
    "cancel":          ["Cancelled.", "Done. Removed.", "Cleared."],
    "list":            [],
    "timer_remaining": [],
}


def process(ctx, deps):
    clean_in = ctx.clean_in
    words    = ctx.words

    _has_after_dur = bool(re.search(
        r'\bafter\s+\d+\s*(second|seconds|minute|minutes|hour|hours)\b',
        clean_in
    ))
    _has_in_dur = bool(re.search(
        r'\bin\s+\d+\s*(second|seconds|minute|minutes|hour|hours)\b',
        clean_in
    ))

    _has_sched = (
        any(t in clean_in for t in SCHED_TRIGGER_PHRASES)
        or any(t in words for t in ["remind", "reminder", "alarm", "timer", "countdown"])
        or _has_after_dur
        or _has_in_dur
    )

    _sched_guard = ctx.is_command or "what time is it" in clean_in
    if not _has_sched or _sched_guard:
        return LayerResult.pass_through()

    sched_tag = _build_sched_tag(clean_in, words)
    if not sched_tag:
        return LayerResult.pass_through()

    ctx.is_command = True

    if sched_tag == "action=timer_ask":
        return LayerResult.stop("How long should I set the timer for?")
    if sched_tag == "action=alarm_ask":
        return LayerResult.stop("What time should I set the alarm for?")
    if sched_tag == "action=reminder_ask":
        return LayerResult.stop("What should I remind you about, and when?")

    _action = (sched_tag.split("action=")[1].split(" ")[0]
               if "action=" in sched_tag else "")
    _ack_list = _SCHED_ACKS.get(_action, ["On it."])
    _ack      = random.choice(_ack_list) if _ack_list else ""

    if _ack:
        return LayerResult.stop(f"{_ack} ###SCHED: {sched_tag}")
    return LayerResult.stop(f"###SCHED: {sched_tag}")