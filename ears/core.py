"""
=============================================================================
PROJECT SEVEN - ears/core.py
Version: 2.0 - speech-detector pipeline

PIPELINE:
    1. ears/stream.py     one open microphone; a neural speech detector (Silero) cuts whole utterances out of
                          the sound, so fans, typing and TV noise never reach Whisper
    2. Echo rejection     utterances that began while Seven was talking, or right after, are Seven hearing itself
    3. Whisper            speech-only audio, greedy decoding, Whisper's own silence and confidence checks
    4. Text checks        non-English or music output, known hallucinations ("thanks for watching"),
                          repetition loops, transcripts that match what Seven just said
    5. Autocorrect        RapidFuzz correction of app names and common words

Returns ("text", "__voice__") for a valid utterance (or "temp_audio.wav" when voice verification needs the audio),
(None, None) otherwise. Every rejection is published to the app ("voice_ignored") so the home screen can show it.
=============================================================================
"""

import io
import json
import os
import re
import threading
import time
import wave

import numpy as np
import colorama
from colorama import Fore

# numpy 2.x compatibility shim
if not hasattr(np, 'iterable'):
    np.iterable = lambda obj: hasattr(obj, '__iter__')

from faster_whisper import WhisperModel

from ears.stream import STREAM, RATE
from ears.hallucination_filter import is_hallucination, is_repetition_loop, is_incoherent
from ears.autocorrect import correct as _autocorrect
from ears.wake_word import normalize_wake

colorama.init(autoreset=True)


# =============================================================================
# CONFIGURATION
# =============================================================================

def _config() -> dict:
    try:
        p = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'SEVEN', 'config.json')
        with open(p, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _get_configured_model() -> str:
    model = os.environ.get('SEVEN_WHISPER_MODEL') or _config().get('brain', {}).get('whisper_model', '').strip()
    if model:
        return model
    # Default by hardware: medium on a GPU, small on a CPU (medium on a CPU made the whole PC lag).
    return "medium.en" if _gpu_available() else "small.en"


def _gpu_available() -> bool:
    """
    Ask CTranslate2, the engine faster-whisper runs on. Do not ask torch: the bundled torch is a CPU-only
    build, so torch.cuda.is_available() is False even on an RTX card and Whisper silently ran on the CPU.
    SEVEN_WHISPER_DEVICE=cpu forces the CPU path (scripts/voice_bench.py measures what users without a GPU get).
    """
    if os.environ.get('SEVEN_WHISPER_DEVICE') == 'cpu':
        return False
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


def _is_voice_id_enabled() -> bool:
    cfg = _config()
    return bool(cfg.get('voice', {}).get('only_me')
                or cfg.get('voice_gates', {}).get('speaker_verify', {}).get('enabled', False))


def voice_settings() -> dict:
    """The listening settings, with defaults. Older installs kept them under voice_gates."""
    cfg = _config()
    v = cfg.get('voice', {})
    gates = cfg.get('voice_gates', {})
    mode = v.get('listen_mode')
    if mode not in ('wake', 'always', 'ptt'):
        mode = 'ptt' if gates.get('push_to_talk', {}).get('enabled') else 'wake'
    sens = v.get('sensitivity') if v.get('sensitivity') in ('relaxed', 'balanced', 'strict') else 'balanced'
    return {
        'listen_mode': mode,
        'sensitivity': sens,
        'follow_up_seconds': float(v.get('follow_up_seconds', 8)),
        'interrupt': bool(v.get('interrupt', True)),
        'only_me': bool(v.get('only_me', False)),
        'mic': v.get('mic', '') or '',
        'wake_words': v.get('wake_words') or ['hey seven', 'ok seven', 'okay seven', 'seven'],
    }


# =============================================================================
# WHISPER LOADER
# =============================================================================

def _load_whisper(model_size: str) -> WhisperModel:
    try:
        return _load_whisper_cached(model_size)
    except Exception:
        # Offline mode blocks fetching a voice model that was never downloaded; allow it once.
        from seven_utils import hf_offline
        with hf_offline.allow_downloads():
            return _load_whisper_cached(model_size)


def _load_whisper_cached(model_size: str) -> WhisperModel:
    if _gpu_available():
        try:
            model = WhisperModel(model_size, device="cuda", compute_type="float16")
            print(Fore.GREEN + f"[EARS] Whisper {model_size}: GPU ready")
            return model
        except Exception as e:
            print(Fore.YELLOW + f"[EARS] GPU init failed: {e}")

    # Leave cores for the rest of the PC: transcription on every core froze other apps.
    threads = max(2, min(4, (os.cpu_count() or 4) // 2))
    model = WhisperModel(model_size, device="cpu", compute_type="int8", cpu_threads=threads)
    print(Fore.YELLOW + f"[EARS] Whisper {model_size}: CPU mode ({threads} threads)")
    return model


_MODEL_SIZE = _get_configured_model()
print(Fore.CYAN + f"[EARS] Loading Whisper ({_MODEL_SIZE})...")
audio_model = _load_whisper(_MODEL_SIZE)

# Two-stage hearing on PCs without a GPU. Whisper always encodes a 30-second window, so small.en takes ~1.5 s per
# request on a laptop CPU while base.en takes ~0.4 s. base.en's mistakes ("open crown" for "open chrome") come with
# low confidence, and its correct transcripts with high confidence, so: hear with base.en, and only when it isn't
# sure, listen again with the accurate model. (scripts/voice_bench.py measured this: same accuracy, ~4x faster.)
_fast_model = None
_UNSURE = -0.45                     # lowest segment avg_logprob below which the fast transcript is re-checked
if not _gpu_available() and _MODEL_SIZE in ("small.en", "medium.en") and not os.environ.get('SEVEN_WHISPER_MODEL') \
        and not _config().get('brain', {}).get('whisper_model'):
    try:
        _fast_model = _load_whisper("base.en")
        print(Fore.CYAN + f"[EARS] Fast first pass: base.en, re-checked with {_MODEL_SIZE} when unsure")
    except Exception as _fm_err:
        print(Fore.YELLOW + f"[EARS] Fast model unavailable, using {_MODEL_SIZE} only: {_fm_err}")


# =============================================================================
# WIRING (main loop and mouth)
# =============================================================================

_force_return_event = threading.Event()
_is_speaking_fn = lambda: False
_spoken_fn = lambda: []            # recent sentences Seven said, for echo rejection
_ended_at_fn = lambda: 0.0         # when Seven last stopped talking
_publish = lambda key, value: None


def set_force_return(val: bool):
    (_force_return_event.set if val else _force_return_event.clear)()


def set_speaking_fn(fn):
    """Register the function that returns True while Seven is speaking (called by the voice loop)."""
    global _is_speaking_fn
    _is_speaking_fn = fn
    STREAM.set_speaking_fn(fn)


def set_mouth(engine):
    """The natural-voice engine, so the ears know what Seven said and when it stopped."""
    global _spoken_fn, _ended_at_fn
    _spoken_fn = engine.recently_said
    _ended_at_fn = engine.ended_at


def set_publisher(fn):
    global _publish
    _publish = fn
    STREAM.set_publisher(fn)


def start():
    """Open the microphone with the current settings. Safe to call again after settings change."""
    s = voice_settings()
    STREAM.configure(sensitivity=s['sensitivity'], device_name=s['mic'])
    STREAM.start()


def _ignored(reason: str, text: str = ""):
    print(Fore.YELLOW + f"[EARS] Ignored: {reason}{f' ({text[:50]})' if text else ''}")
    _publish("voice_ignored", {"reason": reason, "text": text[:80], "at": time.time()})
    STREAM._set_state("idle")
    _deliver_test("", reason, text)


# ── Hearing test (Settings, Voice, Test) ─────────────────────────────────────
# The next utterance goes to the test instead of being acted on, so the user sees exactly what Seven heard.
_test_box = None


def hearing_test(timeout: float = 8.0):
    """Wait for the next utterance; {'heard': text, 'ignored': reason or '', 'raw': text} or None if nothing came."""
    global _test_box
    import queue as _q
    box = _q.Queue(maxsize=1)
    _test_box = box
    try:
        return box.get(timeout=timeout)
    except _q.Empty:
        return None
    finally:
        _test_box = None


def _deliver_test(heard: str, reason: str = "", raw: str = "") -> bool:
    box = _test_box
    if box is None:
        return False
    try:
        box.put_nowait({"heard": heard, "ignored": reason, "raw": raw})
    except Exception:
        pass
    return True


def listening() -> bool:
    """True when the microphone stream is running (the voice loop started it)."""
    return STREAM._thread is not None and STREAM._thread.is_alive()


# =============================================================================
# TRANSCRIPTION
# =============================================================================

def transcribe(audio: np.ndarray, fast: bool = False) -> tuple:
    """
    (text, reason) for 16 kHz float32 speech. text is "" when Whisper itself says there is no reliable speech.
    The speech detector already trimmed the audio, so Whisper's own VAD is off and decoding is greedy (fast).
    """
    try:
        segments = None
        if _fast_model is not None:
            first = list(_run(_fast_model, audio, beam=1))
            if first and min(s.avg_logprob for s in first) >= _UNSURE:
                segments = first
        if segments is None:
            segments = _run(audio_model, audio, beam=1 if fast else 2)
        kept = []
        for seg in segments:
            if getattr(seg, 'no_speech_prob', 0.0) > 0.6 and getattr(seg, 'avg_logprob', 0.0) < -0.5:
                continue                                    # Whisper: no speech here
            if getattr(seg, 'avg_logprob', 0.0) < -1.1:
                continue                                    # a guess, not a hearing
            if getattr(seg, 'compression_ratio', 0.0) > 2.6:
                continue                                    # the same phrase over and over
            kept.append(seg.text)
        text = "".join(kept).strip()
        return text, ("ok" if text else "no clear speech")
    except Exception as e:
        print(Fore.YELLOW + f"[EARS] Whisper error: {e}")
        return "", "transcription failed"


def _run(model, audio, beam):
    segments, _ = model.transcribe(
        audio.astype(np.float32),
        language="en",
        beam_size=beam,
        temperature=0.0,
        condition_on_previous_text=False,
        without_timestamps=True,
        vad_filter=False,
        no_speech_threshold=0.6,
        log_prob_threshold=-1.0,
        compression_ratio_threshold=2.4,
    )
    return segments


def _text_problem(text: str):
    """Why a transcript isn't a real request, or None."""
    if not text.strip():
        return "empty"
    letters = text.replace(" ", "")
    if letters and sum(1 for c in letters if ord(c) < 128) / len(letters) < 0.85:
        return "not English speech (music or noise)"
    if any(c in text for c in '♪♫🎵🎶🎤🎼'):
        return "music"
    words = text.lower().split()
    if len(words) >= 4 and sum(1 for w in words if w.count('-') >= 2) >= 2:
        return "sung syllables"
    clean = re.sub(r"[.!,?]+", "", text.lower()).strip()
    ghost, why = is_hallucination(clean, text.lower())
    if ghost:
        return f"a known mishearing ({why})"
    if is_repetition_loop(clean):
        return "a repetition loop"
    if is_incoherent(clean):
        return "incoherent"
    return None


def _is_echo(text: str) -> bool:
    """True when the transcript is (part of) something Seven just said: Seven hearing its own voice."""
    t = re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()
    if len(t) < 4:
        return False
    try:
        from rapidfuzz import fuzz
        for said in _spoken_fn(within=12.0):
            s = re.sub(r"[^a-z0-9 ]", "", said.lower())
            if fuzz.partial_ratio(t, s) >= 85:
                return True
    except Exception:
        pass
    return False


def _wav_bytes(audio: np.ndarray) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())
    return buf.getvalue()


# =============================================================================
# MAIN LISTEN FUNCTION
# =============================================================================

def listen() -> tuple:
    """
    Wait briefly for the next utterance and return (text, audio_path), or (None, None).
    Returns quickly (about half a second) when nobody is talking, so the voice loop stays responsive.
    """
    start()
    utt = STREAM.next(timeout=0.5)
    if utt is None:
        return None, None

    # Seven hearing itself: began while it was talking, or in the echo tail right after.
    if utt.during_speech or _is_speaking_fn() or utt.started < _ended_at_fn() + 0.35:
        _ignored("Seven's own voice")
        return None, None

    t = time.time()
    text, reason = transcribe(utt.audio)
    if not text:
        _ignored(reason)
        return None, None
    problem = _text_problem(text)
    if problem:
        _ignored(problem, text)
        return None, None
    if _is_echo(text):
        _ignored("Seven's own voice", text)
        return None, None

    final = normalize_wake(_autocorrect(text).strip())
    final = final[:1].upper() + final[1:]
    print(Fore.GREEN + f"[EARS] Heard: '{final}' ({utt.seconds:.1f}s audio, {time.time() - t:.2f}s to text)")
    STREAM._set_state("idle")
    if _deliver_test(final):                    # a hearing test: show it, don't act on it
        return None, None

    audio_out_path = "__voice__"
    if _is_voice_id_enabled():
        try:
            with open("temp_audio.wav", "wb") as f:
                f.write(_wav_bytes(utt.audio))
            audio_out_path = "temp_audio.wav"
        except Exception as e:
            print(Fore.YELLOW + f"[EARS] Audio save failed: {e}")
    return final, audio_out_path


# =============================================================================
# INTERRUPT LISTENER
# While Seven talks the main loop is busy speaking, so this is the only reader of the utterance queue.
# =============================================================================

def listen_for_interrupt(interrupt_words, on_interrupt_callback, stop_event):
    """Stop Seven when the user says a stop word over it. Returns on the first match or when speech ends."""
    start()
    words = [w.lower() for w in interrupt_words]
    while not stop_event.is_set():
        utt = STREAM.next(timeout=0.2)
        if utt is None or utt.speech_seconds > 6.0:      # long stretches are Seven's own sentences
            continue
        text, _ = transcribe(utt.audio, fast=True)
        clean = re.sub(r"[^a-z ]", "", text.lower()).strip()
        if not clean or _is_echo(clean):
            continue
        for word in words:
            if re.search(r'\b' + re.escape(word) + r'\b', clean):
                print(Fore.YELLOW + f"[EARS] Interrupt: '{word}' in '{clean}'")
                on_interrupt_callback()
                return
