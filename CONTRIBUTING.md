# Contributing to Seven

Seven is developed by Seven Labs. This guide is for anyone working on the code.

## Before you start

1. Read the [architecture overview](docs/architecture/overview.md) and the document for the component you will touch
   (for example [the brain](docs/components/brain.md)).
2. Set up your machine with [development setup](docs/development/setup.md).

## Workflow

1. Create a branch from `main`: `feature/<short-name>`, `fix/<short-name>`, `docs/<short-name>` or `chore/<short-name>`.
2. Make the change with tests. A bug fix starts with a failing test.
3. Run the checks locally:

   ```powershell
   venv\Scripts\ruff.exe check .
   venv\Scripts\python.exe -m unittest discover -s tests
   cd frontend
   npm run lint
   npm run build
   ```

4. If you changed pages, run `python scripts/build_app_manifest.py`. If you changed endpoints, run
   `python scripts/build_api_reference.py`.
5. Update the docs that describe what you changed, and add a line under "Unreleased" in `CHANGELOG.md`.
6. Open a pull request into `main`. Describe what changed, why, and how you tested it. CI must be green before merge.

## Standards

See [coding standards](docs/development/coding-standards.md). In short: match the surrounding code, keep one source of
truth, never fail silently, and write plain UI text without em dashes.

## What not to commit

Secrets and keys, `.env` files, databases (`*.db`), `seven_data/`, `data/`, `venv/`, `node_modules/`, build output
(`dist*/`, `python-dist/`), logs, recordings, and anything personal. `.gitignore` covers these; check `git status`
before every commit.

## Reporting a security problem

Do not open a public issue. Follow [SECURITY.md](SECURITY.md).
