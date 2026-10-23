# Testing

## The layers

| Level | What it proves | Where | Needs |
|---|---|---|---|
| Unit | Single functions (parsers, stores, settings, feedback) behave | `tests/test_brain_units.py`, `test_patches.py`, `test_feedback.py`, `test_version.py` | Nothing |
| Scenario | Multi-turn behaviour of the whole brain with a fake model | `test_brain_scenarios.py`, `test_conversation_intelligence.py`, `test_platform.py`, `test_productivity.py`, `test_settings_system_memory.py` | Nothing |
| Guide contract | Every command shown in the in-app Guide is understood | `test_guide_commands.py` | Nothing |
| Golden conversations | Known good answers stay good | `evals/golden_conversations.json` via `test_golden.py` | Nothing |
| Live evaluation | Real model quality and real first-token latency | `scripts/run_evals.py` | Running Seven and Ollama |
| Frontend | Lint rules and a production build | `npm run lint`, `npm run build` in `frontend/` | Node |
| Manual | Voice, real actions, installer, update | Checklist below | The app |

## Running

```powershell
venv\Scripts\python.exe -m unittest discover -s tests -v
```

Run one file or one test:

```powershell
cd tests
..\venv\Scripts\python.exe -m unittest test_guide_commands -v
..\venv\Scripts\python.exe -m unittest test_brain_scenarios.Scenarios.test_4_and_5_remember_then_recall
```

CI installs only `requirements-test.txt` on a clean Windows runner. If a test passes locally but fails in CI, check
that it does not depend on a package that is only in `requirements.txt`.

## How the tests stay isolated

`tests/support.py` is imported first by every test and sets up a sealed world:

- **Model:** `ollama_client.stream_chat` is replaced by a fake that records the exact prompt and returns a fixed reply.
  `LLM_CALLS` lets a test assert that the model was or was not used.
- **Web:** `FakeWeb` is injected through `brain.EXTRA_DEPS["web"]` with a chosen status (ok, offline, error ...).
- **Storage:** every test gets fresh databases in a temporary folder. `SEVEN_TASKS_DB` and `SEVEN_TRIGGERS_DB` point
  the task, trigger and workspace stores away from your real data. `APPDATA` is redirected too.
- **Tasks:** `FakeTaskStore` stands in for the Dashboard's task database.
- **Network state:** `web_provider.set_online_override`.

`BrainTest` gives each test `ask(text)`, `trace()`, `tasks(...)`, `web(status)` and `run_tags(reply, store)`.

A test must never read or write the real `seven_data/`. If a new store is added, give it an environment override and
set it in `support.py`.

## Writing a good brain test

```python
class Example(BrainTest):
    def test_brightness_is_instant(self):
        reply = self.ask("set brightness to 100")
        self.assertIn("###SYS: action=brightness_set value=100", reply)
        self.assertEqual(LLM_CALLS, [])                      # no model involved
        self.assertEqual(self.trace()["answered_by"], "layer_45_system")
```

- Assert on behaviour the user sees (reply, action tag, stored fact), not on internals.
- Assert which layer answered when routing is the point of the test.
- For a bug, write the failing test first.

## Manual checklist before a release

1. Voice: wake word, push to talk, interrupt, pause and resume.
2. Every card on the Guide's "Try it now" section.
3. Open, snap and close a few apps; a workspace save and restore.
4. A reminder that fires with the window closed.
5. Memory: tell a fact, correct it, see both on the Memory page, delete it.
6. Offline: unplug the network; Seven still works and says so for live questions.
7. Install on a clean Windows machine, update from the previous version, uninstall.

## Placeholders

- Automated UI tests (Playwright against the Vite build): not set up yet.
- Automated voice tests with recorded audio: not set up yet.
- Installer smoke test in CI: not set up yet.
