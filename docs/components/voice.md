# Voice (the whole loop)

| | |
|---|---|
| Status | Complete. Describes voice as it works since October 2026 |
| Code | `main_modules/startup/voice_loop.py`, `main_modules/startup/greeting.py`, `main_modules/handlers/pre_executor.py`, `backend/routes/voice.py`, `backend/routes/status.py`, `electron/status.html`, `frontend/src/pages/Landing.jsx`, `frontend/src/pages/settings/VoiceSection.jsx` |
| Tests | `tests/test_greeting.py`, `tests/test_live_voice.py`, `tests/test_voice_text.py` |
| Related | [Ears](ears.md) (hearing), [Mouth](mouth.md) (speaking), [Brain](brain.md) (understanding) |

This page follows one spoken request from the microphone to the answer, and describes everything around it that
the user sees: the greeting, the voice bar, the home screen, Settings and setup.

## 1. One request, start to finish

"Hey Seven, show Chrome":

| Time | What happens | Where |
|---|---|---|
| 0 ms | You finish speaking; the speech detector sees 0.6 s of silence and closes the utterance | `ears/stream.py` |
| ~500 ms | Whisper returns "Hey Seven, show Chrome"; the checks pass | `ears/core.py` |
| | The wake word is found and stripped; a soft chime plays | `voice_loop.py`, `ears/wake_word.py` |
| | `voice_turn` and `user_text` are published; the voice bar shows "show Chrome" | `status.py`, `electron/status.html` |
| ~510 ms | The brain answers instantly (no model): `Chrome. ###WINDOW: action=focus target=chrome` | `brain_modules/layers/layer_45_window.py` |
| ~520 ms | The window action runs now, before speaking, on its own thread: Chrome comes to the front | `pre_executor.py` |
| ~900 ms | Seven says "Chrome."; the voice bar shows it | `mouth/engine.py` |
| after | The handlers run the rest of the tags; window tags already done are skipped | `main_modules/handlers/` |
| +8 s | The follow-up window stays open: the next request needs no "Hey Seven" | `voice_loop.py` |

Opening and closing apps, system settings (`###SYS`) and window actions all run before Seven speaks. Listing windows
waits, because it speaks its own result.

A question for the model ("why is the sky blue?") streams instead: the brain yields sentences, each is spoken as soon as
it exists, and `seven_text` grows sentence by sentence.

## 2. The voice loop: `main_modules/startup/voice_loop.py`

Runs on a daemon thread after the modules load.

1. **Wire up.** The ears get the mouth (is it speaking, what did it say) and the publisher (live state for the app).
   The push-to-talk keyboard listener starts. The greeting runs once (section 3).
2. **Each pass** (about every half second when nobody talks):
   - publish `listening` (true unless paused) and `paused`, every pass, so the app never shows a stale "Idle"
   - read the voice settings; set the stream's sensitivity, mic and push-to-talk key
   - publish `listen_mode` and `follow_up_open`
   - `ears.listen()`: nothing, or a transcript
3. **Gate.** In wake mode the text must start with the wake word, unless the follow-up window is open or the brain is
   waiting for an answer. "Hey Seven" alone chimes and opens the window.
4. **Control words.** Pause ("hold on"), resume ("wake up"), shut down; voice enrollment.
5. **Think.** `thinking` on, `user_text`, a new `voice_turn`; `brain.think()`. File matches from the request
   ("open resume") are moved to `voice_files` for the app.
6. **Act early, then speak.** `pre_execute()` runs OPEN, CLOSE, SYS and WINDOW tags; then the reply is spoken with
   interrupt listening on; then the remaining handlers run.
7. **Follow-up.** The window opens for `voice.follow_up_seconds`.

## 3. The greeting: `main_modules/startup/greeting.py`

One greeting per launch, said by one place (it used to be two: the voice loop and the setup screen both spoke).

- **First launch after setup:** "Hi {name}, I'm Seven. Whenever you need me, just say "Hey Seven" and ask, like "Hey
  Seven, open Chrome". You can also type to me any time."
- **Every launch after:** a greeting and the single most useful thing now, in order: overdue tasks, due today, the next
  reminder today, pending tasks, or a clear day. A battery note is added at 20% or below. Two sentences at most.
- The setup endpoint `POST /api/setup/welcome-greeting` returns the text only; it never speaks.

## 4. Live state: `/ws/status`

`backend/routes/status.py` sends, 10 times a second:

| Field | Meaning |
|---|---|
| `listening`, `thinking`, `speaking`, `paused` | What Seven is doing |
| `user_text`, `seven_text` | The current request and the reply so far |
| `mic_level` | 0..1, the live input level |
| `voice_state` | `idle`, `hearing`, `processing` |
| `voice_ignored` | `{reason, text, at}`: the last thing heard but not acted on, and why |
| `listen_mode`, `follow_up_open` | How Seven listens right now |
| `voice_turn` | Changes when a voice request starts |
| `voice_files` | `{at, data}`: file matches from the last voice request |

## 5. The voice bar: `electron/status.html`

Live captions at the top centre of the screen, in a small always-on-top window that lets clicks through everywhere
except the pill and never takes focus.

| Moment | The pill shows |
|---|---|
| "Hey Seven" | level bars that move with your voice, "Listening" |
| Speaking in the follow-up window, always-on or push to talk | the same, while you talk |
| Your request | what you said, three amber dots while Seven thinks |
| Seven speaks | the sentence being said now, one line, like captions |
| Done | the last sentence for 2.6 s, then it fades |

Only voice requests open it; typing in the app doesn't. Click it to open Seven, right-click for the menu. Settings,
System, **Voice bar**: *While talking* (default), *Always* (adds a small light at the top edge while Seven listens;
hover it for how to talk to Seven), or *Off*. Config: `voice_bar.show` = `active`, `always`, `off`.

It replaced the floating orb panel in the bottom-right corner.

## 6. The home screen

`frontend/src/pages/Landing.jsx`: a greeting, the orb (which grows slightly with your voice), and what Seven is doing
in plain words. Below it, one row of vitals from `GET /api/system/usage` (`brain_modules/resource_usage.py`):

- **Processor, Memory, Graphics:** rings where the grey arc is everything in use and the accent arc is Seven's part
  (the app's processes plus the local AI model).
- **Most memory:** the app using the most memory now; hover for the top apps with Seven ranked among them. People
  blame a new app when their PC is slow; this shows when it's something else.

The reading takes about 15 ms: one `NtQuerySystemInformation` call returns every process's private working set (what
Task Manager calls Memory) and CPU time, and Windows' GPU counters give dedicated graphics memory per process.
Seven's processes are its own executables and anything running from its install folder; the AI model is Ollama's
processes.

The header has a switch for how Seven listens (wake word, always on, push to talk) and a **Test mic** button: it
waits up to 8 seconds for you to say something and shows what Seven heard, or why it ignored it, without acting on it
(the same `POST /api/voice/test` as Settings, Voice, Test). It writes `voice.listen_mode`
and the voice loop picks it up on its next pass, about half a second later. Under the clock, top right, is a short log of the last
seven things Seven heard or ignored, newest first: `Heard "open chrome"`, or `Ignored "let's get lunch" · no "Hey
Seven"`. The log lives in the status store (`useStatus.voiceLog`, built from `voice_turn` and `voice_ignored`), so it
keeps filling while you are on another page.

What Seven answered appears in the voice bar and in Chat, not on the home screen.

## 7. Settings, Voice

`frontend/src/pages/settings/VoiceSection.jsx`:

- **Natural voice:** the eight voices with a preview, speed, and download progress if the voice isn't installed yet.
- **How Seven listens:** wake word, always, or push to talk; sensitivity; microphone; a live level meter; **Test**,
  which shows exactly what Seven heard (or why it ignored it) without acting.
- **Snaps and claps:** sensitivity for snap triggers.
- **Control words:** wake, pause, resume and shutdown phrases.
- **Speech recognition:** the Whisper model.
- **Only respond to my voice:** marked *Coming soon*; it can't be turned on.

## 8. Setup

- The voice files (Kokoro, about 205 MB) and the speech model start downloading as soon as setup opens
  (`POST /api/voice/install`), and the environment step waits for both.
- The personalise step offers the natural voices with previews and a short "How to talk to Seven" note.
- Completing setup saves `engine: kokoro`, the chosen voice, speed 1.0 and `listen_mode: wake`.

## 9. HTTP endpoints

| Method | Path | What it does |
|---|---|---|
| GET | `/api/voice/voices` | The natural voices, the current choice, whether they are installed |
| POST | `/api/voice/preview` | Say a line in a voice (stops any preview playing) |
| POST | `/api/voice/stop` | Stop a preview |
| POST, GET | `/api/voice/install` | Download the voice; progress |
| GET | `/api/voice/mics` | Microphones (WASAPI names, no virtual devices) |
| POST | `/api/voice/test` | Wait up to 8 s for one request; return what was heard, without acting |
| GET | `/api/system/usage` | Seven's share and the apps using the most memory |
| POST | `/api/triggers/snap-test` | Record a few seconds and say whether the mic hears snaps |
| POST | `/api/system/sound-settings` | Open Windows sound settings |
