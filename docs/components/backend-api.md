# Backend API

| | |
|---|---|
| Status | Outline. The full write-up follows when this component is reworked, like the [brain](brain.md) |
| Code | `backend/` |

## Purpose

The local HTTP API that the desktop UI, task panel, overlay and Chrome extension use.

## What exists today

- FastAPI app in `backend/api_server.py`, routes in `backend/routes/`, bound to `127.0.0.1:7777`.
- Every endpoint is listed in the generated [HTTP API reference](../reference/http-api.md).
- `/api/chat` is the main entry to the brain (streaming with Server-Sent Events).
- `/ws/status` and `/api/status` report what Seven is doing (listening, thinking, speaking).
- `backend/admin_server.py` is a separate server for the Seven Labs dashboard and is not part of the desktop app.

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
