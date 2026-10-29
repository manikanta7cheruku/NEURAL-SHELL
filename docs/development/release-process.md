# Release process

## Versions

Seven uses semantic versioning, `MAJOR.MINOR.PATCH`:

| Part | Bump when | Example |
|---|---|---|
| PATCH | Bug fixes only | 1.3.4 to 1.3.5 |
| MINOR | New features, nothing breaks | 1.3.5 to 1.4.0 |
| MAJOR | A new phase or a breaking change to data or settings | 1.9.0 to 2.0.0 |

`version.txt` is the source of truth. `scripts/bump_version.py` updates it together with `package.json` and
`frontend/package.json`; Python reads it through `seven_utils.version.get_version()`. CI runs
`scripts/check_version.py` to catch a mismatch.

```powershell
venv\Scripts\python.exe scripts\bump_version.py --patch
```

## From change to release

```
feature branch  ->  pull request  ->  CI green  ->  merge to main  ->  bump version  ->  build installer
     ->  test the installer  ->  GitHub Release in seven-releases  ->  users get the update in the app
```

1. **Branch and pull request.** Work on `feature/...` or `fix/...`, open a pull request into `main`.
2. **CI.** `.github/workflows/ci.yml` runs ruff and the tests on Windows, lint and build for the frontend, and the version
   check. A red check blocks the merge.
3. **Merge.** Squash or merge commit into `main`.
4. **Bump the version** on `main` and add an entry to `CHANGELOG.md`. Tag the commit `vX.Y.Z`.
5. **Build the installer** in PowerShell from the project root:

   ```powershell
   npm run build:installer
   ```

   This builds the frontend, packages the app with electron-builder into `dist-electron\win-unpacked`, then compiles
   `installer\SEVEN.iss` with Inno Setup into `dist-installer\SEVEN-Setup-<version>.exe`. It needs Inno Setup 6.3 or
   newer (`winget install --id JRSoftware.InnoSetup -e`).
6. **Test the installer** as a brand-new user: install, first-run setup, update from the previous version,
   uninstall. Follow [installer and fresh-install testing](installer-and-fresh-install-testing.md).
7. **Publish.** Create a release tagged `vX.Y.Z` in `manikanta7cheruku/seven-releases` and upload only
   `SEVEN-Setup-<version>.exe`. Paste the changelog into the release notes.

## How users receive it

The updater (`backend/updater.py`) checks 15 seconds after launch and then every 2 hours (unless the user turned
automatic checking off; "Check now" always works), in this order:

1. `%APPDATA%\SEVEN\update_override.json` (testing and emergencies).
2. The Seven server (`/api/updates/latest`), which can target a plan tier, stage rollouts, pause and withdraw. Published
   from the admin dashboard with a summary, New / Improved / Fixed notes and a SHA-256 checksum. A sleeping server is
   retried for about a minute and a half.
3. GitHub Releases in `seven-releases` (any asset whose name ends in `.exe` and contains "Setup"), **only when the server
   cannot be reached at all**. A server answer of "no update" is trusted. The release description is read for a summary,
   `### New` / `### Improved` / `### Fixed` bullets, a `SHA256:` line and a `[critical]` marker.

The user sees a strip at the top of every screen and the Updates page with the notes. "Download" saves the installer
to `%TEMP%`; Seven checks it (a real installer, and the published checksum) and refuses anything that does not match. "Restart and install" writes a
small batch script that waits for Seven to exit, runs the installer with
`/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-`, relaunches `SEVEN.exe` and deletes itself. Everything under
`%APPDATA%\SEVEN` (settings, memory, tasks, licence) is preserved.

## Hotfixes

For an urgent fix: branch from the release tag, fix, bump PATCH, build and publish. The server pathway can push it to
everyone at once or to one tier first.

## Rollback

There is no automatic rollback yet. To roll back, publish the previous installer again under a higher version number
(for example re-release 1.3.4 as 1.3.6). Automatic rollback is on the roadmap.

## Still to set up

- **Code signing.** The installer is unsigned, so Windows SmartScreen warns "unknown publisher". A code-signing
  certificate (OV or EV) is needed before a public beta; sign `SEVEN.exe` and the installer in `build-installer.ps1`.
- **Release automation.** A GitHub Actions workflow that builds and attaches the installer when a tag is pushed.
- **Crash reporting.** Opt-in reporting (Sentry is already a dependency) wired into the backend and Electron.
- **End-to-end update test** of the Inno Setup silent flags.
