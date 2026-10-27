# Configuration

Settings are stored in `%APPDATA%\SEVEN\config.json`. The copy in the repository holds defaults only. `config.py`
loads the file and fills anything missing from its defaults, so a new setting never breaks an old install.

Change settings in the app (Settings) or by chat ("set honesty to 75%"). Brain settings are validated by one registry,
`brain_modules/brain_settings.py`; invalid values are clamped, not rejected with a crash.

| Section | Controls | Main keys |
|---|---|---|
| `identity` | Names and voice phrases | `user_name`, `wake_words`, `pause_words`, `resume_words`, `shutdown_words` |
| `brain` | Model and personality | `model_name` (or `auto`), `temperature`, `streaming`, `tars_humor`, `tars_honesty`, `max_history`, `history_ttl_seconds`, `model_tiers` |
| `memory` | Recall | `min_relevance`, `retrieval_timeout_ms` |
| `voice` | Speaking and listening ([Voice](../components/voice.md)) | `engine`, `voice_id`, `speed`, `listen_mode`, `sensitivity`, `follow_up_seconds`, `interrupt`, `mic`, `wake_words`, `snap_sensitivity` |
| `voice_bar` | The caption pill at the top of the screen | `show` (`active`, `always`, `off`) |
| `voice_id` | Speaker recognition | `enabled`, `similarity_threshold`, `default_speaker` |
| `interrupt` | Talking over Seven | `enabled`, `words`, `listen_during_speech`, `interrupt_cooldown` |
| `web` | Live lookups | `enabled`, `max_results`, `news_max_results`, `timeout` |
| `windows` | Window control | `enabled`, `snap_gap`, `default_monitor` |
| `system` | System controls | `enabled`, `volume_step`, `brightness_step` |
| `scheduler` | Reminders and alarms | `enabled`, `check_interval`, `default_reminder_time`, `fire_through_pause` |
| `knowledge` | Documents | `enabled`, `sources_dir`, `chunk_size`, `top_k`, `auto_index` |
| `commands` | Learned app names and paths | `app_aliases`, `app_paths`, `failed_apps` |
| `license` | Plan | `key`, `tier`, `verified` |
| `updates` | Update checks | `auto_check`, `check_interval_hours`, `channel` |
| `privacy` | What goes online | `telemetry_enabled` |
| `vision`, `gui`, `paths` | Reserved and legacy | |
| top level | Setup state | `setup_complete`, `version`, `email` |

## Environment variables

| Variable | Used by | Purpose |
|---|---|---|
| `SEVEN_FEEDBACK_FORM_URL`, `SEVEN_FEEDBACK_FIELDS` | `backend/routes/feedback.py` | Point feedback at a different Google Form |
| `SEVEN_TASKS_DB`, `SEVEN_TRIGGERS_DB` | task, trigger and workspace stores | Use another database (tests) |
| `SEVEN_TEST`, `SEVEN_DISABLE_CHROMA`, `SEVEN_DISABLE_MIGRATION` | brain and memory | Test mode switches |
| `SEVEN_BACKEND_EXTERNALLY_STARTED` | `electron/main.js` | Do not spawn Python (development) |
| `PYTHONIOENCODING`, `PYTHONUTF8` | Electron when spawning Python | UTF-8 console output |
