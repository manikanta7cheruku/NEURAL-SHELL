"""
mouth/voices.py
The voices Seven can speak with, in one place: setup, Settings and the preview button all read this list.

Natural voices are Kokoro (a neural voice that runs offline on the CPU, model files in %APPDATA%/SEVEN/models/kokoro,
downloaded during setup). If those files aren't there yet, Seven speaks with the bundled Piper voices instead.
"""
import os

# A short, curated list: the clearest Kokoro voices, described the way a person would pick one.
NATURAL = [
    {"id": "af_heart",   "name": "Heart",   "accent": "American", "gender": "female", "note": "Warm and clear. The default."},
    {"id": "af_bella",   "name": "Bella",   "accent": "American", "gender": "female", "note": "Bright and lively"},
    {"id": "af_nicole",  "name": "Nicole",  "accent": "American", "gender": "female", "note": "Soft and calm"},
    {"id": "am_michael", "name": "Michael", "accent": "American", "gender": "male",   "note": "Steady and friendly"},
    {"id": "am_fenrir",  "name": "Fenrir",  "accent": "American", "gender": "male",   "note": "Deep and confident"},
    {"id": "am_puck",    "name": "Puck",    "accent": "American", "gender": "male",   "note": "Light and upbeat"},
    {"id": "bf_emma",    "name": "Emma",    "accent": "British",  "gender": "female", "note": "Polished and gentle"},
    {"id": "bm_george",  "name": "George",  "accent": "British",  "gender": "male",   "note": "Classic and composed"},
]
DEFAULT_VOICE = "af_heart"

KOKORO_FILES = {
    "kokoro-v1.0.fp16.onnx": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.fp16.onnx",
    "voices-v1.0.bin":       "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin",
}
KOKORO_SIZE_MB = 205


def models_dir() -> str:
    return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "SEVEN", "models", "kokoro")


def kokoro_ready() -> bool:
    d = models_dir()
    return all(os.path.exists(os.path.join(d, f)) and os.path.getsize(os.path.join(d, f)) > 1_000_000 for f in KOKORO_FILES)


def is_natural(voice_id: str) -> bool:
    return any(v["id"] == voice_id for v in NATURAL)


def catalog() -> list:
    """Every selectable voice, natural ones first. Piper voices only when no natural voice is installed."""
    out = [dict(v, engine="kokoro", ready=kokoro_ready()) for v in NATURAL]
    if not kokoro_ready():
        here = os.path.dirname(os.path.abspath(__file__))
        vdir = os.path.join(os.environ.get("SEVEN_APP_PATH", os.path.dirname(here)), "mouth", "piper", "voices")
        try:
            for f in sorted(os.listdir(vdir)):
                if f.endswith(".onnx"):
                    vid = f[:-5]
                    out.append({"id": vid, "name": vid.split("-")[1].title(), "accent": "British" if "GB" in vid else "American",
                                "gender": "", "note": "Basic voice", "engine": "piper", "ready": True})
        except Exception:
            pass
    return out


def speed_factor(raw) -> float:
    """Config stores speed either as Kokoro's factor (0.7 to 1.4) or, from older versions, as words a minute (165)."""
    try:
        v = float(raw)
    except Exception:
        return 1.0
    if v > 5:                      # words-a-minute style: 165 was normal
        v = v / 165.0
    return max(0.7, min(1.4, v))
