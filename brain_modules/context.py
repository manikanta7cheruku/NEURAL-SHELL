"""
brain_modules/context.py

Shared context passed to every layer in the brain pipeline.

Layers read from it and some write to it (the memory layer fills
memory_facts, the web layer fills web_context, the LLM layer consumes them).

NEW IN THIS VERSION:
    norm_in        contraction-expanded, punctuation-free input for matching
    speaker_key    the one storage key from session.resolve_key()
    stream_mode    "sentence" (voice), "token" (console SSE) or "text" (string)
    memory_future  semantic retrieval started early, awaited only when needed
    recall_query   set when the user asked a direct question about a stored fact
    answered_by    name of the layer that produced the reply
"""

import time


class BrainContext:
    """Runtime context for one call to brain.think()."""

    def __init__(self, prompt_text, speaker_id, user_name):
        # Inputs
        self.prompt_text = prompt_text
        self.speaker_id = speaker_id
        self.user_name = user_name
        self.speaker_name = user_name if user_name else "there"
        self.speaker_key = ""
        self.started_at = time.time()
        self.stream_mode = "sentence"

        # Cleaned input (layer 0)
        self.clean_in = ""
        self.norm_in = ""
        self.words = []
        self.first_word = ""

        # Classifier flags (layer 0)
        self.is_command = False
        self.is_greeting = False
        self.is_action_cmd = False

        self.FILE_WORDS = {
            "resume", "cv", "pdf", "document", "photo", "image", "screenshot",
            "video", "invoice", "contract", "presentation", "spreadsheet", "edit", "travel",
        }
        self.ALWAYS_FILE_WORDS = {
            "resume", "cv", "folder", "pdf", "document", "photo", "image",
            "screenshot", "video", "report", "invoice", "contract",
            "presentation", "spreadsheet", "edit",
        }

        # Accumulators
        self.memory_context = ""
        self.memory_facts = []
        self.memory_future = None
        self.recall_query = None
        self.knowledge_context = ""
        self.web_context = ""
        self.web_searched = False

        # Signals between layers
        self.new_user_name = None
        self.llm_note = ""            # legacy, unused by the new LLM layer
        self.proactive_hint = ""
        self.inject_capabilities = False
        self.answered_by = ""

    def resolve_memory(self, timeout_s: float = 0.45) -> None:
        """
        Wait (briefly) for the semantic search started by the memory layer.

        Retrieval overlaps with the web, knowledge and fact layers instead of
        blocking in front of them. If it is not ready in time the turn simply
        proceeds without memory; it never stalls the reply.
        """
        fut = self.memory_future
        if fut is None:
            return
        self.memory_future = None
        try:
            facts = fut.result(timeout=timeout_s)
        except Exception:
            facts = []
        if facts:
            self.memory_facts = list(facts)
            self.memory_context = "\n".join(f"- {f}" for f in facts)
