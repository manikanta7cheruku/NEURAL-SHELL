# Knowledge (your documents)

| | |
|---|---|
| Status | Outline. The full write-up follows when this component is reworked, like the [brain](brain.md) |
| Code | `knowledge/`, `backend/routes/knowledge.py`, `brain_modules/layers/layer_53_knowledge.py` |

## Purpose

Lets the user add documents and ask questions about them, entirely offline.

## What exists today

- `indexer.py` reads .txt, .md, .pdf, .docx, .pptx and .xlsx, splits them into chunks and stores them in a ChromaDB collection separate from personal memory.
- Embeddings use the same all-MiniLM-L6-v2 model as memory, so no extra GPU memory is needed.
- The knowledge layer adds matching passages to the model's context; answers are grounded (low temperature).
- The number of files is limited by plan (`knowledge_files`).

## To be written

These sections will follow the structure of the brain document:

- [ ] Purpose
- [ ] How it works
- [ ] Data and configuration
- [ ] Interfaces (what calls it, what it calls)
- [ ] Failure modes and recovery
- [ ] Tests
- [ ] Known limitations
- [ ] Planned work
