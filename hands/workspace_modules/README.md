# Workspace Modules — Architecture & Developer Reference

> **Project:** SEVEN Private AI Voice Assistant v1.4.3+
> **Author:** Manikanta Cheruku
> **Last Updated:** 2026-09-22
> **Platform:** Windows 10/11 x64

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Module Inventory](#module-inventory)
4. [Data Flow — Online Mode](#data-flow--online-mode)
5. [Data Flow — Offline Mode](#data-flow--offline-mode)
6. [Chrome Multi-Profile System](#chrome-multi-profile-system)
7. [Tab Deduplication Engine](#tab-deduplication-engine)
8. [App-Specific Restorers](#app-specific-restorers)
9. [URL Normalization](#url-normalization)
10. [Offline Tab Listener](#offline-tab-listener)
11. [Key Data Structures](#key-data-structures)
12. [Port Map](#port-map)
13. [File Size & Splitting Rules](#file-size--splitting-rules)
14. [Known Limitations](#known-limitations)
15. [Debugging Guide](#debugging-guide)

---

## Overview

The `workspace_modules/` package implements SEVEN's **smart workspace capture and restore** system. A "workspace" is a snapshot of the user's desktop state — open applications, browser tabs across multiple Chrome profiles, VS Code workspaces, Explorer folders, and terminal sessions — stored as a JSON configuration in the SQLite database.

When a workspace trigger fires (via hotkey, voice command, or schedule), the restore engine compares the saved snapshot against the current desktop state and **opens only what is genuinely missing**, with zero duplicate tabs or windows.

### Core Design Principles

- **Never duplicate:** If a tab, window, or app is already open, skip it.
- **Per-profile isolation:** Chrome Account A's tabs are never checked against Account B's live tabs.
- **Offline resilience:** Tab-level dedup works even when the main SEVEN UI is closed.
- **Speed:** Full workspace restore completes in under 500ms for 20+ apps.
- **Safety:** Seven's own processes (Electron, Python backend, daemons) are filtered from all scans.

---

## Architecture Diagram

┌─────────────────────────────────────────────────────────────────┐
│ TRIGGER EVENT │
│ (Hotkey / Voice / Schedule / Panel) │
└──────────────────────────┬──────────────────────────────────────┘
│
▼
┌──────────────────────────────────────────────────────────────────┐
│ trigger_modules/executor.py │
│ _exec_open_workspace(workspace_id) │
│ • Loads workspace config from SQLite │
│ • Checks if Seven backend is alive (50ms socket probe) │
│ • Marks _browser_closed per profile if browser exe not running │
│ • Calls hands.workspace.smart_restore(apps_config) │
└──────────────────────────┬───────────────────────────────────────┘
│
▼
┌──────────────────────────────────────────────────────────────────┐
│ restore.py — smart_restore(apps_config) │
│ │
│ Phase 1: SCAN CURRENT DESKTOP │
│ ┌─────────────┐ ┌──────────────┐ ┌────────────────────────┐ │
│ │ scanner.py │ │ chrome_utils │ │ chrome_utils │ │
│ │ scan_current │ │ get_profiles │ │ get_tabs_per_profile │ │
│ │ (win32gui) │ │ (Local State)│ │ (HTTP → cache → disk) │ │
│ └──────┬───────┘ └──────┬───────┘ └───────────┬────────────┘ │
│ │ │ │ │
│ ▼ ▼ ▼ │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Build dedup sets: │ │
│ │ open_exes, open_ws_paths, open_folders, open_profiles, │ │
│ │ open_chrome_urls_norm, per_profile_urls │ │
│ └─────────────────────────────────────────────────────────┘ │
│ │
│ Phase 2: DIFF SAVED vs CURRENT │
│ For each app in workspace config: │
│ • Browser → per-profile tab dedup (exact + fuzzy URL match) │
│ • VS Code → workspace path + exe match │
│ • Explorer → folder path + title match │
│ • Terminal → window title + working_dir match │
│ • UWP → protocol + name match │
│ • Generic → exe + process name + window title match │
│ │
│ Phase 3: RESTORE MISSING │
│ ┌──────────────────────────────────────────────────────┐ │
│ │ app_restorers.py — restore_one(cfg) │ │
│ │ • _restore_browser() — Chrome/Edge/Brave/Firefox │ │
│ │ • _restore_vscode() — VS Code workspaces │ │
│ │ • _restore_terminal() — PowerShell/CMD/WT │ │
│ │ • _restore_explorer() — File Explorer folders │ │
│ │ • _restore_uwp() — Universal Windows apps │ │
│ │ • _restore_generic() — Any other .exe │ │
│ └──────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘

---

## Module Inventory

| File | Lines | Purpose |
|------|-------|---------|
| `restore.py` | ~350 | **Orchestrator.** Scans desktop, diffs saved vs current, dispatches restores. Entry point: `smart_restore(apps_config)`. |
| `scanner.py` | ~250 | **Desktop scanner.** Enumerates all visible windows via `win32gui.EnumWindows`, classifies each by type (chrome, vscode, explorer, terminal, uwp, app), extracts profile directory from Chrome cmdline. |
| `chrome_utils.py` | ~400 | **Chrome intelligence.** Profile detection from `Local State`, tab fetching via HTTP/cache/disk, profile directory mapping from `Preferences` files, window-to-profile matching. |
| `app_restorers.py` | ~500 | **App launchers.** Type-specific restore logic with geometry positioning, profile-aware Chrome launching, serialized browser launches via threading lock. |
| `enrichment.py` | ~200 | **Profile enrichment.** Pigeonhole allocation that maps extension profile keys to disk directories using email/name matching from `Preferences` files. |
| `url_matching.py` | ~80 | **URL comparison.** Normalizes URLs (strips transient query params), extracts domains, fuzzy matching with domain overlap. |
| `helpers.py` | ~100 | **Utilities.** `find_chrome_profile_dir()` with email/display-name priority resolution. |
| `filters.py` | ~40 | **Process filtering.** `is_seven_process()` excludes SEVEN.exe, electron.exe, python.exe (with "seven" in path) from all window enumeration. |
| `offline_tab_listener.py` | ~180 | **Background HTTP server.** Runs on port 7777 when Seven is closed. Receives Chrome extension tab syncs and persists to disk cache. |
| `document_capture.py` | ~150 | **Document tracking.** Captures open document paths for supported applications. |

---

## Data Flow — Online Mode

**Condition:** Seven UI is running. FastAPI backend is active on port 7777.

Chrome Extension (all profiles)
│
│ POST /api/chrome/tabs (every 3 seconds per profile)
│ Payload: { profile, windows: [{ tabs: [{url, title, pinned}] }] }
▼
backend/routes/chrome.py
│
├─ Stores in _tab_snapshots (in-memory dict)
├─ Writes to %APPDATA%\SEVEN\cache\live_chrome_tabs.json
│
▼
chrome_utils.py → _fetch_tabs_via_http()
│
│ GET http://127.0.0.1:7777/api/chrome/tabs
│
├─ Parses profiles map
├─ Re-keys by disk directory (Default, Profile 1, etc.)
│
▼
restore.py → per_profile_urls = { "Default": {url1, url2}, "Profile 1": {url3} }
│
▼
Per-profile dedup: saved tabs vs live tabs for THAT profile only

---

## Data Flow — Offline Mode

**Condition:** Seven UI is closed. Only `trigger_daemon.py` and `schedule_daemon.py` are running.
Chrome Extension (all profiles)
│
│ POST /api/chrome/tabs (every 3 seconds per profile)
▼
offline_tab_listener.py (started by trigger_daemon supervisor on port 7777)
│
├─ Parses nested windows/tabs payload
├─ Stores per-profile in _tab_snapshots
├─ Writes to %APPDATA%\SEVEN\cache\live_chrome_tabs.json
│
▼
chrome_utils.py → _fetch_tabs_via_http()
│
│ Port 7777 alive (offline listener) → HTTP fetch succeeds
│ Port 7777 dead (transitioning) → reads disk cache directly
│
▼
restore.py → identical dedup logic as online mode


### Supervisor Lifecycle
trigger_daemon.py main loop (every 2 seconds):
│
├─ Socket probe 127.0.0.1:7777
│
├─ Port CLOSED → launch offline_tab_listener.py (pythonw.exe, DETACHED)
│
└─ Port OPEN → do nothing (Seven or listener already owns it)

When Seven starts, FastAPI binds port 7777. The offline listener detects the collision via `SO_REUSEADDR` and the supervisor stops spawning new instances.

---

## Chrome Multi-Profile System

### Directory Structure
%LOCALAPPDATA%\Google\Chrome\User Data
├── Local State ← JSON: profile.info_cache.<dir>
├── Default
│ ├── Preferences ← JSON: account_info[].email, profile.name
│ ├── SingletonLock ← exists ONLY while profile is open
│ ├── SingletonSocket
│ ├── SingletonCookie
│ └── Sessions
│ ├── Tabs_1234567890 ← Chromium SNSS binary session log
│ └── Session_1234567890
├── Profile 1
│ ├── Preferences
│ └── ...
├── Profile 2
└── Profile 3\


### Profile Name Resolution Pipeline

Extension sends ambiguous identifiers (`"default"`, `"cherukumanikanta77"`, `"manikantacheruku10"`). These must be mapped to disk directories (`"Default"`, `"Profile 1"`, `"Profile 2"`).

Extension key: "cherukumanikanta77"
│
▼
_build_profile_dir_map()
Reads ALL Preferences files:
Default/Preferences → account_info[0].email = "cherukumanikanta77@gmail.com"
→ maps "cherukumanikanta77@gmail.com" → "Default"
→ maps "cherukumanikanta77" → "Default"
│
▼
_rekey_by_profile_dir()
"cherukumanikanta77" → exact match → "Default"
"manikantacheruku10" → exact match → "Profile 1"
"sahithicandy99" → exact match → "Profile 3"
"default" → fuzzy match → "Profile 2" (unnamed account)


### Profile Open Detection (3-Layer)

`_is_profile_dir_open()` in `app_restorers.py`:

| Layer | Method | Reliability |
|-------|--------|-------------|
| 1 | psutil cmdline scan for `--profile-directory=<dir>` | High (may miss restricted processes) |
| 2 | win32gui window enumeration + profile matching | Medium (catches visible windows) |
| 3 | SingletonLock file existence + Sessions dir mtime < 5min | Very High (filesystem-level) |

---

## Tab Deduplication Engine

### Online/Offline Per-Profile Dedup (restore.py)

For each saved Chrome config with `profile_dir = "Default"`:
Look up live URLs for "Default" ONLY from per_profile_urls
For each saved tab:
a. normalize_url(saved_url)
b. Exact match against live "Default" URLs → SKIP
c. Fuzzy match (domain overlap + path similarity) → SKIP
d. No match → ADD to missing_tabs
Launch only missing_tabs into "Default" profile


### URL Normalization (url_matching.py)

Stripped query parameters (transient tracking/session params):
t, time, index, feature, ab_channel, pp, start_radio,
utm_source, utm_medium, utm_campaign, utm_term, utm_content,
fbclid, gclid


Remaining parameters are sorted alphabetically for deterministic comparison.

### Cross-Profile Isolation Guarantee

Account A saved tabs → checked ONLY against Account A live tabs
Account B saved tabs → checked ONLY against Account B live tabs
Global URL fallback → activated ONLY when per_profile_urls is empty

---

## App-Specific Restorers

### Browser (Chrome / Edge / Brave / Firefox)

- **Cold start** (`_browser_closed = True`): Launches all saved tabs via `--profile-directory=<dir>` flag.
- **Partial restore** (`_partial = True`): Launches only missing tabs into existing profile window.
- **Serialized launches**: `_browser_launch_lock` (threading.Lock) prevents race conditions when launching multiple profiles simultaneously.
- **Tab launch delay**: 1.2s cold, 0.4s warm between tab opens to prevent Chrome throttling.

### VS Code

- Finds `Code.exe` explicitly (not via PATH).
- Opens workspace via `code <workspace_path>`.
- Dedup by workspace path match.

### Terminal (PowerShell / CMD / Windows Terminal)

- Dedup by **window title** + **working directory** match.
- Does NOT use process-level check (Seven's own child processes include powershell.exe).
- Launches with correct working directory via `start /d <dir>`.

### Explorer

- Dedup by folder path, window title, and generic explorer presence.
- Handles "Home", "This PC", and custom library titles.

### UWP Apps

- Dedup by protocol URI and app name.
- Launches via `start shell:AppsFolder\<PackageFamilyName>!<AppId>`.

### Generic Apps

- Dedup by exe path, window title, and process name.
- Process-level fallback for minimized/background apps.

---

## Offline Tab Listener

### Purpose

When Seven's main FastAPI backend is closed, the Chrome extension has nowhere to POST tab updates. The offline listener provides a minimal HTTP server on port 7777 that:

1. Receives `POST /api/chrome/tabs` from the extension (all profiles).
2. Parses nested `{ profile, windows: [{ tabs }] }` payloads.
3. Maintains per-profile tab state in memory.
4. Persists to `%APPDATA%\SEVEN\cache\live_chrome_tabs.json` on every update.
5. Serves `GET /api/chrome/tabs` for the restore engine.
6. Responds to `GET /api/status` to prevent frontend 404 errors during transitions.

### Process Management

- Launched by `trigger_daemon.py` supervisor thread (every 2s check).
- Runs as `pythonw.exe` with `CREATE_NO_WINDOW` flag (invisible).
- Uses `SO_REUSEADDR` for clean socket rebinding.
- Automatically superseded when FastAPI binds port 7777.

---

## Key Data Structures

### Workspace App Config (from SQLite)

```json
{
  "type": "chrome",
  "name": "chrome (cherukumanikanta77)",
  "exe_path": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "profile_name": "cherukumanikanta77",
  "profile_dir": "Default",
  "tabs": [
    { "url": "https://github.com/...", "title": "GitHub", "pinned": false },
    { "url": "https://youtube.com/...", "title": "YouTube", "pinned": true }
  ],
  "window": {
    "x": 100, "y": 50,
    "width": 1200, "height": 800,
    "is_maximized": false,
    "title": "GitHub - Chrome"
  },
  "_partial": false,
  "_browser_closed": false
}

Supported App Types
chrome, edge, brave, firefox, vscode, explorer,
uwp, powershell, cmd, terminal, pwsh, app

Live Tabs Cache Format (live_chrome_tabs.json)

{
  "available": true,
  "profiles": {
    "cherukumanikanta77": [
      { "url": "https://...", "title": "...", "pinned": false, "profile": "cherukumanikanta77" }
    ],
    "default": [...]
  },
  "tabs": [ ... ],
  "count": 42,
  "timestamp": "2026-09-22T23:00:00"
}


Port Map
Port	Service	Active When
7777	FastAPI backend (online) / offline_tab_listener (offline)	Always one of them
7778	Panel server (panel_server.py)	Seven running
7779	Panel host command listener	Seven running
7891	Overlay IPC (TCP)	Overlay daemon running
11434	Ollama LLM server	Ollama running
8888	Admin dashboard	Seven running

File Size & Splitting Rules
Maximum 800 lines per file. If a module exceeds this, split into sub-modules.
Splitting pattern: Original file becomes a thin re-export (from .sub_module import *).
Naming convention: hands/workspace_modules/<feature>.py (snake_case).
No circular imports: restore.py imports from all others; no module imports from restore.py.
Known Limitations
Scenario	Behavior	Reason
Seven closed + extension not installed	Offline tab dedup falls back to disk cache (last known state)	No live tab source available
Chrome profile opened AFTER last extension sync	Cache may be stale by up to 3 seconds	Extension sync interval
Incognito tabs	Excluded from all tracking	Chrome extension API restriction
Chrome internal pages (chrome://, edge://)	Filtered out	Not restorable via URL
Two identical URLs in same profile	Both detected as open (no duplicate launch)	URL-level dedup, not tab-count

Debugging Guide
Log Locations

%APPDATA%\SEVEN\logs\trigger_daemon.log    ← Trigger execution + workspace restore
%APPDATA%\SEVEN\logs\panel_server.log      ← Panel server activity
%APPDATA%\SEVEN\logs\python_crash.log      ← Backend crash traces
%APPDATA%\SEVEN\cache\live_chrome_tabs.json ← Current tab cache (inspect manually)

Common Debug Steps
Tabs not restoring offline:

Check if live_chrome_tabs.json exists and contains data.
Verify offline_tab_listener.py is running: netstat -ano | findstr 7777.
Check trigger_daemon.log for [WORKSPACE] Live tabs from cache: line.
Duplicate tabs appearing:

Check if per_profile_urls has data in the log.
Verify profile_dir mapping: [WORKSPACE] Chrome per-profile: N profiles.
Ensure _rekey_by_profile_dir() is resolving correctly.
Profile not detected as open:

Check SingletonLock: dir %LOCALAPPDATA%\Google\Chrome\User Data\<Profile>\SingletonLock.
Verify psutil cmdline access (may be restricted in some Windows configs).
Task panel not opening:

Check ports 7778 and 7779: netstat -ano | findstr "7778 7779".
Verify panel_server.py is running.

Environment Variables
SEVEN_APP_PATH    ← Root directory of SEVEN installation
SEVEN_ELECTRON_MODE=1  ← Set when running under Electron
PYTHONUTF8=1      ← Forces UTF-8 encoding for all Python I/O
