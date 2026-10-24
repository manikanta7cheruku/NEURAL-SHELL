# Build the installer and test Seven as a brand-new user

This is the procedure for turning the current code into `SEVEN-Setup-<version>.exe` and then installing it the way
a new user would, on your own computer, without losing your real Seven data.

## Part 1: Build the installer

### One-time setup on the build machine

| Need | How |
|---|---|
| Node.js 20 or newer | https://nodejs.org |
| Project dependencies | `npm install` in the project root and in `frontend/` |
| Inno Setup 6.3 or newer | `winget install --id JRSoftware.InnoSetup -e` |
| Embedded Python for the installer | `npm run prepare-python` (downloads Python 3.11.9 into `python-dist/`; run again only when you change Python packages) |

### Every release

Run these in PowerShell from the project root.

1. Make sure you are on an up-to-date `main` with CI green.

   ```powershell
   git checkout main
   git pull
   ```

2. Set the new version. It updates `version.txt` and both `package.json` files together.

   ```powershell
   venv\Scripts\python.exe scripts\bump_version.py --patch
   ```

   Use `--minor` for new features, `--major` for a new phase. Check with `python scripts\check_version.py`.

3. Close Seven completely (tray icon, Quit), then build:

   ```powershell
   npm run build:installer
   ```

   The script stops anything locking the build folder, builds the frontend, packages the app with electron-builder
   into `dist-electron\win-unpacked`, and compiles `installer\SEVEN.iss` with Inno Setup.

4. The result is `dist-installer\SEVEN-Setup-<version>.exe`. The script prints its size and SHA-256 hash; keep the
   hash in the release notes so testers can confirm they have the right file.

If the build fails:

| Message | Fix |
|---|---|
| `Inno Setup 6 not found` | Install it (above), then open a new PowerShell window |
| `electron-builder failed` or a file is locked | Quit Seven and the task panel (tray, Quit Panel Host) and run again |
| The installed app says packages are missing | Run `npm run prepare-python` again, then rebuild |
| `N packaged paths are longer than 150 characters` | A Python package added very deep folders. Exclude them under the `python-dist/python` filter in `electron-builder.yml` (see the torch entries there) |

### "Error 206: The filename or extension is too long" during install

Windows stops at 260 characters per path. Seven installs to `C:\Users\<name>\AppData\Local\Programs\SEVEN\`, and torch
shipped licence folders nested about 20 levels deep plus C++ headers, which went past the limit. Since 1.4 both are
excluded (62 MB smaller) and the build refuses any path longer than 150 characters, so it cannot happen again.

If you saw this error with an older installer: press Cancel, build a fresh installer (Every release, step 3) and run
it. There is no need to uninstall first or delete anything; the half-finished install is replaced. Your data in
`%APPDATA%\SEVEN` is never touched by the installer.

## Part 2: Test it as a new user on your computer

You want a machine where Seven has never run. Pick the option that fits.

| Option | Clean like a real user | Effort | Notes |
|---|---|---|---|
| A. New Windows user account | Very close | Low | **Recommended on Windows 11 Home.** Separate `%APPDATA%`, `%LOCALAPPDATA%` and Ollama models |
| B. Virtual machine | Exact | High | VirtualBox (free). Needs a Windows 11 image and about 60 GB of disk |
| C. Windows Sandbox | Exact | Low | Windows 11 **Pro** only; not available on Home |
| D. Reset your own data | Close | Low | Risky: always back up first |

### Option A: a second Windows account (recommended)

Seven installs per user and keeps all data per user, so a new account is a genuinely fresh start.

1. Settings, Accounts, Other users, **Add account**, "I don't have this person's sign-in information", **Add a user
   without a Microsoft account**. Name it `seventest`.
2. Copy `dist-installer\SEVEN-Setup-<version>.exe` to `C:\Users\Public\Downloads` so the other account can reach it.
3. Sign out, sign in as `seventest`, run the installer from Public Downloads.
4. Go through the checklist in Part 3.
5. To test again from zero: in `seventest`, uninstall Seven, delete `%APPDATA%\SEVEN`, and run the installer again.
   To remove everything, delete the `seventest` account.

What is shared with your main account: Ollama itself if it was installed for all users, and the device ID (it comes
from Windows, see Part 4). Ollama models are stored per user, so the model download in setup is real.

### Option D: reset your own Seven (only if you must)

1. Quit Seven and the panel host (tray icons).
2. **Back up** your data: rename `%APPDATA%\SEVEN` to `%APPDATA%\SEVEN.backup`.
3. Uninstall Seven from Settings, Apps.
4. Install the new `SEVEN-Setup-<version>.exe` and test.
5. To get your real data back: quit Seven, delete the new `%APPDATA%\SEVEN`, rename `SEVEN.backup` back to `SEVEN`.

### Testing only the setup screens during development

With `npm run dev` running, open `http://localhost:5173/#/setup-preview` (or press Ctrl+R in the app after
changing the address). It shows the setup wizard without resetting anything. It runs the real steps, so the
"Getting this PC ready" step really checks and installs dependencies, and finishing it saves your answers.

## Part 3: First-run checklist

Write down the time each step takes; that is what a new user experiences.

| # | Check | Pass when |
|---|---|---|
| 1 | Download and run the installer | Windows shows the publisher (once code signing is set up); installs without admin rights |
| 2 | First launch | The SEVEN splash appears within a few seconds |
| 3 | Welcome to "Choose Seven's brain" | Every step reads clearly; Back works; nothing overlaps on a small screen |
| 4 | Getting this PC ready | Installs what is missing, shows progress, recovers if the internet drops |
| 5 | Choose Seven's brain | The model marked Recommended matches the PC (see Part 5); the download shows progress |
| 6 | You're all set | The app opens on the home screen |
| 7 | Say "Hey Seven" | The orb turns green and the words appear in the session log |
| 8 | Guide, Try it now | Every card works |
| 9 | Settings, Brain | All catalog models listed; download one; Use switches to it; the next reply uses it |
| 10 | Alt+Shift+T | The task panel opens every time, also after quitting Seven |
| 11 | Restart the PC | The panel hotkey works before Seven is opened; reminders still fire |
| 12 | Feedback page | A test report reaches the Google Form |
| 13 | Uninstall | Seven is removed; `%APPDATA%\SEVEN` stays (expected) |

Collect for any problem: the steps, a screenshot, and `%APPDATA%\SEVEN\logs\` (zip the folder).

### One account per PC: continue or start fresh

Seven allows one account per Windows installation. When setup starts on a PC that was used before, the welcome screen
shows **This PC already has a Seven account** with the name, plan and what is still stored (conversations, facts,
documents, tasks), and two choices:

- **Continue as <name>**: keeps everything and skips the questions Seven already knows the answers to.
- **Start fresh as someone new**: copies everything to `%APPDATA%\SEVEN\backups\before-fresh-start_<date>`, clears it,
  and runs setup from the start. The plan stays, because a licence belongs to the PC.

Seven finds an earlier account from data left in `%APPDATA%\SEVEN` (uninstalling keeps it) or, when online, from the
device registration on the Seven server. To see this screen during development, open `#/setup-preview`.

## Part 4: How Seven identifies a device

There is no account login. Seven registers each computer by a **device ID**:

1. On first run it reads the Windows **MachineGuid** (`HKLM\SOFTWARE\Microsoft\Cryptography\MachineGuid`), a
   value Windows creates at installation.
2. It caches it in `%APPDATA%\SEVEN\data\device_id.txt`. Setup registration, telemetry and licence activation all
   use this same ID (`telemetry.get_device_id()`).
3. If the registry can't be read, it falls back to a random ID, which is then kept in that file.

What this means:

| Situation | Device ID |
|---|---|
| Restart, update Seven, reinstall Seven | Same |
| Delete `%APPDATA%\SEVEN` | Same (read again from Windows) |
| Another Windows account on the same PC | Same (MachineGuid is per machine) |
| Reinstall or reset Windows, new PC | New |

Verified on the development PC: the cached ID matches the MachineGuid.

## Part 5: Fast and smooth on every PC

Seven picks its heavy components by hardware, so a low-end laptop and a gaming PC both stay responsive:

| Hardware | Language model (recommended) | Speech recognition |
|---|---|---|
| Graphics card with 8 GB or more | Qwen 2.5 7B | Whisper medium on the GPU |
| Graphics card with 4 to 8 GB | Llama 3.2 3B | Whisper medium on the GPU |
| No graphics card, 16 GB memory or more | Llama 3.2 3B | Whisper small on the CPU, limited threads |
| No graphics card, less memory | Llama 3.2 1B | Whisper small on the CPU, limited threads |

The model list and these rules live in `brain_modules/model_catalog.py`; setup, Settings and "Automatic" all use
it. The user can always pick a different model in Settings, Brain.

Test on at least one PC from each row before a public release. A borrowed or older laptop without a graphics card
is the most important one: if Seven feels good there, it feels good everywhere.
