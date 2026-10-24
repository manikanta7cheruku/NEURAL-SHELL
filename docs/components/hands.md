# Hands (actions on Windows)

| | |
|---|---|
| Status | Complete for 1.x. Workspaces have their own page: [Workspaces](workspaces.md) |
| Code | `hands/`, action execution in `backend/routes/chat.py` and `main_modules/handlers/` |
| Tests | `tests/test_hands_routing.py`, `tests/test_platform.py`, `tests/test_workspaces.py` |

## Purpose

Seven is the layer between a person and Windows. The brain decides what the user wants; the hands do it on the PC:
open and close apps, arrange windows, change system settings, find and open files, and save and restore workspaces.
Every action produces a receipt, so Seven never says something worked unless it did.

## How a request becomes an action

```
"put chrome on the left"
  -> brain layer 4.5 (layer_45_window) recognises it, replies and appends a tag:
        "Snapping chrome to the left. ###WINDOW: action=snap target=chrome position=left"
  -> backend/routes/chat.py _execute_actions() runs each tag through action_receipts.run_action()
        WINDOW -> hands/windows.py manage_window()     SYS  -> hands/system.py manage_system()
        OPEN   -> hands/core.py open_app()             CLOSE -> hands/core.py close_app()
        WORKSPACE -> hands/workspace_modules/actions.py
  -> receipts: success, failed (with the reason) or unconfirmed
  -> action_receipts.reconcile_reply() replaces an optimistic reply when something failed
```

The voice path runs the same tags through `main_modules/handlers/`. Risky actions wait for a yes first
(`brain.needs_confirmation`): closing every app, airplane mode and emptying the Recycle Bin.

## Apps

`hands/app_launcher.py` tries, in order:

1. A URL or a site name ("open github") in the browser.
2. A drive ("open drive D") or a special folder ("open downloads").
3. Built-in Windows apps with special launchers (Camera, Settings, Calculator, Notepad, File Explorer, WhatsApp).
4. The fast-launch table: common apps and Windows tools by their everyday names, including Control Panel, Device
   Manager, Disk Management, Services, Event Viewer, Registry Editor, Microsoft Store and Settings pages.
5. The installed-apps index (`hands/app_discovery.py`): Start Menu, registry, Store apps, Desktop shortcuts and PATH.
6. A direct path, then AppOpener as a last resort.

**Newly installed apps and games.** The index is rebuilt every 7 days, and also whenever an installer has added or
removed a shortcut in the Start Menu or on the Desktop since the last scan (a check of folder times that takes about
5 ms). When a name is not found, Seven rescans once (about 3 seconds) before giving up, so a game installed a minute
ago opens the first time it is asked for.

`hands/app_closer.py` closes by name, closes all, or closes "this".

## Windows

`hands/windows.py` focuses, minimizes, maximizes, restores, snaps (left, right, corners), centres, resizes, moves to
another monitor, pins on top, changes transparency, closes and undoes. `hands/window_layout.py` arranges several apps
(split, stack, grid).

**"This window".** While the user types to Seven, Seven has focus. So "this window", "close this" and "maximize it"
mean the window the user was in before: Seven walks down the window stack (Z-order) to the first visible window that is
not one of Seven's own. Before 1.4 these acted on Seven itself.

## System

`hands/system.py`: volume (set, up, down, mute), brightness, Wi-Fi, Bluetooth, media keys, dark mode, night light,
do not disturb, airplane mode, battery, lock the PC, take a screenshot (saved to Pictures, Screenshots) and empty the
Recycle Bin. Each returns `(ok, message)` from what Windows reported.

## Files

`hands/files.py` answers "open my resume", "find my photos from Goa" and "open the last pdf I downloaded".

| Source | What it adds |
|---|---|
| Seven's file index (SQLite FTS5) | fast name search over the user's folders and drives |
| Windows Search index (`hands/windows_search.py`) | every file Windows has indexed, matched by name or by the folder it is in |
| File content index (`hands/file_content.py`) | text inside documents, when names do not match |

**Ranking.** A file scores for matching the name (exact, whole word, start of a word), its type when one was asked
("video", "pdf"), and recency. Then three signals from Windows make "my" mean the user's own file:

- opened recently, from Windows Recent items: +400 within a week, +250 within a month
- the user's name from their Windows account in the file name: +150
- in their Desktop, Documents, Downloads or OneDrive: +40

**No guessing.** Short words must match closely ("trip" no longer matches "TRIM_2019"). A request for a type never
returns folders. Plural requests ("my photos") list results instead of opening one. If the best match is weak, Seven
lists the matches and asks. When it opens a file it names it: "Opened Resume.pdf from Documents. 7 other matches are
in the chat if it's not the one."

**Newest file.** "the last pdf I downloaded" or "my latest screenshot" opens the newest matching file in Downloads,
Screenshots, Desktop or Documents. It is never mistaken for "the last item of the list Seven just showed".

## Interfaces

- Tags from the brain: `###OPEN:`, `###CLOSE:`, `###WINDOW:`, `###SYS:`, `###WORKSPACE:`.
- HTTP: `/api/files/open`, `/api/workspaces/*`, `/api/chrome/*`, `/panel/*` ([HTTP reference](../reference/http-api.md)).
- Notifications: `seven_overlay/notifications.py` sends the status card at the top centre of the screen.

## Failure modes

| Problem | Behaviour |
|---|---|
| App not found | rescans installed apps once, then says it couldn't find it |
| Window not found | "Can't find window: X", and the reply says it didn't work |
| Windows Search service off | Seven's own index still answers |
| A Windows API refuses (brightness on some desktops, Bluetooth radios) | the receipt is "failed" with the reason |

## Known limitations

- Seven cannot click inside other apps or read the screen yet. It works through Windows APIs, the shell and UI
  Automation, not by looking.
- Brightness only works on displays that support software control (laptop panels, some monitors).
- Files on drives Windows has not indexed are found only once Seven's own index has covered them.
