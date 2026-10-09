"""
brain_modules/response_generator.py
Central response orchestrator for Seven.

Decides whether a pipeline result should use:
    1. Instant template response (actions) -- <50ms
    2. LLM streaming response (conversation) -- first token <300ms

This module is called by brain.py AFTER the pipeline runs.
It does NOT replace the pipeline. It processes the pipeline's output.

Architecture:
    Pipeline layers detect WHAT to do and return LayerResult.
    If the LayerResult has action_data, this module renders a template.
    If the LayerResult is from the LLM layer, it passes through unchanged.
    If the LayerResult is a plain stop with text containing ###tags,
    it extracts the action and renders a template (backward compat).
"""

import re
from brain_modules.response_templates import render as template_render


def process_response(result, ctx=None) -> str:
    """
    Process a pipeline result into a final response string.

    For action results with ###tags: extract the action info,
    render a natural template, re-attach the tags.

    For plain conversational text: pass through unchanged.

    Args:
        result: string from pipeline (or tuple for streaming)
        ctx: BrainContext (optional, for future mood/familiarity awareness)

    Returns:
        Final response string (may contain ###tags for executor).
    """
    if not isinstance(result, str):
        return result

    # Check if this response has action tags
    tags = re.findall(r"###(\w+):\s*(.*?)(?=###|$)", result, re.DOTALL)
    if not tags:
        return result

    # Extract the conversational part (everything except tags)
    clean_text = re.sub(
        r"###\w+:\s*.*?(?=###|$)", "", result, flags=re.DOTALL
    ).strip()

    # Reconstruct tag string to re-attach
    tag_string = " ".join(
        f"###{cmd}:{arg.strip()}" for cmd, arg in tags
    )

    # Determine action category and render template
    template_text = _resolve_template(tags, clean_text)

    if template_text:
        return f"{template_text} {tag_string}"

    # Fallback: use whatever text the layer produced
    if clean_text:
        return f"{clean_text} {tag_string}"

    return result


def _resolve_template(tags: list, existing_text: str) -> str:
    """
    Given extracted action tags, determine the template category
    and render appropriate text.

    Returns template text or None to use existing text.
    """
    if not tags:
        return None

    cmd = tags[0][0].upper()
    arg = tags[0][1].strip()

    if cmd == "OPEN":
        app_name = arg.replace('"', '').replace("'", "").strip()
        if not app_name:
            return None
        return template_render("app_open", app=app_name)

    if cmd == "CLOSE":
        app_name = arg.replace('"', '').replace("'", "").strip()
        if not app_name:
            return None
        if app_name.startswith("ALL_"):
            real_name = app_name[4:]
            return template_render("app_close_all", app=real_name)
        return template_render("app_close", app=app_name)

    if cmd == "SYS":
        return _resolve_sys_template(arg)

    if cmd == "WINDOW":
        return _resolve_window_template(arg)

    if cmd == "TASK":
        return _resolve_task_template(arg)

    if cmd == "SCHED":
        return template_render("schedule_set")

    return None


def _parse_params(param_str: str) -> dict:
    """Parse 'key=value key2=value2' into dict."""
    params = {}
    for pair in param_str.strip().split():
        if "=" in pair:
            k, v = pair.split("=", 1)
            params[k.strip()] = v.strip()
    return params


def _resolve_sys_template(arg: str) -> str:
    """Map ###SYS: params to template category."""
    params = _parse_params(arg)
    action = params.get("action", "")
    value = params.get("value", "")

    mapping = {
        "volume_up": "volume_up",
        "volume_down": "volume_down",
        "volume_set": "volume_set",
        "volume_mute": "volume_mute",
        "volume_unmute": "volume_unmute",
        "volume_get": "volume_up",
        "brightness_up": "brightness_up",
        "brightness_down": "brightness_down",
        "brightness_set": "brightness_set",
        "brightness_get": "brightness_up",
        "battery": "battery_check",
        "wifi_on": "wifi_on",
        "wifi_off": "wifi_off",
        "bluetooth_on": "bluetooth_on",
        "bluetooth_off": "bluetooth_off",
        "media_play_pause": "media_play_pause",
        "media_next": "media_next",
        "media_prev": "media_prev",
        "media_stop": "media_play_pause",
        "dark_mode_on": "dark_mode_on",
        "dark_mode_off": "dark_mode_off",
        "night_light_on": "night_light_on",
        "night_light_off": "night_light_off",
        "dnd_on": "dnd_on",
        "dnd_off": "dnd_off",
        "airplane_on": "airplane_on",
        "airplane_off": "airplane_off",
    }

    category = mapping.get(action)
    if not category:
        return None

    return template_render(category, value=value)


def _resolve_window_template(arg: str) -> str:
    """Map ###WINDOW: params to template category."""
    params = _parse_params(arg)
    action = params.get("action", "")
    target = params.get("target", "").replace(",", " and ")
    position = params.get("position", "")

    mapping = {
        "minimize": "window_minimize",
        "maximize": "window_maximize",
        "snap": "window_snap",
        "focus": "window_focus",
        "center": "window_minimize",
        "layout": "window_layout",
        "minimize_all": "window_desktop",
        "show_desktop": "window_desktop",
        "swap": "window_layout",
        "pin": "window_pin",
        "unpin": "window_unpin",
        "fullscreen": "window_maximize",
        "solid": "window_unpin",
        "close_window": "window_close",
        "undo": "generic_done",
        "list": "generic_done",
        "transparent": "generic_done",
    }

    category = mapping.get(action, "generic_done")
    return template_render(
        category, target=target, position=position
    )


def _resolve_task_template(arg: str) -> str:
    """Map ###TASK: params to template category."""
    params = _parse_params(arg)
    action = params.get("action", "")

    mapping = {
        "create": "task_created",
        "list": "task_list",
        "complete": "task_completed",
        "delete": "task_deleted",
    }

    category = mapping.get(action, "generic_done")
    return template_render(category)