# Hands (actions on Windows)

| | |
|---|---|
| Status | Outline. The full write-up follows when this component is reworked, like the [brain](brain.md) |
| Code | `hands/`, `main_modules/handlers/` |

## Purpose

Performs actions on the computer: apps, windows, system settings, files, workspaces and notifications.

## What exists today

- `app_launcher.py` and `app_closer.py`: open and close by everyday name, with discovery of installed apps (`app_discovery.py`), special folders and well-known sites.
- `windows.py` and `window_layout.py`: focus, snap, minimize, maximize, layouts (split, stack, quad), monitors, pin on top, transparency, undo. File Explorer windows are matched by window class.
- `system.py`: volume, brightness, Wi-Fi, Bluetooth, media keys, dark mode, night light, do not disturb, airplane mode, battery.
- `files.py` and `file_content.py`: an indexed search over the user's drives by name and by content.
- `workspace.py` and `workspace_modules/`: scan the current desktop (apps, windows, Chrome tabs, documents) and restore it later.
- `scheduler.py` and `notifications.py`: schedules and notifications.
- Every action is run through `action_receipts` in the chat route (see the brain document, section 5).

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
