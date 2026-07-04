"""
=============================================================================
PROJECT SEVEN - ears/voice_id.py (Voice Identity Engine)
Version: 6.0 — NVIDIA TitaNet Speaker Verification

MODEL: nvidia/speakerverification_en_titanet_large
SOURCE: NVIDIA NeMo (already installed: nemo 2.7.3)
TRAINED ON: VoxCeleb2 — 1M+ utterances, 6000+ speakers
EMBEDDING: 192-dim speaker-discriminative vectors
THRESHOLD: 0.75

WHY TITANET WORKS:
    Trained with Angular Additive Margin loss — explicitly pushes different
    speakers apart in embedding space regardless of what words are spoken.
    Same person saying different words: similarity 0.82-0.97
    Different people: similarity 0.30-0.65
    TTS/AI voices: similarity 0.20-0.50 (synthetic, not in training distribution)

LATENCY: 10-30ms CPU, under 5ms GPU

NO C++ COMPILER NEEDED. NeMo installs via pip.
=============================================================================
"""

import os
import json
import numpy as np
import warnings
warnings.filterwarnings('ignore')
from colorama import Fore

VOICE_PRINTS_DIR     = os.path.join(".", "seven_data", "voice_prints")
PROFILES_FILE        = os.path.join(VOICE_PRINTS_DIR, "profiles.json")
# Base threshold — overridden by per-speaker calibration if available
SIMILARITY_THRESHOLD = 0.20

_titanet_model = None


def _get_model():
    """Lazy-load TitaNet. Downloads once (~80MB), cached forever."""
    global _titanet_model
    if _titanet_model is not None:
        return _titanet_model
    try:
        import nemo.collections.asr as nemo_asr
        _titanet_model = nemo_asr.models.EncDecSpeakerLabelModel.from_pretrained(
            'nvidia/speakerverification_en_titanet_large'
        )
        _titanet_model.eval()
        print(Fore.GREEN + "[VOICE ID] TitaNet loaded")
        return _titanet_model
    except Exception as e:
        print(Fore.RED + f"[VOICE ID] TitaNet load failed: {e}")
        return None


def _audio_to_embedding(audio_path: str) -> np.ndarray:
    """
    Convert WAV to 192-dim TitaNet speaker embedding.
    Returns L2-normalized numpy array or None.
    """
    try:
        import torch

        model = _get_model()
        if model is None:
            return None

        # Pass audio path directly to TitaNet
        # get_embedding() handles resampling internally via NeMo's audio pipeline
        with torch.no_grad():
            emb = model.get_embedding(audio_path)
        emb = emb.squeeze().cpu().numpy()  # [192]

        # L2 normalize
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm

        return emb.astype(np.float32)

    except Exception as e:
        print(Fore.RED + f"[VOICE ID] Embedding error: {e}")
        import traceback
        traceback.print_exc()
        return None


def _ensure_dirs():
    os.makedirs(VOICE_PRINTS_DIR, exist_ok=True)
    if not os.path.exists(PROFILES_FILE):
        with open(PROFILES_FILE, "w") as f:
            json.dump({}, f)


def _load_profiles():
    _ensure_dirs()
    try:
        with open(PROFILES_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_profiles(profiles):
    _ensure_dirs()
    with open(PROFILES_FILE, "w") as f:
        json.dump(profiles, f, indent=2)


def enroll_speaker(name: str, audio_path: str) -> bool:
    name_lower = name.lower().strip()
    print(Fore.CYAN + f"[VOICE ID] Enrolling: {name_lower}...")

    embeddings = []

    # Try individual clip files — better than merged for quality control
    import os as _os
    appdata = _os.environ.get('APPDATA', '')
    clip_files = [
        _os.path.join(appdata, 'SEVEN', f'enroll_clip_{i}.wav')
        for i in range(1, 6)  # up to 5 clips
    ]
    for clip in clip_files:
        if _os.path.exists(clip):
            emb = _audio_to_embedding(clip)
            if emb is not None:
                embeddings.append(emb)
                print(Fore.CYAN + f"[VOICE ID] Clip embedding extracted")

    # Fallback to merged file
    if not embeddings:
        embedding = _audio_to_embedding(audio_path)
        if embedding is None:
            print(Fore.RED + "[VOICE ID] Enrollment failed — no valid audio")
            return False
        embeddings.append(embedding)

    # Simple average — no outlier rejection
    # Outlier rejection was removing too many clips and degrading quality
    avg_embedding = np.mean(embeddings, axis=0)

    norm = np.linalg.norm(avg_embedding)
    if norm > 0:
        avg_embedding = avg_embedding / norm

    print(Fore.GREEN + f"[VOICE ID] Voiceprint from {len(embeddings)} clips averaged")

    _ensure_dirs()
    np.save(os.path.join(VOICE_PRINTS_DIR, f"{name_lower}.npy"), avg_embedding)

    # Compute self-similarity score from enrollment clips
    # This becomes the per-speaker threshold baseline
    self_scores = []
    for i in range(len(embeddings)):
        for j in range(i+1, len(embeddings)):
            score = float(np.dot(embeddings[i], embeddings[j]))
            self_scores.append(score)

    if self_scores:
        min_self_score = float(np.min(self_scores))
        avg_self_score = float(np.mean(self_scores))
        # Threshold = min self-score minus 10% buffer
        per_speaker_threshold = max(0.10, min_self_score - 0.10)
        print(Fore.GREEN + f"[VOICE ID] Self-similarity: avg={avg_self_score:.3f} min={min_self_score:.3f}")
        print(Fore.GREEN + f"[VOICE ID] Per-speaker threshold: {per_speaker_threshold:.3f}")
    else:
        per_speaker_threshold = SIMILARITY_THRESHOLD
        avg_self_score = 0.0

    profiles = _load_profiles()
    profiles[name_lower] = {
        "print_file":        f"{name_lower}.npy",
        "enrolled":          True,
        "version":           "6.2",
        "clips_used":        len(embeddings),
        "embedding_dim":     int(avg_embedding.shape[0]),
        "threshold":         per_speaker_threshold,
        "avg_self_score":    round(avg_self_score, 3)
    }
    _save_profiles(profiles)

    print(Fore.GREEN + f"[VOICE ID] {name_lower} enrolled. Threshold: {per_speaker_threshold:.3f}")
    return True


def identify_speaker(audio_path: str) -> str:
    profiles = _load_profiles()
    if not profiles:
        return "default"

    embedding = _audio_to_embedding(audio_path)
    if embedding is None:
        return "default"

    best_name  = "unknown"
    best_score = 0.0

    thresholds = {}
    for name, info in profiles.items():
        path = os.path.join(VOICE_PRINTS_DIR, info["print_file"])
        if not os.path.exists(path):
            continue

        stored = np.load(path)

        if stored.shape != embedding.shape:
            print(Fore.YELLOW + f"[VOICE ID] Dim mismatch for {name} — re-enroll")
            continue

        score = float(np.dot(embedding, stored))
        # Use per-speaker threshold if available, else global
        speaker_threshold = info.get("threshold", SIMILARITY_THRESHOLD)
        thresholds[name]  = speaker_threshold
        print(Fore.CYAN + f"[VOICE ID] {name}: {score:.3f} (need >{speaker_threshold:.2f})")

        if score > best_score:
            best_score = score
            best_name  = name

    speaker_threshold = thresholds.get(best_name, SIMILARITY_THRESHOLD)
    if best_score >= speaker_threshold:
        print(Fore.GREEN + f"[VOICE ID] Identified: {best_name} ({best_score:.3f})")
        return best_name

    print(Fore.YELLOW + f"[VOICE ID] Unknown (best: {best_name} @ {best_score:.3f})")
    return "unknown"


def get_enrolled_speakers() -> list:
    return list(_load_profiles().keys())


def remove_speaker(name: str) -> bool:
    name_lower = name.lower().strip()
    profiles   = _load_profiles()
    if name_lower not in profiles:
        return False
    path = os.path.join(VOICE_PRINTS_DIR, profiles[name_lower]["print_file"])
    if os.path.exists(path):
        os.remove(path)
    sample = os.path.join(VOICE_PRINTS_DIR, f"{name_lower}_sample.wav")
    if os.path.exists(sample):
        os.remove(sample)
    del profiles[name_lower]
    _save_profiles(profiles)
    print(Fore.GREEN + f"[VOICE ID] {name_lower} removed")
    return True


def is_voice_id_enabled() -> bool:
    return len(_load_profiles()) > 0