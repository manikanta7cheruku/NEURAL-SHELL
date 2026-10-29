# Memory stores

| | |
|---|---|
| Status | Outline. The full write-up follows when this component is reworked, like the [brain](brain.md) |
| Code | `memory/` |

## Purpose

Stores what Seven knows: facts, conversations, learning signals and the command log.

## What exists today

- The memory model, provenance and recall are described in the [brain document](brain.md#7-memory).
- `facts_store.py` (SQLite, versioned facts), `conversation_store.py` (SQLite with FTS5), `learning_store.py` (gaps, outcomes, goals), `fact_service.py` (answers and the Memory page), `command_log.py` (apps opened), `limits.py` (storage guards), `mood.py`.
- Paths can be redirected for tests with `set_db_path` and the `SEVEN_*_DB` environment variables.

## Backup and restore (`backend/backup.py`)

Settings, Privacy and data, **Download backup** and **Import** read and write one JSON file
(`GET /api/memory/export`, `POST /api/memory/import`).

- **In the file:** facts with the history of each (the link between a fact and what replaced it is kept), every saved
  chat with its messages, goals and what Seven learned, reminders and alarms, tasks, triggers, workspaces, the commands
  you gave, and your settings. **Not in it:** documents added to Knowledge (they are your own files), the licence and
  email, and settings tied to a PC (the microphone, the AI model chosen, folders).
- **Restore only adds.** Nothing is replaced. Anything already present is skipped (a fact with the same speaker, key,
  value and time; a chat with the same id; a reminder, task, trigger or workspace with the same content), so importing
  the same file twice adds nothing. The answer lists what was added and what was skipped.
- **Owner name.** A backup from a PC whose owner had another name is restored under this PC's owner, so the brain finds it.
- **Reminders** are added through the scheduler's own list, then saved. Writing `schedules.json` directly, as the old
  import did, left the running scheduler holding the old list, which it then wrote back over the imported reminders.
- **Plan limits hold.** Reminders beyond the plan's limit are not added. Triggers beyond the plan's limit of active
  triggers (or that would take a shortcut or phrase another active trigger uses) are restored but turned off.
- **Older backups** (facts and chats as plain lists, from before this format) are still read.
- Facts are marked for the semantic index again and indexed in the background.

## Clear all memory

`DELETE /api/memory/clear` forgets every fact, conversation, goal and learned preference and the command history, then
resets the brain's short-term state. Each store is cleared on its own, so one failing never stops the others, and the
answer names any that could not be cleared. The app also empties what the Console and other pages hold on screen, so
nothing old stays visible after a clear (or after a restore).

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
