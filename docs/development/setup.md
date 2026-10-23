# Development setup

How to run Seven from source on Windows.

## Requirements

| Tool | Version | Notes |
|---|---|---|
| Windows | 10 or 11, 64-bit | Hands use Win32 APIs; the full app does not run on macOS or Linux |
| Python | 3.11 | Matches the embedded Python shipped in the installer |
| Node.js | 20 or newer | CI uses Node 22 |
| Ollama | Latest | https://ollama.com, then `ollama pull llama3.2:3b` (or let Seven pick) |
| Git | Any recent | |
| GPU (optional) | NVIDIA with 6 GB or more VRAM recommended | CPU works with smaller models |

## First time

```powershell
git clone https://github.com/manikanta7cheruku/NEURAL-SHELL.git
cd NEURAL-SHELL

python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

npm install
cd frontend
npm install
cd ..
```

`numpy` must stay below 2.0 (torch, faster-whisper, chromadb and sentence-transformers break on 2.x). The pin is in
`requirements.txt`; do not remove it.

## Run

Two terminals give the fastest loop:

```powershell
# terminal 1: backend, brain, voice loop and daemons
venv\Scripts\python.exe main.py
```

```powershell
# terminal 2: UI with hot reload at http://localhost:5173
cd frontend
npm run dev
```

To run the backend API alone (no voice loop), useful for UI work:

```powershell
venv\Scripts\python.exe -m uvicorn backend.api_server:app --host 127.0.0.1 --port 7777
```

To run the full desktop shell in development: `npm run dev` in the project root (starts the backend, Vite and Electron
together).

Only one backend can own port 7777. If an installed copy of Seven is running, quit it first (tray icon, Quit).

## Where your data goes in development

`seven_paths.py` decides. In a development checkout data usually lives in the project's `seven_data/` and `data/`
folders, both ignored by git. Settings are read from `%APPDATA%\SEVEN\config.json` when it exists. Tests never touch
either: they use temporary folders (see [testing](testing.md)).

## Useful scripts

| Command | What it does |
|---|---|
| `python scripts/build_app_manifest.py` | Rebuild the brain's map of the UI after changing pages |
| `python scripts/build_api_reference.py` | Regenerate `docs/reference/http-api.md` after changing endpoints |
| `python scripts/bump_version.py --patch` | Bump the version everywhere (see [release process](release-process.md)) |
| `python scripts/check_version.py` | Check that all version numbers agree (CI runs this) |
| `python scripts/run_evals.py` | Golden conversations against a running Seven and a real model |
| `python scripts/memory_doctor.py --fix` | Clean legacy facts after upgrading memory |
| `npm run build:installer` | Build the Windows installer |

## Editor

Any editor works. Recommended: VS Code with the Python, Ruff and ESLint extensions. Lint before you push:

```powershell
venv\Scripts\ruff.exe check .
cd frontend
npm run lint
```
