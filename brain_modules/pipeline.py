"""
=============================================================================
brain_modules/pipeline.py

Runs brain pipeline layers in order.
Each layer either stops the pipeline (returns response) or passes through.

WHY A PIPELINE:
    Chain of Responsibility pattern.
    Explicit layer ordering.
    Each layer has one job.
    Adding a new layer = one file + one line in LAYER_ORDER.

LAYER ORDER MATTERS:
    Layer 1 runs before Layer 2, which runs before Layer 3, etc.
    Reordering breaks behavior. Do not reorder without understanding why.
=============================================================================
"""

from colorama import Fore


# ─────────────────────────────────────────────────────────────────────────
# LAYER ORDER — Do not change without reason.
# Each entry is a module path. Layers are instantiated and cached.
# ─────────────────────────────────────────────────────────────────────────

LAYER_ORDER = [
    "brain_modules.layers.layer_00_input_prep",
    "brain_modules.layers.layer_01_name",
    "brain_modules.layers.layer_02_repetition",
    "brain_modules.layers.layer_03_identity",
    "brain_modules.layers.layer_38_file_root",
    "brain_modules.layers.layer_04_tars",
    "brain_modules.layers.layer_43_file_search",
    "brain_modules.layers.layer_45_tasks",
    "brain_modules.layers.layer_45_suggest",
    "brain_modules.layers.layer_45_scheduler",
    "brain_modules.layers.layer_45_battery",
    "brain_modules.layers.layer_45_system",
    "brain_modules.layers.layer_45_window",
    "brain_modules.layers.layer_45_app",
    "brain_modules.layers.layer_05_memory",
    "brain_modules.layers.layer_53_knowledge",
    "brain_modules.layers.layer_55_web",
    "brain_modules.layers.layer_59_app_history",
    "brain_modules.layers.layer_06_personal_filter",
    "brain_modules.layers.layer_07_facts",
    "brain_modules.layers.layer_08_llm",
]

# Cache of instantiated layer modules
_LAYER_CACHE = {}


def _get_layer(module_path):
    """Lazy-load a layer module and cache it."""
    if module_path not in _LAYER_CACHE:
        try:
            module = __import__(module_path, fromlist=["process"])
            _LAYER_CACHE[module_path] = module
        except Exception as e:
            print(Fore.RED + f"[PIPELINE] Failed to load {module_path}: {e}")
            import traceback; traceback.print_exc()
            _LAYER_CACHE[module_path] = None
    return _LAYER_CACHE[module_path]


def run(ctx, deps):
    """
    Run all pipeline layers in order.

    ARGS:
        ctx  (BrainContext): shared context for this think() call
        deps (dict): dependency map — includes seven_memory, mood_engine,
                     config module, etc. Passed to each layer that needs them.

    RETURNS:
        Whatever the first stopping layer returns.
        Could be a string, an empty string, or ("__STREAM__", generator).
    """
    for module_path in LAYER_ORDER:
        layer = _get_layer(module_path)
        if not layer or not hasattr(layer, "process"):
            continue

        try:
            result = layer.process(ctx, deps)
        except Exception as e:
            # Graceful degradation — one layer failing does not kill the pipeline
            print(Fore.YELLOW + f"[PIPELINE] Layer {module_path} error: {e}")
            import traceback; traceback.print_exc()
            continue

        if result is None:
            # Layer returned nothing → pass through
            continue

        if result.is_stop:
            if result.action == "stop_stream":
                return ("__STREAM__", result.generator)
            return result.response

    # No layer stopped — should never happen (Layer 8 LLM always stops)
    return "Processing error. No layer produced a response."