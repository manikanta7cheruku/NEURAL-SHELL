# Installing SEVEN brain v4

1. Read `docs/HANDOFF.md` section A and follow it. The short version:
2. Copy this folder's contents over your repository root (diff the rewritten files first).
3. `python scripts/apply_patches.py` (dry run), then `python scripts/apply_patches.py --apply`.
4. `python -m unittest discover -s tests` (expect OK).
5. Start Seven, run `python scripts/memory_doctor.py --fix` once, then follow the manual test plan in `docs/HANDOFF.md`.

Full documentation: `docs/BRAIN.md`. Roadmap: `docs/ROADMAP.md`. Self-learning design: `docs/SELF_LEARNING.md`.
