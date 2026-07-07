"""
=============================================================================
brain_modules/context.py

Shared context passed to every layer in the brain pipeline.

Contains:
    - Original prompt_text and speaker_id from main.py
    - Cleaned input (clean_in, words, first_word)
    - Classifier flags (is_command, is_greeting, _is_action_cmd)
    - File word sets (used by multiple layers)
    - Layer 5 accumulators (memory_context, knowledge_context, web_context)
    - USER_NAME reference and speaker_name

Layers read from this context, and some layers write to it
(e.g. memory layer writes memory_context which LLM layer uses).

WHY A CONTEXT OBJECT:
    Alternative: pass 10+ arguments to every layer function.
    That's fragile and ugly. A context object keeps the API clean.
    Adding a new field affects ONE class, not every layer signature.
=============================================================================
"""


class BrainContext:
    """
    Runtime context for one call to brain.think().
    Layers read and mutate this object as they process the input.
    """

    def __init__(self, prompt_text, speaker_id, user_name):
        # ── Inputs from main.py ──────────────────────────────────
        self.prompt_text = prompt_text
        self.speaker_id  = speaker_id
        self.user_name   = user_name

        # ── Speaker resolution (set by input_prep layer) ─────────
        self.speaker_name = user_name if user_name else "there"

        # ── Cleaned input (set by input_prep layer) ──────────────
        self.clean_in   = ""
        self.words      = []
        self.first_word = ""

        # ── Classifier flags (set by input_prep layer) ───────────
        self.is_command     = False
        self.is_greeting    = False
        self.is_action_cmd  = False

        # ── File word sets (populated by input_prep layer) ───────
        # Words that are NEVER app names — always file/folder references.
        # Used by file search layer AND personal question filter layer.
        self.FILE_WORDS = {
            "resume", "cv", "pdf", "document", "photo",
            "image", "screenshot", "video", "invoice",
            "contract", "presentation", "spreadsheet", "edit", "travel",
        }
        self.ALWAYS_FILE_WORDS = {
            "resume", "cv", "folder", "pdf", "document", "photo",
            "image", "screenshot", "video", "report", "invoice",
            "contract", "presentation", "spreadsheet", "edit",
        }

        # ── Layer accumulators (set by memory/knowledge/web layers) ──
        self.memory_context    = ""
        self.knowledge_context = ""
        self.web_context       = ""
        self.web_searched      = False

        # ── Signal that USER_NAME must be updated in brain.py ────
        # If a layer wants to update USER_NAME (e.g. name-setting layer),
        # it sets this. brain.py reads it after pipeline runs.
        self.new_user_name = None