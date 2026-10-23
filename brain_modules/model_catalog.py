"""
brain_modules/model_catalog.py

The one list of language models Seven offers, with what each is good at and
what hardware it needs. The setup wizard, Settings, automatic model choice,
the context size sent to Ollama and Seven's own answers about its model all
read from here, so they cannot disagree.

Sizes are the default 4-bit downloads from the Ollama library. "vram" is the
graphics memory needed to run fully on the GPU while Whisper also uses about
1.5 GB; "ram" is what a CPU-only machine needs to stay responsive.
"""

from typing import Any, Dict, List, Optional

CATALOG: List[Dict[str, Any]] = [
    {"id": "llama3.2:1b", "name": "Llama 3.2 1B", "maker": "Meta", "params": "1 billion", "size_gb": 1.3,
     "vram": 2, "ram": 4, "context": 4096, "speed": "Fastest",
     "good_at": "voice commands, quick answers and controlling your PC",
     "weak_at": "deeper conversation, reasoning and code",
     "best_for": "older laptops and PCs without a graphics card"},
    {"id": "llama3.2:3b", "name": "Llama 3.2 3B", "maker": "Meta", "params": "3 billion", "size_gb": 2.0,
     "vram": 4, "ram": 16, "context": 4096, "speed": "Fast",
     "good_at": "everyday conversation, writing and summaries",
     "weak_at": "harder reasoning and longer code",
     "best_for": "laptops with a small graphics card, or 16 GB of memory"},
    {"id": "qwen2.5:7b", "name": "Qwen 2.5 7B", "maker": "Alibaba", "params": "7 billion", "size_gb": 4.7,
     "vram": 7.5, "ram": 16, "context": 8192, "speed": "Balanced",
     "good_at": "natural conversation, reasoning, writing and code",
     "weak_at": "speed on PCs without a graphics card",
     "best_for": "PCs with a graphics card of 8 GB or more"},
    {"id": "llama3.1:8b", "name": "Llama 3.1 8B", "maker": "Meta", "params": "8 billion", "size_gb": 4.9,
     "vram": 7.5, "ram": 16, "context": 8192, "speed": "Balanced",
     "good_at": "warm, natural conversation and writing",
     "weak_at": "speed on PCs without a graphics card",
     "best_for": "PCs with a graphics card of 8 GB or more"},
    {"id": "qwen2.5-coder:7b", "name": "Qwen 2.5 Coder 7B", "maker": "Alibaba", "params": "7 billion",
     "size_gb": 4.7, "vram": 7.5, "ram": 16, "context": 8192, "speed": "Balanced",
     "good_at": "writing, explaining and fixing code",
     "weak_at": "casual conversation, where general models sound more natural",
     "best_for": "developers with a graphics card of 8 GB or more"},
    {"id": "gemma2:9b", "name": "Gemma 2 9B", "maker": "Google", "params": "9 billion", "size_gb": 5.4,
     "vram": 10, "ram": 24, "context": 8192, "speed": "Thorough",
     "good_at": "careful reasoning and polished writing",
     "weak_at": "speed, unless the graphics card has 10 GB or more",
     "best_for": "high-end PCs and workstations"},
]

_BY_ID = {m["id"]: m for m in CATALOG}


def _base(model_id: str) -> str:
    return (model_id or "").strip().lower().removesuffix(":latest")


def get(model_id: str) -> Optional[Dict[str, Any]]:
    """Catalog entry for an installed or configured model name, or None for models outside the catalog."""
    return _BY_ID.get(_base(model_id))


def context_window(model_id: str) -> int:
    """Tokens of context Seven asks Ollama for with this model."""
    entry = get(model_id)
    if entry:
        return entry["context"]
    low = _base(model_id)
    return 2048 if "tinyllama" in low else 8192 if any(t in low for t in ("7b", "8b", "9b", "13b", "14b")) else 4096


def recommend(vram_gb: float, ram_gb: float, has_gpu: bool) -> Dict[str, Any]:
    """The best model for this hardware, with the reason, so every user starts fast and smooth."""
    if has_gpu and vram_gb >= 7.5:
        pick, why = "qwen2.5:7b", f"a graphics card with {vram_gb:g} GB runs a 7B model fully on the GPU"
    elif has_gpu and vram_gb >= 4:
        pick, why = "llama3.2:3b", f"a graphics card with {vram_gb:g} GB keeps a 3B model fast"
    elif ram_gb >= 16:
        pick, why = "llama3.2:3b", f"{ram_gb:g} GB of memory runs a 3B model on the processor"
    else:
        pick, why = "llama3.2:1b", "the smallest model keeps Seven responsive on this hardware"
    return {"id": pick, "reason": why}


def fits(entry: Dict[str, Any], vram_gb: float, ram_gb: float, has_gpu: bool) -> bool:
    """Whether a model will run smoothly here (fully on the GPU, or on the CPU with enough memory)."""
    return (has_gpu and vram_gb >= entry["vram"]) or ram_gb >= entry["ram"]


def best_installed(installed: List[str], vram_gb: float, ram_gb: float, has_gpu: bool) -> Optional[str]:
    """For "Automatic": the strongest installed catalog model that still fits, else the smallest installed."""
    names = {_base(n): n for n in installed}
    usable = [m for m in CATALOG if m["id"] in names and fits(m, vram_gb, ram_gb, has_gpu)
              and m["id"] != "qwen2.5-coder:7b"]          # a coding model is never the automatic default
    if usable:
        return names[max(usable, key=lambda m: m["size_gb"])["id"]]
    ranked = sorted((m for m in CATALOG if m["id"] in names), key=lambda m: m["size_gb"])
    return names[ranked[0]["id"]] if ranked else (installed[0] if installed else None)
