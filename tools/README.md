# Internal tools

Tools for running Seven Labs, not part of the app. Nothing in this folder is packaged into the installer
(`electron-builder.yml` lists the shipped files explicitly).

| Tool | Purpose |
|---|---|
| `admin_tools.py` | Generate licence keys, grant referral rewards, publish update records. Run from the project root: `python tools/admin_tools.py` |
