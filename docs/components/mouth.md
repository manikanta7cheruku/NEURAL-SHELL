# Mouth (voice output)

| | |
|---|---|
| Status | Complete. Describes the mouth as rebuilt in October 2026 |
| Code | `mouth/engine.py`, `mouth/voices.py`, `mouth/tone.py`, `mouth/core.py`, `mouth/speaker.py`, `seven_utils/audio.py` |
| Tests | `tests/test_voice_text.py` (sentence splitting and tone), `scripts/voice_bench.py` (uses the voice to generate test speech) |
| Related | [Voice](voice.md), [Ears](ears.md) |

## 1. What the mouth does

The mouth speaks Seven's replies. It has to:

1. Sound like a person: a natural neural voice, offline, with tone that fits what is said.
2. Start at once: the first words play while the rest of the reply is still being written.
3. Stop at once: "stop" means silence now, not at the end of the sentence.
4. Tell the ears what it said and when it stopped, so Seven never answers its own voice.

The old mouth started a new Python process and then `piper.exe` for every sentence, loading the voice from scratch
each time, and began only after the whole reply was ready.

## 2. The voice: Kokoro

Kokoro v1.0 (82M parameters), run with ONNX Runtime on the CPU through `kokoro-onnx`.

- **Model:** `kokoro-v1.0.fp16.onnx` plus `voices-v1.0.bin`, about 205 MB, in `%APPDATA%\SEVEN\models\kokoro`.
  Downloaded during setup from the moment the setup window opens (`backend/bootstrap.py ensure_voice_model`), with
  progress shown in setup.
- **Why fp16:** benchmarked on an 8-core laptop CPU, the int8 model ran at about real time (too slow to stay ahead),
  fp16 at 0.28 of real time (about 3.5 times faster than speech). fp32 is the same speed and twice the size.
- **Threads:** intra-op threads = half the logical cores, between 2 and 8.
- **Voices** (`mouth/voices.py`): Heart (default), Bella, Nicole, Michael, Fenrir, Puck (American), Emma, George
  (British). British voices use the `en-gb` phonemizer.
- **Packaging:** `kokoro-onnx==0.4.9` is installed with `--no-deps` so pip can't upgrade numpy to 2.x, which would
  break Whisper and torch; the installer build checks numpy is still 1.x.

## 3. Speaking: `mouth/engine.py`

```
sentences (a list, or the brain's stream) --> tone.chunks() --> synthesis thread (one sentence ahead)
                                                                     |
                                                                     v  queue (2)
                                              playback: PyAudio, 24 kHz, 1024-sample chunks (~43 ms)
                                                                     |
                                                       stop() checked between chunks: silence in < 50 ms
```

- **Warm.** The model loads once in the background at startup (`warm()`), including a first tiny synthesis that
  compiles kernels, so the first reply isn't the slow one ("Natural voice ready in 2.7s").
- **Pipeline.** A synthesis thread stays one sentence ahead of playback, so there are no gaps between sentences. The
  first words play about 0.4 s after the first sentence exists.
- **Chunks** (`tone.chunks`): action tags after `###` are cut off (they are for the hands), the text is split into
  sentences, and a long first sentence is split at a comma so the first words play sooner.
- **Interrupt.** `stop()` sets a flag checked every 43 ms of audio; measured 74 ms from "stop" being recognised to
  silence.
- **Memory for the ears.** The engine keeps the last 12 sentences with their times (`recently_said()`) and when it
  stopped (`ended_at()`), which the ears use to drop Seven's own voice.
- **Chime.** `chime("wake")` plays a soft two-note sound the moment Seven hears "Hey Seven", so you know it is
  listening before it answers. `done` and `error` exist too. It never blocks.
- **Audio device.** Streams open and close through the shared PortAudio instance (`seven_utils/audio.py`); see
  [Ears](ears.md) section 3 for why.

## 4. Tone: `mouth/tone.py`

A neural voice already reads punctuation and phrasing; tone adds what people notice. Each sentence gets a speed
factor (multiplied with your chosen speed) and a pause after it:

| Tone | When | Speed | Pause after |
|---|---|---|---|
| gentle | sorry, loss, difficult, take care... | 0.90 | 0.35 s |
| clear | overdue, urgent, battery low | 1.00 | 0.20 s |
| bright | great, done, all set, "!" | 1.05 | 0.15 s |
| asking | ends with "?" | 1.00 | 0.30 s |
| neutral | everything else | 1.00 | 0.12 s |

## 5. How the rest of Seven reaches the mouth

- **In the app process** (`mouth/core.py`): `enable_inprocess()` is called after the modules load. From then on
  `speak()`, `speak_streamed()`, `interrupt()` and `is_speaking()` go to the engine.
- **In helper processes** (reminders from the schedule daemon): `mouth/speaker.py` speaks with Kokoro when the model is
  installed, and falls back to Piper or Windows' own voice (SAPI) when it isn't.
- **Previews:** `POST /api/voice/preview` (Settings and setup) stops any preview playing and says a line in the chosen
  voice and speed.

## 6. Data and configuration

`config.json`, section `voice`:

| Key | Meaning | Default |
|---|---|---|
| `engine` | `kokoro` (natural), `piper` or `sapi` | `kokoro` |
| `voice_id` | one of the natural voices | `af_heart` |
| `speed` | 0.7 to 1.4 (old 165-style rates are converted) | 1.0 |

## 7. Failure modes

| Problem | What happens |
|---|---|
| Voice not downloaded yet | Setup keeps downloading; previews answer "still downloading"; helper processes use Piper or SAPI |
| Synthesis error on a sentence | Logged, the rest of the reply still plays |
| Output device missing | Logged as a playback error; the reply still shows in the app and voice bar |

## 8. Known limitations and planned work

- Emotion is expressed through speed and pauses, not a different speaking style. A more expressive model could be
  offered as an option on PCs with a GPU.
- English only.
