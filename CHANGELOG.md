# Changelog

All notable changes to Seven. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project uses [semantic versioning](docs/development/release-process.md#versions).

## [Unreleased]

Version 1.3.2 is the build for the friends' test, 1.3.3 the update that tests the new update flow, and the public launch stays 1.3.4.

### Added
- **Seven says itself when it is not hearing you.** The home screen shows the problem and what to do (waiting for "Hey Seven",
  push to talk on, a stuck voice loop, Seven mistaking its own voice for yours, only noise reaching it, speech recognition not
  ready), and Settings, System, Hearing shows a live microphone meter and speech detector next to the list of problems. Every
  change is written to `logs\hearing_debug.log` with the numbers behind it and is in the Diagnostics report. (`ears/doctor.py`)
- A changed-files update is applied only to the exact build it was made from; any other build gets the full installer.
- `bump_version.py` rewrites every place the version is written.
- **Hearing diagnostics.** The report now says what the microphone delivers (level in dBFS, the voice detector's best score),
  the listening mode actually in effect, what happened to the last 40 things it heard (a count per reason, with the most
  likely cause), and whether the voice loop is still running (it prints the line a stuck loop is waiting at). A standalone
  Microphone Check (Start menu, or `backend/ear_check.py`) records six seconds and shows the level, the detector score and the
  transcript, without Seven running. Logs show only the last 7 days, treat a multi-line message as one entry, and show native
  crashes with their date and the crashing thread.
- If the microphone delivers only digital silence for 8 seconds (muted at the hardware, a driver that gives nothing), Seven
  tries the other microphones and switches to one that works, and says which; when none works it says so on the home screen.
  The test mic says why it heard nothing: push to talk, a silent or very quiet microphone, or sound without speech.
- **Updates carry only what changed.** A release can publish a small package with just the files that differ from the previous
  version (a few MB instead of about 670 MB); people on exactly that version download it, everyone else the full installer. The
  package is checked as a whole and file by file, applied with a backup, and rolled back if anything fails.
  `npm run build:update -- --prev <version>`; the dashboard's Releases form has a "Changed files only" section. See
  `docs/operations/updates.md`.
- The download shows how much is done, how fast it is going and how long is left, and continues from where it stopped when the
  connection drops.
- After an update the Updates page says "Seven is now X", or why the update did not install and where the log is.
- **Diagnostics.** One plain-text health report for any PC: microphone and Windows privacy switches, speech models, each native
  library imported in a child process, the AI model, internet and server, registration, and the last log warnings. Settings,
  System, Diagnostics (Copy report); `http://127.0.0.1:7777/api/diagnostics/report`; right click the voice bar or tray icon;
  Start menu, SEVEN Diagnostics when Seven will not start. See `docs/operations/diagnostics.md`.
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
- **False alarms on the home screen.** "Seven stopped acting on what it hears" appeared at the end of every long answer (the voice loop does not
  pass while it is thinking and speaking; it is now stuck only after a minute idle or ten minutes answering), and "Seven hears sound
  but cannot find words" appeared after a few ambient noises. The home screen now shows only what is plainly broken, as one short line; the
  ignored-sound explanations stay in Settings, System, Hearing, and count only the last two minutes. The home content no longer slides
  up behind the header when it is taller than the window.
- **"Restart and install" closed Seven and did nothing.** The update script was started as a detached process, and PowerShell, a console
  program, exits at once without one, so no line of it ran. It now starts in its own process group with a hidden console and breaks
  away from Seven's job, and a test starts it the way the app does.
- **Updates could download and then not install.** The launcher started Seven again a few seconds after starting the installer,
  without waiting for it, and said nothing when it failed, so the old version kept running and the update was offered again. The
  installer now runs to the end, the version on disk is checked, the result is recorded and shown, and Seven starts only
  afterwards. An installer built before the version was bumped is refused with a clear message.
- **Seven could be stuck on "Getting ready" forever.** One failed load wrote a safe mode flag that nothing deleted, so every
  later start skipped the speech and brain (no listening, test mic "not listening", no error). Safe mode now needs three
  failed starts in a row, an update clears it, a good start clears it, the reason is shown, and there is a Try again button.
- **New users did not reach the admin dashboard.** Registration was one attempt with a 5 to 10 second limit, which a sleeping
  server misses, and it read a name that was stale right after setup. It now wakes the server and retries until confirmed.
- The test mic says why it cannot hear (speech model still downloading, microphone cannot open, Windows blocking the
  microphone) instead of a bare conflict, and tries to reopen a stopped microphone.
- Seven now says when it could not start its hearing or when Windows blocks the microphone.
- Quit SEVEN also closes the panel host and overlay helpers (about 400 MB each) that used to stay behind, and these helpers
  start 25 seconds after Seven opens instead of competing with it during the first seconds. Only one overlay is started.
- The invisible spot at the top of the screen that opened Seven when clicked (the hidden voice bar) no longer takes clicks.
- A second overlay helper no longer stays alive forever when one is already running (each held ~400 MB). Diagnostics
  flags duplicate helpers, folds repeated log lines and leaves out harmless noise (phonemizer, brightness, filelock).
- `/api/panel/get-hotkey` answered 404 for the Settings page.
- Graphics shows "No dedicated GPU" instead of zeros on PCs without an NVIDIA card.
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
