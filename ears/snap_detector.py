"""
ears/snap_detector.py
Finger snaps and claps as triggers, without firing on everything else that clicks.

A snap is a very short, very bright, broadband burst followed by near silence. So are keyboard keys, mouse clicks
and a pen on a desk, which is why loudness and peak ratios alone fired at random. This detector checks the sound
the way a person would, in four stages:

  1. Candidate   high-frequency energy (above 2 kHz) jumps well above the room's own running level within a few
                 milliseconds. Relative to the room, so a quiet laptop mic and a loud headset both work.
  2. Shape       rises in under ~8 ms, falls 20 dB within ~80 ms, is bright and broadband (centre of energy 1.2-7 kHz,
                 not tonal), and is followed by near silence: speech, music, doors and knocks all fail one of these.
  3. Not typing  any candidate within ~150 ms of a key press or mouse click is dropped (Seven sees the keyboard and
                 mouse), which removes the main cause of false triggers.
  4. Pattern     1, 2 or 3 taps 0.12-0.8 s apart, counted after 0.8 s of quiet. A single snap needs a clearly stronger
                 sound than a double, because a single is the easiest to fake.

Laptop microphones: many run the sound through Windows "voice clarity" or noise suppression first, which flattens
snaps. snap_test() tells the user whether their mic hears snaps, and if not, what to change.

Detector.feed() is pure (frames in, events out), so scripts/snap_bench.py tests it with recorded or synthetic sounds.
"""
import collections
import threading
import time

import numpy as np

# sensitivity -> (candidate rise above the room in dB, extra dB a single snap needs)
SENSITIVITY = {"relaxed": (14.0, 4.0), "balanced": (18.0, 5.0), "strict": (23.0, 6.0)}

MIN_GAP, MAX_GAP = 0.12, 0.8          # seconds between taps of one pattern
INPUT_VETO_BEFORE, INPUT_VETO_AFTER = 0.15, 0.06
REFRACTORY = 1.0                      # after a pattern fires


class Detector:
    """Frames in, tap patterns out. No audio devices: stream audio through feed()."""

    def __init__(self, rate=48000, sensitivity="balanced"):
        from scipy.signal import butter
        self.rate = rate
        self.hop = max(1, int(rate * 0.0025))                      # 2.5 ms envelope steps
        self.b, self.a = butter(2, 2000 / (rate / 2), btype="high")
        self.zi = np.zeros(max(len(self.a), len(self.b)) - 1)
        self.set_sensitivity(sensitivity)
        self.floor = -70.0                                          # running HF level of the room, dB
        self.env_hist = collections.deque(maxlen=8)                 # last 20 ms of HF envelope
        self.raw = collections.deque(maxlen=int(rate * 0.6))        # last 0.6 s of full-band audio
        self.hf = collections.deque(maxlen=int(rate * 0.6))
        self.t = 0.0                                                # stream time, seconds
        self.pending = []                                           # candidates waiting for their tail
        self.taps = []                                              # accepted taps (time, margin)
        self.blocked_until = 0.0
        self.input_times = collections.deque(maxlen=64)
        self.last_reject = ""
        self.stats = collections.Counter()

    def set_sensitivity(self, s):
        self.sensitivity = s if s in SENSITIVITY else "balanced"
        self.onset_db, self.single_extra = SENSITIVITY[self.sensitivity]

    def note_input(self, at: float):
        """A key press or mouse click happened at stream time `at`."""
        self.input_times.append(at)

    def block(self, seconds: float):
        self.blocked_until = max(self.blocked_until, self.t + seconds)

    # ── streaming ────────────────────────────────────────────────────────
    def feed(self, frame: np.ndarray) -> list:
        """Process float32 samples; return the patterns (tap counts) completed in this frame."""
        from scipy.signal import lfilter
        hf, self.zi = lfilter(self.b, self.a, frame, zi=self.zi)
        out = []
        for i in range(0, len(frame) - self.hop + 1, self.hop):
            seg_hf = hf[i:i + self.hop]
            self.raw.extend(frame[i:i + self.hop])
            self.hf.extend(seg_hf)
            self.t += self.hop / self.rate
            db = 10 * np.log10(float(np.mean(seg_hf ** 2)) + 1e-12)
            prev = max(self.env_hist) if self.env_hist else db
            self.env_hist.append(db)

            rising = db - self.floor >= self.onset_db and db - prev >= self.onset_db * 0.6
            if rising and (not self.pending or self.t - self.pending[-1]["t"] > 0.09) and self.t >= self.blocked_until:
                self.pending.append({"t": self.t, "margin": db - self.floor, "floor": self.floor})
            elif not self.pending or self.t - self.pending[-1]["t"] > 0.3:
                # The room's level follows quickly down and slowly up, and ignores the bursts themselves.
                rate = 0.02 if db > self.floor else 0.2
                self.floor += (db - self.floor) * rate

            # A candidate is judged once 0.26 s of its tail has arrived.
            while self.pending and self.t - self.pending[0]["t"] >= 0.26:
                cand = self.pending.pop(0)
                ok, why = self._judge(cand)
                self.stats["accepted" if ok else why] += 1
                if ok:
                    self.taps.append((cand["t"], cand["margin"]))
                else:
                    self.last_reject = why
            out += self._pattern()
        return out

    # ── stage 2 and 3 ────────────────────────────────────────────────────
    def _judge(self, cand) -> tuple:
        t0 = cand["t"]
        if any(t0 - INPUT_VETO_BEFORE <= it <= t0 + INPUT_VETO_AFTER for it in self.input_times):
            return False, "typing or clicking"
        pre = 0.15                                                     # keep 150 ms from before the onset
        n_back = int((self.t - t0 + pre) * self.rate)
        raw = np.array(self.raw)[-n_back:]
        hf = np.array(self.hf)[-n_back:]
        if len(raw) < int((pre + 0.2) * self.rate):
            return False, "too short"
        hop = self.hop
        on = int(pre * self.rate)                                      # the onset, in samples
        env = np.array([10 * np.log10(np.mean(hf[i:i + hop] ** 2) + 1e-12) for i in range(0, len(hf) - hop, hop)])
        on_h = on // hop
        k = on_h - 4 + int(np.argmax(env[on_h - 4:on_h + int(0.03 * self.rate / hop)]))   # peak within 30 ms
        peak = env[k]
        rise_ms = (k - (on_h - 2)) * 2.5
        if peak < -55:
            return False, "too faint"
        if rise_ms > 10:
            return False, "too slow to rise (not a snap)"
        below = np.where(env[k:] < peak - 20)[0]
        decay_ms = (below[0] * 2.5) if len(below) else 999
        if decay_ms > 80:
            return False, "rings too long (speech, music or a bang)"
        burst = raw[on - 64: on + int(0.04 * self.rate)]
        tail = raw[on + int(0.09 * self.rate): on + int(0.25 * self.rate)]
        before = raw[: on - int(0.01 * self.rate)]
        burst_db = 10 * np.log10(np.mean(burst ** 2) + 1e-12)
        tail_db = 10 * np.log10(np.mean(tail ** 2) + 1e-12)
        before_db = 10 * np.log10(np.mean(before ** 2) + 1e-12)
        # After a snap the room goes back to how it sounded before; after a word or a note, it doesn't.
        if tail_db > max(burst_db - 18, before_db + 6):
            return False, "sound continues after it (speech or music)"
        spec = np.abs(np.fft.rfft(burst * np.hanning(len(burst)))) + 1e-9
        freqs = np.fft.rfftfreq(len(burst), 1 / self.rate)
        centroid = float(np.sum(freqs * spec) / np.sum(spec))
        if not 1200 <= centroid <= 7000:
            return False, "too dull (a knock or thump)" if centroid < 1200 else "too thin (a tick)"
        flatness = float(np.exp(np.mean(np.log(spec))) / np.mean(spec))
        if flatness < 0.08:
            return False, "tonal (a beep or a note)"
        return True, "ok"

    # ── stage 4 ──────────────────────────────────────────────────────────
    def _pattern(self) -> list:
        if not self.taps or self.t - self.taps[-1][0] < MAX_GAP:
            return []
        taps, self.taps = self.taps, []
        # Taps too close together are one sound (a snap's echo); too far apart were already split by MAX_GAP.
        merged = [taps[0]]
        for t, m in taps[1:]:
            if t - merged[-1][0] >= MIN_GAP:
                merged.append((t, m))
        n = len(merged)
        if n > 3:
            self.stats["more than three taps"] += 1
            return []
        if n == 1 and merged[0][1] < self.onset_db + self.single_extra:
            self.stats["single snap too faint"] += 1
            self.last_reject = "single snap too faint"
            return []
        self.block(REFRACTORY)
        return [n]


# ═════════════════════════════════════════════════════════════════════════
# LIVE MICROPHONE
# ═════════════════════════════════════════════════════════════════════════

def _open_input(pa, device_index=None):
    """The mic at the best rate it supports: 48 kHz keeps a snap's sharp edge, 16 kHz works too."""
    import pyaudio
    for rate in (48000, 44100, 16000):
        try:
            stream = pa.open(format=pyaudio.paFloat32, channels=1, rate=rate, input=True,
                             frames_per_buffer=int(rate * 0.01), input_device_index=device_index)
            return stream, rate
        except Exception:
            continue
    raise RuntimeError("No microphone could be opened")


class SnapDetector:
    """The live detector used by the trigger daemon. Same interface as the old TriggerDetector."""

    def __init__(self, sensitivity="balanced", device_index=None, debug=False):
        self.sensitivity = sensitivity if sensitivity in SENSITIVITY else "balanced"
        self.device_index = device_index
        self.on_pattern = lambda count: None
        self._running = threading.Event()
        self._paused = threading.Event()
        self._thread = None
        self._det = None
        self._t0 = 0.0
        self._hooks = []

    def set_sensitivity(self, level):
        self.sensitivity = level
        if self._det:
            self._det.set_sensitivity(level)

    def suppress(self, duration_ms=3000):
        if self._det:
            self._det.block(duration_ms / 1000)

    def pause(self):
        self._paused.set()

    def resume(self):
        self._paused.clear()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._running.set()
        self._start_input_hooks()
        self._thread = threading.Thread(target=self._run, daemon=True, name="SnapDetector")
        self._thread.start()

    def stop(self):
        self._running.clear()
        for h in self._hooks:
            try:
                h.stop()
            except Exception:
                pass
        self._hooks = []

    def _start_input_hooks(self):
        """Watch the keyboard and mouse (without blocking them) so their clicks are never taken for snaps."""
        try:
            from pynput import keyboard, mouse

            def seen(*_a, **_k):
                if self._det is not None:
                    self._det.note_input(time.time() - self._t0)
            self._hooks = [keyboard.Listener(on_press=seen), mouse.Listener(on_click=lambda *a: seen())]
            for h in self._hooks:
                h.daemon = True
                h.start()
        except Exception as e:
            print(f"[SNAP] Keyboard and mouse watch unavailable: {e}")

    def _run(self):
        import pyaudio
        pa = pyaudio.PyAudio()
        backoff = 1.0
        while self._running.is_set():
            stream = None
            try:
                stream, rate = _open_input(pa, self.device_index)
                self._det = Detector(rate, self.sensitivity)
                self._t0 = time.time()
                print(f"[SNAP] Listening for snaps and claps ({rate} Hz, {self.sensitivity})")
                backoff = 1.0
                n = int(rate * 0.01)
                while self._running.is_set():
                    frame = np.frombuffer(stream.read(n, exception_on_overflow=False), dtype=np.float32)
                    if self._paused.is_set():
                        continue
                    for count in self._det.feed(frame):
                        print(f"[SNAP] Pattern: {count}")
                        try:
                            self.on_pattern(count)
                        except Exception as e:
                            print(f"[SNAP] Trigger error: {e}")
            except Exception as e:
                print(f"[SNAP] Microphone error: {e}. Retrying in {backoff:.0f}s")
                time.sleep(backoff)
                backoff = min(backoff * 2, 15)
            finally:
                if stream is not None:
                    try:
                        stream.close()
                    except Exception:
                        pass
        pa.terminate()


# ═════════════════════════════════════════════════════════════════════════
# SNAP TEST (the trigger form's "Test my mic")
# ═════════════════════════════════════════════════════════════════════════

def snap_test(seconds: float = 6.0, device_index=None) -> dict:
    """
    Listen while the user snaps three times; say in plain words whether this mic hears snaps.
    {"ok": bool, "heard": taps accepted, "sharp": sharp sounds noticed, "verdict": str, "advice": str|None}
    """
    import pyaudio
    pa = pyaudio.PyAudio()
    try:
        stream, rate = _open_input(pa, device_index)
    except Exception as e:
        pa.terminate()
        return {"ok": False, "heard": 0, "sharp": 0, "verdict": "No microphone could be opened.", "advice": str(e)}
    det = Detector(rate, "relaxed")
    taps = 0
    end = time.time() + seconds
    n = int(rate * 0.01)
    try:
        while time.time() < end:
            frame = np.frombuffer(stream.read(n, exception_on_overflow=False), dtype=np.float32)
            before = len(det.taps)
            det.feed(frame)
            taps += max(0, len(det.taps) - before)
        for _ in range(int(1.0 / 0.01)):                     # let the last candidate finish
            det.feed(np.zeros(n, dtype=np.float32))
            taps = max(taps, det.stats["accepted"])
    finally:
        stream.close()
        pa.terminate()
    taps = det.stats["accepted"]
    sharp = sum(det.stats.values())
    if taps >= 2:
        return {"ok": True, "heard": taps, "sharp": sharp, "verdict": f"Your mic hears snaps clearly ({taps} heard).",
                "advice": None}
    if sharp >= 2:
        return {"ok": False, "heard": taps, "sharp": sharp,
                "verdict": "Your mic noticed sharp sounds, but they arrive softened.",
                "advice": "Windows is probably filtering the microphone. In Sound settings, open your microphone and turn "
                          "off Audio enhancements (or Voice clarity), then test again. A headset mic works best."}
    return {"ok": False, "heard": taps, "sharp": sharp, "verdict": "Your mic didn't hear the snaps.",
            "advice": "Snap closer to the microphone, or turn off Audio enhancements for it in Windows Sound settings. "
                      "Many laptop mics remove short sounds like snaps; a headset or USB mic hears them reliably."}
