# Coding standards

## General

- Match the code around you: naming, comment density and idiom.
- One source of truth. If two places need the same list or number, one reads it from the other.
- No silent failures. Log, report to the user, or return an explicit status.
- Small pull requests that do one thing, with tests.

## Python

- Python 3.11. Lint with `ruff check .` (rules in `ruff.toml`; CI fails on errors).
- Module docstring at the top: what the module is for and why it exists. Explain the why, not the what.
- Brain layers return `LayerResult` and never raise into the pipeline.
- New stores take their path from an environment variable or a `set_db_path` function so tests can isolate them.
- Avoid shadowing imported names inside functions (a `get_version` shadow once caused a recursion and a 500 error).
- Print statements that include emoji are fine; the API server forces UTF-8 output.

## Frontend

- React function components and hooks; state in Zustand stores under `src/stores/`.
- Build pages from the UI kit (`src/components/ui.jsx`). Do not hand-roll buttons, inputs or sections.
- Colours only through tokens (`bg-s-surface`, `text-s-text-2` ...), so both themes work.
- Type scale: page title 15px, section 13px, body 12.5px, secondary 11.5px, meta 11px.
- Every page gets a `/* SEVEN_DOC {...} */` comment so the brain can explain it.
- Lint with `npm run lint`. Errors block CI; warnings are tracked debt.

## Writing (UI text and docs)

- Plain words, short sentences, active voice.
- Say what happened and what to do next. "Seven is not running yet. Give it a moment and try again."
- Never claim something worked unless it did.
- No em dashes. Use a full stop, a comma or a colon.
- Sentence case for headings and buttons ("Save workspace", not "Save Workspace").

## Commits and branches

- Branch from `main`: `feature/...`, `fix/...`, `chore/...`, `docs/...`.
- Conventional commit subjects: `feat(guide): ...`, `fix(brain): ...`, `docs: ...`, `chore(ci): ...`.
- The body explains why. Reference the issue if there is one.
- Never commit secrets, databases, `venv/`, build output or personal data (see `.gitignore`).
