# Components

Seven is built from parts named after what a person uses to help someone: it listens (ears), thinks (brain), speaks
(mouth) and acts (hands), with memory, knowledge and the app around them. Each page here explains one part: what it
is for, how it works, the data it keeps, how it fails and how it is tested.

| Component | What it does | Code | Document |
|---|---|---|---|
| [Brain](brain.md) | Understands each message and decides: act, answer from evidence, or ask the model | `brain.py`, `brain_modules/` | **Complete** |
| [Companion](companion.md) | Seven as a friend: it writes to you in its own chat thread, asks about you and itself, and speaks only when you are idle | `companion/` | **Complete** |
| [Voice](voice.md) | One spoken request end to end: the voice loop, greeting, voice bar, home screen readings, settings | `main_modules/startup/`, `electron/status.html` | **Complete** |
| [Ears](ears.md) | Microphone to requests: speech detector, Whisper, wake word, push to talk, snaps and claps | `ears/` | **Complete** |
| [Mouth](mouth.md) | A natural offline voice that starts at once and stops at once | `mouth/` | **Complete** |
| [Hands](hands.md) | Apps, windows, system settings, files | `hands/` | Complete |
| [Workspaces](workspaces.md) | Save everything open, restore only what is missing | `hands/workspace_modules/` | Complete |
| [Memory](memory.md) | Facts, conversations, learning and command log stores | `memory/` | Outline (model in the brain doc) |
| [Knowledge](knowledge.md) | The user's documents, read locally and answered with page citations | `knowledge/` | Complete |
| [Backend API](backend-api.md) | Local HTTP API for the app and helper processes | `backend/` | Outline |
| [Frontend](frontend.md) | The desktop UI | `frontend/` | Outline |
| [Desktop shell](desktop-shell.md) | Electron, windows, hotkeys, process supervision, installer | `electron/`, `installer/` | Outline |
| [Background services](background-services.md) | Schedules and triggers that run while the app is closed | `*_daemon.py`, `trigger_modules/` | Outline |
| [Licensing and updates](licensing-and-updates.md) | Plans, licence keys, telemetry, in-app updates | `license.py`, `backend/updater.py` | Outline |

When a component is reworked, its outline becomes a full document in the same format as the brain page, in the same
pull request as the code.
