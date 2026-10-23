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
