# Frontend (desktop UI)

| | |
|---|---|
| Status | Outline. The full write-up follows when this component is reworked, like the [brain](brain.md) |
| Code | `frontend/` |

## Purpose

The React app inside the Electron window.

## What exists today

- React 18, Vite 5, Tailwind CSS 4, Zustand stores (`src/stores/`), React Router with hash routes.
- Shared UI kit in `src/components/ui.jsx` (PageShell, Section, Row, Button, Badge, Toggle, Dialog, Sheet, FloatingMenu, Toaster ...); helpers in `src/lib/`. Type scale: page title 15px, section 13px, body 12.5px.
- Colours: the palette block at the top of `src/index.css` is the only place to change them. Ink (background), Bone (text), Lagoon `#3cc8b4` (the accent) and Brass `#e2b25b` (highlights), plus green, red and blue for status. The light theme under `:root[data-theme="light"]` redefines the same names. The overlay cards (`seven_overlay/`), the task panel (`task_panel/`) and `electron/status.html` are separate pages and repeat the hex values.
- Icons: Phosphor (`@phosphor-icons/react`) in the sidebar, chat and file cards; some older pages still use lucide. The brand mark is `src/components/Mark.jsx` (VII).
- Motion: transitions sit in the base layer of `index.css` so Tailwind `transition-*` classes win over them. Panels use `ease-[cubic-bezier(0.32,0.72,0,1)]`.
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
