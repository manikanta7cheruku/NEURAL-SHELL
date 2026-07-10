"""
=============================================================================
LAYER 4.5h: TRIGGER / WORKSPACE VOICE DETECTION

Catches voice commands for trigger and workspace management:

TRIGGER FIRE:
  "Seven focus"           → fires trigger named "focus"
  "Seven chrome"          → fires trigger with voice_phrase "chrome"

WORKSPACE:
  "Save current workspace as Focus"
  "Save this workspace as Morning"
  "Open workspace Focus"
  "Restore Focus workspace"
  "Switch to Focus"

Emits ###TRIGGER: and ###WORKSPACE: tags for handler execution.

Tag format:
  ###TRIGGER: action=fire phrase=focus
  ###WORKSPACE: action=save name=Focus
  ###WORKSPACE: action=restore name=Focus
=============================================================================
"""

from colorama import Fore
from brain_modules.layer_result import LayerResult


# ─────────────────────────────────────────────────────────────────────────
# WORKSPACE TRIGGERS
# ─────────────────────────────────────────────────────────────────────────

_WORKSPACE_SAVE_TRIGGERS = [
    "save current workspace as",
    "save this workspace as",
    "save workspace as",
    "remember this workspace as",
    "remember workspace as",
    "save my workspace as",
    "create workspace",
    "new workspace",
]

_WORKSPACE_RESTORE_TRIGGERS = [
    "open workspace",
    "restore workspace",
    "switch to workspace",
    "load workspace",
    "launch workspace",
    "open my workspace",
    "restore my workspace",
    "switch to",
    "go to workspace",
]

_WORKSPACE_LIST_TRIGGERS = [
    "show my workspaces",
    "list workspaces",
    "what workspaces",
    "my workspaces",
    "show workspaces",
]


def process(ctx, deps):
    clean_in = ctx.clean_in

    # ── Workspace save ─────────────────────────────────────────────
    for trigger in sorted(_WORKSPACE_SAVE_TRIGGERS, key=len, reverse=True):
        if trigger in clean_in:
            name = clean_in.replace(trigger, "").strip()
            # Strip filler words
            for art in ["the ", "a ", "my ", "called "]:
                if name.startswith(art):
                    name = name[len(art):].strip()
            name = name.strip('.,!-:;"\' ')

            if not name:
                return LayerResult.stop(
                    "What should I call this workspace? "
                    'Say "save workspace as Focus" for example.'
                )

            # Use pipe delimiter for multi-word names
            name_safe = name.replace(" ", "|||")
            ctx.is_command = True
            return LayerResult.stop(
                f"Scanning your desktop to save workspace '{name}'. "
                f"###WORKSPACE: action=save name={name_safe}"
            )

    # ── Workspace restore ──────────────────────────────────────────
    for trigger in sorted(_WORKSPACE_RESTORE_TRIGGERS, key=len, reverse=True):
        if trigger in clean_in:
            name = clean_in.replace(trigger, "").strip()
            for art in ["the ", "a ", "my ", "called "]:
                if name.startswith(art):
                    name = name[len(art):].strip()
            name = name.strip('.,!-:;"\' ')

            if not name:
                return LayerResult.stop(
                    "Which workspace? Say the name, like 'open workspace Focus'."
                )

            name_safe = name.replace(" ", "|||")
            ctx.is_command = True
            return LayerResult.stop(
                f"Opening workspace '{name}'. "
                f"###WORKSPACE: action=restore name={name_safe}"
            )

    # ── Workspace list ─────────────────────────────────────────────
    if any(t in clean_in for t in _WORKSPACE_LIST_TRIGGERS):
        ctx.is_command = True
        return LayerResult.stop("###WORKSPACE: action=list")

    # ── Voice trigger fire ─────────────────────────────────────────
    # Check if input matches any registered voice phrase
    # Voice phrases are stored in DB, loaded at daemon startup
    # Here we check via API or direct DB
    try:
        from backend.routes.triggers import db_get_by_voice_phrase

        # User says "Seven focus" → clean_in = "focus" (wake word stripped)
        # Or user says "seven open focus" → clean_in = "open focus"
        # Try the full clean input first, then individual words
        phrases_to_try = [clean_in]

        # Also try removing common prefixes
        _voice_prefixes = [
            "open ", "launch ", "start ", "run ",
            "activate ", "fire ", "trigger ",
        ]
        for prefix in _voice_prefixes:
            if clean_in.startswith(prefix):
                stripped = clean_in[len(prefix):].strip()
                if stripped:
                    phrases_to_try.append(stripped)

        for phrase in phrases_to_try:
            trigger = db_get_by_voice_phrase(phrase)
            if trigger:
                phrase_safe = phrase.replace(" ", "|||")
                ctx.is_command = True
                return LayerResult.stop(
                    f"Firing trigger '{trigger['name']}'. "
                    f"###TRIGGER: action=fire phrase={phrase_safe}"
                )

    except Exception as e:
        # DB not available or triggers not set up — silently pass through
        pass

    return LayerResult.pass_through()