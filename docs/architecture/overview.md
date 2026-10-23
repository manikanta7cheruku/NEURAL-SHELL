# Architecture overview

## Processes

Seven is a desktop app made of a few cooperating local processes. Nothing listens on the network; every port is bound
to `127.0.0.1`.

```
SEVEN.exe (Electron main process, electron/main.js)
  |-- main window            React app (frontend/), loaded from frontend/dist or the Vite dev server
  |-- panel host             floating task panel, global hotkey Alt+Shift+T (electron/panel_host.js)
  |-- overlay daemon         notifications and arrangement overlays (electron/overlay_daemon.js)
  |-- spawns: python main.py
        |-- API server        FastAPI on 127.0.0.1:7777 (backend/api_server.py, backend/routes/*)
        |-- voice loop        ears -> brain -> mouth (main_modules/startup/voice_loop.py)
        |-- background        telemetry, battery monitor, morning brief, updater checks
        |-- daemons           trigger_daemon.py (phrases, hotkeys, audio triggers)
                              schedule_daemon.py (reminders, alarms, timers)
Ollama (separate install)     runs the language model, http://127.0.0.1:11434
Chrome extension (optional)   reports open tabs so workspaces can restore them
```

If the Python process exits, Electron restarts it. The UI shows "Connecting" and retries until the API answers.

## One request, end to end

```
voice:  microphone -> ears (VAD, noise gates, AEC, wake word, speech-to-text, voice ID)
                                                   |
text:   Console -> POST /api/chat ------------------+
                                                   v
                                     brain.think()  (brain.py)
                                                   |
                         ordered layers (brain_modules/pipeline.py)
          instant layers answer commands in milliseconds and emit action tags (###OPEN, ###SYS, ###WINDOW, ...)
          memory, knowledge and web layers gather evidence
          the model layer streams a reply only when nothing else answered
                                                   |
                         action tags run in hands/* and produce receipts
                         the reply is reconciled with the receipts (a failure is never reported as done)
                                                   |
                         reply streamed to the UI and spoken by mouth (Piper TTS)
                         transcript, facts and outcomes saved; learning runs on a background worker
```

The brain is documented in depth in [components/brain.md](../components/brain.md).

## Repository layout

| Path | What it is |
|---|---|
| `main.py` | Python entry point: checks the environment, starts the API, voice loop and daemons |
| `brain.py`, `brain_modules/` | The brain: pipeline, layers, memory gate, policy, prompts, learning |
| `ears/` | Audio input: voice activity, noise handling, wake word, speech-to-text, voice identity |
| `mouth/` | Speech output (Piper neural TTS, fallback engine) |
| `hands/` | Actions on Windows: apps, windows, system settings, files, workspaces, notifications |
| `memory/` | Stores: facts, conversations, learning, command log, limits |
| `knowledge/` | Document indexing and retrieval for the Knowledge page |
| `web/` | Optional live lookups and the "does this need the web" classifier |
| `backend/` | FastAPI app and routes used by the UI, panel, overlay and extension |
| `main_modules/` | Startup sequence and the voice path's action handlers |
| `trigger_modules/`, `trigger_daemon.py`, `schedule_daemon.py` | Background triggers and schedules |
| `seven_overlay/`, `task_panel/` | Overlay and task panel content |
| `frontend/` | React 18, Vite 5, Tailwind CSS 4 desktop UI |
| `electron/` | Desktop shell, windows, hotkeys, process supervision |
| `installer/` | Inno Setup script for the Windows installer |
| `chrome_extension/` | Tab reporting extension for workspaces |
| `config.py`, `seven_paths.py`, `seven_utils/` | Configuration, data paths, version |
| `license.py`, `telemetry.py`, `server_sync.py` | Plans, usage reporting, server communication |
| `scripts/` | Build, release, manifest and maintenance scripts |
| `tools/` | Internal Seven Labs tools (licence keys); never packaged |
| `assets/` | Brand assets (logo) |
| `tests/`, `evals/` | Automated tests and golden conversations |
| `docs/` | This documentation |

## Where data lives

| Data | Location |
|---|---|
| Settings | `%APPDATA%\SEVEN\config.json` (the repository copy is only the default) |
| Memory | `%APPDATA%\SEVEN\seven_data\memory\` (facts, conversations, learning, Chroma index) |
| Tasks, triggers, workspaces | `seven_data\tasks.db`, `seven_data\triggers.db` |
| Schedules | `schedules.json` |
| Licence, device ID, usage | `data\license.db`, `data\device_id.txt`, `data\telemetry.db` |
| Feedback waiting to send | `seven_data\feedback_queue.json` |
| App files | `%LOCALAPPDATA%\Programs\SEVEN` (replaced on update; user data is never touched) |

In a development checkout some of these resolve inside the project folder (`seven_paths.py` decides). Both
`seven_data/` and `data/` are ignored by git.

See [privacy and data](privacy-and-data.md) for what goes online.

## Technology choices

| Concern | Choice | Why (details in [decisions](decisions/README.md)) |
|---|---|---|
| Language model | Ollama with a hardware-matched model | Local, simple model management, GPU and CPU support |
| Speech-to-text | faster-whisper with noise gates and a hallucination filter | Offline and private, good accuracy on GPU and CPU |
| Text-to-speech | Piper | Natural voice, fast on CPU, offline |
| Facts and transcripts | SQLite (FTS5 for search) | Reliable, zero setup, inspectable |
| Semantic recall | ChromaDB with sentence-transformers | Local vector search; derived from SQLite, rebuildable |
| API | FastAPI on localhost | Typed, fast, easy for the UI and helper processes to share |
| UI | React, Vite, Tailwind | Fast iteration, one design system, small bundle |
| Shell | Electron | Windows integration (tray, global hotkeys, overlays) with a web UI |
| Installer | Inno Setup | Predictable per-user install and silent updates |

## Quality gates

GitHub Actions (`.github/workflows/ci.yml`) runs on every pull request: ruff and the unit tests on Windows, ESLint and
a production build of the frontend on Ubuntu, and a version consistency check. See
[testing](../development/testing.md).
