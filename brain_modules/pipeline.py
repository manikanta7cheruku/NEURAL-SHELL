"""
brain_modules/pipeline.py

Runs brain pipeline layers in order. Each layer either stops the pipeline
(returns a response) or passes through.

Chain of Responsibility: explicit ordering, one job per layer, a failing
layer never kills the pipeline.

LAYER ORDER MATTERS. What changed in this version:
    layer_025_social    instant social replies, placed BEFORE repetition and
                        identity so "hey" never reaches memory or the model.
    layer_56_live_guard after web search: if a live-data question got no web
                        results, answer honestly instead of letting the model
                        invent weather or news.
"""

import logging
import time as _time

_log = logging.getLogger("seven.pipeline")

LAYER_ORDER = [
    "brain_modules.layers.layer_00_input_prep",
    "brain_modules.layers.layer_01_name",
    "brain_modules.layers.layer_025_social",
    "brain_modules.layers.layer_02_repetition",
    "brain_modules.layers.layer_03_identity",
    "brain_modules.layers.layer_38_file_root",
    "brain_modules.layers.layer_04_tars",
    "brain_modules.layers.layer_43_file_search",
    "brain_modules.layers.layer_45_tasks",
    "brain_modules.layers.layer_45_suggest",
    "brain_modules.layers.layer_45_trigger",
    "brain_modules.layers.layer_45_scheduler",
    "brain_modules.layers.layer_45_battery",
    "brain_modules.layers.layer_45_system",
    "brain_modules.layers.layer_45_window",
    "brain_modules.layers.layer_45_app",
    "brain_modules.layers.layer_05_memory",
    "brain_modules.layers.layer_53_knowledge",
    "brain_modules.layers.layer_55_web",
    "brain_modules.layers.layer_56_live_guard",
    "brain_modules.layers.layer_59_app_history",
    "brain_modules.layers.layer_06_personal_filter",
    "brain_modules.layers.layer_07_facts",
    "brain_modules.layers.layer_075_proactive",
    "brain_modules.layers.layer_08_llm",
]

_LAYER_CACHE = {}


def _get_layer(module_path):
    """Lazy-load a layer module and cache it (including failures)."""
    if module_path not in _LAYER_CACHE:
        try:
            _LAYER_CACHE[module_path] = __import__(module_path, fromlist=["process"])
        except Exception as exc:
            _log.error("Failed to load %s: %s", module_path, exc, exc_info=True)
            _LAYER_CACHE[module_path] = None
    return _LAYER_CACHE[module_path]


def run(ctx, deps):
    """
    Run all layers in order.

    Returns whatever the first stopping layer returns: a string, "" for
    intentional silence, or ("__STREAM__", generator). Records which layer
    answered in ctx.answered_by.
    """
    try:
        from brain_modules.observability import record_layer_latency as _rec
    except Exception:
        _rec = None

    for module_path in LAYER_ORDER:
        layer = _get_layer(module_path)
        if not layer or not hasattr(layer, "process"):
            continue

        short = module_path.rsplit(".", 1)[-1]
        t0 = _time.time()
        try:
            result = layer.process(ctx, deps)
        except Exception as exc:
            _log.warning("Layer %s error: %s", short, exc, exc_info=True)
            result = None
        if _rec:
            try:
                _rec(short, (_time.time() - t0) * 1000)
            except Exception:
                pass

        if result is None:
            continue
        if result.is_stop:
            ctx.answered_by = short
            if result.action == "stop_stream":
                return ("__STREAM__", result.generator)
            return result.response

    ctx.answered_by = "none"
    return "Processing error. No layer produced a response."
