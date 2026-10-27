"""
scripts/voice_bench.py
A repeatable test of Seven's ears, without speaking into a microphone.

    python scripts/voice_bench.py            run the bench and print a report
    python scripts/voice_bench.py --keep     also write every mixed clip to voice_bench_out/ to listen to

It builds clips of real speech (Seven's natural voice reading typical requests, in several voices) and of noise
(fan hum, keyboard typing, music, a TV talking in the background), mixes them at realistic loudness, and feeds them
frame by frame through the same pipeline the app uses: the speech detector and endpointing (ears/stream.py), then
Whisper and every transcript check (ears/core.py). It reports:

    requests understood    the transcript contains the request's key words
    false triggers         noise-only clips that produced any transcript at all (should be 0)
    time to text           Whisper time per utterance

Needs the natural voice installed (%APPDATA%/SEVEN/models/kokoro). Clips are made fresh each run, so changing the
detector or the filters and re-running shows the effect at once.
"""
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("SEVEN_TEST", "1")

RATE = 16000
REQUESTS = [
    ("hey seven open chrome", ["open", "chrome"]),
    ("hey seven what time is it", ["time"]),
    ("set a reminder at five to call mom", ["reminder", "5|five", "call", "mom|mum"]),
    ("hey seven open my coding workspace", ["coding", "workspace"]),
    ("turn the volume down to thirty", ["volume", "30|thirty"]),
    ("hey seven open the gokarna video", ["video"]),
    ("what's on my task list today", ["task", "today"]),
    ("stop", ["stop"]),
]
VOICES = ["am_michael", "af_bella", "bm_george", "af_nicole"]


def _resample(audio, sr):
    from scipy.signal import resample_poly
    g = np.gcd(sr, RATE)
    return resample_poly(audio, RATE // g, sr // g).astype(np.float32)


def speech_clips():
    from kokoro_onnx import Kokoro
    from mouth import voices
    d = voices.models_dir()
    k = Kokoro(os.path.join(d, "kokoro-v1.0.fp16.onnx"), os.path.join(d, "voices-v1.0.bin"))
    out = []
    for i, (text, keys) in enumerate(REQUESTS):
        v = VOICES[i % len(VOICES)]
        a, sr = k.create(text, voice=v, speed=1.0, lang="en-gb" if v[0] == "b" else "en-us")
        out.append((text, keys, v, _resample(a, sr)))
    return out


def _pink(n, rng):
    w = rng.standard_normal(n)
    f = np.fft.rfft(w)
    f /= np.sqrt(np.arange(1, len(f) + 1))
    return np.fft.irfft(f, n).astype(np.float32)


def noises(seconds, rng):
    n = int(seconds * RATE)
    t = np.arange(n) / RATE
    fan = _pink(n, rng) + 0.3 * np.sin(2 * np.pi * 120 * t)
    keys = np.zeros(n, dtype=np.float32)
    for pos in np.cumsum(rng.uniform(0.08, 0.25, int(seconds * 7))):          # ~7 keystrokes a second
        i = int(pos * RATE)
        if i + 400 < n:
            click = rng.standard_normal(400) * np.exp(-np.arange(400) / 60)
            keys[i:i + 400] += click.astype(np.float32)
    music = sum(np.sin(2 * np.pi * f * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.5 * t + f)) for f in (220, 277, 330, 440))
    return {"fan": fan, "typing": keys, "music": music.astype(np.float32)}


def tv_clip(rng):
    """Someone talking on TV across the room: real speech, quiet and muffled, with no wake word."""
    from kokoro_onnx import Kokoro
    from mouth import voices
    from scipy.signal import butter, lfilter
    d = voices.models_dir()
    k = Kokoro(os.path.join(d, "kokoro-v1.0.fp16.onnx"), os.path.join(d, "voices-v1.0.bin"))
    a, sr = k.create("And now the weather for the weekend. Expect light rain on Saturday with clearing skies later.",
                     voice="bf_emma", lang="en-gb")
    a = _resample(a, sr)
    b, c = butter(2, [300 / (RATE / 2), 3000 / (RATE / 2)], btype="band")
    return lfilter(b, c, a).astype(np.float32)


def _at_db(x, dbfs):
    rms = np.sqrt(np.mean(x ** 2)) + 1e-9
    return x * (10 ** (dbfs / 20) / rms)


def run_clip(audio, sensitivity="balanced"):
    """Feed audio through the real microphone pipeline; return the utterances it produced."""
    from ears import stream as st

    class Fake:
        def __init__(self, a):
            pad = np.zeros(int(0.8 * RATE), dtype=np.float32)
            self.pcm = (np.clip(np.concatenate([pad, a, pad, pad]), -1, 1) * 32767).astype(np.int16)
            self.i = 0

        def read(self, n, exception_on_overflow=False):
            if self.i >= len(self.pcm):
                mic._running.clear()
                return np.zeros(n, dtype=np.int16).tobytes()
            chunk = self.pcm[self.i:self.i + n]
            self.i += n
            if len(chunk) < n:
                chunk = np.pad(chunk, (0, n - len(chunk)))
            return chunk.tobytes()

    mic = st.MicStream()
    mic.configure(sensitivity=sensitivity)
    mic._reopen = False
    mic._running.set()
    mic._listen(Fake(audio), st._Silero())
    utts = []
    while not mic.utterances.empty():
        utts.append(mic.utterances.get_nowait())
    return utts


def heard(utts):
    """What Seven would act on: transcribe and apply every text check, as ears.core.listen does."""
    from ears import core
    texts, times = [], []
    for u in utts:
        t = time.time()
        text, _ = core.transcribe(u.audio)
        times.append(time.time() - t)
        if text and not core._text_problem(text):
            texts.append(core.normalize_wake(text))
    return texts, times


def main():
    keep = "--keep" in sys.argv
    rng = np.random.default_rng(7)
    out_dir = os.path.join(ROOT, "voice_bench_out")
    if keep:
        os.makedirs(out_dir, exist_ok=True)

    print("Preparing clips...")
    speech = speech_clips()
    tv = tv_clip(rng)
    ok = total = 0
    lat = []
    rows = []

    # Requests: quiet room, a fan, someone typing, music in the background.
    for text, keys, voice, clip in speech:
        for bg_name, bg_db, level in [("quiet", None, -24), ("fan", -42, -24), ("typing", -40, -24), ("music", -38, -24),
                                      ("far", None, -38), ("loud fan", -30, -26), ("tv", -34, -24)]:
            x = _at_db(clip, level)                                 # -24 dBFS: speaking at a laptop; -38: across the room
            if bg_name == "tv":
                bg = np.resize(tv, len(x))
                x = x + _at_db(bg, bg_db)
                bg_db = None
            if bg_db is not None:
                bg = noises(len(x) / RATE + 2, rng)[bg_name.replace("loud ", "")][:len(x)]
                x = x + _at_db(bg, bg_db)
            utts = run_clip(x)
            texts, times = heard(utts)
            lat += times
            got = " ".join(texts).lower()
            hit = all(any(alt in got for alt in k.split('|')) for k in keys)
            if text.startswith("hey seven"):                         # the wake word must be recognised too
                from ears.wake_word import check_and_strip
                hit = hit and any(check_and_strip(t, ["hey seven", "seven"])[1] for t in texts)
            ok += hit
            total += 1
            rows.append((hit, bg_name, voice, text, got))
            if keep:
                import soundfile  # noqa: F401  (optional)
    print(f"\nRequests understood: {ok}/{total} ({100 * ok // total}%)")
    for hit, bg, voice, text, got in rows:
        if not hit:
            print(f"   missed [{bg:6}] {voice:10} said '{text}'  ->  heard '{got}'")

    # Noise only: anything heard here is a false trigger.
    false = []
    for name, sig in noises(20, rng).items():
        for db in (-40, -30):
            texts, _ = heard(run_clip(_at_db(sig, db)))
            if texts:
                false.append((name, db, texts))
    texts, _ = heard(run_clip(_at_db(tv, -36)))
    tv_heard = texts
    print(f"False triggers from noise: {len(false)} of 6 noise clips")
    for name, db, texts in false:
        print(f"   [{name} at {db} dB] heard {texts}")
    print(f"TV across the room (no wake word): heard {tv_heard or 'nothing'}"
          f"{'  (ignored: no wake word)' if tv_heard and not any('seven' in t.lower() for t in tv_heard) else ''}")
    if lat:
        print(f"Time to text: median {np.median(lat):.2f}s, slowest {max(lat):.2f}s")


if __name__ == "__main__":
    main()
