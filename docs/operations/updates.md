# Updates

How a new version gets from your dashboard onto a user's PC, what the user sees, what can go wrong and where to look.
The steps for you, as the person publishing, are in [Publishing an update](#publishing-an-update).

| | |
|---|---|
| Code | `backend/updater.py` (check, download, plan), `backend/update_install.py` (install, result), `backend/update_package.py` (changed-files packages), `backend/routes/updates.py`, `frontend/src/pages/Updates.jsx`, `frontend/src/stores/useUpdate.js` |
| Release tooling | `scripts/build_update_package.py`, `scripts/build-installer.ps1`, `installer/SEVEN.iss` |
| Server | `SEVEN-SERVER`: `/api/updates/latest`, `/admin/updates/publish`, the dashboard's Releases tab |
| Tests | `tests/test_updater.py`, `tests/test_update_install.py`, `SEVEN-SERVER/tests/test_server.py` |

## What the user sees

1. A strip at the top of Seven and the Updates page: "Seven 1.3.4 is available", the notes you wrote, and how big the download is.
2. **Download**. The page shows `412 MB of 672 MB · 8.2 MB/s · about 1 minute left`. If the connection drops it continues from
   where it stopped, it does not start again.
3. **Restart and install**. Seven closes, the update is applied, Seven opens as the new version.
4. The Updates page then says "Seven is now 1.3.4". If anything went wrong it says so, why, and where the log is, and the
   update is offered again. Nothing is lost either way: settings, memory, tasks and the licence are not touched.

## Two kinds of update

| | Changed files only (patch) | Full installer |
|---|---|---|
| Size | a few MB (only the files that differ) | about 670 MB |
| Used when | the release has a patch **built for exactly the version this PC has** | every other case: older versions, a release without a patch, Seven running from source |
| How it is applied | the changed files are copied in, each one checked, with a backup that is put back if anything fails | the installer runs silently over the same folder |
| Checked | the package's SHA-256, then every file inside it against the list made at build time, then every file again after it is copied | the SHA-256, that it is a real installer, and that its version is the one announced |

A patch is built against one earlier version, so people more than one release behind take the full installer. The server only
offers a patch to the version it was built for; the app checks that again.

## The patch only goes onto the build it was made from

A patch lists, besides the files it carries, the SHA-256 of **every other file of the old build** and of the old copy of each file
it replaces. Before anything is touched the install script checks them all. A PC whose files are not exactly that build (the same
version number was built again since, a file was changed by hand) gets "Nothing was changed; the full installer will be used
instead", the patch is not tried again for that version (`%APPDATA%\SEVEN\patch_blocked.json`), and Download then fetches the
full installer. The Python runtime folder is left out of this check; a patch that changes it carries those files, each checked
against its old copy.

## How the install works

Seven cannot replace its own files while it runs, so installing starts a PowerShell script (`update_install.py`) that outlives
it. In order:

1. wait for Seven and its backend to exit;
2. stop everything else running from the install folder (the panel host, the overlay and the Python helpers are all started
   from it and would hold files open);
3. a full update runs the installer (`/VERYSILENT`) and **waits for it to finish**; a patch copies the files, backing each one
   up first;
4. read the version that is now on disk. A patch that fails or leaves the wrong version is rolled back;
5. write `%APPDATA%\SEVEN\update_result.json` and only then start Seven again.

The next start reads the result file and tells the person. Before this, the launcher started Seven again a few seconds after the
installer began, whether or not the installer had finished, so a slow or failed install left the old version running and the
update offered again with no explanation.

| File | What it is |
|---|---|
| `%APPDATA%\SEVEN\update_result.json` | `{status: ok or failed, from, to, detail, log}` of the last install |
| `%APPDATA%\SEVEN\logs\update_install.log` | the script's own log: what it waited for, stopped and decided |
| `%APPDATA%\SEVEN\logs\installer.log` | the installer's log (full updates) |
| `%APPDATA%\SEVEN\update_backup\<version>\` | the files a patch replaced, kept until the next update |
| `%TEMP%\SEVEN-Setup-<version>.exe`, `%TEMP%\seven-update\` | the download and the staged patch; removed after a successful install |

## Publishing an update

Once per version, in order. Full detail for the dashboard is in the admin guide.

1. **Bump the version** (`venv\Scripts\python.exe scripts\bump_version.py 1.3.4`). It rewrites every place the number is
   written (version.txt, both package.json files, the lockfile, config.json, config.py, the installer script, the README
   badge); `python scripts\check_version.py` confirms. Update `CHANGELOG.md`, commit and push.
2. **Build the installer**: `npm run build:installer`. This also records the release's manifest,
   `release-manifests\manifest-1.3.4.json.gz`. **Keep it and commit it**: it is what the next patch is compared against.
3. **Build the changed-files update** for people on the previous version:
   `npm run build:update -- --prev 1.3.3` (needs `release-manifests\manifest-1.3.3.json.gz`, recorded when 1.3.3 was built).
   It prints the patch's SHA-256 and size and writes `dist-installer\SEVEN-Patch-1.3.3-to-1.3.4.zip`.
   The script stops with an error if the build folder is not the version in `version.txt`.
4. **Upload both files** to the GitHub release `v1.3.4` in `seven-releases`: `SEVEN-Setup-1.3.4.exe` and the patch zip.
5. **Dashboard, Releases**: version, installer link, installer checksum and size as before, then under **Changed files only**:
   applies to `1.3.3`, the patch link, its SHA-256 and its size. Publish.
6. **Check it like a user** on a PC with 1.3.3: Updates, Check now (it should say "Only what changed is downloaded: N MB"),
   Download, Restart and install, then confirm Updates says "Seven is now 1.3.4".

The first release after this change has no earlier manifest, so it ships as a full installer only; build the manifest for it,
and from the release after that every update can carry a patch.

## Things that stop an update working

| Symptom | Cause | What to do |
|---|---|---|
| "This installer is version 1.3.2, but the update says 1.3.3" | the installer was built before the version was bumped | bump, rebuild, upload again, publish again |
| "The update could not be applied (...). Nothing was changed." | a file was locked or damaged while copying; the backup was put back | read `update_install.log`; the full installer is the fallback |
| "The installer stopped with code N" | the installer failed (disk full, antivirus) | read `installer.log` from the path in the message |
| "The update package is damaged" | the published checksum is not that file's checksum | rebuild, upload, publish with the printed checksum |
| the update is offered again after installing | the installed version is not the published one (an old installer, or a patch for a different version) | compare the dashboard's version with what Updates shows; the result card says which |
| the update never reaches a PC | the dashboard release is paused or targets another plan; or the server was asleep | Releases tab; the app also checks GitHub when the server cannot be reached |

## Limits

- A patch is only for the version it was built against. Skipping versions means the full installer.
- A patch that changes the Python packages (a new library) is as large as those packages, which can be most of the full installer.
- Files a patch adds are not known to the uninstaller (it removes the Python folder and what the installer put there); a later full
  installer takes over everything again.
- The installer is not code-signed yet, so Windows SmartScreen may warn on a first manual install. Updates run from Seven do not
  show it.
