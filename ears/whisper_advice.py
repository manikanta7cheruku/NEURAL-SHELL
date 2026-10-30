"""
ears/whisper_advice.py

Which speech model suits this PC, and what to be careful about with each, in words a person can act on. Settings, Voice
shows it beside every model, the same way Settings, Brain does for language models (brain_modules/model_catalog.py).

Whisper runs on the graphics card only when CTranslate2 finds an NVIDIA (CUDA) card; any other graphics (Intel, AMD,
a laptop's integrated chip) means the processor does the work, so "has a graphics card" here means CUDA.

    recommended_id(hw)     the model to suggest for this PC
    advise(model_id, hw)   {"recommended": bool, "level": "ok" | "caution", "note": str}

hw is {"cuda": bool, "vram_gb": float, "ram_gb": float, "gpu": str | None}; unknown readings are 0 and never block.
"""

MODEL_GB = {"base.en": 0.15, "small.en": 0.48, "medium.en": 1.5, "large-v3": 3.1}


def recommended_id(hw: dict) -> str:
    """small.en nearly everywhere; base.en on a processor-only PC with very little memory."""
    ram = float(hw.get("ram_gb") or 0)
    if not hw.get("cuda") and 0 < ram < 8:
        return "base.en"
    return "small.en"


def advise(model_id: str, hw: dict) -> dict:
    cuda = bool(hw.get("cuda"))
    vram = float(hw.get("vram_gb") or 0)
    ram = float(hw.get("ram_gb") or 0)
    gpu = hw.get("gpu") or "your graphics card"
    rec = model_id == recommended_id(hw)

    def out(level, note):
        return {"recommended": rec, "level": level, "note": note}

    if model_id == "base.en":
        if rec:
            return out("ok", "Best for this PC: it has little memory, and this model is the lightest.")
        if cuda:
            return out("ok", "Very fast, but it makes more mistakes than Small, which your graphics card runs easily.")
        return out("ok", "The fastest, with noticeably more mistakes. Good on a low-memory PC.")

    if model_id == "small.en":
        if rec and cuda:
            return out("ok", f"The best balance for this PC: fast on {gpu} and accurate. About 480 MB.")
        if rec:
            return out("ok", "The best balance for this PC. On a processor Seven hears with the fast model first and "
                             "uses this one only when it is unsure.")
        return out("ok", "Accurate and quick to download. About 480 MB.")

    if model_id == "medium.en":
        if cuda and vram >= 4:
            return out("ok", f"Runs fast on {gpu}. A little more accurate than Small, and a 1.5 GB download.")
        if cuda:
            return out("caution", f"{gpu} has {vram:g} GB of memory, which is tight for this model. It may be slow or "
                                  "fall back to the processor.")
        if 0 < ram < 12:
            return out("caution", "Slow on a processor, and it needs about 3 GB of free memory, which this PC may not "
                                  "spare. Small is a better choice.")
        return out("caution", "Slow without an NVIDIA graphics card: Seven would take several seconds to understand you. "
                              "Choose it only if accuracy matters more than speed.")

    if model_id == "large-v3":
        if cuda and vram >= 8:
            return out("ok", f"The most accurate. Needs a strong graphics card, which {gpu} is. A 3 GB download.")
        if cuda:
            return out("caution", f"Needs about 8 GB of graphics memory and {gpu} has {vram:g} GB, so it would be very "
                                  "slow or fail to load. Not recommended.")
        return out("caution", "Very slow without an NVIDIA graphics card, and it uses a lot of memory. Not recommended.")

    return out("ok", "")
