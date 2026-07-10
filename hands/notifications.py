"""
=============================================================================
hands/notifications.py

Trigger fire notifications: sound effect + Windows toast.

Sound: plays a short system sound using winsound (built-in, zero dependencies).
Toast: shows a Windows notification via winotify (already installed).

DESIGN:
  Action fires FIRST, then sound + toast simultaneously.
  Sound should be quick (< 100ms playback).
  Toast shows trigger name and action type.

SOUND OPTIONS:
  "default"  → Windows system asterisk sound (professional, subtle)
  "chime"    → Windows system hand sound (higher pitched)
  "click"    → Windows system default sound (shortest)
  "none"     → silent

All sounds are built into Windows — no audio files needed.
=============================================================================
"""

import threading
from colorama import Fore


def notify_trigger_fired(trigger_name, action_type="", sound="default"):
    """
    Show notification and play sound for a trigger fire.
    Runs in background thread so it doesn't block action execution.
    
    Args:
        trigger_name: display name of trigger
        action_type:  what the trigger did (for toast body)
        sound:        "default", "chime", "click", "none"
    """
    threading.Thread(
        target=_do_notify,
        args=(trigger_name, action_type, sound),
        daemon=True
    ).start()


def _do_notify(trigger_name, action_type, sound):
    """Internal: play sound + show toast simultaneously."""

    # Play sound (non-blocking)
    if sound != "none":
        try:
            _play_sound(sound)
        except Exception as e:
            print(Fore.YELLOW + f"[NOTIFY] Sound failed: {e}")

    # Show Windows toast
    try:
        _show_toast(trigger_name, action_type)
    except Exception as e:
        print(Fore.YELLOW + f"[NOTIFY] Toast failed: {e}")


def _play_sound(sound_type):
    """Play a Windows system sound."""
    import winsound

    sound_map = {
        "default": winsound.MB_ICONASTERISK,
        "chime":   winsound.MB_ICONHAND,
        "click":   winsound.MB_OK,
    }

    flag = sound_map.get(sound_type, winsound.MB_ICONASTERISK)
    # SND_ASYNC = play without blocking
    winsound.MessageBeep(flag)


def _show_toast(trigger_name, action_type):
    """Show a Windows toast notification."""
    try:
        from winotify import Notification

        # Action type to human-readable
        action_labels = {
            "open_app":       "App launched",
            "open_url":       "URL opened",
            "open_file":      "File opened",
            "open_folder":    "Folder opened",
            "open_workspace": "Workspace restored",
            "run_command":    "Command executed",
            "seven_action":   "Seven action",
        }
        body = action_labels.get(action_type, "Trigger activated")

        toast = Notification(
            app_id="Seven AI",
            title=f"⚡ {trigger_name}",
            msg=body,
            duration="short"
        )
        toast.show()

    except Exception as e:
        print(Fore.YELLOW + f"[NOTIFY] Toast error: {e}")


def test_sound(sound_type="default"):
    """Test a sound type. Called from settings UI."""
    try:
        _play_sound(sound_type)
        return True
    except Exception:
        return False