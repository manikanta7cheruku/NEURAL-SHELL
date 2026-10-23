# Mouth (voice output)

| | |
|---|---|
| Status | Outline. The full write-up follows when this component is reworked, like the [brain](brain.md) |
| Code | `mouth/` |

## Purpose

Speaks Seven's replies and stops instantly when interrupted.

## What exists today

- `mouth/core.py` runs text-to-speech as a subprocess that can be killed mid-sentence (`speak()`, `interrupt()`).
- Piper neural voices (`mouth/piper/`, binaries and voices are shipped with the installer, not in git).
- Sentence streaming from the brain lets speech start at the first clause.

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
