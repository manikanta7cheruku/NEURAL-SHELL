# Privacy and data

Seven's promise is that what you say and what it remembers stay on your computer. This page lists, from the code,
everything Seven stores and every connection it can make, so the promise can be checked.

## Never leaves the computer

- Audio from the microphone, wake word detection and speech-to-text.
- Conversations and transcripts.
- Facts, preferences and everything on the Memory page.
- Documents added to Knowledge and their index.
- Tasks, schedules, triggers and workspaces.
- Files found or opened by search.
- The language model's input and output (Ollama runs locally).

## Connections Seven can make

| Purpose | Destination | What is sent | When | Can the user turn it off |
|---|---|---|---|---|
| Live lookups (weather, news, prices) | DuckDuckGo search (`web/core.py`) | The search query | Only for questions that need fresh data | Yes, Settings, Privacy & data (web) |
| Check for updates | Seven server, then GitHub Releases | Current version and plan tier | 15 s after start, then every 2 hours | Yes, Updates page (auto check) |
| Download an update | GitHub Releases | Nothing beyond the download request | When the user clicks download | User initiated |
| Licence activation and validation | Seven server (`license.py`) | Licence key, device ID | On activation and periodic validation; 30-day offline grace | Paid plans only |
| First-run registration | Seven server (`backend/routes/setup.py`) | Name, email, device ID | Once during setup | Required by setup today |
| Usage statistics | Seven server (`telemetry.py`) | Minutes of use, app version, device ID, country | Periodically | Yes, Settings, Privacy & data (telemetry). **On by default** |
| Country for statistics | ipapi.co | The IP address (implicit in the request) | With usage statistics | Off with telemetry |
| Announcements | Seven server | Device ID | Periodically | Off with telemetry |
| Feedback | Google Forms | Category, severity, details, optional email, optional app and Windows version | When the user presses Send | User initiated |
| First-run downloads | ollama.com, model registry | Download requests | Setup, or when changing models | User initiated |

The brain can describe this list itself: `self_knowledge.outbound_flows` builds its answer to "what do you send?" from
the live configuration, so it changes when a setting changes.

## Stored on the computer

See the storage table in the [architecture overview](overview.md#where-data-lives).

## User controls

- Memory page: see, edit and delete any fact or conversation; clear everything.
- Settings, Privacy & data: web lookups, telemetry, storage budget, delete all data.
- Export: memory export (Ultimate plan today).
- Uninstall removes the app; user data stays in `%APPDATA%\SEVEN` until the user deletes it.

## Gaps to close before public beta

1. Telemetry should be **opt-in**, asked once during setup, rather than on by default.
2. Registration should explain why an email is needed and allow skipping it on the free plan.
3. A published privacy policy that matches this page.
4. Encryption at rest for `seven_data` (planned, optional).
