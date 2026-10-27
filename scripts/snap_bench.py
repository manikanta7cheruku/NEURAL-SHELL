"""
scripts/snap_bench.py
A repeatable test of snap and clap triggers, without snapping at a microphone.

    python scripts/snap_bench.py

Builds sounds with the physics of the real thing (a snap: a broadband burst with a 1 ms attack and a ~10 ms decay; a
clap: lower and a little longer; a keyboard key: a 3 ms tick plus a thud, with the key press reported the way the
live detector sees it; a desk knock; a beep; music; real speech from Seven's voice), places them in a room with fan
noise, and runs them through ears/snap_detector.Detector. Snap and clap patterns must be counted exactly; everything
else must produce nothing.
"""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ears.snap_detector import Detector  # noqa: E402

RATE = 48000
rng = np.random.default_rng(11)


def _band(x, lo, hi):
    from scipy.signal import butter, lfilter
    b, a = butter(2, [lo / (RATE / 2), min(hi, RATE / 2 - 100) / (RATE / 2)], btype="band")
    return lfilter(b, a, x)


def burst(lo, hi, attack_ms, decay_ms, dur_ms=120):
    n = int(RATE * dur_ms / 1000)
    t = np.arange(n) / RATE
    env = np.minimum(1, t / (attack_ms / 1000)) * np.exp(-t / (decay_ms / 1000))
    x = _band(rng.standard_normal(n), lo, hi) * env
    return (x / (np.max(np.abs(x)) + 1e-9)).astype(np.float32)


def snap():
    return burst(1500, 7000, 0.6, 9)


def clap():
    return burst(800, 5000, 1.0, 16)


def key():
    return 0.7 * burst(2000, 9000, 0.3, 2.5, 40) + 0.5 * burst(150, 800, 1, 8, 40)


def knock():
    return burst(80, 700, 1.5, 25)


def beep():
    t = np.arange(int(RATE * 0.12)) / RATE
    return (np.sin(2 * np.pi * 2000 * t) * np.minimum(1, t / 0.002)).astype(np.float32)


def speech():
    from kokoro_onnx import Kokoro
    from mouth import voices
    from scipy.signal import resample_poly
    d = voices.models_dir()
    k = Kokoro(os.path.join(d, "kokoro-v1.0.fp16.onnx"), os.path.join(d, "voices-v1.0.bin"))
    a, sr = k.create("Pick up the black cat. Tap the desk twice, then stop, please.", voice="am_michael", lang="en-us")
    return resample_poly(a, 2, 1).astype(np.float32)                 # 24 kHz -> 48 kHz


def music(seconds):
    t = np.arange(int(RATE * seconds)) / RATE
    drum = np.zeros_like(t)
    for s in np.arange(0, seconds, 0.5):                             # a beat with hi-hats
        i = int(s * RATE)
        h = burst(5000, 12000, 0.3, 20, 80) * 0.5
        drum[i:i + len(h)] += h[:len(drum) - i]
    tones = sum(np.sin(2 * np.pi * f * t) for f in (220, 330, 440)) * 0.2
    return (drum + tones).astype(np.float32)


def room(events, seconds, loud_db, fan_db=-50, input_at=()):
    """Place (time, sound) events in a room with fan noise; returns (audio, times of key/mouse input)."""
    n = int(RATE * seconds)
    fan = rng.standard_normal(n)
    fan = np.cumsum(fan) * 0.02
    fan -= np.convolve(fan, np.ones(400) / 400, mode="same")          # brown-ish hum
    x = fan / (np.sqrt(np.mean(fan ** 2)) + 1e-9) * 10 ** (fan_db / 20)
    for at, s in events:
        i = int(at * RATE)
        s = s / (np.max(np.abs(s)) + 1e-9) * 10 ** (loud_db / 20)
        x[i:i + len(s)] += s[:n - i]
    return x.astype(np.float32), list(input_at)


def run(audio, inputs=(), sensitivity="balanced"):
    d = Detector(RATE, sensitivity)
    for t in inputs:
        d.note_input(t)
    out = []
    for i in range(0, len(audio), 480):
        out += d.feed(audio[i:i + 480])
    for _ in range(150):                                             # 1.5 s of silence to finish patterns
        out += d.feed(np.zeros(480, dtype=np.float32))
    return out, d


def main():
    cases = []
    for level, where in [(-12, "close to the mic"), (-24, "at arm's length"), (-32, "across the desk")]:
        cases += [
            (f"2 snaps, {where}", room([(0.5, snap()), (0.85, snap())], 3, level)[0], (), [2]),
            (f"3 snaps, {where}", room([(0.5, snap()), (0.8, snap()), (1.15, snap())], 3, level)[0], (), [3]),
            (f"2 claps, {where}", room([(0.5, clap()), (0.9, clap())], 3, level)[0], (), [2]),
        ]
    cases += [
        ("1 clear snap", room([(0.5, snap())], 2.5, -12)[0], (), [1]),
        ("two separate double snaps", room([(0.5, snap()), (0.8, snap()), (3.0, snap()), (3.3, snap())], 5, -18)[0],
         (), [2, 2]),
    ]
    # Things that must never fire.
    typing_t = list(np.cumsum(rng.uniform(0.09, 0.3, 30)) + 0.3)
    typed, _ = room([(t, key()) for t in typing_t], 9, -14)
    cases += [
        ("fast typing", typed, typing_t, []),
        ("mouse clicks", room([(0.5, key()), (1.4, key()), (1.7, key())], 3, -16)[0], [0.5, 1.4, 1.7], []),
        ("knocking on the desk", room([(0.5, knock()), (0.8, knock())], 3, -10)[0], (), []),
        ("a notification beep", room([(0.5, beep()), (0.9, beep())], 3, -14)[0], (), []),
        ("music with a beat", music(6) * 0.3, (), []),
        ("someone talking", np.concatenate([np.zeros(RATE // 2, np.float32), speech() * 0.5]), (), []),
        ("a single faint snap", room([(0.5, snap())], 2.5, -40)[0], (), []),
        ("silence", np.zeros(RATE * 3, np.float32), (), []),
    ]

    passed = 0
    for name, audio, inputs, want in cases:
        got, d = run(audio, inputs)
        ok = got == want
        passed += ok
        rejected = {k: v for k, v in d.stats.items() if k != "accepted" and v}
        print(f"{'ok  ' if ok else 'FAIL'} {name:34} expected {want!s:8} got {got!s:8}"
              f"{'' if ok else f'  rejections: {rejected}'}")
    print(f"\n{passed}/{len(cases)} passed")
    return passed == len(cases)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
