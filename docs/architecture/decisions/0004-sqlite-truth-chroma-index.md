# 0004: SQLite is the source of truth; Chroma is a derived index

- Status: Accepted
- Date: 2026 (brain v4)

## Context

Earlier versions stored facts only as vectors in ChromaDB. Corrections could not be tracked, deleted facts came back
in semantic recall, and there was no history to answer "what did I prefer before?".

## Decision

Facts live in SQLite (`memory/facts_store.py`) as versioned rows with provenance (`origin`, `status`, `valid_from`,
`valid_to`, source message). Conversations live in SQLite with FTS5 search. Chroma holds a semantic index built from
those rows in the background, and it can be rebuilt at any time.

## Alternatives considered

- **Chroma only.** Fast to build, impossible to audit.
- **A graph database.** Expressive, but heavy for a desktop install.

## Consequences

- Seven can say when and where it learned something and what changed since.
- Two stores must stay consistent. Recall filters out anything that is no longer active in SQLite.
