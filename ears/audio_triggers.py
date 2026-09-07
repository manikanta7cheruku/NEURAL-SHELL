"""
=============================================================================
ears/audio_triggers.py

Professional snap/clap detection with signature validation.

Uses THREE-LAYER classification to reject false positives:

  LAYER 1 — Transient Detection (fast onset)
    Real snaps rise from silence to peak in <15ms.
    Speech and sustained sounds rise slowly (>50ms).

  LAYER 2 — Spectral Analysis (frequency signature)
    Snaps are broadband bursts with energy 2-8 kHz.
    Speech is dominated by 200-3000 Hz (voice fundamental + formants).
    Uses FFT to compute high-freq-to-low-freq energy ratio.

  LAYER 3 — Decay Envelope (fast decay)
    Real snaps decay to <30% of peak within 60ms.
    Speech sustains for 200-500ms per syllable.

Also includes:
  - Adaptive noise floor (adjusts to room ambient)
  - Suppression window (prevents re-trigger during Seven's TTS)
  - Auto-selection of best mic (headset preferred)

HONEST LIMITATIONS:
  - Laptop mics with heavy AGC may miss weak snaps
  - Very loud claps close to mic may still trigger during speech
  - Recommend USB mic or wired headset for best results
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
# AUDIO CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────

SAMPLE_RATE = 16000
CHUNK_SIZE  = 320          # 20ms at 16kHz (enough for FFT resolution)
CHANNELS    = 1
FORMAT      = pyaudio.paInt16


# ─────────────────────────────────────────────────────────────────────────
# SIGNATURE THRESHOLDS
# These define what a "real snap" looks like acoustically
# ─────────────────────────────────────────────────────────────────────────

# Fraction of energy that must be in high-frequency band (2-8 kHz)
# Snaps: 0.6-0.9 (broadband high energy)
# Speech: 0.1-0.3 (dominated by low-mid)
# Music/TV: 0.3-0.5 (mixed)
SNAP_HIGH_FREQ_RATIO_MIN = 0.45

# Max time for signal to rise from noise floor to peak (in ms)
# Snaps: 5-15 ms
# Claps: 5-20 ms
# Speech: 30-200 ms
MAX_ATTACK_MS = 25

# Min ratio of peak-to-decay within 60ms window
# Snaps: peak/decay > 3.0 (fast decay)
# Speech: peak/decay < 2.0 (sustained)
MIN_DECAY_RATIO = 2.5

# Sensitivity profiles — how loud must the snap be
SENSITIVITY_PROFILES = {
    "low": {
        "peak_min":        0.20,   # louder snaps only
        "leap_ratio":      6.0,    # much louder than background
    },
    "medium": {
        "peak_min":        0.12,
        "leap_ratio":      4.0,
    },
    "high": {
        "peak_min":        0.06,
        "leap_ratio":      2.5,
    },
}

# Pattern grouping
PATTERN_WINDOW_MS        = 600
TAP_COOLDOWN_MS          = 180
POST_PATTERN_COOLDOWN_MS = 1500


# ─────────────────────────────────────────────────────────────────────────
# MICROPHONE SELECTION
# ─────────────────────────────────────────────────────────────────────────

def _find_best_input_device():
    """
    Auto-select the best mic for snap detection.
    Prefers USB / headset / external over built-in laptop array mics.
    """
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

                # Quick 0.5s noise floor sample
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

                    if avg > 0.3:  # saturated
                        continue

                    score = 0
                    if avg < 0.02:
                        score += 3
                    elif avg < 0.05:
                        score += 1

                    for kw in headset_keywords:
                        if kw in name:
                            score += 4
                            break

                    for kw in builtin_keywords:
                        if kw in name:
                            score -= 2
                            break

                    if "wasapi" in name:
                        score += 2

                    candidates.append((score, i, info['name'], avg))
                except Exception:
                    pass
            except Exception:
                continue

        pa.terminate()

        if not candidates:
            print(Fore.YELLOW + "[TRIGGERS] No mic found — snap detection disabled")
            return None

        candidates.sort(reverse=True)
        best_score, best_idx, best_name, best_avg = candidates[0]

        is_headset = any(kw in best_name.lower() for kw in headset_keywords)
        mic_type = "HEADSET/USB (good)" if is_headset else "LAPTOP MIC (limited)"

        print(Fore.CYAN + f"[TRIGGERS] Selected: {best_name} — {mic_type}")
        if not is_headset:
            print(Fore.YELLOW + "[TRIGGERS] For best results, use a USB mic or wired headset.")

        return best_idx

    except Exception as e:
        print(Fore.YELLOW + f"[TRIGGERS] Device selection failed: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────
# SIGNATURE ANALYSIS
# ─────────────────────────────────────────────────────────────────────────

def _compute_spectral_ratio(samples, sample_rate):
    """
    Compute the ratio of high-frequency energy (2-8 kHz) to total energy.
    Snaps: 0.5-0.9. Speech: 0.1-0.3.
    """
    if len(samples) < 32:
        return 0.0

    # Apply Hann window to reduce spectral leakage
    windowed = samples * np.hanning(len(samples))

    # FFT
    fft = np.abs(np.fft.rfft(windowed))
    freqs = np.fft.rfftfreq(len(windowed), d=1.0 / sample_rate)

    total_energy = float(np.sum(fft ** 2)) + 1e-9

    # High-freq band: 2 kHz to 8 kHz (or Nyquist)
    high_max = min(8000, sample_rate // 2)
    mask = (freqs >= 2000) & (freqs <= high_max)
    high_energy = float(np.sum(fft[mask] ** 2))

    return high_energy / total_energy


def _compute_attack_time(peak_history, event_start_idx, sample_ms_per_chunk):
    """
    Compute how many ms the signal took to rise from noise floor to peak.
    Real snaps: <15 ms. Speech: >50 ms.
    """
    if event_start_idx <= 0 or event_start_idx >= len(peak_history):
        return 999.0

    # Look at the 5 chunks before the peak
    lookback = max(0, event_start_idx - 5)
    pre_peak = peak_history[lookback:event_start_idx + 1]

    if len(pre_peak) < 2:
        return 999.0

    peak = max(pre_peak)
    if peak < 0.05:
        return 999.0

    # Find first chunk that was above 20% of peak
    threshold = peak * 0.2
    for i, p in enumerate(pre_peak):
        if p >= threshold:
            chunks_to_peak = len(pre_peak) - 1 - i
            return chunks_to_peak * sample_ms_per_chunk

    return 999.0


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

        self.suppressed_until = 0
        self.paused           = False

        # Rolling history for background noise floor + attack analysis
        self._peak_history   = deque(maxlen=30)   # ~600ms history
        self._sample_history = deque(maxlen=8)    # last 8 chunks of raw samples

        # Adaptive noise floor
        self._noise_floor = 0.02
        self._noise_alpha = 0.02  # slow adaptation

        # Event tracking (during a suspected snap)
        self._event = None
        self._event_max_peak = 0.0

        self._load_thresholds()

    def _load_thresholds(self):
        profile = SENSITIVITY_PROFILES.get(
            self.sensitivity, SENSITIVITY_PROFILES["medium"]
        )
        self.peak_min   = profile["peak_min"]
        self.leap_ratio = profile["leap_ratio"]

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
                    # 20ms chunks
                    actual_chunk = int(actual_rate * 0.02)
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

        # Warmup — build initial noise floor
        print(Fore.CYAN + "[TRIGGERS] Calibrating noise floor (2 seconds)...")
        warmup_end = time.time() + 2.0
        warmup_peaks = []
        while self._running and time.time() < warmup_end:
            try:
                raw = self._stream.read(self._actual_chunk, exception_on_overflow=False)
                samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                if self._actual_channels == 2:
                    samples = samples.reshape(-1, 2).mean(axis=1)
                peak = float(np.max(np.abs(samples)))
                warmup_peaks.append(peak)
                self._peak_history.append(peak)
                self._sample_history.append(samples)
            except Exception:
                pass

        if warmup_peaks:
            self._noise_floor = max(0.005, float(np.median(warmup_peaks)))
        print(Fore.GREEN + f"[TRIGGERS] Noise floor: {self._noise_floor:.3f}. Ready.")

        while self._running:
            try:
                raw = self._stream.read(self._actual_chunk, exception_on_overflow=False)
                samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

                if self._actual_channels == 2:
                    samples = samples.reshape(-1, 2).mean(axis=1)

                if self.paused or time.time() < self.suppressed_until:
                    self._peak_history.append(0)
                    self._sample_history.append(samples)
                    continue

                peak_amp = float(np.max(np.abs(samples)))
                now = time.time()

                # Adaptive noise floor (only when NOT in event)
                if self._event is None and peak_amp < self._noise_floor * 3:
                    self._noise_floor = (
                        (1 - self._noise_alpha) * self._noise_floor +
                        self._noise_alpha * peak_amp
                    )
                    self._noise_floor = max(0.005, self._noise_floor)

                self._process_chunk(samples, peak_amp, now)
                self._peak_history.append(peak_amp)
                self._sample_history.append(samples)
                self._check_pattern_ready()

            except Exception as e:
                if self.debug:
                    print(f"[TRIGGERS] Loop error: {e}")
                time.sleep(0.3)

    def _process_chunk(self, samples, peak_amp, now):
        """
        Process a single audio chunk.
        Detect start of event → collect event samples → classify on end.
        """
        # Threshold for "something happening" = noise floor * leap_ratio
        event_threshold = self._noise_floor * self.leap_ratio

        # Not in an event, and this chunk is too quiet → nothing to do
        if self._event is None and peak_amp < event_threshold:
            return

        # Start of new event
        if self._event is None and peak_amp >= event_threshold:
            self._event = {
                "start_time": now,
                "start_idx": len(self._peak_history),
                "samples": [samples.copy()],
                "peak": peak_amp,
                "peak_time": now,
                "chunks": 1,
            }
            return

        # Continuation of event
        if self._event is not None:
            self._event["samples"].append(samples.copy())
            self._event["chunks"] += 1
            if peak_amp > self._event["peak"]:
                self._event["peak"] = peak_amp
                self._event["peak_time"] = now

            # Event ends when signal drops back to noise floor level
            # OR when it's gone on too long (> 100ms — too long to be a snap)
            elapsed_ms = (now - self._event["start_time"]) * 1000

            if peak_amp < event_threshold * 0.6 or elapsed_ms > 100:
                self._finalize_event(now)

    def _finalize_event(self, now):
        """
        Classify the completed event as snap or noise.
        Applies all three signature checks.
        """
        if self._event is None:
            return

        event = self._event
        self._event = None

        # Combine all samples for spectral analysis
        combined = np.concatenate(event["samples"])
        duration_ms = (now - event["start_time"]) * 1000
        peak = event["peak"]

        # ── CHECK 1: Peak must be above minimum ──
        if peak < self.peak_min:
            if self.debug:
                print(f"  reject: peak={peak:.3f} < min={self.peak_min}")
            return

        # ── CHECK 2: Spectral signature (high freq energy) ──
        high_freq_ratio = _compute_spectral_ratio(combined, self._actual_rate)
        if high_freq_ratio < SNAP_HIGH_FREQ_RATIO_MIN:
            if self.debug:
                print(f"  reject: spectrum {high_freq_ratio:.2f} < {SNAP_HIGH_FREQ_RATIO_MIN} (likely speech/noise)")
            return

        # ── CHECK 3: Attack time (how fast peak rose) ──
        attack_ms = _compute_attack_time(
            list(self._peak_history), event["start_idx"], self._chunk_ms
        )
        if attack_ms > MAX_ATTACK_MS:
            if self.debug:
                print(f"  reject: attack {attack_ms:.0f}ms > {MAX_ATTACK_MS}ms (not sharp enough)")
            return

        # ── CHECK 4: Decay envelope (snap decays fast) ──
        # Peak was at event["peak_time"]. Check next 60ms of history.
        chunks_since_peak = event["chunks"]
        if chunks_since_peak >= 3:
            # Look at the last chunk of the event vs the peak chunk
            last_chunk_peak = float(np.max(np.abs(event["samples"][-1])))
            decay_ratio = peak / (last_chunk_peak + 1e-6)
            if decay_ratio < MIN_DECAY_RATIO:
                if self.debug:
                    print(f"  reject: decay {decay_ratio:.1f}x < {MIN_DECAY_RATIO}x (sustained, not snap)")
                return

        # PASSED all checks — real snap
        if self.debug:
            print(Fore.GREEN + f"  TAP: peak={peak:.3f} attack={attack_ms:.0f}ms "
                  f"spectrum={high_freq_ratio:.2f} dur={duration_ms:.0f}ms")

        self._register_tap(event["start_time"])

    def _register_tap(self, timestamp):
        # Prevent double-counting
        if self._pending_taps:
            last_time = self._pending_taps[-1]
            if (timestamp - last_time) * 1000 < TAP_COOLDOWN_MS:
                return

        # Post-pattern cooldown
        if (timestamp - self._last_pattern_time) * 1000 < POST_PATTERN_COOLDOWN_MS:
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
            try:
                device_index = int(sys.argv[i + 1])
            except ValueError:
                pass

    print("=" * 60)
    print("SEVEN SNAP/CLAP DETECTION — Signature-Based Classifier")
    print("=" * 60)
    print(f"Sensitivity: {sens}   Debug: {debug_mode}   Device: {device_index}")
    print()
    print("Test cases:")
    print("  1. Silence 10 sec       → should print NOTHING")
    print("  2. Talk normally 10 sec → should print NOTHING")
    print("  3. Type on keyboard     → should print NOTHING (mostly)")
    print("  4. Snap once, clearly   → should fire quickly")
    print("  5. Clap twice           → should fire as '2 taps'")
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

    detector = TriggerDetector(
        sensitivity=sens, debug=debug_mode, device_index=device_index
    )
    detector.on_pattern = on_pattern
    detector.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
        detector.stop()
        print("Done.")