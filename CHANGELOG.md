# Changelog

All notable changes to Seven. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project uses [semantic versioning](docs/development/release-process.md#versions).

## [Unreleased]

### Added
- Setup loads Seven while its last page waits. As soon as the AI model has downloaded, Seven starts loading its brain,
  ears and voice (silently); the last page shows the three steps with progress and keeps Launch Seven off until they are
  done, so Launch opens the app straight away with no restart. If loading cannot start or takes over four minutes,
  Launch works the old way. (`POST /api/setup/prepare`, `GET /api/setup/prepare-status`.)
- Guide page rebuilt: live "Try it now" commands, every ability with phrases that work today, a setup checklist,
  privacy facts, questions, shortcuts and what is coming next. Every phrase is checked by `tests/test_guide_commands.py`.
- Professional documentation in `docs/`: product overview, PRD, roadmap, architecture, decision records, component
  documents (brain complete), development, release process, troubleshooting and a generated HTTP API reference.
- `scripts/build_api_reference.py` generates `docs/reference/http-api.md` from the code.
- `/api/chat` returns action receipts in non-streaming responses.

### Fixed
- Opening Seven no longer waits on a speech-model download. The setup wizard now fetches it (with progress) when it is
  missing, and if it is still missing at launch the app opens anyway and the home screen says it is getting speech
  recognition ready. Before, a first launch could sit on the loading screen for minutes.
- Finishing setup restarted the backend twice, throwing away a download the first restart had started. It restarts once.
- The loading screen shows the real start-up steps (engine, brain, ears, voice) instead of an attempt counter.
- The welcome tour now highlights Test mic. A sentence the voice split in two kept the previous step, so the listening
  switch stayed lit.
- The welcome tour names and highlights each link along the bottom (Overview, Chat, Tasks, Reminders, Memory, Search and
  Welcome guide) and says what each is for. Each link also has a tooltip.
- The welcome tour raises a screen dimmer than 60 percent to 60 (where the display allows it).
- Opening the welcome guide has Seven say why feedback matters; closing it stops Seven. The tour replays from the card
  (header link and a "Take the tour again" section).
- "Snap Chrome to the left" targeted "chrom" (a character-set strip removed the trailing "e").
- "Put Chrome and File Explorer side by side" split "File Explorer" into two apps. Multi-word app names now work in
  layouts and snaps, and File Explorer windows are found by window class.
- "Is wifi on" and "is bluetooth on" turned the radio on instead of reporting its state.
- In-app updates launched the Inno Setup installer with the NSIS flag `/S`; they now use `/VERYSILENT`.
- System actions could fail with a "charmap" encoding error when the backend ran in a non-UTF-8 console.
- Tests no longer read the real triggers and workspaces database (`SEVEN_TRIGGERS_DB`).
- The Updates page described the check schedule incorrectly.

### Changed
- The Guide moved from `/blog` to `/guide` (the old address redirects).
- Private notes moved from `docs/` to the ignored `localdocs/`.

## [1.3.4] - 2026-10

### Added
- Dashboard, home screen with a new orb, Updates and Feedback pages (feedback reaches Google Forms with an offline queue).
- Console with a resizable, collapsible chats panel; redesigned Tasks, Schedules and Triggers.
- Tasks, schedules, triggers and workspaces by chat and voice.
- Settings, Memory and Plans redesigned; light theme; collapsible sidebar; shared UI components.
- Change any setting by chat, answers about this PC from live readings, live model switching.
- Brain v4: layered pipeline with conversation intelligence, versioned facts with provenance, action receipts, goals
  and learning stores.
- CI with tests, ruff, ESLint, build and version checks.

### Fixed
- Voice conversations were missing from Memory.
- The Memory page showed a different store than the brain used.
- `/api/status` recursed into the version route and returned 500.
- The app could hang on "Loading configuration" when the backend was still starting.

## Earlier versions

History before 1.3.4 is in the git log.
