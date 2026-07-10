"""
=============================================================================
ears/audio_triggers_ml.py

ML-based audio trigger detection for headset/USB mic users.
Uses YAMNet for sound classification + DSP for onset detection.

Combined approach:
  1. DSP onset detector catches candidate events (fast, ~30ms)
  2. YAMNet classifies the candidate (accurate, ~100ms)
  3. Both must agree for trigger to fire (reduces false positives)

WHEN TO USE:
  This file used instead of audio_triggers.py when:
    - User has external mic (USB or headset)
    - Mic compatibility test passed in setup wizard

WHEN NOT TO USE:
  Built-in laptop mics with aggressive AGC (HP OMEN, Dell, etc.)
  → These filter snaps at hardware level, nothing we can do
=============================================================================
"""

import time
import threading
import numpy as np
from collections import deque
from colorama import Fore

try:
    import pyaudio
except ImportError:
    print(Fore.RED + "[AUDIO ML] pyaudio required")
    raise


SAMPLE_RATE = 16000
CHUNK_SIZE  = 800   # 50ms
CHANNELS    = 1
FORMAT      = pyaudio.paInt16

PATTERN_WINDOW_MS = 900
TAP_COOLDOWN_MS   = 250
POST_PATTERN_COOLDOWN_MS = 1500

YAMNET_CONFIDENCE_THRESHOLD = 0.25  # lowered for real-world mic quality


class MLTriggerDetector:
    """
    Combined DSP + YAMNet detector for reliable snap/clap detection.
    Only used when external mic is available (headset, USB mic).
    """

    def __init__(self, sensitivity="medium", device_index=None, debug=False):
        self.sensitivity  = sensitivity
        self.device_index = device_index
        self.debug        = debug

        self.on_pattern   = None
        self.on_detection = None

        self._running = False
        self._thread  = None
        self._audio   = None
        self._stream  = None

        self._pending_taps      = deque()
        self._last_pattern_time = 0

        self.suppressed_until = 0
        self.paused           = False

        self._classifier = None
        self._recent_peaks = deque(maxlen=5)
        self._audio_buffer = deque(maxlen=35)  # ~1.75 seconds at 50ms chunks

    def start(self):
        if self._running:
            return
        self._running = True

        # Load YAMNet classifier
        try:
            from ears.yamnet_wrapper import YAMNetClassifier
            self._classifier = YAMNetClassifier()
            print(Fore.GREEN + "[AUDIO ML] YAMNet loaded")
        except Exception as e:
            print(Fore.YELLOW + f"[AUDIO ML] YAMNet not available, using DSP only: {e}")

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print(Fore.GREEN + f"[AUDIO ML] Started (sensitivity={self.sensitivity})")

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
        print(Fore.YELLOW + "[AUDIO ML] Stopped")

    def suppress(self, duration_ms=3000):
        self.suppressed_until = time.time() + (duration_ms / 1000.0)

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

    def _run(self):
        try:
            self._audio = pyaudio.PyAudio()
            self._stream = self._audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                input=True,
                frames_per_buffer=CHUNK_SIZE,
                input_device_index=self.device_index,
            )
        except Exception as e:
            print(Fore.RED + f"[AUDIO ML] Mic open failed: {e}")
            self._running = False
            return

        # Warmup
        print(Fore.CYAN + "[AUDIO ML] Warming up...")
        warmup_end = time.time() + 2.0
        while self._running and time.time() < warmup_end:
            try:
                raw = self._stream.read(CHUNK_SIZE, exception_on_overflow=False)
                samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                self._audio_buffer.append(samples)
            except Exception:
                pass
        print(Fore.GREEN + "[AUDIO ML] Ready")

        while self._running:
            try:
                raw = self._stream.read(CHUNK_SIZE, exception_on_overflow=False)
                samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

                if self.paused or time.time() < self.suppressed_until:
                    self._audio_buffer.append(samples)
                    continue

                peak = float(np.max(np.abs(samples)))
                self._audio_buffer.append(samples)

                # DSP onset check first (fast)
                is_onset = self._check_onset(peak)

                if is_onset:
                    # Run YAMNet on last 1 second of audio
                    if self._classifier:
                        confidence = self._classify_recent_audio()
                        if confidence > YAMNET_CONFIDENCE_THRESHOLD:
                            if self.debug:
                                print(Fore.GREEN + f"  ML CONFIRMED (conf={confidence:.2f})")
                            self._register_tap()
                        elif self.debug:
                            print(Fore.YELLOW + f"  ML REJECTED (conf={confidence:.2f})")
                    else:
                        # No YAMNet — use DSP only
                        self._register_tap()

                self._recent_peaks.append(peak)
                self._check_pattern_ready()

            except Exception:
                time.sleep(0.3)

    def _check_onset(self, peak):
        """Quick DSP check for sudden loudness spike."""
        if peak < 0.15:
            return False

        if self._recent_peaks:
            avg = sum(self._recent_peaks) / len(self._recent_peaks)
            if avg > 0.01 and (peak / avg) < 3.0:
                return False

        if self.debug:
            print(Fore.CYAN + f"  DSP onset: peak={peak:.3f}")

        return True

    def _classify_recent_audio(self):
        """Run YAMNet on the last ~1 second of audio buffer."""
        if len(self._audio_buffer) < 20:
            return 0.0

        # Take last 20 chunks (~1 second at 50ms chunks)
        recent = list(self._audio_buffer)[-20:]
        audio_1s = np.concatenate(recent)

        try:
            result = self._classifier.classify(audio_1s, sample_rate=SAMPLE_RATE)
            snap_conf = result.get("snap", 0)
            clap_conf = result.get("clap", 0)
            return max(snap_conf, clap_conf)
        except Exception as e:
            if self.debug:
                print(Fore.RED + f"  YAMNet error: {e}")
            return 0.0

    def _register_tap(self):
        now = time.time()
        if self._pending_taps:
            if (now - self._pending_taps[-1]) * 1000 < TAP_COOLDOWN_MS:
                return
        if (now - self._last_pattern_time) * 1000 < POST_PATTERN_COOLDOWN_MS:
            return

        self._pending_taps.append(now)
        print(Fore.CYAN + f"[AUDIO ML] Tap {len(self._pending_taps)}")

        if self.on_detection:
            try:
                self.on_detection()
            except Exception:
                pass

    def _check_pattern_ready(self):
        if not self._pending_taps:
            return
        now = time.time()
        if (now - self._pending_taps[-1]) * 1000 < PATTERN_WINDOW_MS:
            return

        count = len(self._pending_taps)
        self._pending_taps.clear()
        if count > 3:
            return

        self._last_pattern_time = now
        print(Fore.GREEN + f"[AUDIO ML] PATTERN: {count} tap{'s' if count > 1 else ''}")

        if self.on_pattern:
            try:
                self.on_pattern(count)
            except Exception as e:
                print(Fore.RED + f"[AUDIO ML] Callback error: {e}")