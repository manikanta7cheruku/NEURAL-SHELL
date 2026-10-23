# Desktop shell (Electron)

| | |
|---|---|
| Status | Outline. The full write-up follows when this component is reworked, like the [brain](brain.md) |
| Code | `electron/`, `installer/` |

## Purpose

Starts and supervises everything, owns windows, tray and global hotkeys.

## What exists today

- `electron/main.js` starts `python main.py`, restarts it if it exits, loads the UI and registers Alt+S.
- `panel_host.js` runs the floating task panel (default hotkey Alt+Shift+T).
- `overlay_daemon.js` keeps notification and arrangement overlays ready and listens on TCP 7891 for commands from Python.
- Packaged with electron-builder into `dist-electron/win-unpacked`, then Inno Setup (`installer/SEVEN.iss`).

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
