# Ears (voice input)

| | |
|---|---|
| Status | Complete. Describes the ears as rebuilt in October 2026 |
| Code | `ears/stream.py`, `ears/core.py`, `ears/wake_word.py`, `ears/push_to_talk.py`, `ears/snap_detector.py`, `seven_utils/audio.py` |
| Tests | `tests/test_voice_text.py`, `tests/test_live_voice.py`, `tests/test_snap_detector.py`; benches `scripts/voice_bench.py`, `scripts/snap_bench.py` |
| Related | [Voice](voice.md) (the loop, greeting and voice bar), [Mouth](mouth.md), [Brain](brain.md) |

## 1. What the ears do

The ears turn the microphone into requests. They have to:

1. Hear only speech. A fan, typing, music, a TV or Seven's own voice must never become a request.
2. Be fast. Text should exist about half a second after you stop talking.
3. Know when they are being spoken to: "Hey Seven", a follow-up a few seconds after a reply, push to talk, or always on.
4. Never invent words. Whisper fills silence with "Thank you for watching"; that must not reach the brain.
5. Show their work. The app can see the live level, "Hearing you", and what was ignored and why.

The old ears decided "is someone talking?" by loudness (an RMS threshold, calibration and crest checks). Loudness
cannot tell a voice from a fan, so noise got through and Whisper made up words for it, while quiet speech fell under
the threshold. The rebuild replaces loudness with a neural speech detector.

## 2. The pipeline

```
microphone (16 kHz mono, one stream for the whole app)
   |  32 ms frames                                                   ears/stream.py
   v
Silero VAD (speech probability per frame) --> live level and state --> status feed (orb, voice bar)
   |
   v
endpointing: start / continue / end (or the push-to-talk key)  -->  Utterance (audio, timings, during_speech)
   |
   v
own voice?  (started while Seven spoke, or within 0.35 s after)  --> ignored "Seven's own voice"
   |                                                                  ears/core.py listen()
   v
Whisper (two-stage on CPU, one model on GPU)
   |
   v
checks: empty, non-English, music, known mishearing, repetition, incoherent, echo of Seven's words
   |
   v
autocorrect + wake-word spelling ("Hey 7" -> "Hey Seven")  -->  text to the voice loop
```

## 3. Capture: `ears/stream.py`

`MicStream` keeps one input stream open for the life of the app and hands over whole utterances through a queue.

- **Device.** The mic chosen in Settings (or Windows' default). Settings shows WASAPI's full names; the stream opens the
  device on Windows' standard audio system (MME), which converts to 16 kHz where WASAPI would refuse. Names are matched
  both ways round because MME cuts them to 31 characters.
- **Speech detector.** Silero VAD v6, the ONNX file that ships with faster-whisper, run one 512-sample frame at a time
  with its recurrent state (h, c) and 64 samples of context kept between frames. One thread, about 0.2 ms a frame.
- **Endpointing.** A small state machine per sensitivity:

  | Sensitivity | Start probability | Keep-going probability | Silence that ends it |
  |---|---|---|---|
  | relaxed | 0.40 | 0.25 | 0.75 s |
  | balanced (default) | 0.55 | 0.35 | 0.60 s |
  | strict | 0.70 | 0.45 | 0.55 s |

  Speech starts after about 100 ms (three frames) above the start probability, and keeps about 300 ms from before
  that (pre-roll) so the first syllable is not cut. It continues while frames stay above the lower keep-going
  probability (hysteresis, so pauses between words don't split a sentence) and ends after the silence above, or at
  15 seconds. Under 0.35 s of actual speech (a cough, a click) is dropped as "too short".
- **Push to talk.** When the mode is push to talk, the key replaces start and end: holding it starts an utterance
  with the same pre-roll, letting go ends it immediately. The detector still has to find 0.35 s of speech in it, so a
  tap is nothing. See section 6.
- **Live state.** Every frame updates a level (-60 to -10 dBFS mapped to 0..1, published about 12 times a second)
  and a state: `idle`, `hearing`, `processing`. Utterances that begin while Seven is speaking are marked
  `during_speech`.
- **Listeners.** Other code can receive every frame (`add_listener`), so the snap detector can share the mic.
- **Recovery.** An unplugged headset or busy device closes the stream and retries with backoff (1 s doubling to 15 s).

### One PortAudio per process: `seven_utils/audio.py`

PortAudio's initialisation is not thread-safe. The mic, the voice, the snap detector and the mic list used to each
create their own `pyaudio.PyAudio()` from different threads, and two starting together crashed the backend with an
access violation the moment Seven began speaking. Everything now uses one shared instance created under a lock, and
opens and closes streams through `audio.open_stream()` and `audio.close_stream()`, also under the lock.

## 4. Understanding: `ears/core.py`

`listen()` waits up to half a second for an utterance, so the voice loop stays responsive, then:

1. **Own voice.** Ignored if it began while Seven was talking, or within 0.35 s after Seven stopped (the room's echo).
2. **Speech to text** (which model suits the PC is `ears/whisper_advice.py`, shown in Settings, Voice). faster-whisper, English, greedy decoding, no Whisper VAD (the audio is already trimmed), no
   conditioning on previous text.
   - **GPU:** `small.en` (float16) by default, about 480 MB to download. `medium.en` (1.5 GB, a little more accurate)
     is one click away in Settings, Voice, and a PC that already has `medium.en` and not `small.en` keeps it.
   - **CPU:** two stages. Whisper always encodes a 30-second window, so `small.en` takes about 1.5 s on a laptop CPU
     while `base.en` takes about 0.4 s. `base.en`'s mistakes come with low confidence and its correct transcripts with
     high confidence, so Seven hears with `base.en` and re-checks with `small.en` only when the lowest segment
     `avg_logprob` is below -0.45.
   - Overrides: `SEVEN_WHISPER_MODEL`, `SEVEN_WHISPER_DEVICE=cpu`, or the model picked in Settings, Voice.
   - Segments with `no_speech_prob > 0.6` and low confidence, or `avg_logprob < -1.1`, are dropped.
3. **Checks** (`_text_problem`): empty; mostly non-ASCII (music or another language); music symbols; sung syllables;
   a known Whisper hallucination (`hallucination_filter.py`, `hallucinations.json`); a repetition loop; incoherent.
4. **Echo.** If the text fuzzily matches (85% partial ratio) something Seven said in the last 12 seconds, it is
   Seven's voice coming back through the speakers.
5. **Clean-up.** Autocorrect for common mishearings, then `normalize_wake()` so "Hey 7", "H7" or "A7" become
   "Hey Seven" (section 5).

Anything dropped is published as `voice_ignored` with a reason, which the status feed carries to the app.

`hearing_test()` (Settings, Voice, Test, and the home screen's Test mic) reads the microphone itself for up to 10
seconds, with the voice loop standing aside, and returns exactly what was heard, or why it was
ignored, without acting on it. `listen_for_interrupt()` runs while Seven speaks: short utterances only (long ones are
Seven's own sentences), fast transcription, and a whole-word match against the interrupt words ("stop", "wait").

## 5. Being spoken to: listening modes

| Mode | When Seven acts | Notes |
|---|---|---|
| Wake word (default) | The request starts with "Hey Seven" (or "Seven", "OK Seven") | Background talk is ignored |
| Always | Everything it hears | Best alone in a quiet room |
| Push to talk | Only while Shift is held | No wake word needed |

- **Wake word** (`ears/wake_word.py`). Whole-word match at the start of the text, so "Seventeen apps" never wakes
  Seven. Whisper writes the name many ways; `normalize_wake()` maps "Hey 7", "H7", "A7" and similar to "Hey Seven",
  but only "a"/"h" with a digit or a bare 7 followed by a pause or a verb, so "a seven-day" or "7 tasks" are left alone.
- **"Hey Seven" alone** plays a soft chime and opens the follow-up window: you can pause before saying what you want.
- **Follow-up window.** For 8 seconds after Seven answers (`voice.follow_up_seconds`), no wake word is needed.
- **Paused.** "Hold on", "stop listening" and the other pause words pause Seven; "wake up" resumes.

## 6. Push to talk: `ears/push_to_talk.py`

A pynput keyboard listener watches Shift. `is_held()` is True while Shift is held on its own. Shift is also how
capitals are typed, so a Shift held together with any other key is typing: that hold doesn't count until Shift is
released and pressed again alone. The mic stream asks `is_held()` every frame (section 3).

## 7. Snaps and claps: `ears/snap_detector.py`

Triggers can fire on two or three finger snaps or claps. A snap is a very short, very bright, broadband burst followed
by near silence; so are keys, mouse clicks and a pen on a desk, which is why loudness and peak ratios alone fired at
random. The detector works in four stages:

1. **Candidate.** High-frequency energy (above 2 kHz) jumps well above the room's own running level within a few
   milliseconds. Relative to the room, so a quiet laptop mic and a loud headset both work.
2. **Shape.** Rises in under about 8 ms, falls 20 dB within about 80 ms, centre of energy 1.2 to 7 kHz and not tonal,
   and the tail returns to the level of the room before the onset. Speech, music, doors and knocks fail one of these.
3. **Not typing.** A candidate within 150 ms before or 60 ms after a key press or mouse click is dropped. This removes
   the main cause of the old false triggers.
4. **Pattern.** One to three taps 0.12 to 0.8 s apart, counted after 0.8 s of quiet. A single snap needs a stronger
   sound than a double.

Sensitivity (relaxed, balanced, strict) sets how far above the room a candidate must rise. `Detector.feed()` is pure
(frames in, events out), so `scripts/snap_bench.py` and the tests run it on synthetic snaps, claps, keys, knocks,
beeps, music and speech (19 of 19 correct).

**Laptop microphones.** Many laptops pass the mic through Windows "voice clarity" or noise suppression, which
flattens snaps. Triggers, Snap or clap, **Test my mic** records a few seconds, reports what it heard, and when snaps
are flattened says so and offers to open Windows sound settings (turn off Audio enhancements, or use a headset mic).
A very loud fan within about 8 dB of the snap hides snaps at arm's length.

The trigger daemon (`trigger_modules/audio_listener.py`) runs its own `SnapDetector` with the sensitivity from
`voice.snap_sensitivity`.

## 8. Data and configuration

`%APPDATA%\SEVEN\config.json`, section `voice` (Settings, Voice):

| Key | Values | Default |
|---|---|---|
| `listen_mode` | `wake`, `always`, `ptt` | `wake` (older installs with push to talk on become `ptt`) |
| `sensitivity` | `relaxed`, `balanced`, `strict` | `balanced` |
| `follow_up_seconds` | seconds without a wake word after a reply | 8 |
| `interrupt` | say "stop" over Seven | true |
| `mic` | a microphone name, empty for Windows' default | empty |
| `wake_words` | phrases that start a request | hey seven, ok seven, okay seven, seven |
| `snap_sensitivity` | `relaxed`, `balanced`, `strict` | `balanced` |
| `only_me` | respond only to an enrolled voice | always off for now (coming in a later version) |

Whisper models download into the Hugging Face cache during setup (`backend/bootstrap.py ensure_speech_model`).

## 9. Interfaces

- **Called by** the voice loop (`listen`, `listen_for_interrupt`, `voice_settings`, `STREAM.configure`,
  `STREAM.set_push_to_talk`), Settings (`hearing_test`), the trigger daemon (`SnapDetector`).
- **Calls** the mouth through `set_speaking_fn` and `set_mouth` (is Seven speaking, what it said, when it stopped)
  and the app through `set_publisher` (`mic_level`, `voice_state`, `voice_ignored`).
- **HTTP:** `GET /api/voice/mics`, `POST /api/voice/test`, `POST /api/triggers/snap-test`.
- `import ears` is lazy, so the trigger daemon can use the snap detector without loading Whisper.

## 10. Failure modes

| Problem | What happens |
|---|---|
| Mic unplugged or busy | The stream closes and retries with backoff; `last_error` holds the reason |
| No GPU | Two-stage CPU hearing, median 0.57 s from end of speech to text |
| Whisper model missing | Downloaded during setup; offline mode allows that one download |
| Seven hears itself | Dropped by timing (during or 0.35 s after speech) and by text match |
| Noise or music | Never starts an utterance (VAD) or fails the text checks; shown as "skipped" |

## 11. Measurements

`scripts/voice_bench.py` plays Kokoro-generated requests through the real pipeline under quiet, fan, typing, music,
distance, loud fan and TV conditions, plus noise-only clips: 56 of 56 understood, 0 of 6 false triggers, TV ignored.
End of speech to text: median 0.57 s on CPU (was 1.73 s), 0.64 s on GPU.

## 12. Known limitations and planned work

- The wake word is matched on Whisper's text, so every utterance is transcribed. A small always-on keyword model
  (openWakeWord trained on "Hey Seven") would save CPU and catch the name faster.
- There is no acoustic echo cancellation. Echo is handled by timing and text; with loud speakers and no headset,
  saying "stop" over Seven works less reliably.
- "Only respond to my voice" (speaker verification) is disabled until it is fast and reliable enough.
- Older modules (`aec.py`, `agc.py`, `noise_floor.py`, `signal_gates.py`, `vad.py`, `voice_id_gate.py`) are no
  longer used by the pipeline and can be removed.
