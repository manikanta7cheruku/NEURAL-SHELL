# Architecture decision records

Each record explains one significant decision: the situation, what was chosen, what else was considered and what it
costs. Records are not rewritten after the fact. A later decision that changes course gets a new record that
supersedes the old one.

| # | Decision | Status |
|---|---|---|
| [0001](0001-local-first.md) | Everything runs on the user's computer | Accepted |
| [0002](0002-layered-brain-pipeline.md) | The brain is an ordered pipeline of layers; the model is the last one | Accepted |
| [0003](0003-ollama-for-models.md) | Run language models through Ollama | Accepted |
| [0004](0004-sqlite-truth-chroma-index.md) | SQLite is the source of truth; Chroma is a derived index | Accepted |
| [0005](0005-electron-react-fastapi.md) | Electron and React for the app, FastAPI on localhost for the backend | Accepted |
| [0006](0006-action-receipts.md) | Every action produces a receipt and the reply is reconciled with it | Accepted |
| [0007](0007-inno-setup-installer.md) | Inno Setup instead of NSIS for the installer | Accepted |

To add a record, copy [0000-template.md](0000-template.md) and take the next number.
