# 0005: Electron and React for the app, FastAPI on localhost for the backend

- Status: Accepted
- Date: 2025 (recorded 2026-10-23)

## Context

The core is Python (audio, models, Windows automation). The app needs a modern UI, global hotkeys, overlays and a
floating panel.

## Decision

Electron hosts a React UI. Python runs as a child process and exposes a FastAPI server on `127.0.0.1:7777`. The UI,
task panel, overlay and Chrome extension all talk to that one API.

## Alternatives considered

- **Qt or Tkinter in Python.** One language, but slower UI work and a dated look.
- **Tauri.** Smaller binaries, but less mature Windows integration for what Seven needs today.

## Consequences

- A larger install (Electron plus embedded Python).
- A clear boundary: every UI feature is an HTTP endpoint that tests can call.
