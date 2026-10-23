# Frontend (desktop UI)

| | |
|---|---|
| Status | Outline. The full write-up follows when this component is reworked, like the [brain](brain.md) |
| Code | `frontend/` |

## Purpose

The React app inside the Electron window.

## What exists today

- React 18, Vite 5, Tailwind CSS 4, Zustand stores (`src/stores/`), React Router with hash routes.
- Shared UI kit in `src/components/ui.jsx` (PageShell, Section, Row, Button, Badge, Dialog, Toaster ...); helpers in `src/lib/`. Type scale: page title 15px, section 13px, body 12.5px.
- Design tokens in `src/index.css`, with a light theme under `:root[data-theme="light"]`.
- Pages: Home (orb), Dashboard, Console, Tasks, Schedules, Triggers, Memory, Knowledge, Settings, Plans, Updates, Feedback, Guide.
- `/* SEVEN_DOC {...} */` comments describe each page for the brain's app map.
- The Guide's commands live in `src/guide/guide.json` and are tested by `tests/test_guide_commands.py`.

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
