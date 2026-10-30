# Changelog

All notable changes to Seven. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project uses [semantic versioning](docs/development/release-process.md#versions).

## [Unreleased]

### Added
- **Seven the friend (companion).** Seven now reaches out the way a new friend does, instead of saying a canned line after
  a silence: it asks about you, tells you what it is becoming and how it works, shares a small fact, checks in when you
  seem down and follows up on your goals. Everything is written into Seven's own chat thread (pinned at the top of Chat,
  with an unread count) and said aloud only when you are idle. A different number each day (3, 5 or 7), 7 to 17 minutes
  apart, none in quiet hours, none while you type or talk to Seven, more space if you do not answer. Your answers are
  remembered, Seven asks one thing back after replying in the thread, and what it wrote while you were away is said after
  the greeting. Pace, quiet hours, voice and topics are set only in the thread's settings. See
  `docs/components/companion.md`.
- Settings, Voice, Speech recognition knows this PC (NVIDIA card and its memory, PC memory) and says so beside every
  model: one is marked "Recommended for this PC", and the others carry a plain caution when they would be slow or
  would not fit ("Slow without an NVIDIA graphics card: several seconds to understand you"). The same idea as the
  language-model list in Settings, Brain. (`ears/whisper_advice.py`)
- Downloads say which model they are: the setup wizard's brain step shows a card ("Downloading Qwen 2.5 7B, 4.7 GB,
  42%, speed and time left"), the chosen model's card shows the percentage, and Settings, Brain shows the same card at
  the top while a model downloads, even after its window is closed or the page is reopened. The speech row in step 4
  names its model too ("Downloading the Small speech model, 340 of 480 MB").
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
- A language-model download could silently lose its status text (a variable used before it existed). It now reports
  plain words for each phase and names the model in any error ("Llama 3.1 8B could not be downloaded ...").
- Speech recognition now defaults to `small.en` (about 480 MB) on every PC instead of `medium.en` (1.5 GB) on PCs with a
  graphics card, so setup and a first launch are about three times quicker to download. Medium is the optional upgrade in
  Settings, Voice, with real download progress. A PC that already has medium and not small keeps medium.
- Setup step 4 showed "Downloading 1%" for minutes for speech recognition. The download engine wrote the big file only
  when it finished, so watching the folder grow told nothing. Speech and search models now use the plain download,
  which grows its file as it goes (same speed measured), and the step shows real progress ("340 of 1500 MB").
- The speech download now starts when the setup wizard opens (`POST /api/setup/speech-install`), not at step 4, so the
  biggest download is under way or finished by the time it is needed. The size label says 600 MB to 1.5 GB (a PC with a
  graphics card downloads the larger, more accurate model).
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
