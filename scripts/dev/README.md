# Developer scripts

One-off diagnostics kept for reference. They are not part of the app or the
test suite (`tests/`), and they are not packaged into the installer.

Run them from the repository root so imports resolve:

```bash
PYTHONPATH=. python scripts/dev/test_memory.py
```

| Script | What it does |
|---|---|
| `check_data.py` | Prints the contents of the local telemetry database |
| `create_icon.py` | Generates the app icon with Pillow |
| `fix_email.py` | Re-saves the license email into the local database |
| `test_api.py` | Calls each API endpoint on a running backend (port 7777) |
| `test_baseline.py` | Older manual baseline checks, run before refactors |
| `test_memory.py` | Exercises the ChromaDB memory system on its own |
| `test_speakers.py` | Prints stored facts to check speaker ids |
