"""
=============================================================================
PROJECT SEVEN - ears/core.py (The Listener)
Version: 2.0 — Clean Signal Pipeline

WHAT CHANGED FROM 1.3:
    1. Removed adjust_for_ambient_noise — conflicted with adaptive floor
    2. Removed initial_prompt from Whisper — was teaching it to hallucinate
    3. Tightened Whisper confidence thresholds — no_speech 0.6->0.7, logprob -0.7->-0.5
    4. Tightened Silero VAD threshold 0.4->0.5
    5. Lowered crest factor minimum 3.5->2.2 — was blocking quiet/distant voices
    6. Raised phrase_time_limit 7->15 seconds — was cutting off natural speech
    7. Removed word count cap (>18) — was silently dropping real input
    8. Removed valid starters filter — was blocking natural conversation
    9. Removed passive voice filter — was blocking real phrases
    10. Removed narration filter — was blocking real questions
    11. Removed trailing-off filter — was blocking real sentences
    12. Cleaned ghost filter — removed real words (alright, yes, no)
    13. Cleaned forbidden list — removed patterns that match real speech
    14. Raised filler ratio threshold 0.75->0.85, minimum 4->6 words
=============================================================================
"""

import speech_recognition as sr
import os
import re
import io
import json
import wave
import threading
import numpy as np
import colorama
from colorama import Fore

# Compatibility shim: numpy.iterable was removed in numpy 2.0.
# faster-whisper 1.x calls numpy.iterable internally.
# If the runtime numpy is 2.x (e.g. in embedded Python environment),
# patch it back in before WhisperModel loads.
if not hasattr(np, 'iterable'):
    np.iterable = lambda obj: hasattr(obj, '__iter__')

from faster_whisper import WhisperModel

colorama.init(autoreset=True)


def _get_configured_whisper_model() -> str:
    """
    Read Whisper model size from config.json, set via Settings > Voice >
    Speech Recognition. Falls back to medium.en for installs that have
    not touched this setting yet, matching the previous fixed default.
    """
    try:
        _cfg_path = os.path.join(
            os.environ.get('APPDATA', os.path.expanduser('~')),
            'SEVEN', 'config.json'
        )
        if os.path.exists(_cfg_path):
            with open(_cfg_path, 'r', encoding='utf-8') as _f:
                _cfg = json.load(_f)
            _model = _cfg.get('brain', {}).get('whisper_model', '').strip()
            if _model:
                return _model
    except Exception:
        pass
    return "medium.en"


MODEL_SIZE      = _get_configured_whisper_model()
AUDIO_TEMP_PATH = "temp_audio.wav"

# External interrupt flag — set True to make listen() return immediately
_force_return = False

def set_force_return(val: bool):
    global _force_return
    _force_return = val


# =============================================================================
# WHISPER MODEL LOADER
# =============================================================================

def _load_whisper_model(model_size: str) -> WhisperModel:
    try:
        import torch
        if torch.cuda.is_available():
            _device_name = torch.cuda.get_device_name(0)
            print(Fore.CYAN + f"[EARS] GPU detected: {_device_name}")
            model = WhisperModel(model_size, device="cuda", compute_type="float16")
            print(Fore.GREEN + f"[EARS] Whisper loaded on GPU (CUDA) ✓ — expect <0.3s transcription")
            return model
        else:
            print(Fore.YELLOW + "[EARS] CUDA not available — falling back to CPU")
    except Exception as e:
        print(Fore.YELLOW + f"[EARS] GPU load failed ({e}) — falling back to CPU")

    try:
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        print(Fore.YELLOW + f"[EARS] Whisper loaded on CPU — transcription will be slower")
        return model
    except Exception as e:
        print(Fore.RED + f"[EARS] CPU load also failed: {e}")
        raise


print(Fore.CYAN + f"[EARS] Loading Whisper Model ({MODEL_SIZE})...")
audio_model = _load_whisper_model(MODEL_SIZE)


# =============================================================================
# ADAPTIVE NOISE FLOOR
#
# HOW IT WORKS:
#   1. At startup: record 1.5 seconds of silence, measure RMS, set baseline
#   2. Every rejected clip feeds its RMS into a rolling 20-sample average
#   3. Threshold = rolling_average x MULTIPLIER (2.2)
#   4. Environment gets louder: threshold rises naturally
#   5. Fan turns off: next clips are quieter, average drops, threshold drops
#   6. Hard cap at 500 prevents runaway from music or TV bleed
# =============================================================================

_noise_floor     = 0.0
_noise_samples   = []
_NOISE_WINDOW    = 20
_MULTIPLIER      = 2.2
_MIN_CREST       = 2.2   # lowered from 3.5 — quiet voices and laptop mics dip below 3.5
_MIN_DURATION    = 0.4   # minimum speech duration in seconds
_floor_lock      = threading.Lock()
_initial_floor   = 0.0
_NOISE_FLOOR_CAP = 500


def _update_noise_floor(rms: float):
    global _noise_floor, _noise_samples
    with _floor_lock:
        _noise_samples.append(rms)
        if len(_noise_samples) > _NOISE_WINDOW:
            _noise_samples.pop(0)
        prev         = _noise_floor
        new_floor    = sum(_noise_samples) / len(_noise_samples)
        _noise_floor = min(new_floor, _NOISE_FLOOR_CAP)
        if prev > 0 and abs(_noise_floor - prev) / prev > 0.20:
            print(Fore.CYAN + f"[EARS] Noise floor adjusted: {prev * _MULTIPLIER:.0f} -> {_noise_floor * _MULTIPLIER:.0f}")


def _get_threshold() -> float:
    with _floor_lock:
        if _noise_floor == 0:
            return 300
        return _noise_floor * _MULTIPLIER


# =============================================================================
# NOISE FLOOR DECAY — recovers from "stuck high" threshold
#
# PROBLEM:
#   The noise floor only lowers when a clip is captured AND rejected.
#   If a loud environment pushes the floor way up, and the room then goes
#   quiet, nothing quiet enough ever crosses the new high threshold again —
#   so there is never another sample to lower the average with. The floor
#   gets stuck high forever until Seven is restarted.
#
# FIX:
#   Every time listen() times out with zero audio, count it. After a few
#   consecutive silent timeouts, ease the floor down a step. Any real
#   captured audio resets the counter, since that proves the mic still
#   works fine at the current threshold.
# =============================================================================

_consecutive_timeouts  = 0
_timeout_lock          = threading.Lock()
_DECAY_AFTER_TIMEOUTS  = 3      # roughly 30s of total silence at 10s per timeout
_DECAY_FACTOR          = 0.85
_MIN_NOISE_FLOOR       = 50.0


def _decay_noise_floor():
    global _noise_floor, _consecutive_timeouts
    with _timeout_lock:
        _consecutive_timeouts += 1
        if _consecutive_timeouts >= _DECAY_AFTER_TIMEOUTS:
            with _floor_lock:
                if _noise_floor > _MIN_NOISE_FLOOR:
                    old_thresh   = _noise_floor * _MULTIPLIER
                    _noise_floor = max(_MIN_NOISE_FLOOR, _noise_floor * _DECAY_FACTOR)
                    print(Fore.CYAN + f"[EARS] Quiet for a while — easing threshold: {old_thresh:.0f} -> {_noise_floor * _MULTIPLIER:.0f}")
            _consecutive_timeouts = 0


def _reset_timeout_counter():
    global _consecutive_timeouts
    with _timeout_lock:
        _consecutive_timeouts = 0


def _do_initial_calibration():
    global _noise_samples, _noise_floor, _initial_floor
    try:
        _r = sr.Recognizer()
        with sr.Microphone() as _src:
            print(Fore.CYAN + "[EARS] Calibrating ambient noise — 1.5 seconds, stay quiet...")
            _audio = _r.record(_src, duration=1.5)
            _wav   = _audio.get_wav_data()
            with wave.open(io.BytesIO(_wav), 'rb') as _cwf:
                _pcm = _cwf.readframes(_cwf.getnframes())
            _arr   = np.frombuffer(_pcm, dtype=np.int16).astype(np.float32)
            _rms   = float(np.sqrt(np.mean(_arr ** 2)))
            with _floor_lock:
                _noise_samples = [_rms] * 5
                _noise_floor   = _rms
                _initial_floor = _rms
            print(Fore.GREEN + f"[EARS] Noise floor: {_rms:.0f} | Voice threshold: {_rms * _MULTIPLIER:.0f}")
    except Exception as e:
        print(Fore.YELLOW + f"[EARS] Calibration failed: {e} — using default")
        with _floor_lock:
            _noise_samples = [136.0] * 5
            _noise_floor   = 136.0
            _initial_floor = 136.0


_do_initial_calibration()


# =============================================================================
# SIGNAL QUALITY CHECK
#
# Three gates before Whisper even runs:
#   Gate 1 — RMS energy: is there enough sound energy to be speech?
#   Gate 2 — Duration: is the clip long enough to be a word?
#   Gate 3 — Crest factor: is the sound shaped like speech (spiky) vs noise (flat)?
#
# Noise (fan, AC, hum) is flat — low crest factor.
# Speech is spiky — consonants create sharp peaks relative to average.
# This is the most reliable hardware-level filter before any AI runs.
# =============================================================================

def _check_signal_quality(wav_data: bytes) -> tuple:
    """
    Check if audio signal looks like speech before sending to Whisper.

    Returns:
        (passed: bool, rms: float, reason: str)
    """
    try:
        with wave.open(io.BytesIO(wav_data), 'rb') as _wf:
            _sample_rate = _wf.getframerate()
            _pcm_raw     = _wf.readframes(_wf.getnframes())
        audio_np  = np.frombuffer(_pcm_raw, dtype=np.int16).astype(np.float32)
        rms       = float(np.sqrt(np.mean(audio_np ** 2)))
        peak      = float(np.max(np.abs(audio_np)))
        dur       = len(audio_np) / float(_sample_rate)
        threshold = _get_threshold()

        # Gate 1: energy
        if rms < threshold:
            return False, rms, f"RMS {rms:.0f} < threshold {threshold:.0f} — below noise floor"

        # Gate 2: duration
        if dur < _MIN_DURATION:
            return False, rms, f"Duration {dur:.2f}s < {_MIN_DURATION}s — too short"

        # Gate 3: crest factor
        crest = peak / rms if rms > 0 else 0
        if crest < _MIN_CREST:
            return False, rms, f"Crest {crest:.2f} < {_MIN_CREST} — diffuse noise not speech"

        print(Fore.CYAN + f"[EARS] Signal OK — RMS:{rms:.0f} Crest:{crest:.2f} Dur:{dur:.2f}s Thresh:{threshold:.0f}")
        return True, rms, "ok"

    except Exception as e:
        # If signal check fails, let Whisper decide
        print(Fore.YELLOW + f"[EARS] Signal check error: {e} — passing to Whisper")
        return True, 0.0, "check_failed"


# =============================================================================
# WHISPER OUTPUT FILTER
#
# Only filters things Whisper hallucinates from silence or near-silence.
# Does NOT filter real speech patterns.
# Does NOT filter by word count.
# Does NOT filter by sentence structure.
# Does NOT filter by what word the sentence starts with.
# =============================================================================

# Exact phrases Whisper generates from silence — verified hallucinations
_SILENCE_HALLUCINATIONS = {
    "thank you", "thanks", "you",
    "bye", "goodbye",
    "the", "a", "i",
    "so", "and", "or", "but",
    "hmm", "hm", "uh", "um", "ah", "oh",
    "music", "applause", "laughter",
    "subtitles", "caption", "captions",
    "subscribe", "like and subscribe",
    "thanks for watching", "thank you for watching",
    "thank you so much for watching", "thank you very much for having me",
    "thanks so much for watching", "thanks very much for having me",
    "thank you so much", "thanks so much",
    "see you next time", "see you in the next video",
    "i'll see you", "see you soon", "see you later",
    "have a great day", "have a good day", "have a good one",
    "take care", "take care everyone", "take care guys",
    "good luck", "good luck everyone",
    "that's all", "thats all", "that's it", "thats it",
    "and that's it", "and thats it",
    "i hope you enjoyed", "hope you enjoyed",
    "if you have any questions", "feel free to",
    "don't forget", "dont forget",
    "please like", "please subscribe",
    "hit the bell", "notification bell",
    "peace out", "peace", "later guys", "later",
    "cheerio", "cheers everyone", "cheers guys",
    "see you in my next video", "see you guys in the next video",
    "see you in the next one", "see you next week",
    "we'll see you next time", "well see you next time",
    "ill see you in the next video", "i will see you in the next video",
    "i'll see you in the next video", "i'll see you next time",
    "don't forget to like and subscribe", "dont forget to like and subscribe",
    "like comment and subscribe", "hit the like button",
    "have a great day", "have a good day", "take care",
    "peace", "peace out", "later", "later guys",
    "that's all for today", "thats all for today",
    "thanks for watching guys", "thank you for watching guys",
    "welcome back", "welcome back to", "welcome to my channel",
    "bada ba ba ba", "ba ba ba", "da da da", "la la la",
    ".", "..", "...", " ", "",
}

# Substring patterns that only appear in Whisper hallucinations, never in real voice commands
_HALLUCINATION_SUBSTRINGS = [
    # These patterns ONLY appear in Whisper hallucinations
    # They are never part of real voice assistant commands
    "amara.org",
    "mooji.org",
    "www.",
    ".org",
    "bada ba",
    "ba ba ba ba",
    "da da da da",
    "la la la la",
    # YouTube-specific endings — only reject if the full YouTube phrase is present
    "next video",
    "my channel",
    "in this video",
    "in today's video",
    "in todays video",
    "like and subscribe",
    "smash that like",
    "hit the like button",
    "notification bell",
    "hit the bell",
    "please subscribe",
    "leave a comment below",
    "drop a comment below",
]

# Filler words — used only for ratio check, not for filtering themselves
_FILLER_WORDS = {
    "the", "a", "an", "is", "it", "to", "of", "and", "or", "but",
    "in", "on", "at", "for", "well", "so", "that", "this", "what",
    "i", "you", "he", "she", "they", "we", "my", "your", "his", "her",
    "up", "with", "be", "are", "was", "do", "did", "have", "has",
}


def _detect_repetition_loop(clean: str) -> bool:
    """
    Detect Whisper's hallucination pattern of repeating phrases.

    When Whisper cannot understand audio clearly, it loops the same
    phrase. Example: "I don't know what to say I don't know what to say"

    Method: split text into overlapping chunks of 4 words.
    If any 4-word chunk appears more than once, it is a loop.

    Returns True if repetition loop detected.
    """
    words = clean.split()
    if len(words) < 8:
        return False

    # Build 4-word chunks
    chunk_size = 4
    chunks = []
    for i in range(len(words) - chunk_size + 1):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)

    # If any chunk appears more than once, it is a repetition loop
    seen = set()
    for chunk in chunks:
        if chunk in seen:
            return True
        seen.add(chunk)

    return False


def _is_incoherent(clean: str) -> bool:
    """
    Detect semantically incoherent transcriptions.

    Whisper sometimes produces word salad from background noise.
    Example: "on a new place of time week"

    Two checks:
    1. Preposition density — incoherent text has abnormally high
       preposition density because Whisper fills gaps with connectors.
    2. No recognizable content word — if there are zero content words
       from common English vocabulary in a 5+ word phrase, it is noise.

    Only runs on clips 5+ words. Short clips cannot be judged this way.

    Returns True if text appears incoherent.
    """
    words = clean.split()
    if len(words) < 5:
        return False

    # Common prepositions and connectors — high density = word salad
    _connectors = {
        "a", "an", "the", "of", "in", "on", "at", "to", "for",
        "with", "by", "from", "up", "about", "into", "through",
        "during", "before", "after", "above", "below", "between",
        "out", "off", "over", "under", "again", "then", "once",
        "new", "place", "time", "way", "part", "just", "also",
    }

    # Minimum vocabulary — words that indicate real human intent
    # If NONE of these appear in a 5+ word clip, it is noise
    _real_intent_words = {
        "open", "close", "play", "stop", "set", "show", "find",
        "what", "how", "why", "when", "where", "who", "which",
        "remind", "schedule", "volume", "brightness", "search",
        "weather", "timer", "alarm", "task", "memory", "tell",
        "seven", "hey", "hello", "yes", "no", "help", "know",
        "name", "do", "can", "will", "would", "could", "should",
        "like", "want", "need", "make", "go", "get", "see", "say",
        "think", "feel", "have", "had", "work", "day", "today",
        "good", "bad", "great", "okay", "sure", "well", "right",
        "chrome", "spotify", "notepad", "browser", "file", "folder",
    }

    connector_count = sum(1 for w in words if w in _connectors)
    connector_ratio = connector_count / len(words)

    # More than 70% connectors with no real intent word = incoherent
    has_intent = any(w in _real_intent_words for w in words)
    if connector_ratio > 0.70 and not has_intent:
        return True

    return False


def _is_hallucination(clean: str, raw_lower: str = "") -> tuple:
    """
    Check if Whisper output is a known hallucination.

    Args:
        clean:     lowercased text with punctuation stripped
        raw_lower: lowercased text with punctuation intact — needed because
                   some hallucination patterns (like "www." or ".org") only
                   match when the period is still present

    Returns:
        (is_hallucination: bool, reason: str)
    """
    # Exact match against known silence outputs
    if clean in _SILENCE_HALLUCINATIONS:
        return True, f"silence hallucination: '{clean}'"

    # Outro hallucinations
    # Whisper often invents these from silence or TV/audio bleed
    if clean.startswith(("thank you", "thanks")):
        if any(k in clean for k in (
            "watching", "having me", "joining", "listening",
            "for me", "for watching", "for having me"
        )):
            return True, f"outro hallucination: '{clean}'"

    # Substring match — checked against punctuation-preserved text so
    # patterns like "www." and ".org" can actually match
    _check_text = raw_lower if raw_lower else clean
    for pattern in _HALLUCINATION_SUBSTRINGS:
        if pattern in _check_text:
            return True, f"hallucination pattern: '{pattern}'"

    words = clean.split()

    # Repeated single syllable — "ba ba ba", "da da da"
    if len(words) >= 3:
        unique = set(words)
        if len(unique) == 1 and len(list(unique)[0]) <= 3:
            return True, f"repeated syllable: '{clean}'"

    # Extremely high filler ratio — only for 6+ word clips
    # 0.85 threshold: 85% of words must be pure filler to reject
    # Real sentences like "what is the weather" pass (50% filler)
    # Pure filler noise like "the the the and the and" fails (100%)
    if len(words) >= 6:
        content_words = [w for w in words if w not in _FILLER_WORDS]
        filler_ratio  = 1 - (len(content_words) / len(words))
        if filler_ratio > 0.85:
            return True, f"pure filler ({filler_ratio:.0%}): '{clean}'"

    return False, ""


# =============================================================================
# MAIN LISTEN FUNCTION
# =============================================================================

def listen():
    """
    Listen for speech and return transcribed text.

    Signal pipeline:
        Microphone -> SpeechRecognition energy gate -> WAV
        -> RMS gate -> Duration gate -> Crest gate
        -> Whisper (model set in config, VAD enabled)
        -> Confidence filter -> Hallucination filter
        -> Autocorrect -> Return

    Returns:
        (transcribed_text: str, audio_path: str) on success
        (None, None) on silence, noise, or hallucination
    """
    print(Fore.WHITE + "[EARS] ── Waiting for audio...")
    recognizer = sr.Recognizer()

    try:
        mic = sr.Microphone()
    except Exception as _mic_err:
        print(Fore.YELLOW + f"[EARS] Microphone init failed: {_mic_err}")
        import time as _t
        _t.sleep(2)
        return None, None

    try:
        with mic as source:
            # Do NOT call adjust_for_ambient_noise here.
            # Our adaptive floor is more accurate and does not conflict.
            recognizer.dynamic_energy_threshold = False
            recognizer.energy_threshold         = _get_threshold()
            recognizer.pause_threshold          = 0.8
            recognizer.non_speaking_duration    = 0.4
            recognizer.phrase_threshold         = 0.1

            if _force_return:
                recognizer.energy_threshold = 50
                _listen_timeout = 1.5
                _phrase_limit   = 1
            else:
                _listen_timeout = 10  # bounded — was None (infinite block), which
                                       # made it impossible for the noise floor to
                                       # ever decay back down after a loud environment
                _phrase_limit   = 15  # raised from 7 — natural speech can be 10-12 seconds

            try:
                print(Fore.WHITE + f"[EARS] ── Listening... (energy_threshold={recognizer.energy_threshold:.0f})")
                audio    = recognizer.listen(
                    source,
                    timeout=_listen_timeout,
                    phrase_time_limit=_phrase_limit
                )
                wav_data = audio.get_wav_data()
                print(Fore.WHITE + f"[EARS] ── Audio captured ({len(wav_data)} bytes)")
                _reset_timeout_counter()

            except sr.WaitTimeoutError:
                _decay_noise_floor()
                return None, None
            except OSError as _ose:
                print(Fore.YELLOW + f"[EARS] Microphone disconnected: {_ose}")
                import time as _t
                _t.sleep(1)
                return None, None
            except Exception:
                return None, None

            # ── Gate 1/2/3: Signal quality before Whisper ─────────────────
            print(Fore.WHITE + "[EARS] ── Running signal quality gates...")
            passed, rms, reason = _check_signal_quality(wav_data)
            if not passed:
                _update_noise_floor(rms)
                print(Fore.YELLOW + f"[EARS] ── GATE REJECTED: {reason}")
                return None, None
            print(Fore.WHITE + "[EARS] ── Gates passed. Sending to Whisper...")

            # ── Write WAV for Whisper ──────────────────────────────────────
            try:
                with open(AUDIO_TEMP_PATH, "wb") as f:
                    f.write(wav_data)
            except Exception as _we:
                print(Fore.YELLOW + f"[EARS] WAV write failed: {_we}")
                return None, None

            # ── Whisper Transcription ──────────────────────────────────────
            # no_speech_threshold=0.7  — raised from 0.6, rejects more silence
            # log_prob_threshold=-0.5  — raised from -0.7, rejects low confidence
            # vad_filter=True          — Silero VAD runs inside Whisper
            # vad threshold=0.5        — raised from 0.4, more aggressive
            # NO initial_prompt        — removed, was biasing Whisper to hallucinate
            try:
                _result = audio_model.transcribe(
                    AUDIO_TEMP_PATH,
                    beam_size=5,
                    language="en",
                    condition_on_previous_text=False,
                    no_speech_threshold=0.7,
                    log_prob_threshold=-0.5,
                    vad_filter=True,
                    vad_parameters={
                        "threshold":               0.5,
                        "min_speech_duration_ms":  200,
                        "min_silence_duration_ms": 300,
                    },
                )
                # faster-whisper returns (generator, info) tuple
                # Must consume generator immediately before info goes out of scope
                if isinstance(_result, tuple):
                    segments = list(_result[0])
                else:
                    segments = list(_result)
            except Exception as _wh:
                print(Fore.YELLOW + f"[EARS] Whisper error: {_wh}")
                return None, None

            # ── Confidence Filter ──────────────────────────────────────────
            print(Fore.WHITE + f"[EARS] ── Whisper returned {len(segments)} segment(s)")
            confident_segments = []
            for seg in segments:
                _nsp = seg.no_speech_prob if hasattr(seg, 'no_speech_prob') else 0.0
                _txt = seg.text.strip() if hasattr(seg, 'text') else ''
                print(Fore.WHITE + f"[EARS] ── Segment: '{_txt}' | no_speech_prob={_nsp:.3f}")
                if _nsp > 0.5:
                    print(Fore.YELLOW + f"[EARS] ── CONFIDENCE REJECTED (no_speech={_nsp:.2f}): '{_txt}'")
                    continue
                confident_segments.append(seg)

            full_text = "".join([s.text for s in confident_segments]).strip()
            print(Fore.WHITE + f"[EARS] ── After confidence filter: '{full_text}'")
            if not full_text:
                print(Fore.YELLOW + "[EARS] ── Empty after confidence filter. Discarding.")
                return None, None

            # ── Clean for filter checks ────────────────────────────────────
            clean = full_text.lower().strip()
            for ch in [".", "!", ",", "?", "..."]:
                clean = clean.replace(ch, "")
            clean = clean.strip()

            if len(clean) < 2:
                return None, None

            # ── Hallucination Filter ───────────────────────────────────────
            print(Fore.WHITE + f"[EARS] ── Checking hallucination: '{clean}'")
            is_ghost, ghost_reason = _is_hallucination(clean, full_text.lower().strip())
            if is_ghost:
                print(Fore.YELLOW + f"[EARS] ── HALLUCINATION REJECTED: {ghost_reason}")
                return None, None
            print(Fore.WHITE + "[EARS] ── Hallucination check passed.")

            # ── Repetition Loop Detection ──────────────────────────────────
            # Whisper hallucinates by repeating phrases when audio is ambiguous.
            # "I don't know I don't know I don't know" is not real speech.
            # Detect by splitting into chunks and checking for repeated phrases.
            _rep_check = _detect_repetition_loop(clean)
            if _rep_check:
                print(Fore.YELLOW + f"[EARS] ── REPETITION LOOP REJECTED: '{clean[:60]}'")
                return None, None

            # ── Semantic Coherence Check ───────────────────────────────────
            # "on a new place of time week" is incoherent — no human says this.
            # Check if the transcription has at least minimal semantic structure.
            _coh_check = _is_incoherent(clean)
            if _coh_check:
                print(Fore.YELLOW + f"[EARS] ── INCOHERENT REJECTED: '{clean[:60]}'")
                return None, None

            # ── Autocorrect ────────────────────────────────────────────────
            # Corrects common Whisper mishearing of "Seven" and related words
            corrections = {
                "semen":         "seven",
                "savin":         "seven",
                "sibin":         "seven",
                "simon":         "seven",
                "siman":         "seven",
                "heaven":        "seven",
                "siwen":         "seven",
                "so when":       "seven",
                "servant":       "seven",
                "siren":         "seven",
                "sevan":         "seven",
                "i7":            "hi seven",
                "i 7":           "hi seven",
                "fight explorer":"file explorer",
                "five explorer": "file explorer",
                "and roll my voice": "enroll my voice",
                "and roll":      "enroll",
                "in role":       "enroll",
                "in roll":       "enroll",
                "unroll":        "enroll",
                "what's the whether": "what is the weather",
                "what's the weather": "what is the weather",
                "whether":       "weather",
            }
            result_text = full_text.lower().strip()
            for wrong, right in corrections.items():
                if wrong in result_text:
                    result_text = result_text.replace(wrong, right)

            final = result_text.strip().capitalize()
            if not final:
                return None, None

            print(Fore.GREEN + f"[EARS] Heard: '{final}'")
            return final, AUDIO_TEMP_PATH

    except OSError as _outer_ose:
        print(Fore.YELLOW + f"[EARS] Mic stream error: {_outer_ose}")
        import time as _t
        _t.sleep(1)
        return None, None
    except Exception:
        return None, None


# =============================================================================
# INTERRUPT LISTENER
# Runs during TTS speech. Lightweight. Detects stop words only.
# =============================================================================

def listen_for_interrupt(interrupt_words, on_interrupt_callback, stop_event):
    """
    Lightweight listener running while Seven is speaking.
    Uses beam_size=1 for speed. Only checks for interrupt words.
    Does not run the full signal pipeline — speed matters here.
    """
    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = False
    recognizer.energy_threshold         = _get_threshold()
    recognizer.pause_threshold          = 0.6
    recognizer.non_speaking_duration    = 0.3

    _interrupt_ghosts = {
        "thank you", "thanks", "you", "bye", "okay",
        "subtitles", "subscribe", "caption",
    }

    while not stop_event.is_set():
        try:
            with sr.Microphone() as source:
                try:
                    audio = recognizer.listen(source, timeout=1.5, phrase_time_limit=3)
                except sr.WaitTimeoutError:
                    continue

                interrupt_audio_path = "temp_interrupt.wav"
                try:
                    with open(interrupt_audio_path, "wb") as f:
                        f.write(audio.get_wav_data())
                except Exception:
                    continue

                try:
                    _int_result = audio_model.transcribe(
                        interrupt_audio_path,
                        beam_size=1,
                        language="en",
                        no_speech_threshold=0.7,
                        vad_filter=True,
                    )
                    if isinstance(_int_result, tuple):
                        _int_segments = list(_int_result[0])
                    else:
                        _int_segments = list(_int_result)
                    text = "".join([s.text for s in _int_segments]).strip().lower()
                except Exception:
                    continue
                finally:
                    try:
                        os.remove(interrupt_audio_path)
                    except Exception:
                        pass

                if not text or len(text) < 2:
                    continue

                clean = text.replace(".", "").replace("!", "").replace(",", "").strip()

                if clean in _interrupt_ghosts:
                    continue

                for word in interrupt_words:
                    if re.search(r'\b' + re.escape(word) + r'\b', clean):
                        print(Fore.YELLOW + f"[EARS] Interrupt: '{clean}' matched '{word}'")
                        on_interrupt_callback()
                        return

        except Exception:
            continue

    try:
        if os.path.exists("temp_interrupt.wav"):
            os.remove("temp_interrupt.wav")
    except Exception:
        pass