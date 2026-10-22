"""
brain_modules/brain_settings.py

Brain Configuration made real: every setting has a type, bounds, a default and
a statement of WHERE it is applied, so the UI can show configured versus
effective values, invalid values are clamped instead of crashing, and the
active model is distinguished from the selected one.
"""

from typing import Any, Dict, Optional, Tuple

# path: (type, min, max, default, applied_by)
SETTINGS: Dict[str, Tuple[type, Any, Any, Any, str]] = {
    "brain.model_name": (str, None, None, "auto", "layer_08_llm (model used for replies)"),
    "brain.temperature": (float, 0.1, 1.0, 0.3, "layer_08_llm (capped lower for grounded and factual answers)"),
    "brain.tars_humor": (int, 0, 100, 75, "prompt_builder (tone only; never affects facts or tools)"),
    "brain.tars_honesty": (int, 0, 100, 85, "prompt_builder (directness; uncertainty is always admitted)"),
    "brain.streaming": (bool, None, None, True, "layer_08_llm (sentence streaming for voice)"),
    "brain.history_ttl_seconds": (int, 60, 86400, 1800, "chat_history (how long recent turns stay in context)"),
    "brain.follow_up_timeout": (int, 15, 300, 90, "dialogue_manager (reference memory, existing layer)"),
    "brain.search_max_results": (int, 3, 20, 8, "file search layers (existing layers)"),
    "brain.auto_open_best_match": (bool, None, None, True, "file search layers (existing layers)"),
    "brain.content_search_enabled": (bool, None, None, True, "file search layers (existing layers)"),
    "brain.prefer_browser_for_unknown": (bool, None, None, True, "app layer (existing layer)"),
    "brain.curiosity_level": (str, None, ("off", "low", "normal"), "normal", "curiosity (how often Seven asks back)"),
    "brain.reasoning_model": (str, None, None, "", "layer_08_llm (optional model for hard questions)"),
    "memory.min_relevance": (float, 0.3, 0.95, 0.70, "layer_05_memory (semantic recall threshold)"),
    "memory.retrieval_timeout_ms": (int, 50, 3000, 450, "layer_08_llm (how long to wait for memory)"),
    "web.enabled": (bool, None, None, True, "web_provider (live lookups)"),
    "privacy.telemetry_enabled": (bool, None, None, True, "telemetry (usage statistics)"),
    "storage.max_mb": (int, 0, 10_000_000, 0, "limits (0 = no budget)"),
}


def _get(cfg: dict, path: str, default: Any) -> Any:
    cur: Any = cfg
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def coerce(path: str, value: Any) -> Tuple[Any, bool, str]:
    """(effective value, was_valid, note). Out-of-range values are clamped, bad types fall back to the default."""
    typ, lo, hi, default, _ = SETTINGS[path]
    try:
        if typ is bool:
            if isinstance(value, str):
                value = value.strip().lower() in ("1", "true", "yes", "on")
            return bool(value), True, ""
        if typ is str:
            v = str(value).strip()
            if isinstance(hi, tuple):
                return (v, True, "") if v in hi else (default, False, f"must be one of {', '.join(hi)}")
            return v, True, ""
        v = typ(value)
        if lo is not None and v < lo:
            return lo, False, f"minimum is {lo}"
        if hi is not None and v > hi:
            return hi, False, f"maximum is {hi}"
        return v, True, ""
    except (TypeError, ValueError):
        return default, False, f"expected {typ.__name__}"


def effective(config) -> Dict[str, Dict[str, Any]]:
    """For every setting: what is configured, what is actually used, and who applies it."""
    cfg = getattr(config, "KEY", config)
    out = {}
    for path, (_t, _lo, _hi, default, applied_by) in SETTINGS.items():
        configured = _get(cfg, path, default)
        eff, valid, note = coerce(path, configured)
        out[path] = {"configured": configured, "effective": eff, "valid": valid, "note": note,
                     "default": default, "applied_by": applied_by}
    return out


def get_effective(config, path: str) -> Any:
    cfg = getattr(config, "KEY", config)
    return coerce(path, _get(cfg, path, SETTINGS[path][3]))[0]


def validate_update(path: str, value: Any) -> Tuple[bool, Any, str]:
    """(accepted, value to store, message) for a settings change."""
    if path not in SETTINGS:
        return False, value, "unknown setting"
    eff, valid, note = coerce(path, value)
    return valid, eff, note


def model_status(config, active_model: str, installed: Optional[list]) -> Dict[str, Any]:
    """Selected versus active model, with installation check and an honest size note."""
    selected = get_effective(config, "brain.model_name") or "auto"
    ok = None if installed is None else any(active_model == m or active_model.split(":")[0] == m.split(":")[0]
                                            for m in installed)
    note = "Smaller models answer faster but reason less reliably; larger models need more memory."
    if selected != "auto" and active_model and selected.split(":")[0] != active_model.split(":")[0]:
        note = f"You selected {selected} but {active_model} is active (the selection was not installed or not applied yet)."
    return {"selected": selected, "active": active_model, "installed": ok, "note": note}


def generation(config, is_voice: bool, decision=None, grounded: bool = False) -> Dict[str, Any]:
    """Temperature and token multiplier actually used for a reply."""
    temp = float(get_effective(config, "brain.temperature"))
    if is_voice:
        temp = min(0.7, temp + 0.05)
    cap = getattr(decision, "temperature_cap", None)
    if grounded:
        cap = min(cap, 0.2) if cap else 0.2
    if cap is not None:
        temp = min(temp, cap)
    return {"temperature": round(temp, 2), "token_multiplier": getattr(decision, "token_multiplier", 1.0)}
