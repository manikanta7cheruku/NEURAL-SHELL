"""
=============================================================================
ears/audio_triggers.py

Professional snap/clap detection using RMS-based adaptive noise gating.

DESIGN:
  Traditional peak thresholds fail because voice peaks can equal snap peaks.
  Solution: track two separate metrics.
    - RMS (Root Mean Square) = sustained loudness (voice, background noise)
    - PEAK = instantaneous max amplitude (snap, click, transient)

  A snap has HIGH peak but LOW RMS in the surrounding window.
  Voice has HIGH peak AND HIGH RMS.
  Ratio peak / rms_background is the KEY discriminator.

DETECTION PIPELINE:
  1. Track rolling 1.5s RMS as "background floor"
  2. When peak > (background_rms × spike_ratio) → event start
  3. Classify event:
       a. Duration < 100ms (snap is brief)
       b. Attack ratio > 4x (rose sharply)
       c. Spectrum centroid > 2000 Hz (high-freq bright, not voice bass)
       d. Decay ratio > 2x (drops fast)
       e. Peak/RMS spike ratio > 6x (transient signature)
  4. Any voice/rumble fails at least one check

CALIBRATION:
  User taps 3 times → Seven records peaks → sets user_peak_min = median × 0.6
  Stored in config.json per device.

DESIGNED FOR: USB headsets, wired mics, USB condenser mics.
LAPTOP MICS: not supported (AGC destroys transients).
=============================================================================
"""

import os
import json
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
CHUNK_SIZE  = 320          # 20 ms at 16 kHz
CHANNELS    = 1
FORMAT      = pyaudio.paInt16

# Sensitivity profiles — spike ratios above ADAPTIVE background RMS
SENSITIVITY_PROFILES = {
    "low": {
        "spike_ratio":       10.0,   # peak must be 10× rolling RMS
        "min_peak":          0.10,   # never trigger below this
        "spectrum_centroid": 2500,   # must be brighter than 2.5 kHz
        "attack_ratio":      5.0,    # rose 5× in one chunk
        "decay_ratio":       2.5,    # dropped 2.5× within 80 ms
    },
    "medium": {
        "spike_ratio":       7.0,
        "min_peak":          0.06,
        "spectrum_centroid": 2000,
        "attack_ratio":      4.0,
        "decay_ratio":       2.0,
    },
    "high": {
        "spike_ratio":       5.0,
        "min_peak":          0.04,
        "spectrum_centroid": 1700,
        "attack_ratio":      3.0,
        "decay_ratio":       1.7,
    },
}

# Timing
MAX_EVENT_MS      = 120
MIN_EVENT_MS      = 5
PATTERN_WINDOW_MS = 700
TAP_COOLDOWN_MS   = 200
POST_PATTERN_MS   = 1500

# RMS tracking window (background noise average)
RMS_WINDOW_CHUNKS = 75          # 75 × 20ms = 1.5 seconds
RMS_ALPHA         = 0.05        # slow adaptation


# ─────────────────────────────────────────────────────────────────────────
# CALIBRATION STORAGE
# ─────────────────────────────────────────────────────────────────────────

def _get_calibration_path():
    appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
    d = os.path.join(appdata, "SEVEN", "audio")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "snap_calibration.json")


def load_calibration():
    """Return dict {peak_min: float, mic_name: str} or None."""
    try:
        p = _get_calibration_path()
        if os.path.exists(p):
            with open(p, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return None


def save_calibration(peak_min, mic_name):
    try:
        p = _get_calibration_path()
        with open(p, "w") as f:
            json.dump({
                "peak_min": float(peak_min),
                "mic_name": str(mic_name),
                "calibrated_at": time.time(),
            }, f)
        return True
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────
# MIC SELECTION
# ─────────────────────────────────────────────────────────────────────────

def _find_best_input_device():
    try:
        pa = pyaudio.PyAudio()
        count = pa.get_device_count()

        headset_keywords = ["hyperx", "stinger", "cloud", "headset",
                            "usb", "wireless", "external", "airpods",
                            "buds", "audio-technica", "shure", "blue",
                            "logitech", "razer", "steelseries"]

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
                    if avg < 0.02:
                        score += 3
                    for kw in headset_keywords:
                        if kw in name:
                            score += 4
                            break
                    if "wasapi" in name:
                        score += 2

                    candidates.append((score, i, info['name']))
                except Exception:
                    pass
            except Exception:
                continue

        pa.terminate()

        if not candidates:
            return None, None

        candidates.sort(reverse=True)
        _, best_idx, best_name = candidates[0]
        return best_idx, best_name

    except Exception:
        return None, None


# ─────────────────────────────────────────────────────────────────────────
# SIGNAL ANALYSIS
# ─────────────────────────────────────────────────────────────────────────

def _spectral_centroid(samples, sample_rate):
    """
    Compute spectral centroid (the 'center of mass' of the spectrum).
    Voice: 500-1500 Hz. Snaps/claps: 2000-5000 Hz.
    """
    if len(samples) < 32:
        return 0.0

    windowed = samples * np.hanning(len(samples))
    fft = np.abs(np.fft.rfft(windowed))
    freqs = np.fft.rfftfreq(len(windowed), d=1.0 / sample_rate)

    total = float(np.sum(fft)) + 1e-9
    weighted = float(np.sum(freqs * fft))
    return weighted / total


# ─────────────────────────────────────────────────────────────────────────
# TRIGGER DETECTOR
# ─────────────────────────────────────────────────────────────────────────

class TriggerDetector:

    def __init__(self, sensitivity="medium", device_index=None, debug=False):
        if device_index is None:
            device_index, self._mic_name = _find_best_input_device()
        else:
            self._mic_name = None

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

        # RMS envelope tracking
        self._rms_history       = deque(maxlen=RMS_WINDOW_CHUNKS)
        self._background_rms    = 0.005

        # Recent peaks for attack detection
        self._recent_peaks      = deque(maxlen=5)

        # Event state
        self._event             = None
        self._event_pre_peak    = 0.0
        self._event_pre_rms     = 0.005

        self._load_thresholds()

    def _load_thresholds(self):
        profile = SENSITIVITY_PROFILES.get(self.sensitivity, SENSITIVITY_PROFILES["medium"])
        self.spike_ratio        = profile["spike_ratio"]
        self.min_peak           = profile["min_peak"]
        self.spectrum_centroid  = profile["spectrum_centroid"]
        self.attack_ratio_min   = profile["attack_ratio"]
        self.decay_ratio_min    = profile["decay_ratio"]

        # Load user calibration if present
        calib = load_calibration()
        if calib and calib.get("peak_min"):
            self.min_peak = float(calib["peak_min"])
            print(Fore.CYAN + f"[TRIGGERS] Loaded calibration: peak_min={self.min_peak:.3f}")

    def set_sensitivity(self, level):
        if level in SENSITIVITY_PROFILES:
            self.sensitivity = level
            self._load_thresholds()

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

    def get_threshold(self):
        """Adaptive threshold = max(background_rms × spike_ratio, min_peak)."""
        adaptive = self._background_rms * self.spike_ratio
        return max(adaptive, self.min_peak)

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
                    actual_chunk = int(actual_rate * 0.02)
                    actual_channels = min(2, int(info['maxInputChannels']))
                    if not self._mic_name:
                        self._mic_name = info['name']
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

        # ── CALIBRATION: 2s silence to establish background RMS ──
        print(Fore.CYAN + "[TRIGGERS] Measuring background noise (2s silence)...")
        warmup_end = time.time() + 2.0
        warmup_rms = []
        while self._running and time.time() < warmup_end:
            try:
                raw = self._stream.read(self._actual_chunk, exception_on_overflow=False)
                samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                if self._actual_channels == 2:
                    samples = samples.reshape(-1, 2).mean(axis=1)
                rms = float(np.sqrt(np.mean(samples ** 2)))
                warmup_rms.append(rms)
                self._rms_history.append(rms)
            except Exception:
                pass

        if warmup_rms:
            self._background_rms = float(np.median(warmup_rms))
            self._background_rms = max(0.001, self._background_rms)

        print(Fore.GREEN + f"[TRIGGERS] Background RMS: {self._background_rms:.4f}")
        print(Fore.GREEN + f"[TRIGGERS] Snap threshold: {self.get_threshold():.4f} "
              f"(peak must exceed this)")
        print(Fore.GREEN + f"[TRIGGERS] Mic: {self._mic_name or 'unknown'}")

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
                rms_amp  = float(np.sqrt(np.mean(samples ** 2)))
                now      = time.time()

                # Update background RMS (only when not in event)
                if self._event is None:
                    self._rms_history.append(rms_amp)
                    # Use median of window for robust background estimate
                    if len(self._rms_history) >= 10:
                        self._background_rms = float(np.median(list(self._rms_history)))
                        self._background_rms = max(0.001, self._background_rms)

                self._process_chunk(samples, peak_amp, rms_amp, now)
                self._recent_peaks.append(peak_amp)
                self._check_pattern_ready()

            except Exception as e:
                if self.debug:
                    print(f"[TRIGGERS] Loop error: {e}")
                time.sleep(0.3)

    def _process_chunk(self, samples, peak_amp, rms_amp, now):
        threshold = self.get_threshold()

        # Nothing to process
        if self._event is None and peak_amp < threshold:
            return

        # Start new event
        if self._event is None:
            self._event_pre_peak = max(self._recent_peaks) if self._recent_peaks else 0.0
            self._event_pre_rms  = self._background_rms
            self._event = {
                "start_time": now,
                "samples": [samples.copy()],
                "peak": peak_amp,
                "peak_time": now,
                "chunks": 1,
                "peak_chunk_rms": rms_amp,
            }
            return

        # Continue event
        self._event["samples"].append(samples.copy())
        self._event["chunks"] += 1
        if peak_amp > self._event["peak"]:
            self._event["peak"] = peak_amp
            self._event["peak_time"] = now
            self._event["peak_chunk_rms"] = rms_amp

        elapsed_ms = (now - self._event["start_time"]) * 1000

        # End event
        if peak_amp < threshold * 0.5 or elapsed_ms > MAX_EVENT_MS:
            self._finalize_event(now)

    def _finalize_event(self, now):
        if self._event is None:
            return

        event = self._event
        self._event = None

        combined     = np.concatenate(event["samples"])
        duration_ms  = (now - event["start_time"]) * 1000
        peak         = event["peak"]

        # ── CHECK 1: Duration bounds ──
        if duration_ms < MIN_EVENT_MS:
            if self.debug:
                print(f"  reject: duration {duration_ms:.0f}ms too short")
            return

        if duration_ms > MAX_EVENT_MS:
            if self.debug:
                print(f"  reject: duration {duration_ms:.0f}ms too long (voice/sustained)")
            return

        # ── CHECK 2: Peak minimum ──
        if peak < self.min_peak:
            if self.debug:
                print(f"  reject: peak {peak:.3f} < min {self.min_peak:.3f}")
            return

        # ── CHECK 3: Peak/RMS spike ratio (THE KEY DISCRIMINATOR) ──
        # Snap: peak much higher than surrounding RMS
        # Voice: peak similar to RMS (sustained sound)
        spike_ratio = peak / (self._event_pre_rms + 0.001)
        if spike_ratio < self.spike_ratio:
            if self.debug:
                print(f"  reject: spike ratio {spike_ratio:.1f}x < {self.spike_ratio:.1f}x "
                      f"(too sustained — likely voice)")
            return

        # ── CHECK 4: Attack ratio ──
        attack_ratio = peak / (self._event_pre_peak + 0.001)
        if attack_ratio < self.attack_ratio_min:
            if self.debug:
                print(f"  reject: attack {attack_ratio:.1f}x too gradual")
            return

        # ── CHECK 5: Spectral centroid (frequency signature) ──
        centroid = _spectral_centroid(combined, self._actual_rate)
        if centroid < self.spectrum_centroid:
            if self.debug:
                print(f"  reject: centroid {centroid:.0f}Hz < {self.spectrum_centroid}Hz "
                      f"(too low-freq — voice/rumble)")
            return

        # ── CHECK 6: Decay ──
        last_chunk_peak = float(np.max(np.abs(event["samples"][-1])))
        decay_ratio = peak / (last_chunk_peak + 0.001)
        if decay_ratio < self.decay_ratio_min:
            if self.debug:
                print(f"  reject: decay {decay_ratio:.1f}x too slow")
            return

        # PASSED all checks
        if self.debug:
            print(Fore.GREEN + f"  TAP: peak={peak:.3f} spike={spike_ratio:.1f}x "
                  f"attack={attack_ratio:.1f}x centroid={centroid:.0f}Hz "
                  f"decay={decay_ratio:.1f}x dur={duration_ms:.0f}ms")

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
# CALIBRATION HELPER (called from UI)
# ─────────────────────────────────────────────────────────────────────────

def run_calibration(seconds=10):
    """
    Interactive calibration.
    User snaps 3 times. We measure their actual peaks and store
    peak_min = median × 0.55 so real snaps clear the bar.

    IMPORTANT: This is OPTIONAL. Default sensitivity works for most
    headsets. Calibration is only needed if:
      - Your snaps are unusually quiet
      - You have unusual background noise
      - Detection is missing snaps or firing on voice
    """
    device_idx, mic_name = _find_best_input_device()
    if device_idx is None:
        return {"success": False, "message": "No microphone found"}

    pa = pyaudio.PyAudio()
    try:
        info = pa.get_device_info_by_index(device_idx)
        rate = int(info['defaultSampleRate'])
        chunk = int(rate * 0.02)
        channels = min(2, int(info['maxInputChannels']))

        stream = pa.open(
            format=pyaudio.paInt16, channels=channels,
            rate=rate, input=True, frames_per_buffer=chunk,
            input_device_index=device_idx,
        )
    except Exception as e:
        pa.terminate()
        return {"success": False, "message": f"Mic open failed: {e}"}

    # ── PHASE 1: Measure background for 1 second ──
    print("[CALIB] Background sampling (1s of silence)...")
    bg_peaks = []
    end = time.time() + 1.0
    while time.time() < end:
        try:
            raw = stream.read(chunk, exception_on_overflow=False)
            s = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            if channels == 2:
                s = s.reshape(-1, 2).mean(axis=1)
            bg_peaks.append(float(np.max(np.abs(s))))
        except Exception:
            pass

    # Use 95th percentile as background ceiling (ignores rare spikes)
    bg_ceiling = float(np.percentile(bg_peaks, 95)) if bg_peaks else 0.02

    # Snap threshold for CAPTURE = only 1.5x above background ceiling
    # (much more lenient than actual detection so we don't miss captures)
    snap_capture_threshold = max(bg_ceiling * 1.5, 0.02)

    print(f"[CALIB] Background ceiling: {bg_ceiling:.4f}")
    print(f"[CALIB] Will capture peaks above: {snap_capture_threshold:.4f}")
    print(f"[CALIB] Snap 3 times in the next {seconds} seconds...")

    # ── PHASE 2: Capture up to 5 snap peaks ──
    peaks = []
    end = time.time() + seconds
    last_snap = 0
    while time.time() < end and len(peaks) < 5:
        try:
            raw = stream.read(chunk, exception_on_overflow=False)
            s = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            if channels == 2:
                s = s.reshape(-1, 2).mean(axis=1)
            p = float(np.max(np.abs(s)))

            # Capture if peak exceeds threshold AND at least 0.3s since last capture
            if p > snap_capture_threshold and (time.time() - last_snap) > 0.3:
                peaks.append(p)
                last_snap = time.time()
                print(f"[CALIB] Captured snap {len(peaks)}: peak={p:.3f}")
        except Exception:
            pass

    try:
        stream.stop_stream()
        stream.close()
        pa.terminate()
    except Exception:
        pass

    if len(peaks) < 2:
        return {
            "success": False,
            "message": f"Only captured {len(peaks)} snap(s). "
                       f"Try again — snap louder and closer to the mic.",
            "peaks": peaks,
            "background": round(bg_ceiling, 4),
        }

    # Threshold at 50% of median snap peak (gives comfortable margin)
    # But never lower than 2x background (avoids voice false positives)
    median_peak = float(np.median(peaks))
    peak_min = round(median_peak * 0.5, 3)
    min_safe = round(bg_ceiling * 2.5, 3)
    peak_min = max(peak_min, min_safe)
    peak_min = max(0.02, min(0.30, peak_min))

    saved = save_calibration(peak_min, mic_name or "unknown")

    return {
        "success": True,
        "peaks": [round(p, 3) for p in peaks],
        "peak_min": peak_min,
        "median": round(median_peak, 3),
        "background": round(bg_ceiling, 4),
        "mic_name": mic_name,
        "saved": saved,
        "message": f"Calibrated successfully. Detection threshold: {peak_min:.3f}",
    }

# ─────────────────────────────────────────────────────────────────────────
# STANDALONE TEST
# ─────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if "--calibrate" in sys.argv:
        print("=" * 60)
        print("SNAP CALIBRATION")
        print("=" * 60)
        result = run_calibration()
        print()
        print(json.dumps(result, indent=2))
        sys.exit(0)

    debug_mode = "--debug" in sys.argv
    sens = "medium"
    for i, a in enumerate(sys.argv):
        if a == "--sensitivity" and i + 1 < len(sys.argv):
            sens = sys.argv[i + 1]

    print("=" * 60)
    print("SEVEN SNAP DETECTION — Adaptive Noise Gate")
    print("=" * 60)
    print(f"Sensitivity: {sens}   Debug: {debug_mode}")
    print()
    print("Test cases:")
    print("  1. Silence           → nothing")
    print("  2. Talk loudly       → nothing (spike ratio filter)")
    print("  3. Shout             → nothing (sustained voice)")
    print("  4. Snap fingers      → fires")
    print("  5. Clap hands        → fires")
    print()
    print("Run --calibrate first to personalize your threshold.")
    print("Ctrl+C to stop.")
    print("=" * 60)

    def on_pattern(count):
        print()
        print("!" * 60)
        print(f">>> PATTERN FIRED: {count} tap{'s' if count > 1 else ''}")
        print("!" * 60)
        print()

    detector = TriggerDetector(sensitivity=sens, debug=debug_mode)
    detector.on_pattern = on_pattern
    detector.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        detector.stop()