# 0007: Inno Setup instead of NSIS for the installer

- Status: Accepted
- Date: 2026-09

## Context

The electron-builder NSIS installer failed on some machines during upgrades ("failed to uninstall old application
files") and was hard to customise.

## Decision

electron-builder only produces the unpacked app (`dist-electron/win-unpacked`). Inno Setup (`installer/SEVEN.iss`)
builds the single installer `SEVEN-Setup-<version>.exe`, installed per user under `%LOCALAPPDATA%\Programs\SEVEN`.

## Consequences

- In-app updates must launch the installer with Inno's silent flags (`/VERYSILENT /SUPPRESSMSGBOXES /NORESTART`). The
  updater still passed the NSIS flag `/S` until 2026-10-23. It is corrected in `backend/routes/updates.py` but still
  needs an end-to-end update test.
- Releases publish one file instead of three.
