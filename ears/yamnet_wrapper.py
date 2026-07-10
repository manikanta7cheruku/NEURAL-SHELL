"""
=============================================================================
ears/yamnet_wrapper.py

YAMNet audio classifier wrapper for Seven trigger detection.

WHAT IS YAMNET:
    Google's pre-trained audio classifier.
    Trained on 2 million YouTube clips.
    Recognizes 521 sound classes including "Finger snapping" and
    "Hands (clapping)".
    Size: ~17MB.
    Runs on CPU.

CLASSES OF INTEREST (from AudioSet ontology):
    class 428: "Finger snapping"
    class 427: "Hands"                 (contains clapping generally)
    class 430: "Applause"              (crowd clapping)
    class 431: "Chatter"               (voice — we IGNORE this class)
    class  0:  "Speech"                (voice — we IGNORE this class)

MODEL LOCATION:
    Downloaded once to: seven_data/models/yamnet/
    Loaded from cache thereafter (offline forever).

USAGE:
    classifier = YAMNetClassifier()
    result = classifier.classify(audio_samples, sample_rate=16000)
    # result = {"snap": 0.72, "clap": 0.05, "voice": 0.02, "top_5": [...]}
=============================================================================
"""

import os
import sys
import numpy as np
from colorama import Fore

# Suppress TensorFlow warnings for cleaner output
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

try:
    import tensorflow as tf
    import tensorflow_hub as hub
except ImportError:
    print(Fore.RED + "[YAMNET] tensorflow / tensorflow_hub not installed")
    print(Fore.RED + "[YAMNET] Run Stage 1A to install dependencies")
    raise


# ─────────────────────────────────────────────────────────────────────────
# MODEL CACHE LOCATION
# ─────────────────────────────────────────────────────────────────────────

def _get_model_cache_dir():
    """Return path to model cache directory. Create if missing."""
    # Follow Seven's convention — models under seven_data/
    try:
        from seven_paths import paths
        base = paths._seven_data
    except Exception:
        base = os.path.join(os.getcwd(), "seven_data")

    model_dir = os.path.join(base, "models", "yamnet")
    os.makedirs(model_dir, exist_ok=True)
    return model_dir


# Tell TensorFlow Hub where to cache downloaded models
os.environ["TFHUB_CACHE_DIR"] = _get_model_cache_dir()

YAMNET_URL = "https://tfhub.dev/google/yamnet/1"


# ─────────────────────────────────────────────────────────────────────────
# CLASS INDEX MAP
# Full YAMNet class list has 521 entries. We hardcode the ones we care
# about for fast lookup. Loaded dynamically at init for accuracy.
# ─────────────────────────────────────────────────────────────────────────

# Keywords to identify tap-related classes
SNAP_KEYWORDS = ["finger snap"]
CLAP_KEYWORDS = ["hands", "clap", "applause", "slap"]
VOICE_KEYWORDS = ["speech", "chatter", "conversation", "narration",
                  "monologue", "female speech", "male speech",
                  "child speech", "whispering", "singing"]


# ─────────────────────────────────────────────────────────────────────────
# YAMNET CLASSIFIER
# ─────────────────────────────────────────────────────────────────────────

class YAMNetClassifier:
    """
    Wraps YAMNet model for sound classification.
    
    USAGE:
        classifier = YAMNetClassifier()   # loads model (slow first time)
        result = classifier.classify(audio_np_array, sample_rate=16000)
        
        result = {
            "snap": 0.72,        # confidence 0-1 for finger snapping
            "clap": 0.05,        # confidence 0-1 for clapping/hands
            "voice": 0.02,       # confidence 0-1 for speech/voice
            "top_5": [           # top 5 predictions for debugging
                ("Finger snapping", 0.72),
                ("Music", 0.10),
                ...
            ]
        }
    """

    _model = None
    _class_names = None
    _snap_indices = None
    _clap_indices = None
    _voice_indices = None

    def __init__(self):
        if YAMNetClassifier._model is None:
            self._load_model()

    def _load_model(self):
        """Load YAMNet from local cache or download if first time."""
        print(Fore.CYAN + "[YAMNET] Loading model (may download ~17MB on first run)...")
        try:
            model = hub.load(YAMNET_URL)
            YAMNetClassifier._model = model
            print(Fore.GREEN + "[YAMNET] Model loaded")

            # Load class names from model
            class_map_path = model.class_map_path().numpy().decode("utf-8")
            class_names = self._load_class_names(class_map_path)
            YAMNetClassifier._class_names = class_names
            print(Fore.CYAN + f"[YAMNET] {len(class_names)} sound classes available")

            # Find indices for our classes of interest
            YAMNetClassifier._snap_indices = self._find_indices(
                class_names, SNAP_KEYWORDS
            )
            YAMNetClassifier._clap_indices = self._find_indices(
                class_names, CLAP_KEYWORDS
            )
            YAMNetClassifier._voice_indices = self._find_indices(
                class_names, VOICE_KEYWORDS
            )

            print(Fore.CYAN + f"[YAMNET] Snap classes: {YAMNetClassifier._snap_indices}")
            print(Fore.CYAN + f"[YAMNET] Clap classes: {YAMNetClassifier._clap_indices}")
            print(Fore.CYAN + f"[YAMNET] Voice classes: {len(YAMNetClassifier._voice_indices)} found")

        except Exception as e:
            print(Fore.RED + f"[YAMNET] Failed to load: {e}")
            import traceback; traceback.print_exc()
            raise

    def _load_class_names(self, csv_path):
        """Load YAMNet class names from CSV mapping file."""
        import csv
        names = []
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)  # skip header row
            for row in reader:
                # Format: index, mid, display_name
                names.append(row[2])
        return names

    def _find_indices(self, class_names, keywords):
        """Return list of class indices matching any keyword."""
        indices = []
        for i, name in enumerate(class_names):
            name_lower = name.lower()
            if any(kw in name_lower for kw in keywords):
                indices.append((i, name))
        return indices

    def classify(self, audio_samples, sample_rate=16000):
        """
        Classify a snippet of audio.
        
        ARGS:
            audio_samples: numpy array of float32 in [-1, 1] range
            sample_rate:   must be 16000 (YAMNet requirement)
        
        RETURNS:
            dict with snap/clap/voice confidences and top-5 predictions
        """
        # YAMNet requires 16kHz mono float32
        if sample_rate != 16000:
            raise ValueError(f"YAMNet requires 16kHz, got {sample_rate}")

        # Ensure float32 in correct range
        if audio_samples.dtype != np.float32:
            audio_samples = audio_samples.astype(np.float32)

        # YAMNet requires 1D array
        if len(audio_samples.shape) > 1:
            audio_samples = audio_samples.mean(axis=1)

        # Normalize if needed (YAMNet expects [-1, 1])
        max_val = np.max(np.abs(audio_samples))
        if max_val > 1.0:
            audio_samples = audio_samples / max_val

        # Run inference — returns (scores, embeddings, spectrogram)
        # scores shape: (num_frames, 521) — one prediction per 0.48s frame
        scores, embeddings, spectrogram = YAMNetClassifier._model(audio_samples)
        scores_np = scores.numpy()

        # Aggregate: take mean across all frames
        mean_scores = np.mean(scores_np, axis=0)

        # Extract our targeted confidences (max across matching classes)
        snap_conf = max(
            [mean_scores[idx] for idx, _ in YAMNetClassifier._snap_indices],
            default=0.0
        )
        clap_conf = max(
            [mean_scores[idx] for idx, _ in YAMNetClassifier._clap_indices],
            default=0.0
        )
        voice_conf = max(
            [mean_scores[idx] for idx, _ in YAMNetClassifier._voice_indices],
            default=0.0
        )

        # Top 5 predictions for debugging
        top_5_indices = np.argsort(mean_scores)[-5:][::-1]
        top_5 = [
            (YAMNetClassifier._class_names[i], float(mean_scores[i]))
            for i in top_5_indices
        ]

        return {
            "snap":  float(snap_conf),
            "clap":  float(clap_conf),
            "voice": float(voice_conf),
            "top_5": top_5,
        }


# ─────────────────────────────────────────────────────────────────────────
# STANDALONE TEST — Stage 1D
# Records 3 seconds of audio, classifies with YAMNet, prints results
# ─────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import time
    import pyaudio

    device_index = 2
    for i, a in enumerate(sys.argv):
        if a == "--device" and i + 1 < len(sys.argv):
            try:
                device_index = int(sys.argv[i + 1])
            except ValueError:
                pass

    print("=" * 60)
    print("STAGE 1D: YAMNET STANDALONE DETECTION TEST v2")
    print("=" * 60)
    print()
    print(f"Recording device: {device_index}")
    print()
    print("FIX FROM v1: This version has countdown + peak-window analysis")
    print("             so short sounds like snaps are properly detected.")
    print()
    print("=" * 60)
    print()

    classifier = YAMNetClassifier()

    print()
    print("=" * 60)
    print("READY TO TEST")
    print("=" * 60)
    print()

    def record_with_countdown(label, duration=3.0, countdown=True):
        """Record audio with visible countdown before start."""
        print(f"\n>>> {label}")

        audio = pyaudio.PyAudio()

        try:
            info = audio.get_device_info_by_index(device_index)
            rate = int(info['defaultSampleRate'])
            channels = min(2, int(info['maxInputChannels']))
        except Exception:
            rate = 44100
            channels = 2

        chunk = int(rate * 0.05)  # 50ms chunks for fine granularity

        # Countdown BEFORE recording
        if countdown:
            for c in [3, 2, 1]:
                print(f"    Starting in {c}...", end="\r", flush=True)
                time.sleep(1)
            print("    RECORDING NOW - MAKE THE SOUND!   ")

        stream = audio.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=rate,
            input=True,
            frames_per_buffer=chunk,
            input_device_index=device_index,
        )

        frames = []
        num_chunks = int((duration * rate) / chunk)

        # Show live peak during recording
        max_peak = 0
        for i in range(num_chunks):
            data = stream.read(chunk, exception_on_overflow=False)
            frames.append(data)

            # Show peak
            samples = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
            peak = float(np.max(np.abs(samples)))
            max_peak = max(max_peak, peak)

            # Progress bar
            elapsed = (i + 1) * (chunk / rate)
            remaining = duration - elapsed
            bar_len = int(peak * 30)
            bar = "█" * bar_len + "·" * (30 - bar_len)
            print(f"    [{bar}] {remaining:.1f}s left  peak={peak:.3f}",
                  end="\r", flush=True)

        print()
        print(f"    Recording done. Max peak captured: {max_peak:.3f}")

        stream.stop_stream()
        stream.close()
        audio.terminate()

        if max_peak < 0.01:
            print(f"    ⚠ WARNING: No audio captured (max peak = {max_peak:.3f})")
            print(f"    Mic may not be receiving sound. Check device {device_index}")

        raw = b"".join(frames)
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

        if channels == 2:
            samples = samples.reshape(-1, 2).mean(axis=1)

        if rate != 16000:
            import librosa
            samples = librosa.resample(samples, orig_sr=rate, target_sr=16000)

        return samples, max_peak

    def classify_with_peak_window(samples):
        """
        Instead of averaging across whole recording, find the LOUDEST
        1-second window and analyze THAT.
        
        Why: A snap is 30ms in a 3-second recording. Averaging dilutes it
        to 1% signal. Finding peak window gives us 100% signal in 1 second.
        """
        SR = 16000
        WINDOW_SEC = 1.0
        window_size = int(SR * WINDOW_SEC)
        hop_size = int(SR * 0.1)  # slide by 100ms

        if len(samples) <= window_size:
            # Recording shorter than window, just classify whole thing
            return classifier.classify(samples, sample_rate=SR)

        best_result = None
        best_snap_conf = 0
        best_clap_conf = 0
        best_window_peak = 0

        # Scan through all 1-second windows
        for start in range(0, len(samples) - window_size + 1, hop_size):
            window = samples[start:start + window_size]
            window_peak = float(np.max(np.abs(window)))

            # Skip near-silent windows
            if window_peak < 0.05:
                continue

            result = classifier.classify(window, sample_rate=SR)

            # Track best snap/clap detection
            if result['snap'] > best_snap_conf or result['clap'] > best_clap_conf:
                if result['snap'] > best_snap_conf:
                    best_snap_conf = result['snap']
                if result['clap'] > best_clap_conf:
                    best_clap_conf = result['clap']
                best_result = result
                best_window_peak = window_peak

        # If no loud window found, classify whole thing
        if best_result is None:
            return classifier.classify(samples, sample_rate=SR)

        return best_result

    def run_test(label, expected):
        input(f">>> {label}: press ENTER to start (expected: {expected})")
        samples, max_peak = record_with_countdown(label)

        print(f"    Analyzing with peak-window scan...")
        result = classify_with_peak_window(samples)

        print()
        print(f"    RESULTS FOR: {label}")
        print(f"    ─────────────────────────────────────────")
        print(f"    Max audio peak:   {max_peak:.3f}")
        print(f"    Snap confidence:  {result['snap']*100:5.1f}%")
        print(f"    Clap confidence:  {result['clap']*100:5.1f}%")
        print(f"    Voice confidence: {result['voice']*100:5.1f}%")
        print(f"    Top 5 predictions:")
        for name, conf in result['top_5']:
            marker = "  ⭐" if any(kw in name.lower() for kw in
                                  ["snap", "clap", "hand", "applause"]) else "  "
            print(f"    {marker}{conf*100:5.1f}%  {name}")
        print()
        return result

    input("Press ENTER when ready to start (5 tests total, each has countdown)...")

    r1 = run_test("TEST 1 — SILENCE",       "no sound detected")
    r2 = run_test("TEST 2 — SPEECH",        "high voice confidence")
    r3 = run_test("TEST 3 — SINGLE SNAP",   "high snap confidence")
    r4 = run_test("TEST 4 — SINGLE CLAP",   "high clap confidence")
    r5 = run_test("TEST 5 — MULTIPLE SNAPS","high snap confidence")

    print()
    print("=" * 60)
    print("FINAL VERDICT")
    print("=" * 60)
    print()

    snap_conf = max(r3['snap'], r5['snap'])
    clap_conf = r4['clap']

    print(f"  Best snap confidence:  {snap_conf*100:.1f}%")
    print(f"  Best clap confidence:  {clap_conf*100:.1f}%")
    print(f"  Voice test:            {r2['voice']*100:.1f}% (should be >30%)")
    print(f"  Silence test:          {r1['voice']*100:.1f}% (should be ~0%)")
    print()

    if snap_conf >= 0.40 or clap_conf >= 0.40:
        print(f"  ✓ DETECTION WORKS — build full pipeline")
    elif snap_conf >= 0.15 or clap_conf >= 0.15:
        print(f"  ~ WEAK BUT DETECTABLE — add preprocessing and retest")
    else:
        print(f"  ✗ INSUFFICIENT — YAMNet cannot detect on this mic")

    print()
    import time
    import pyaudio

    # Parse device index from command line
    device_index = 2  # default to OMEN Cam & Voice from previous test
    for i, a in enumerate(sys.argv):
        if a == "--device" and i + 1 < len(sys.argv):
            try:
                device_index = int(sys.argv[i + 1])
            except ValueError:
                pass

    print("=" * 60)
    print("STAGE 1D: YAMNET STANDALONE DETECTION TEST")
    print("=" * 60)
    print()
    print(f"Recording device: {device_index}")
    print()
    print("This test:")
    print("  1. Loads YAMNet (first run downloads 17MB)")
    print("  2. Records 3 seconds of audio")
    print("  3. Runs YAMNet on the recording")
    print("  4. Shows snap/clap confidence + top 5 predictions")
    print()
    print("=" * 60)
    print()

    # Load classifier
    classifier = YAMNetClassifier()

    print()
    print("=" * 60)
    print("READY TO TEST")
    print("=" * 60)
    print()

    def record_and_classify(label):
        """Record 3 seconds and run YAMNet."""
        print(f"\n>>> {label}")
        print("    Recording for 3 seconds... GO NOW!")

        audio = pyaudio.PyAudio()

        try:
            info = audio.get_device_info_by_index(device_index)
            rate = int(info['defaultSampleRate'])
            channels = min(2, int(info['maxInputChannels']))
        except Exception:
            rate = 44100
            channels = 2

        chunk = int(rate * 0.1)  # 100ms chunks
        duration = 3.0

        stream = audio.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=rate,
            input=True,
            frames_per_buffer=chunk,
            input_device_index=device_index,
        )

        frames = []
        num_chunks = int((duration * rate) / chunk)
        for _ in range(num_chunks):
            data = stream.read(chunk, exception_on_overflow=False)
            frames.append(data)

        stream.stop_stream()
        stream.close()
        audio.terminate()

        print("    Recording done. Analyzing...")

        # Convert to numpy
        raw = b"".join(frames)
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

        # Convert to mono if stereo
        if channels == 2:
            samples = samples.reshape(-1, 2).mean(axis=1)

        # Resample to 16kHz if needed (YAMNet requirement)
        if rate != 16000:
            import librosa
            samples = librosa.resample(samples, orig_sr=rate, target_sr=16000)

        # Classify
        result = classifier.classify(samples, sample_rate=16000)

        # Print results
        print()
        print(f"    RESULTS FOR: {label}")
        print(f"    ─────────────────────────────────")
        print(f"    Snap confidence:  {result['snap']*100:5.1f}%")
        print(f"    Clap confidence:  {result['clap']*100:5.1f}%")
        print(f"    Voice confidence: {result['voice']*100:5.1f}%")
        print(f"    Top 5 predictions:")
        for name, conf in result['top_5']:
            print(f"      {conf*100:5.1f}%  {name}")
        print()

        return result

    # Wait for user
    input("Press ENTER when ready to run tests (5 tests total)...")

    print()
    input(">>> TEST 1: Silence — press ENTER, stay silent for 3 seconds")
    r1 = record_and_classify("SILENCE")

    input(">>> TEST 2: Speak normally — press ENTER, talk for 3 seconds")
    r2 = record_and_classify("SPEECH")

    input(">>> TEST 3: Snap once — press ENTER, snap fingers once")
    r3 = record_and_classify("SINGLE SNAP")

    input(">>> TEST 4: Clap once — press ENTER, clap once")
    r4 = record_and_classify("SINGLE CLAP")

    input(">>> TEST 5: Multiple snaps — press ENTER, snap 3 times fast")
    r5 = record_and_classify("MULTIPLE SNAPS")

    # Verdict
    print()
    print("=" * 60)
    print("VERDICT")
    print("=" * 60)
    print()

    snap_conf = max(r3['snap'], r5['snap'])
    clap_conf = r4['clap']

    if snap_conf >= 0.60:
        print(f"  ✓ SNAP DETECTED at {snap_conf*100:.1f}% confidence")
        print(f"    YAMNet works well for snap detection on your mic")
    elif snap_conf >= 0.30:
        print(f"  ~ SNAP DETECTED at {snap_conf*100:.1f}% confidence (marginal)")
        print(f"    YAMNet detects it but we need to lower threshold or add preprocessing")
    else:
        print(f"  ✗ SNAP NOT DETECTED (only {snap_conf*100:.1f}% confidence)")
        print(f"    YAMNet cannot reliably detect snaps on this mic")

    print()
    if clap_conf >= 0.60:
        print(f"  ✓ CLAP DETECTED at {clap_conf*100:.1f}% confidence")
    elif clap_conf >= 0.30:
        print(f"  ~ CLAP DETECTED at {clap_conf*100:.1f}% confidence (marginal)")
    else:
        print(f"  ✗ CLAP NOT DETECTED (only {clap_conf*100:.1f}% confidence)")

    print()
    print(f"  Voice test (should be HIGH):    {r2['voice']*100:.1f}%")
    print(f"  Silence test (should be LOW):   {r1['voice']*100:.1f}% voice")
    print()
    print("=" * 60)
    print("DECISION MATRIX")
    print("=" * 60)
    print()

    if snap_conf >= 0.60 or clap_conf >= 0.60:
        print("  ✓ CONTINUE with full ML pipeline (Stage 1E → 1G)")
    elif snap_conf >= 0.30 and clap_conf >= 0.30:
        print("  ~ MARGINAL — add RNNoise preprocessing, retest")
    else:
        print("  ✗ INSUFFICIENT — YAMNet cannot detect on this mic")
        print("     Recommend: ship without audio triggers, use hotkeys instead")

    print()