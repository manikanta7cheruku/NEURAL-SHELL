# Licensing, telemetry and updates

| | |
|---|---|
| Status | Outline. The full write-up follows when this component is reworked, like the [brain](brain.md) |
| Code | `license.py`, `telemetry.py`, `server_sync.py`, `backend/updater.py`, `backend/routes/updates.py` |

## Purpose

Plans, licence keys, usage statistics and in-app updates.

## What exists today

- Plans and limits: see [plans and pricing](../product/plans-and-pricing.md).
- Licence keys are validated against the Seven server with a 30-day offline grace period and bound to a device ID.
- Telemetry sends minutes of use and app version; it can be turned off in Settings (see [privacy and data](../architecture/privacy-and-data.md)).
- Updates: a local override file, then the Seven server, then GitHub Releases. The download is launched with Inno Setup's silent flags by a detached script that relaunches the app. Details in the [release process](../development/release-process.md).

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
