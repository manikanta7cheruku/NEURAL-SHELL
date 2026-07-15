"""
=============================================================================
ears/audio_triggers.py

Audio trigger detection engine.
Uses ONSET DETECTION optimized for laptop mics with AGC (like HP OMEN).

KEY INSIGHT:
    Laptop mics with AGC (Auto Gain Control) pre-amplify audio before
    loud events arrive, so pre-silence detection fails.
    
    Instead we use ONSET DETECTION:
      - Detect sudden LEAP in loudness (quiet → very loud in one chunk)
      - Very high peak threshold (only real events pass)
      - Fast decay check (real snaps decay in 200ms, sustained sounds don't)
    
    This is how professional beat detection works in music software.

WORKS ON:
    HP OMEN, Dell, Lenovo laptops (all with AGC)
    External USB mics (also works, less filtering needed)
    Bluetooth headsets

TERMINOLOGY:
    UI: "Snap Detection"
    User can snap, clap, or knock — all counted as taps.
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
CHUNK_SIZE  = 800          # 50ms
CHANNELS    = 1
FORMAT      = pyaudio.paInt16


# ─────────────────────────────────────────────────────────────────────────
# SENSITIVITY PROFILES — Onset detection based
# ─────────────────────────────────────────────────────────────────────────

SENSITIVITY_PROFILES = {
    "low": {
        "onset_peak_min":  0.20,
        "leap_ratio":      8.0,
        "decay_ms":        250,
        "decay_ratio":     0.4,
    },
    "medium": {
        "onset_peak_min":  0.15,
        "leap_ratio":      5.0,
        "decay_ms":        300,
        "decay_ratio":     0.5,
    },
    "high": {
        "onset_peak_min":  0.08,
        "leap_ratio":      3.0,
        "decay_ms":        350,
        "decay_ratio":     0.6,
    },
}

# Pattern grouping
PATTERN_WINDOW_MS = 900
TAP_COOLDOWN_MS   = 200

# Cooldown after pattern fires
POST_PATTERN_COOLDOWN_MS = 1500


# ─────────────────────────────────────────────────────────────────────────
# TRIGGER DETECTOR
# ─────────────────────────────────────────────────────────────────────────

def _find_best_input_device():
    """
    Auto-select the best microphone for snap detection.

    Selection criteria:
      1. Has input channels
      2. Low background noise (avg < 0.05 over 0.5s sample)
      3. Good dynamic range (max/avg ratio > 2)
      4. Prefer WASAPI over DirectSound over MME
      5. Prefer headset/external over built-in array mics

    Avoids saturated devices (avg > 0.3).
    """
    try:
        import pyaudio
        pa = pyaudio.PyAudio()
        count = pa.get_device_count()

        headset_keywords  = ["hyperx", "stinger", "cloud", "headset",
                              "usb", "wireless", "external"]
        builtin_keywords  = ["array", "omen", "amd", "realtek", "laptop",
                              "internal", "integrated"]

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
                        format=pyaudio.paInt16,
                        channels=1,
                        rate=rate,
                        input=True,
                        frames_per_buffer=chunk,
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
                    mx  = max(levels)

                    # Skip saturated devices
                    if avg > 0.3:
                        continue

                    # Skip completely silent (disconnected/dummy)
                    # unless it's a headset (may be silent when no sound)
                    score = 0

                    # Low noise floor = good
                    if avg < 0.02:
                        score += 3
                    elif avg < 0.05:
                        score += 1

                    # Headset/external preferred
                    for kw in headset_keywords:
                        if kw in name:
                            score += 3
                            break

                    # Built-in array = lower priority
                    for kw in builtin_keywords:
                        if kw in name:
                            score -= 2
                            break

                    # WASAPI preferred (lower latency, cleaner signal)
                    if "wasapi" in name:
                        score += 2
                    elif "directsound" in name:
                        score += 1

                    candidates.append((score, i, info['name'], avg, mx))

                except Exception:
                    pass

            except Exception:
                continue

        pa.terminate()

        if not candidates:
            print(Fore.YELLOW + "[TRIGGERS] No suitable input device found")
            return None

        candidates.sort(reverse=True)
        best_score, best_idx, best_name, best_avg, best_max = candidates[0]

        print(Fore.CYAN + f"[TRIGGERS] Selected device {best_idx}: "
              f"{best_name} (noise={best_avg:.3f})")
        return best_idx

    except Exception as e:
        print(Fore.YELLOW + f"[TRIGGERS] Device selection failed: {e}")
        return None

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

        self._pending_taps      = deque()
        self._last_pattern_time = 0

        self.suppressed_until = 0
        self.paused           = False

        # Rolling peak history for leap detection
        # Store last ~500ms of peak values (10 chunks at 50ms each)
        self._peak_history = deque(maxlen=10)

        # Candidate onset awaiting decay confirmation
        # (timestamp, peak_amp)
        self._candidate = None
        self._candidate_history = deque(maxlen=20)  # peaks after candidate

        self._load_thresholds()

    def _load_thresholds(self):
        profile = SENSITIVITY_PROFILES.get(self.sensitivity,
                                            SENSITIVITY_PROFILES["medium"])
        self.onset_peak_min = profile["onset_peak_min"]
        self.leap_ratio     = profile["leap_ratio"]
        self.decay_ms       = profile["decay_ms"]
        self.decay_ratio    = profile["decay_ratio"]

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
                    actual_chunk = int(actual_rate * 0.05)
                    actual_channels = min(2, int(info['maxInputChannels']))
                    print(Fore.CYAN + f"[TRIGGERS] Device rate: {actual_rate}Hz, "
                          f"chunk: {actual_chunk}, channels: {actual_channels}")
                except Exception:
                    pass

            self._stream = self._audio.open(
                format=FORMAT,
                channels=actual_channels,
                rate=actual_rate,
                input=True,
                frames_per_buffer=actual_chunk,
                input_device_index=self.device_index,
            )
            self._actual_rate = actual_rate
            self._actual_chunk = actual_chunk
            self._actual_channels = actual_channels

        except Exception as e:
            print(Fore.RED + f"[TRIGGERS] Failed to open mic: {e}")
            self._running = False
            return

        # Warmup
        print(Fore.CYAN + "[TRIGGERS] Warming up (2 seconds)...")
        warmup_end = time.time() + 2.0
        while self._running and time.time() < warmup_end:
            try:
                raw = self._stream.read(self._actual_chunk, exception_on_overflow=False)
                samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                if self._actual_channels == 2:
                    samples = samples.reshape(-1, 2).mean(axis=1)
                peak = float(np.max(np.abs(samples)))
                self._peak_history.append(peak)
            except Exception:
                pass

        print(Fore.GREEN + "[TRIGGERS] Ready. Snap/clap to test.")

        while self._running:
            try:
                raw = self._stream.read(self._actual_chunk, exception_on_overflow=False)
                samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

                if self._actual_channels == 2:
                    samples = samples.reshape(-1, 2).mean(axis=1)

                if self.paused or time.time() < self.suppressed_until:
                    self._peak_history.append(0)
                    continue

                peak_amp = float(np.max(np.abs(samples)))
                now      = time.time()

                if self.debug and peak_amp > 0.15:
                    print(f"  peak={peak_amp:.3f}")

                # If tracking a candidate, watch its decay
                if self._candidate is not None:
                    self._track_candidate(peak_amp, now)
                else:
                    # Look for new onset
                    self._detect_onset(peak_amp, now)

                self._peak_history.append(peak_amp)
                self._check_pattern_ready()

            except Exception:
                time.sleep(0.3)

    def _detect_onset(self, peak_amp, now):
        """
        Detect a sudden LEAP in loudness = onset of a tap event.
        No pre-silence requirement — just needs to be significantly louder
        than the recent past.
        """

        # Must be loud enough
        if peak_amp < self.onset_peak_min:
            return

        # Compute recent average (excluding last chunk to avoid tap itself)
        if len(self._peak_history) < 3:
            return

        recent = list(self._peak_history)[-6:]  # last 300ms
        recent_avg = sum(recent) / len(recent)

        # LEAP check: current peak must be much louder than recent average
        if recent_avg < 0.01:  # avoid division issues, treat as silence
            recent_avg = 0.01

        leap = peak_amp / recent_avg
        if leap < self.leap_ratio:
            return

        # Post-pattern cooldown
        if (now - self._last_pattern_time) * 1000 < POST_PATTERN_COOLDOWN_MS:
            return

        # Onset detected — start candidate tracking
        self._candidate = (now, peak_amp)
        self._candidate_history.clear()
        if self.debug:
            print(Fore.CYAN + f"  ? ONSET (peak={peak_amp:.3f}, leap={leap:.1f}x) "
                  f"— tracking decay")

    def _track_candidate(self, peak_amp, now):
        """
        Track the candidate's decay pattern.
        Real snap: decays quickly to below decay_ratio of peak within decay_ms.
        Sustained sound (music, siren): stays loud.
        """
        cand_time, cand_peak = self._candidate
        elapsed_ms = (now - cand_time) * 1000

        self._candidate_history.append(peak_amp)

        # Check if we're past the decay window
        if elapsed_ms >= self.decay_ms:
            # Compute average peak over decay window
            if self._candidate_history:
                decay_avg = sum(self._candidate_history) / len(self._candidate_history)
                decay_pct = decay_avg / cand_peak

                if decay_pct <= self.decay_ratio:
                    # Good decay — confirmed tap
                    if self.debug:
                        print(Fore.GREEN + f"  ✓ CONFIRMED (decay to "
                              f"{decay_pct*100:.0f}% in {elapsed_ms:.0f}ms)")
                    self._register_tap(cand_time)
                else:
                    # Bad decay — sustained sound, not a tap
                    if self.debug:
                        print(Fore.YELLOW + f"  ✗ REJECTED (poor decay, "
                              f"still at {decay_pct*100:.0f}% after {elapsed_ms:.0f}ms)")

            self._candidate = None
            self._candidate_history.clear()

    def _register_tap(self, timestamp):
        if self._pending_taps:
            last_time = self._pending_taps[-1]
            if (timestamp - last_time) * 1000 < TAP_COOLDOWN_MS:
                return

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
    print("SEVEN TRIGGER DETECTION — Onset Detection Mode")
    print("Optimized for laptop mics with AGC")
    print("=" * 60)
    print()
    print(f"Sensitivity: {sens}")
    print(f"Debug mode:  {debug_mode}")
    print(f"Device:      {device_index}")
    print()
    print("Test cases:")
    print("  1. Silence 10 sec — should print NOTHING")
    print("  2. Talk normally — should print NOTHING")
    print("  3. Snap/clap loudly — should fire quickly")
    print()
    print("Press Ctrl+C to stop.")
    print("=" * 60)
    print()

    def on_pattern(count):
        print()
        print("!" * 60)
        print(f">>> TRIGGER FIRED: {count} tap{'s' if count > 1 else ''}")
        print("!" * 60)
        print()

    detector = TriggerDetector(
        sensitivity=sens,
        debug=debug_mode,
        device_index=device_index
    )
    detector.on_pattern = on_pattern
    detector.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nStopping...")
        detector.stop()
        print("Done.")