# Workspaces

| | |
|---|---|
| Status | Complete for 1.x |
| Code | `hands/workspace_modules/`, `backend/routes/workspaces.py`, `chrome_extension/`, `seven_overlay/` |
| UI | Triggers page, Workspaces tab (`frontend/src/pages/triggers/WorkspaceTab.jsx`) |
| Tests | `tests/test_workspaces.py` |

## Purpose

A workspace is everything open for one kind of work: apps, every browser tab in every window and profile, folders,
documents and code projects. The user saves it once ("save my workspace as Study") and brings it back later
("open my Study workspace", a hotkey, or a trigger). Restoring opens only what is not already open, so it can be run
at any time without duplicating anything.

## Saving: what is captured

`scanner.scan_current()` walks every window that has a taskbar button, skips Seven's own windows and passing
dialogs ("Pick an app", Task Manager), then each kind is filled in:

| Kind | How | File |
|---|---|---|
| Browser windows (Chrome, Edge, Brave) | UI Automation reads every tab title, the active tab's address and Chrome's profile button. The Seven extension's URLs are matched to the titles. Incognito and InPrivate windows are skipped | `browser_capture.py`, `browser_tabs.py` |
| Code projects | VS Code's window title names the folder; it is matched against VS Code's recently opened list | `enrichment.py` |
| Folders | File Explorer windows are paired with their folders by window handle, including Windows 11 Explorer tabs | `enrichment.py` |
| Documents | Word, Excel and PowerPoint report their open files through Office itself (OneDrive and Protected View included); other editors from the window title and command line | `document_capture.py` |
| Terminals | working folder of the process | `scanner.py` |
| Other apps | executable, title, position and size | `scanner.py` |

### Browser tabs, and why the extension matters

UI Automation (the accessibility layer screen readers use) gives every tab's title and the active tab's address, with
no extension. Windows does not expose the addresses of the other tabs, and Chromium locks its session file while it
runs. The Seven extension (`chrome_extension/`, works in Chrome, Edge and Brave) reports every tab's address to
`http://127.0.0.1:7777/api/chrome/tabs` every 3 seconds and on every change. With it, every tab can be reopened.
Without it, tabs other than the active one are saved by title only; the workspace says how many, and restore still uses
their titles to avoid duplicates.

When Seven is closed, `offline_tab_listener.py` takes port 7777 so the extension keeps reporting; the trigger daemon
restarts it when needed and Seven takes the port back when it starts.

## Restoring: only what is missing

`restore.smart_restore()` scans the desktop again and compares item by item.

| Kind | Already open when |
|---|---|
| Browser tab | its address, or a tab with the same title, is open in the same browser and profile |
| Document | that file is open (so a saved Word document opens even if Word is running) |
| Code project | a VS Code window has that folder |
| Folder | an Explorer window shows that folder |
| Other apps | the executable or window is open |

Browsers (`browser_restore.py`):

- Each browser restores into itself (Edge into Edge) with the saved profile.
- **No overlap with the browser's own restore.** When the browser has no window open, it may reopen its last session
  by itself ("Continue where you left off", or Edge after running in the background). Seven starts it plainly, waits
  for that, compares, opens only what is missing, and closes the leftover blank "New tab".
- A saved window whose tabs are all missing comes back as its own window, so multi-window layouts survive.

Windows are moved back to their saved position and size, or maximized.

## Doing it by voice or chat

| Say | Tag | Result |
|---|---|---|
| "scan my current workspace", "capture my setup", "save this workspace" | `###WORKSPACE: action=save` | saved under a dated name |
| "save what I have open as Study", "save my workspace as Study" | `action=save name=Study` | saved as Study, or Study updated |
| "open my Study workspace", "restore workspace Study" | `action=restore id=… name=Study` | restored |

The reply reports what happened ("Saved Study: 9 apps and 37 tabs."). `hands/workspace_modules/actions.py` is the one
place chat, voice, triggers and the Workspaces page save and restore through.

## The status card

`seven_overlay/notification.html` is a small card at the top centre of the screen, kept loaded by
`electron/overlay_daemon.js` and driven over TCP port 7891 by `seven_overlay/notifications.py`. It has states:
**working** (spinner and a moving hairline), **done** (a drawn check and a short chime), **error**. A working card
turns into its result in place:

```python
from seven_overlay.notifications import progress
with progress("Scanning your workspace", "Windows, tabs and documents") as card:
    ...
    card.done("Saved Study", "9 apps", "37 tabs")
```

Triggers that open a workspace show the same card, then the arrangement card.

## Known limitations

- Unsaved changes in a document cannot be restored. Seven reopens the file as it is on disk.
- Without the extension, only the active tab of each browser window keeps its address.
- Firefox tabs are not captured (it has no Chromium session or UI Automation tab list Seven reads yet).
- Apps that do not remember their own state (a calculator's value, a game's level) open fresh.
