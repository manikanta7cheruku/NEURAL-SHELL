"""
brain_modules/chat_title.py

Names a chat after what it is about ("Brightness and volume", "Operating systems notes") instead of its first
message cut at 48 characters. Runs in the background after the first exchange and again after the third, with a
tiny call to the local model. A chat the user renamed is never touched: only a title that still equals the
automatic one (the start of the first message) is replaced.
"""

import logging
import re
import threading

_log = logging.getLogger("seven.chat_title")
_RETITLE_AT = (2, 6)                 # message counts: after the first exchange, then after the third
_running = set()


def _auto_title(first_user_text: str) -> str:
    return re.sub(r"\s+", " ", first_user_text)[:48]


def _clean(title: str) -> str:
    title = title.strip().strip('"\'`*#.').strip()
    title = re.sub(r"^(?:title|chat title)\s*:\s*", "", title, flags=re.I)
    title = title.splitlines()[0] if title else ""
    words = title.split()
    if not 1 <= len(words) <= 7 or len(title) > 48:
        return ""
    return title[0].upper() + title[1:]


def maybe_retitle(conv_id: str, model: str) -> None:
    """Start a background retitle when this chat just reached a retitle point."""
    if not conv_id or conv_id in _running:
        return
    try:
        from memory import conversation_store
        conv = conversation_store.get_conversation(conv_id)
    except Exception:
        return
    if not conv or conv.get("message_count") not in _RETITLE_AT:
        return
    _running.add(conv_id)
    threading.Thread(target=_retitle, args=(conv_id, model), daemon=True, name="ChatTitle").start()


def _retitle(conv_id: str, model: str) -> None:
    try:
        from memory import conversation_store
        from brain_modules import ollama_client
        conv = conversation_store.get_conversation(conv_id) or {}
        msgs = conversation_store.get_messages(conv_id, limit=8)
        users = [m["content"] for m in msgs if m.get("role") == "user"]
        if not users:
            return
        current = conv.get("title") or ""
        if current and current != _auto_title(users[0]):
            return                                        # renamed by the user, or already given a topic title
        lines = "\n".join(f"{m['role']}: {m['content'][:200]}" for m in msgs[:6])
        payload = {
            "model": model, "keep_alive": "24h",
            "messages": [
                {"role": "system", "content": "You name chats. Reply with only a title of 2 to 5 words that says what "
                                              "the chat is about. No quotes, no punctuation at the end."},
                {"role": "user", "content": lines},
            ],
            "options": {"temperature": 0.2, "num_predict": 16},
        }
        title = _clean(ollama_client.chat_once(payload))
        if title:
            conversation_store.rename(conv_id, title)
    except Exception as exc:
        _log.debug("chat title skipped: %s", exc)
    finally:
        _running.discard(conv_id)
