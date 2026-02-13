"""
=============================================================================
PROJECT SEVEN - ears/voice_id.py (Voice Identity Engine)
Version: 1.2

PURPOSE:
    Identifies WHO is speaking by comparing voice against stored prints.
    Uses resemblyzer (CPU only, 17MB model, no VRAM impact).

HOW IT WORKS:
    1. ENROLLMENT: User speaks for 5-10 seconds
       → Audio converted to 256-number voice vector (embedding)
       → Vector saved to seven_data/voice_prints/name.npy

    2. IDENTIFICATION: Every time someone speaks
       → Audio converted to voice vector
       → Compared against ALL stored voice prints
       → Closest match above threshold = identified speaker
       → Below threshold = "unknown" speaker

    3. SIMILARITY: Cosine similarity between vectors
       → 1.0 = identical voice
       → 0.85+ = same person (our threshold)
       → Below 0.85 = different person or unknown

STORAGE: seven_data/voice_prints/
=============================================================================
"""

import os
import json
import numpy as np
from colorama import Fore

# Paths
VOICE_PRINTS_DIR = "./seven_data/voice_prints"
PROFILES_FILE = os.path.join(VOICE_PRINTS_DIR, "profiles.json")

# Similarity threshold — above this = same person
# 0.85 is a good balance between accuracy and flexibility
# Lower = more false positives (wrong person identified)
# Higher = more false negatives (correct person not recognized)
SIMILARITY_THRESHOLD = 0.82

# Lazy-load resemblyzer (only when voice ID is actually used)
_encoder = None


def _get_encoder():
    """Lazy-load the voice encoder. Only loads once."""
    global _encoder
    if _encoder is None:
        print(Fore.CYAN + "[VOICE ID] Loading speaker encoder model (first time may download ~17MB)...")
        from resemblyzer import VoiceEncoder
        _encoder = VoiceEncoder()
        print(Fore.GREEN + "[VOICE ID] Speaker encoder loaded.")
    return _encoder


def _ensure_dirs():
    """Create voice prints directory if it doesn't exist."""
    os.makedirs(VOICE_PRINTS_DIR, exist_ok=True)
    if not os.path.exists(PROFILES_FILE):
        with open(PROFILES_FILE, "w") as f:
            json.dump({}, f)


def _load_profiles():
    """Load speaker profiles mapping."""
    _ensure_dirs()
    try:
        with open(PROFILES_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def _save_profiles(profiles):
    """Save speaker profiles mapping."""
    _ensure_dirs()
    with open(PROFILES_FILE, "w") as f:
        json.dump(profiles, f, indent=2)


def _audio_to_embedding(audio_path):
    """
    Convert an audio file to a voice embedding vector.

    Args:
        audio_path: Path to .wav file

    Returns:
        numpy array of shape (256,) or None if failed
    """
    try:
        from resemblyzer import preprocess_wav
        encoder = _get_encoder()

        wav = preprocess_wav(audio_path)

        # Need at least 1 second of audio for reliable embedding
        if len(wav) < 16000:
            print(Fore.YELLOW + "[VOICE ID] Audio too short for voice identification.")
            return None

        embedding = encoder.embed_utterance(wav)
        return embedding

    except Exception as e:
        print(Fore.RED + f"[VOICE ID] Error processing audio: {e}")
        return None


def enroll_speaker(name, audio_path):
    """
    Enroll a new speaker by creating their voice print.

    Args:
        name: Speaker's name (e.g., "mani", "guest")
        audio_path: Path to .wav file of them speaking

    Returns:
        bool: True if enrollment succeeded
    """
    name_lower = name.lower().strip()
    print(Fore.CYAN + f"[VOICE ID] Enrolling speaker: {name_lower}...")

    embedding = _audio_to_embedding(audio_path)
    if embedding is None:
        print(Fore.RED + f"[VOICE ID] Enrollment failed for {name_lower}.")
        return False

    # Save voice print as numpy file
    _ensure_dirs()
    print_path = os.path.join(VOICE_PRINTS_DIR, f"{name_lower}.npy")
    np.save(print_path, embedding)

    # Update profiles
    profiles = _load_profiles()
    profiles[name_lower] = {
        "print_file": f"{name_lower}.npy",
        "enrolled": True
    }
    _save_profiles(profiles)

    print(Fore.GREEN + f"[VOICE ID] ✅ Speaker '{name_lower}' enrolled successfully.")
    return True


def identify_speaker(audio_path):
    """
    Identify who is speaking by comparing against stored voice prints.

    Args:
        audio_path: Path to .wav file to identify

    Returns:
        str: Speaker name (e.g., "mani") or "unknown"
    """
    profiles = _load_profiles()

    # No profiles enrolled yet
    if not profiles:
        return "default"

    # Get embedding for current audio
    current_embedding = _audio_to_embedding(audio_path)
    if current_embedding is None:
        return "default"

    best_match = "unknown"
    best_score = 0.0

    for name, info in profiles.items():
        print_path = os.path.join(VOICE_PRINTS_DIR, info["print_file"])

        if not os.path.exists(print_path):
            continue

        # Load stored voice print
        stored_embedding = np.load(print_path)

        # Cosine similarity
        similarity = np.dot(current_embedding, stored_embedding) / (
            np.linalg.norm(current_embedding) * np.linalg.norm(stored_embedding)
        )

        print(Fore.CYAN + f"[VOICE ID] {name}: similarity = {similarity:.3f}")

        if similarity > best_score:
            best_score = similarity
            best_match = name

    # Check if best match meets threshold
    if best_score >= SIMILARITY_THRESHOLD:
        print(Fore.GREEN + f"[VOICE ID] Identified: {best_match} (score: {best_score:.3f})")
        return best_match
    else:
        print(Fore.YELLOW + f"[VOICE ID] Unknown speaker (best: {best_match} at {best_score:.3f})")
        return "unknown"


def get_enrolled_speakers():
    """Return list of enrolled speaker names."""
    profiles = _load_profiles()
    return list(profiles.keys())


def remove_speaker(name):
    """Remove a speaker's voice print."""
    name_lower = name.lower().strip()
    profiles = _load_profiles()

    if name_lower not in profiles:
        print(Fore.YELLOW + f"[VOICE ID] Speaker '{name_lower}' not found.")
        return False

    # Delete voice print file
    print_path = os.path.join(VOICE_PRINTS_DIR, profiles[name_lower]["print_file"])
    if os.path.exists(print_path):
        os.remove(print_path)

    # Remove from profiles
    del profiles[name_lower]
    _save_profiles(profiles)

    print(Fore.GREEN + f"[VOICE ID] Speaker '{name_lower}' removed.")
    return True


def is_voice_id_enabled():
    """Check if any speakers are enrolled (voice ID is active)."""
    profiles = _load_profiles()
    return len(profiles) > 0