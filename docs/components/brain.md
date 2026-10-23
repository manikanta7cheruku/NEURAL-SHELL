# Brain

| | |
|---|---|
| Status | Complete. Describes brain v4 as it exists in this repository |
| Code | `brain.py`, `brain_modules/`, `memory/` |
| Tests | `tests/test_brain_units.py`, `test_brain_scenarios.py`, `test_conversation_intelligence.py`, `test_platform.py`, `test_productivity.py`, `test_settings_system_memory.py`, `test_guide_commands.py`, `test_golden.py` |
| Related | [Architecture overview](../architecture/overview.md), ADRs [0002](../architecture/decisions/0002-layered-brain-pipeline.md), [0004](../architecture/decisions/0004-sqlite-truth-chroma-index.md), [0006](../architecture/decisions/0006-action-receipts.md) |

## 1. What the brain does

The brain turns one message ("set brightness to 100", "what did I say my favourite language was?", "explain
recursion") into the right outcome: an action on the computer, an answer from stored evidence, or a reply from the
language model. It has to behave like one consistent person over time:

1. Understand the goal, not only the words.
2. Know the user through evidence it can show: what was said, when, and in which chat.
3. Know itself: what it can do right now, how its own app works, and what leaves the machine.
4. Be honest: say "I don't know", "I'm offline" or "that failed" instead of inventing.
5. Act reliably: claim an action worked only when a receipt says so.
6. Learn without drifting: from explicit facts, corrections, feedback and verified outcomes, never from silent guesses.
7. Stay fast: instant paths in milliseconds, streamed tokens for everything else.

Rules every change must respect:

- **One source of truth** per fact about the world: the capability registry, the app map, the settings registry,
  plan limits. Never a second copy inside a prompt.
- **Deterministic where correctness matters** (commands, identity, time, abilities, recall, data flow). The model is
  for conversation.
- **Evidence before assertion.** Personal facts come from stored evidence.
- **Nothing is silently dropped.** Failures are reported and history is never deleted to make room.
- **The reply path stays cheap.** Learning, indexing and summaries run on a background worker.

## 2. Where the brain sits

```
Console (React)                              Voice loop (ears and mouth)
   |  POST /api/chat  (stream=true: SSE)        |  brain.think(text, speaker, "sentence")
   v                                            v
backend/routes/chat.py  ---------------->  brain.py : think()
   |  runs action tags, collects receipts,          |
   |  asks before risky actions                     v
   |                                       brain_modules/pipeline.py  (ordered layers, section 4)
   |                                                |
   |      +-------------------+-------------------+-+-----------------+------------------+
   |      v                   v                   v                   v                  v
   |  conversation_state  intent_router +     memory_gate +      decision_policy    prompt_builder +
   |  (working memory)    self_knowledge      fact_service       (mode, evidence)   ollama_client
   |                                          (SQLite truth)                        (streamed tokens)
   v
action_receipts  <---  hands/*                memory/*: facts_store, conversation_store, learning_store
                                              Chroma user_facts (derived index), idle_worker, reflection
```

## 3. Lifecycle of one message

`brain.think(text, speaker_id, stream_mode, conversation_id)`:

1. **Resolve who and where.** `session.resolve_key` turns the speaker into a storage key (the owner's name once it is
   set). `conversation_store.ensure` returns the conversation: the one the UI sent, the current chat (6 hour idle
   window) or a new one.
2. **Save the user message first.** If saving fails, the reply is still produced and the trace carries
   `storage_error`, so the UI can say "this message was not saved".
3. **Dialogue checks.** Pending confirmations ("close all 7 Chrome windows?") and references ("open the second one").
4. **Run the pipeline.** The first layer that answers wins (section 4).
5. **Finish.** Prefix acknowledgements from compound messages, update working memory, save the assistant message,
   queue background learning.

`stream_mode` decides the shape of the result: `text` (a string), `token` (a generator for the Console's SSE stream)
or `sentence` (a generator that flushes at clause boundaries so speech can start early).

`backend/routes/chat.py` then executes any action tags in the reply, reconciles the reply with the receipts and
streams it to the UI. Each SSE stream sends the conversation id, then tokens, an optional save warning, a `done` event
with the trace, and `[DONE]`. Non-streaming responses include `receipts`.

## 4. The pipeline

Each layer receives a shared `BrainContext` and returns a `LayerResult`: either "stop with this reply" or "pass on".
Layers are imported lazily; one that fails to import is skipped and logged, never fatal.

| Order | Layer | What it handles | Stops? |
|---|---|---|---|
| 00 | `input_prep` | Speaker, cleaned text (`clean_in`, `norm_in`, words), flags; silent acknowledgements ("ok") unless Seven is waiting for an answer | "ok" only |
| 01 | `name` | "My name is ..." (the rest of a compound message continues) | Name only |
| 015 | `state` | Answers to Seven's own questions, risky-action confirmations, reference resolution, one clarifying question when ambiguous | When pending |
| 025 | `social` | Greetings, thanks, goodbyes, "how are you", pushback, without memory or model | Yes |
| 02 | `repetition` | The same genuine question again | Yes |
| 03 | `identity` | Who Seven is, who made it, version, model, hardware questions, time and date, "can you ..." | Yes |
| 034 | `settings` | "Set honesty to 75%", "switch your model to ...", "what are your settings" | Yes |
| 036 | `productivity` | Show and change tasks, schedules, triggers and workspaces by name | Yes |
| 035 | `router` | Semantic intents about Seven itself (abilities, how the app works, where data lives) and the user's goals | Yes |
| 38 | `file_root` | "Add M:\edit to search folders" | Yes |
| 04 | `tars` | Personality sliders and mood analysis (mood affects tone) | When matched |
| 43 | `file_search` | "Open my resume", "find the invoice pdf" | Yes |
| 45a | `tasks` | Create, list, complete tasks | Yes |
| 45b | `suggest` | "I need to finish X" suggests a task without creating it | Yes |
| 45h | `trigger` | Fire triggers, save and restore workspaces | Yes |
| 45c | `scheduler` | Reminders, alarms, timers, recurring, cancel | Yes |
| 45d | `battery` | Battery and charging | Yes |
| 45e | `system` | Volume, brightness, Wi-Fi, Bluetooth, media, dark mode, night light, DND, airplane mode | Yes |
| 45f | `window` | Focus, snap, minimize, maximize, layouts, monitors, pin, transparency, undo | Yes |
| 45g | `app` | Open, close and search for apps and sites | Yes |
| 05 | `memory` | Direct recall from stored evidence; starts semantic search in the background when needed | On recall |
| 53 | `knowledge` | Retrieves passages from the user's documents into the context | No |
| 55 | `web` | Asks the web provider; records a `WebOutcome` (ok, offline, disabled, error, empty, not needed) | No |
| 56 | `live_guard` | Honest reply when fresh data was needed and is unavailable | Yes |
| 59 | `app_history` | "What apps did I open today" | Yes |
| 06 | `personal_filter` | Honest "I don't know" for personal questions with no evidence, with near-miss help | Yes |
| 07 | `facts` | Style feedback, corrections, new facts, goals, explicit "remember" | Explicit only |
| 075 | `proactive` | Adds a gentle suggestion hint for the model | No |
| 08 | `llm` | Policy, prompt, streamed generation, optional curiosity question, recording | Always |

Order matters. Settings and productivity run before the router and file search so "show my tasks" is never treated as
a file lookup and "set humor to 40" is never treated as a question about the app.

## 5. Commands and action tags

Instant layers do not perform actions themselves. They return a short spoken reply plus a tag, for example
`Brightness to 100%. ###SYS: action=brightness_set value=100`. The tag format is `###KIND: key=value key=value`.
Spaces inside a value are written as `|||` (for example `targets=chrome,file|||explorer`).

| Tag | Produced by | Executed by | Examples |
|---|---|---|---|
| `OPEN`, `CLOSE`, `SEARCH` | `layer_45_app` | `hands/app_launcher.py`, `app_closer.py` | open chrome, close spotify |
| `WINDOW` | `layer_45_window` via `command_router._build_window_tag` | `hands/windows.py` | snap, layouts, pin, transparency |
| `SYS` | `layer_45_system`, `layer_45_battery` via `_build_system_tag` | `hands/system.py` | volume, brightness, toggles |
| `SCHED` | `layer_45_scheduler` | `hands/scheduler.py` | reminder, alarm, timer, cancel |
| `TASK` | `layer_45_tasks`, `productivity`, `lifecycle` | `lifecycle.execute_task_action` | create, complete, delete |
| `TRIGGER`, `WORKSPACE` | `layer_45_trigger`, `productivity` | trigger and workspace routes | fire, save, restore |

Two executors read the same tags: `backend/routes/chat.py` for the Console and `main_modules/handlers/*` for voice.

**Receipts.** In the chat route every tag runs through `action_receipts.run_action`, which returns `success`,
`failed` or `unconfirmed` (it verifies the process for known apps). `reconcile_reply` rewrites the reply when an action
failed ("I tried to change that setting, but it didn't work"). `brain.note_receipts` records outcomes for tool health
and offers to remember an alias when a failed launch is followed by a verified different one.

**Risk.** High-risk actions (`CLOSE: ALL_*`, airplane mode on) pause for a yes when `agent.confirm_risky` is on (the
default). Questions about state ("is wifi on") always read the state; they never toggle it.

## 6. Conversations and working memory

- A **conversation** is a saved chat (`conversations` and `messages` tables, short hex ids).
- **Short-term context is keyed `<speaker>#<conversation>`**: chat history for the model, the repetition thread and
  working memory (`conversation_state`: topic, entities, pending question, last recalled fact, last receipts). A new
  chat starts clean while long-term facts stay available.
- **Cross-chat retrieval** happens only when the user points at the past ("last time", "earlier"). Snippets from other
  chats are added as evidence and labelled "what was said, not verified truth".
- **References** ("that movie", "it") resolve to the topic of recent turns. Several candidates mean a question, not a
  guess.
- When the owner's name is set, everything stored under the old key moves to the new one
  (`brain._migrate_speaker_key`).

## 7. Memory

| Store | File | Role |
|---|---|---|
| Facts | `facts_structured.db` | **Source of truth.** Versioned slots with provenance |
| Conversations | `conversations.db` | Permanent transcript, FTS5 search, summaries |
| Learning | `learning.db` | Knowledge gaps, outcomes, goals, mention counts |
| Semantic index | Chroma `user_facts` | Derived from facts, rebuildable, written in the background |
| Legacy | Chroma `conversations` | Imported once into real conversations |

**Facts** are one row per version of a slot (`favorite_programming_language`, `likes:movie:interstellar`,
`reason:<slot>`), with `raw_value`, `value`, `origin` (explicit, observed, inferred), `status` (current, former,
deleted), `valid_from`, `valid_to`, `source_msg_id`, `conversation_id`, `confidence` and `mentions`. A new value closes
the old row instead of overwriting it, so "what did I prefer before?" stays answerable.

**Extraction** (`fact_extractor`) accepts only declarative statements. Questions and commands never become facts.
Values are validated, passing states ("my code is broken") are not stored, and an explicit "remember" is always
honoured. "I love X" (`likes:`) is kept separate from "my favourite is X" (`favorite_`). "I prefer X over Y" stores X and
supersedes Y. A "because ..." clause is stored as a separate reason.

**Answers from evidence** (`fact_service`): current value, history, timeline, provenance ("You first told me Python on
Oct 7, then changed it to JavaScript today") and reasons (only if the user gave one). The Memory page uses the same
service (`add_manual`, `edit`, `delete`, `forget_all`), so what the page shows is what the brain recalls.
`_still_active` filters semantic hits that were deleted or replaced.

**Limits** (`memory/limits.py`): conversations and facts are unlimited on every plan. Writes are refused, with a
message to the user, only when disk space is low or an optional storage budget is reached.

## 8. Knowing itself and the computer

- **Capability registry** (`capabilities.py`). Every ability declares what it needs (a module, a setting, a plan
  feature, the internet). `status()` reports available, degraded (recent failures), disabled, unavailable,
  needs internet or needs a plan. Modules can self-register with a top-level `CAPABILITY = {...}` literal that is read
  with `ast`, without importing the module. A `NOT_YET` list makes Seven say "not yet" for planned abilities such as
  seeing the screen.
- **App map** (`app_map.py`, `brain_modules/data/app_map.json`). Generated from the frontend: routes, page titles,
  `PageShell`, `Section` and `Row` props, sidebar labels and `/* SEVEN_DOC {...} */` comments. Answers "where do I
  change X". Rebuild with `python scripts/build_app_manifest.py` (CI builds the frontend the same way).
- **Settings registry** (`brain_settings.SETTINGS`). Type, bounds, default and where each setting applies.
  `settings_control.py` parses chat requests against it; `/api/config/brain` validates against the same registry.
- **System info** (`system_info.py`). Live readings through psutil, the registry CPU name, `nvidia-smi` and the
  Windows build number. "What GPU do I have" is answered from these, never from the model.
- **Data flow** (`self_knowledge.outbound_flows`). Built from live configuration so "where is my data" and "what do
  you send" always agree.
- **Intent router** (`intent_router.py`, `data/intents.json`). Character n-gram TF-IDF similarity to labelled
  examples, with negative examples and learned corrections.

## 9. When the model answers

`decision_policy.decide()` chooses a mode:

| Mode | When | Effect |
|---|---|---|
| `chat` | Ordinary conversation | Normal settings |
| `grounded` | Web or document evidence present | Temperature capped at 0.2 |
| `deep` | Complex requests | 1.6x tokens, temperature capped at 0.3, optional `brain.reasoning_model` |
| `clarify` | Ambiguous references | One short question instead of a guess |

It also produces an **evidence status** list ("Live information is unavailable (offline)", "Nothing is stored about
this") that the model receives as plain text, so it states limits instead of guessing.

**Prompt** (`prompt_builder.build_messages`): a stable system prompt first (`<identity>`, `<character>`,
`<behavioral_rules>`) so Ollama can reuse its prompt cache, two few-shot exchanges, time-limited history, then the
user message with a `<reference_only>` block only when needed (`<memory_context>`, `<web_results>`,
`<knowledge_context>`, `<capabilities>`, `<user_goals>`, `<conversation_notes>`, `<evidence_status>`, `<clock>`).
Identity (Seven, made by Seven Labs) is a constant and never read from config.

**Output** (`response_filter.StreamSanitizer`) strips role prefixes, echoed tags and any `###` action text from the
token stream. A post-check (`unsupported_personal_claim`) refuses replies that assert personal history without
evidence in text mode; streamed modes cannot retract, so they only record it.

**Model management.** `ollama_client` is the only module that talks to Ollama: one pooled connection, `keep_alive`
of 24 hours, warm-up at start, constant `num_ctx` per model. `brain.current_model()` reads the configured model on
every call, so a switch from Settings or chat applies to the next message. `brain_manager.py` recommends a model by
VRAM. If generation is interrupted, the partial reply is saved.

## 10. Learning

Three mechanisms sit on top of memory and policy, each bounded and reversible:

- **Goals** (`goals.py`). Explicit goals ("I'm building ...", "I need to finish X by Friday") are tracked with a
  lifecycle and given to the model so it serves the purpose behind a request. Goals are never inferred.
- **Outcomes** (`learning_store.outcomes`). Receipts, corrections, thumbs feedback and question outcomes change only
  tool health, confirmed aliases and question pacing. Outcomes never become facts about the user.
- **Curiosity** (`curiosity.py`). At most one grounded question every few turns, tied to a recorded gap. Ignored
  questions cool down. Level: `brain.curiosity_level` (off, low, normal).

Background jobs on the `idle_worker`: `learn`, `apply_correction`, `index_fact`, `store_conversation`, `reindex`,
`migrate`, `import_legacy`, `reflect`, `consolidate`. Summaries are extractive, so no model call and no invention.

## 11. Settings that change the brain

All live in `brain_settings.SETTINGS` and can be changed in Settings, Brain or by chat. Verified by tests: model,
temperature, humor and honesty (prompt only), streaming, history window, memory relevance and retrieval timeout,
curiosity level, web lookups, telemetry and storage budget. `GET /api/brain/settings` shows configured and effective
values; invalid values are clamped.

## 12. Performance

Instant layers answer in milliseconds. Memory search overlaps other layers, capped by `memory.retrieval_timeout_ms`.
Voice uses sentence streaming so speech starts at the first clause. First-token and total latency are recorded and
visible at `/api/brain/diagnostics`.

## 13. Tracing a request

To see why Seven answered the way it did:

1. `GET /api/brain/diagnostics` for the model, latency, memory and worker queue.
2. The `done` event of `/api/chat` (or `brain.get_trace(speaker, conversation)`) includes `answered_by` (the layer
   that stopped the pipeline), the mode, sources and timings.
3. In a test, `BrainTest.ask()` and `self.trace()` give the same information without a model (see
   [testing](../development/testing.md)).

## 14. Extending the brain

| To add | Do this |
|---|---|
| A new command | Handle it in the right layer (or a new layer added to `LAYER_ORDER`), return a tag, execute it in `chat.py` and `main_modules/handlers`, add phrases to `frontend/src/guide/guide.json` and tests |
| A new ability Seven can describe | Add `CAPABILITY = {...}` to the module, or an entry in `capabilities._builtin` |
| A new screen or control | Write the JSX with `PageShell`/`Section`/`Row`, add a `SEVEN_DOC` comment, rebuild the app map |
| A new intent about Seven | Add a label with 8 to 15 examples to `intents.json`, a handler in `self_knowledge.answer`, a test |
| A new setting | Add it to `brain_settings.SETTINGS` and a test proving where it takes effect |
| A new learning signal | Record an outcome; change behaviour only through a bounded, reversible, tested channel |

## 15. Known limitations

- Free conversation quality is set by the local model. A 1B model cannot carry the personality or reasoning mode well;
  3B to 8B is recommended.
- The voice path executes tags through its own handlers; receipts and risky-action confirmation are wired into the
  chat route only.
- Process verification works only for apps with a known process name; others are reported as unconfirmed.
- Known misroutes: "switch to Chrome" restores a workspace named "chrome" instead of focusing the window; "what do
  you know about me" and "where is my data stored" give weak answers; "remind me to drink water every hour" stores
  "every hour" as part of the message.
- Streamed replies cannot be retracted after an unsupported claim.
- Encryption at rest is not implemented.
- Semantic recall needs the embedding model, which loads in the background; direct recall works before it is ready.
