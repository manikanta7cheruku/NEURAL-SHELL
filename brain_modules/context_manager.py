"""
brain_modules/context_manager.py

Compatibility shim. Conversation history now lives in chat_history.py and is
sent to the model as structured chat messages, not as a text blob.

This module keeps the old function names so any caller that still imports
them keeps working, but writes are no-ops: the LLM layer is the only writer
of model history (so commands and greetings can never pollute it).
"""

from brain_modules import chat_history, session


def add_user_turn(speaker_id: str, text: str) -> None:
    """No-op. History is written by the LLM layer after a reply completes."""


def add_seven_turn(speaker_id: str, text: str) -> None:
    """No-op. See add_user_turn."""


def get_history(speaker_id: str) -> list:
    """Return history as legacy 'User: ...' / 'Seven: ...' lines."""
    key = session.resolve_key(speaker_id)
    lines = []
    for m in chat_history.get_messages(key, max_age_s=None):
        lines.append(("User: " if m["role"] == "user" else "Seven: ") + m["content"])
    return lines


def get_history_string(speaker_id: str) -> str:
    """Legacy text form of get_history()."""
    return "\n".join(get_history(speaker_id))


def clear_history(speaker_id: str = None) -> None:
    """Clear one speaker's history, or all history."""
    chat_history.clear(session.resolve_key(speaker_id) if speaker_id else None)


def assemble_prompt(system_prompt: str, speaker_id: str, web_context: str = "",
                    knowledge_context: str = "", memory_context: str = "") -> str:
    """Legacy single-string prompt. Kept only for callers that bypass the chat API."""
    parts = [system_prompt, ""]
    for block in (web_context, knowledge_context, memory_context):
        if block:
            parts += [block, ""]
    history = get_history_string(speaker_id)
    if history:
        parts += ["LOG:", history]
    parts.append("Seven:")
    return "\n".join(parts)
