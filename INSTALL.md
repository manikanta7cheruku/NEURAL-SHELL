# Installing the brain overhaul

1. Close Seven. Commit or back up your repo.
2. Copy the contents of this folder over the repo root (same relative paths). Every file here
   replaces the file of the same name; `layer_025_social.py`, `layer_56_live_guard.py`,
   `brain_modules/{session,speech_acts,social_engine,fact_extractor,memory_gate,learning,
   capabilities,response_filter}.py`, `memory/fact_service.py`, `backend/routes/brain.py`,
   `scripts/` and `tests/` are new.
3. Apply the five small edits in PATCHES.md.
4. Run the tests:  `python -m unittest discover -s tests -v`
5. Start Seven, then run `python scripts/memory_doctor.py --fix` once to clean old memory.
6. Run `python scripts/brain_smoke_test.py` for live timings, and open
   http://127.0.0.1:7777/api/brain/diagnostics to see the model, latencies and memory health.
