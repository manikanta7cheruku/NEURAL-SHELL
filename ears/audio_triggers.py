"""
=============================================================================
ears/audio_triggers.py

Snap/clap detection with ADAPTIVE thresholds.

Key insight from testing: laptop mics with AGC compress peaks to ~0.10-0.15.
Fixed thresholds fail. This version LEARNS your mic's noise floor and
sets thresholds RELATIVE to what your mic actually produces.

Detection pipeline:
  1. Calibrate noise floor for 3 seconds at startup
  2. Compute adaptive peak threshold = max(noise_floor * leap_ratio, 0.04)
  3. When peak exceeds threshold, capture event
  4. Classify using RELATIVE metrics:
       - Attack: peak rose from below (0.5 * threshold) within 30ms
       - Spectrum: high-freq (2-8kHz) energy > 30% of total
       - Decay: signal drops below threshold within 80ms
       - Duration: total event < 120ms

Honest limitation: laptop mics compress everything. Even snap and speech
peaks converge. We use SPECTRUM and DECAY as the strongest filters
because they survive AGC compression.
=============================================================================
"""

import time
import threading
from collections import deque
from colorama import Fore

try:
    import numpy as np
except ImportError:
    print(Fore.RED + "[TRIGGERS] numpy required")
    raise

try:
    import pyaudio
except ImportError:
    print(Fore.RED + "[TRIGGERS] pyaudio required")
    raise


# ─────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────

SAMPLE_RATE = 16000
CHUNK_SIZE  = 320          # 20ms at 16kHz
CHANNELS    = 1
FORMAT      = pyaudio.paInt16

# Adaptive thresholds — computed at runtime from noise floor
SENSITIVITY_PROFILES = {
    "low": {
        "leap_ratio":      8.0,    # need 8x above noise floor
        "absolute_min":    0.08,   # never trigger below this
        "spectrum_min":    0.40,
    },
    "medium": {
        "leap_ratio":      5.0,
        "absolute_min":    0.04,
        "spectrum_min":    0.30,
    },
    "high": {
        "leap_ratio":      3.5,
        "absolute_min":    0.025,
        "spectrum_min":    0.22,
    },
}

# Time constants
MAX_EVENT_MS       = 120     # snap shouldn't last longer than this
MIN_EVENT_MS       = 8       # too short = digital glitch
DECAY_WINDOW_MS    = 80      # signal must drop within this time
PATTERN_WINDOW_MS  = 700     # wait this long after last tap
TAP_COOLDOWN_MS    = 200
POST_PATTERN_MS    = 1500    # cooldown after firing pattern


# ─────────────────────────────────────────────────────────────────────────
# MIC SELECTION (unchanged — works well)
# ─────────────────────────────────────────────────────────────────────────

def _find_best_input_device():
    try:
        pa = pyaudio.PyAudio()
        count = pa.get_device_count()

        headset_keywords = ["hyperx", "stinger", "cloud", "headset",
                            "usb", "wireless", "external", "airpods",
                            "buds", "audio-technica", "shure", "blue",
                            "logitech", "razer", "steelseries"]
        builtin_keywords = ["array", "omen", "amd", "realtek", "laptop",
                            "internal", "integrated", "built-in", "conexant"]

        candidates = []

        for i in range(count):
            try:
                info = pa.get_device_info_by_index(i)
                if info['maxInputChannels'] < 1:
                    continue

                name = info['name'].lower()
                rate = int(info['defaultSampleRate'])
                chunk = int(rate * 0.05)

                try:
                    stream = pa.open(
                        format=pyaudio.paInt16, channels=1, rate=rate,
                        input=True, frames_per_buffer=chunk,
                        input_device_index=i,
                    )
                    levels = []
                    for _ in range(10):
                        raw = stream.read(chunk, exception_on_overflow=False)
                        s = (np.frombuffer(raw, dtype=np.int16)
                             .astype(np.float32) / 32768.0)
                        levels.append(float(np.abs(s).max()))
                    stream.stop_stream()
                    stream.close()

                    avg = sum(levels) / len(levels)
                    if avg > 0.3:
                        continue

                    score = 0
                    if avg < 0.02: score += 3
                    elif avg < 0.05: score += 1

                    for kw in headset_keywords:
                        if kw in name: score += 4; break
                    for kw in builtin_keywords:
                        if kw in name: score -= 2; break
                    if "wasapi" in name: score += 2

                    candidates.append((score, i, info['name'], avg))
                except Exception:
                    pass
            except Exception:
                continue

        pa.terminate()

        if not candidates:
            return None

        candidates.sort(reverse=True)
        best_score, best_idx, best_name, best_avg = candidates[0]

        is_headset = any(kw in best_name.lower() for kw in headset_keywords)
        mic_type = "HEADSET/USB (recommended)" if is_headset else "LAPTOP MIC (limited by AGC)"

        print(Fore.CYAN + f"[TRIGGERS] Selected: {best_name}")
        print(Fore.CYAN + f"[TRIGGERS] Type: {mic_type}, noise floor: {best_avg:.3f}")
        return best_idx

    except Exception as e:
        print(Fore.YELLOW + f"[TRIGGERS] Device selection failed: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────
# SIGNAL ANALYSIS
# ─────────────────────────────────────────────────────────────────────────

def _spectral_ratio(samples, sample_rate):
    """Ratio of high-freq (2-8kHz) energy to total energy."""
    if len(samples) < 32:
        return 0.0

    windowed = samples * np.hanning(len(samples))
    fft = np.abs(np.fft.rfft(windowed))
    freqs = np.fft.rfftfreq(len(windowed), d=1.0 / sample_rate)

    total = float(np.sum(fft ** 2)) + 1e-9
    high_max = min(8000, sample_rate // 2)
    mask = (freqs >= 2000) & (freqs <= high_max)
    high = float(np.sum(fft[mask] ** 2))
    return high / total


# ─────────────────────────────────────────────────────────────────────────
# TRIGGER DETECTOR
# ─────────────────────────────────────────────────────────────────────────

class TriggerDetector:

    def __init__(self, sensitivity="medium", device_index=None, debug=False):
        if device_index is None:
            device_index = _find_best_input_device()

        self.sensitivity  = sensitivity
        self.device_index = device_index
        self.debug        = debug

        self.on_pattern   = None
        self.on_detection = None

        self._running = False
        self._thread  = None
        self._audio   = None
        self._stream  = None

        self._actual_rate     = SAMPLE_RATE
        self._actual_chunk    = CHUNK_SIZE
        self._actual_channels = CHANNELS
        self._chunk_ms        = 20.0

        self._pending_taps      = deque()
        self._last_pattern_time = 0
        self.suppressed_until   = 0
        self.paused             = False

        # Rolling noise floor
        self._noise_floor       = 0.02
        self._noise_alpha       = 0.03   # adapts over ~1 second

        # Event state
        self._event             = None
        self._event_pre_peak    = 0.0    # loudest chunk in last 3 chunks before event

        # Recent chunks for pre-event peak tracking
        self._recent_peaks      = deque(maxlen=3)

        self._load_thresholds()

    def _load_thresholds(self):
        profile = SENSITIVITY_PROFILES.get(self.sensitivity, SENSITIVITY_PROFILES["medium"])
        self.leap_ratio    = profile["leap_ratio"]
        self.absolute_min  = profile["absolute_min"]
        self.spectrum_min  = profile["spectrum_min"]

    def set_sensitivity(self, level):
        if level in SENSITIVITY_PROFILES:
            self.sensitivity = level
            self._load_thresholds()
            print(Fore.CYAN + f"[TRIGGERS] Sensitivity: {level}")

    def suppress(self, duration_ms=3000):
        self.suppressed_until = time.time() + (duration_ms / 1000.0)

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print(Fore.GREEN + f"[TRIGGERS] Started (sensitivity={self.sensitivity})")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                pass
        if self._audio:
            try:
                self._audio.terminate()
            except Exception:
                pass
        print(Fore.YELLOW + "[TRIGGERS] Stopped")

    def _get_threshold(self):
        """Adaptive threshold = max(noise_floor * leap_ratio, absolute_min)."""
        adaptive = self._noise_floor * self.leap_ratio
        return max(adaptive, self.absolute_min)

    def _run(self):
        try:
            self._audio = pyaudio.PyAudio()

            actual_rate = SAMPLE_RATE
            actual_chunk = CHUNK_SIZE
            actual_channels = CHANNELS

            if self.device_index is not None:
                try:
                    info = self._audio.get_device_info_by_index(self.device_index)
                    actual_rate = int(info['defaultSampleRate'])
                    actual_chunk = int(actual_rate * 0.02)  # 20ms
                    actual_channels = min(2, int(info['maxInputChannels']))
                except Exception:
                    pass

            self._stream = self._audio.open(
                format=FORMAT, channels=actual_channels,
                rate=actual_rate, input=True,
                frames_per_buffer=actual_chunk,
                input_device_index=self.device_index,
            )
            self._actual_rate = actual_rate
            self._actual_chunk = actual_chunk
            self._actual_channels = actual_channels
            self._chunk_ms = (actual_chunk / actual_rate) * 1000.0

        except Exception as e:
            print(Fore.RED + f"[TRIGGERS] Failed to open mic: {e}")
            self._running = False
            return

        # ── CALIBRATION PHASE — 3 seconds of silence ──
        print(Fore.CYAN + "[TRIGGERS] Calibrating for 3 seconds — please stay silent...")
        warmup_end = time.time() + 3.0
        warmup_peaks = []
        while self._running and time.time() < warmup_end:
            try:
                raw = self._stream.read(self._actual_chunk, exception_on_overflow=False)
                samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                if self._actual_channels == 2:
                    samples = samples.reshape(-1, 2).mean(axis=1)
                warmup_peaks.append(float(np.max(np.abs(samples))))
            except Exception:
                pass

        if warmup_peaks:
            # Use 90th percentile so we don't over-adapt to occasional sounds
            self._noise_floor = float(np.percentile(warmup_peaks, 90))
            self._noise_floor = max(0.003, self._noise_floor)

        threshold = self._get_threshold()
        print(Fore.GREEN + f"[TRIGGERS] Calibration done.")
        print(Fore.GREEN + f"[TRIGGERS] Noise floor: {self._noise_floor:.4f}")
        print(Fore.GREEN + f"[TRIGGERS] Snap threshold: {threshold:.4f} "
              f"(peaks above this trigger detection)")

        while self._running:
            try:
                raw = self._stream.read(self._actual_chunk, exception_on_overflow=False)
                samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

                if self._actual_channels == 2:
                    samples = samples.reshape(-1, 2).mean(axis=1)

                if self.paused or time.time() < self.suppressed_until:
                    self._recent_peaks.append(0)
                    continue

                peak_amp = float(np.max(np.abs(samples)))
                now = time.time()

                # Adapt noise floor when NOT in an event
                if self._event is None:
                    threshold = self._get_threshold()
                    if peak_amp < threshold * 0.5:
                        self._noise_floor = (
                            (1 - self._noise_alpha) * self._noise_floor +
                            self._noise_alpha * peak_amp
                        )
                        self._noise_floor = max(0.003, self._noise_floor)

                self._process_chunk(samples, peak_amp, now)
                self._recent_peaks.append(peak_amp)
                self._check_pattern_ready()

            except Exception as e:
                if self.debug:
                    print(f"[TRIGGERS] Loop error: {e}")
                time.sleep(0.3)

    def _process_chunk(self, samples, peak_amp, now):
        threshold = self._get_threshold()

        # Not in event and below threshold → nothing to do
        if self._event is None and peak_amp < threshold:
            return

        # Start new event
        if self._event is None:
            # Snapshot pre-event peak (loudest of last 3 chunks)
            self._event_pre_peak = max(self._recent_peaks) if self._recent_peaks else 0.0
            self._event = {
                "start_time": now,
                "samples": [samples.copy()],
                "peak": peak_amp,
                "peak_time": now,
                "chunks": 1,
            }
            return

        # Continue event
        self._event["samples"].append(samples.copy())
        self._event["chunks"] += 1
        if peak_amp > self._event["peak"]:
            self._event["peak"] = peak_amp
            self._event["peak_time"] = now

        elapsed_ms = (now - self._event["start_time"]) * 1000

        # End event if signal dropped OR event ran too long
        if peak_amp < threshold * 0.5 or elapsed_ms > MAX_EVENT_MS:
            self._finalize_event(now)

    def _finalize_event(self, now):
        if self._event is None:
            return

        event = self._event
        self._event = None

        combined = np.concatenate(event["samples"])
        duration_ms = (now - event["start_time"]) * 1000
        peak = event["peak"]
        threshold = self._get_threshold()

        # ── CHECK 1: Duration ──
        if duration_ms < MIN_EVENT_MS:
            if self.debug:
                print(f"  reject: duration {duration_ms:.0f}ms too short (glitch)")
            return

        if duration_ms > MAX_EVENT_MS:
            if self.debug:
                print(f"  reject: duration {duration_ms:.0f}ms too long (sustained sound)")
            return

        # ── CHECK 2: Attack — signal must rise sharply ──
        # Pre-event peak (0.5s before) should be much lower than event peak
        attack_ratio = peak / (self._event_pre_peak + 0.001)
        if attack_ratio < 2.5:
            if self.debug:
                print(f"  reject: attack {attack_ratio:.1f}x too gradual "
                      f"(pre={self._event_pre_peak:.3f}, peak={peak:.3f})")
            return

        # ── CHECK 3: Spectrum — high-frequency content ──
        # Focus on peak samples where signature is strongest
        spectrum = _spectral_ratio(combined, self._actual_rate)
        if spectrum < self.spectrum_min:
            if self.debug:
                print(f"  reject: spectrum {spectrum:.2f} < {self.spectrum_min:.2f} "
                      f"(likely speech/rumble)")
            return

        # ── CHECK 4: Decay — signal must drop fast ──
        last_chunk_peak = float(np.max(np.abs(event["samples"][-1])))
        decay_ratio = peak / (last_chunk_peak + 0.001)
        if decay_ratio < 1.8:
            if self.debug:
                print(f"  reject: decay {decay_ratio:.1f}x too slow "
                      f"(sustained, not sharp)")
            return

        # PASSED
        if self.debug:
            print(Fore.GREEN + f"  TAP: peak={peak:.3f} attack={attack_ratio:.1f}x "
                  f"spectrum={spectrum:.2f} decay={decay_ratio:.1f}x "
                  f"dur={duration_ms:.0f}ms threshold={threshold:.3f}")

        self._register_tap(event["start_time"])

    def _register_tap(self, timestamp):
        if self._pending_taps:
            last_time = self._pending_taps[-1]
            if (timestamp - last_time) * 1000 < TAP_COOLDOWN_MS:
                return

        if (timestamp - self._last_pattern_time) * 1000 < POST_PATTERN_MS:
            return

        self._pending_taps.append(timestamp)
        print(Fore.CYAN + f"[TRIGGERS] Tap {len(self._pending_taps)}")

        if self.on_detection:
            try:
                self.on_detection()
            except Exception:
                pass

    def _check_pattern_ready(self):
        if not self._pending_taps:
            return

        now = time.time()
        last_time = self._pending_taps[-1]
        if (now - last_time) * 1000 < PATTERN_WINDOW_MS:
            return

        count = len(self._pending_taps)
        self._pending_taps.clear()

        if count > 3:
            print(Fore.YELLOW + f"[TRIGGERS] Ignored: {count} taps (max 3)")
            return

        self._last_pattern_time = now
        print(Fore.GREEN + f"[TRIGGERS] PATTERN: {count} tap{'s' if count > 1 else ''}")

        if self.on_pattern:
            try:
                self.on_pattern(count)
            except Exception as e:
                print(Fore.RED + f"[TRIGGERS] Callback error: {e}")


# ─────────────────────────────────────────────────────────────────────────
# STANDALONE TEST
# ─────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    debug_mode = "--debug" in sys.argv
    sens = "medium"
    device_index = None
    for i, a in enumerate(sys.argv):
        if a == "--sensitivity" and i + 1 < len(sys.argv):
            sens = sys.argv[i + 1]
        if a == "--device" and i + 1 < len(sys.argv):
            try: device_index = int(sys.argv[i + 1])
            except ValueError: pass

    print("=" * 60)
    print("SEVEN SNAP DETECTION — Adaptive Classifier")
    print("=" * 60)
    print(f"Sensitivity: {sens}   Debug: {debug_mode}   Device: {device_index}")
    print()
    print("Sensitivity guide:")
    print("  low    = strictest (best for noisy rooms — fewer false positives)")
    print("  medium = balanced (default)")
    print("  high   = most lenient (best for quiet rooms + weak mics)")
    print()
    print("For laptop mic: use --sensitivity high")
    print("For USB headset: use --sensitivity medium or low")
    print()
    print("Ctrl+C to stop.")
    print("=" * 60)
    print()

    def on_pattern(count):
        print()
        print("!" * 60)
        print(f">>> PATTERN FIRED: {count} tap{'s' if count > 1 else ''}")
        print("!" * 60)
        print()

    detector = TriggerDetector(sensitivity=sens, debug=debug_mode, device_index=device_index)
    detector.on_pattern = on_pattern
    detector.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
        detector.stop()