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

- **First launch after setup:** the spoken welcome tour (section 3a).
- **Every launch after:** a greeting and the single most useful thing now, in order: overdue tasks, due today, the next
  reminder today, pending tasks, or a clear day. A battery note is added at 20% or below. Two sentences at most.
- The setup endpoint `POST /api/setup/welcome-greeting` returns the text only; it never speaks.

### 3a. Ready, then the welcome tour

**The app opens when Seven can speak.** The backend answers requests long before its brain, ears and voice are loaded,
so the app used to open in a half-working state and the greeting arrived late. Now the voice loop publishes `ready`
(`GET /api/ready`, `{ready, stage}`) once the brain and apps are loaded, the ears are listening and the natural voice
is warm, and the app shows a loading screen with the stage ("Loading Seven's brain", "Starting the ears", "Warming
up the voice") until then. The voice starts loading at the very beginning, beside the rest, instead of after it. The
greeting starts 0.8 s after `ready`, as the window appears. After two minutes the app opens anyway, so one broken part
never locks anyone out; the needs-attention strip says what is wrong.

**The first launch after setup** runs `main_modules/startup/tour.py` instead of a one-line welcome:

1. **Audio check.** If the volume is muted or at 40% or less, it is raised to 60% (never higher, never lowered) and
   Seven says so, with how to change it. At 41% or more nothing is touched.
2. **The tour,** about 25 seconds, spoken as one stream so sentences follow each other without gaps. As each sentence
   starts, the status feed's `tour` value changes and the screen lights up what Seven is talking about: the orb
   ("I'm an assistant that lives on your PC"), the listening switch ("Hey Seven"), Test mic, the footer pages and
   Ctrl+K. The rest of the screen dims (`TourLayer`). The voice bar shows the captions, and a **Skip tour** button stops
   the talking and goes straight to the card.
3. **The welcome card** (`WelcomeCard`) opens. It is about what Seven is and where it is going, and it asks for
   feedback; it is not a how-to (Guide covers that). A fixed-size card with three tabs so nothing jumps:
   - **About:** what Seven is, the larger aim (an assistant that can do whatever you can do at a computer, running on
     your own device), and what it stands for.
   - **Roadmap:** what works today and what is next as one line each, then the later scope in full: seeing and using
     your screen, multi-step work, looking after your PC, messages and email, creating, phone and home, accessibility
     and languages, safety and privacy. No dates. The text is `frontend/src/lib/roadmap.js`, a summary of
     `docs/product/roadmap.md`; update both when something ships.
   - **Feedback:** how to tell us what is off or missing, and what stays on the PC versus what is shared to run the
     beta (name, email, country and usage time, which Settings, Privacy and data can turn off).
   **Send feedback** is in the footer on every tab, because feedback is what the beta is for.
4. **The card is for everyone, at any time.** It is not only a first-run thing. A quiet pill on the home screen and
   Overview (`WelcomeHint`) opens it. It is also reachable from the **Welcome guide** link in the home footer (always
   there), the **Welcome and roadmap** button on Guide, and Ctrl+K ("Show the welcome guide", "Roadmap: what is coming",
   "Send feedback"). "Hide the home hint" in the card removes only the pill. `window.dispatchEvent(new CustomEvent(
   'seven:welcome', { detail: { tab: 'roadmap' } }))` opens it on a tab.

State lives in `%APPDATA%\SEVEN\greeting.json`: `welcomed` (set as the tour starts, so a crash can't loop it),
`tour_done`, `hint_dismissed`. Ctrl+K has **Replay the welcome tour** and **Show the welcome guide**.

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
| `ready`, `ready_stage` | Seven's brain, ears and voice are loaded (the app opens on this); the stage until then |
| `tour` | `{step, n}`: the thing the first-run tour is talking about (`audio`, `intro`, `listen`, `mic`, `pages`, `outro`), `card` when the card should open, then null |
| `welcome` | `{tour_done, hint_dismissed}` |

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
waits up to 10 seconds for you to say something and shows what Seven heard, or why it ignored it, without acting on it
(the same `POST /api/voice/test` as Settings, Voice, Test). It writes `voice.listen_mode`
and the voice loop picks it up on its next pass, about half a second later. Under the clock, top right, is a short log of the last
seven things Seven heard or ignored, newest first: `Heard "open chrome"`, or `Ignored "let's get lunch" · no "Hey
Seven"`. The log lives in the status store (`useStatus.voiceLog`, built from `voice_turn` and `voice_ignored`), so it
keeps filling while you are on another page.

What Seven answered appears in the voice bar and in Chat, not on the home screen.

### Needs attention

When Seven can't do its job, one quiet line appears under the header with a button to the fix, and nothing appears
when all is well. `GET /api/attention` (`backend/routes/attention.py`) reports, most important first:

| Level | Problem | Button |
|---|---|---|
| error | The microphone can't be opened (unplugged, or used by another app). Can't be dismissed | Choose microphone |
| warn | The natural voice failed to download, or isn't installed | Open voice settings |
| warn | The AI model isn't running (reported only after Seven has been up 90 s, so a slow start isn't an alarm) | Open brain settings |
| info | The natural voice is downloading, with the percentage | none |

The app adds an update that is ready and a plan that ends within 7 days. The first item shows; "+N more" lists the
rest; warnings and notes can be dismissed for the session. Nothing is reported before setup finishes. The raw
microphone error never reaches the screen, only the plain sentence.

### Navigation

The footer holds the five pages used every day (Overview, Chat, Tasks, Reminders, Memory; keys 1 to 5), Settings is the
gear in the header (key comma) and **Ctrl+K** opens the command palette from any page: go to a page, open a settings
section, test the microphone, change how Seven listens, or switch the theme. "Overview" (`/dashboard`) is the page
the sidebar used to call "Home"; the home screen is the one with the orb.


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
| POST | `/api/voice/test` | Wait up to 10 s for one request; return what was heard, without acting |
| GET | `/api/system/usage` | Seven's share and the apps using the most memory |
| GET | `/api/attention` | What needs the user's attention (microphone, voice, AI model), most important first |
| GET | `/api/ready` | Is Seven ready (brain, ears and voice loaded), and the stage until then |
| GET | `/api/welcome` | The first-run welcome state |
| POST | `/api/welcome/hint/hide`, `/api/welcome/hint/show` | Hide or show the getting-started hint |
| POST | `/api/tour/skip`, `/api/tour/ack`, `/api/tour/replay` | Skip the spoken tour, acknowledge the card opened, run the tour again |
| POST | `/api/triggers/snap-test` | Record a few seconds and say whether the mic hears snaps |
| POST | `/api/system/sound-settings` | Open Windows sound settings |
