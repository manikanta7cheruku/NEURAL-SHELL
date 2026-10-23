# Background services

| | |
|---|---|
| Status | Outline. The full write-up follows when this component is reworked, like the [brain](brain.md) |
| Code | `schedule_daemon.py`, `trigger_daemon.py`, `trigger_modules/`, `main_modules/startup/` |

## Purpose

Work that must keep running when the main window is closed.

## What exists today

- `schedule_daemon.py` fires reminders and battery alerts, even when Seven is closed; it starts at Windows login.
- `trigger_daemon.py` listens for trigger phrases, global hotkeys and audio triggers (`trigger_modules/`).
- Startup sequence and helpers in `main_modules/startup/`: validation, module loading, battery monitor, morning brief, daemon launchers.

## To be written

These sections will follow the structure of the brain document:

- [ ] Purpose
- [ ] How it works
- [ ] Data and configuration
- [ ] Interfaces (what calls it, what it calls)
- [ ] Failure modes and recovery
- [ ] Tests
- [ ] Known limitations
- [ ] Planned work
