"""
seven_utils/hf_offline.py

The embedding model (all-MiniLM-L6-v2) is downloaded once during setup. After that Seven must never ask
huggingface.co about it: offline, every check retries for about 20 seconds before giving up, which is what made
chat stall when the PC had no internet.

huggingface_hub reads HF_HUB_OFFLINE once, when it is first imported, so enable() has to run at the very top of
each entry point, before anything imports transformers or sentence_transformers.
"""

import os

EMBEDDING_MODEL = "all-MiniLM-L6-v2"


def local_model_path(model_name: str = EMBEDDING_MODEL):
    """Folder of the cached model, or None when it has not been downloaded yet."""
    home = os.path.expanduser("~")
    snapshots = os.path.join(home, ".cache", "huggingface", "hub",
                             f"models--sentence-transformers--{model_name}", "snapshots")
    try:
        for name in sorted(os.listdir(snapshots)):
            path = os.path.join(snapshots, name)
            if os.path.isfile(os.path.join(path, "config.json")):
                return path
    except OSError:
        pass
    for path in (os.path.join(home, ".cache", "torch", "sentence_transformers", f"sentence-transformers_{model_name}"),
                 os.path.join(home, ".cache", "sentence_transformers", f"sentence-transformers_{model_name}")):
        if os.path.isfile(os.path.join(path, "config.json")):
            return path
    return None


def enable() -> bool:
    """Turn on offline mode when the model is already on disk. Returns whether it did."""
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    if local_model_path() is None:
        return False
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    return True


class allow_downloads:
    """Lift offline mode for one deliberate download (the setup wizard fetching the voice model)."""

    def __enter__(self):
        self._saved = {k: os.environ.pop(k, None) for k in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")}
        self._const = None
        try:
            from huggingface_hub import constants
            self._const, constants.HF_HUB_OFFLINE = constants.HF_HUB_OFFLINE, False
        except Exception:
            pass
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            if v is not None:
                os.environ[k] = v
        if self._const is not None:
            from huggingface_hub import constants
            constants.HF_HUB_OFFLINE = self._const
        return False
