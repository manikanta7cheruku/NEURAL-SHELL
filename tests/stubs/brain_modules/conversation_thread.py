"""Test stub used only when the real brain_modules/conversation_thread.py is absent (standalone runs)."""
import re
import threading


class ConversationThread:
    _lock = threading.Lock()
    _threads = {}
    _metadata = {}
    _max_turns = 10

    @classmethod
    def add_turn(cls, sid, user, reply):
        sid = sid or "default"
        reply = re.sub(r"###\w+:\s*\S+", "", reply).strip()
        if not user.strip() or not reply:
            return
        with cls._lock:
            cls._threads.setdefault(sid, []).append((user.strip(), reply))
            if len(cls._threads[sid]) > cls._max_turns:
                cls._threads[sid].pop(0)

    @classmethod
    def get_turns(cls, sid, limit=5):
        with cls._lock:
            return list(cls._threads.get(sid or "default", [])[-limit:])

    @classmethod
    def clear(cls, sid):
        with cls._lock:
            cls._threads[sid] = []
            cls._metadata[sid] = {}

    @classmethod
    def set_metadata(cls, sid, key, value):
        with cls._lock:
            d = cls._metadata.setdefault(sid, {})
            if value is None:
                d.pop(key, None)
            else:
                d[key] = value

    @classmethod
    def get_metadata(cls, sid, key, default=None):
        with cls._lock:
            return cls._metadata.get(sid, {}).get(key, default)
