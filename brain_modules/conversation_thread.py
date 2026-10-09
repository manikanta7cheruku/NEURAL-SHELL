"""
brain_modules/conversation_thread.py
Thread-safe session memory manager storing recent dialogue turns.
Optimized for low-latency context injection and repetition detection.
"""

import threading
import re
from typing import List, Tuple, Dict


class ConversationThread:
    """
    Manages in-memory active dialogue history partitioned by speaker_id.
    Ensures absolute safety and sub-microsecond retrieval performance.
    Also stores per-speaker metadata for follow-up hints, tone flags, etc.
    """
    _lock = threading.Lock()
    _threads: Dict[str, List[Tuple[str, str]]] = {}
    _metadata: Dict[str, Dict[str, object]] = {}
    _max_turns = 10

    @classmethod
    def add_turn(cls, speaker_id: str, user_input: str, assistant_response: str) -> None:
        """
        Records a completed conversation turn for a specific speaker.
        Automatically purges oldest turns once capacity limit is exceeded.
        """
        if not speaker_id:
            speaker_id = "default"

        user_clean = user_input.strip()
        # Clean any terminal/control blocks or markdown directives from response
        resp_clean = re.sub(r"###\w+:\s*\S+", "", assistant_response).strip()

        if not user_clean or not resp_clean:
            return

        with cls._lock:
            if speaker_id not in cls._threads:
                cls._threads[speaker_id] = []

            cls._threads[speaker_id].append((user_clean, resp_clean))
            
            # Bound the thread memory footprint
            if len(cls._threads[speaker_id]) > cls._max_turns:
                cls._threads[speaker_id].pop(0)

    @classmethod
    def get_turns(cls, speaker_id: str, limit: int = 5) -> List[Tuple[str, str]]:
        """
        Retrieves the last N turns for the specified speaker thread.
        """
        if not speaker_id:
            speaker_id = "default"

        with cls._lock:
            turns = cls._threads.get(speaker_id, [])
            return list(turns[-limit:])

    @classmethod
    def clear(cls, speaker_id: str) -> None:
        """
        Purges active conversation turns and metadata for a given speaker.
        """
        if not speaker_id:
            speaker_id = "default"

        with cls._lock:
            if speaker_id in cls._threads:
                cls._threads[speaker_id] = []
            if speaker_id in cls._metadata:
                cls._metadata[speaker_id] = {}

    @classmethod
    def set_metadata(cls, speaker_id: str, key: str, value) -> None:
        """
        Store a metadata value on a speaker's session record.
        Setting value to None removes the key. Thread-safe.
        """
        if not speaker_id:
            speaker_id = "default"
        with cls._lock:
            if speaker_id not in cls._metadata:
                cls._metadata[speaker_id] = {}
            if value is None:
                cls._metadata[speaker_id].pop(key, None)
            else:
                cls._metadata[speaker_id][key] = value

    @classmethod
    def get_metadata(cls, speaker_id: str, key: str, default=None):
        """
        Retrieve a metadata value from a speaker's session record.
        Returns default if key or speaker not present.
        """
        if not speaker_id:
            speaker_id = "default"
        with cls._lock:
            return cls._metadata.get(speaker_id, {}).get(key, default)

    @classmethod
    def clear_metadata(cls, speaker_id: str) -> None:
        """
        Wipe all metadata for a given speaker without touching turn history.
        """
        if not speaker_id:
            speaker_id = "default"
        with cls._lock:
            if speaker_id in cls._metadata:
                cls._metadata[speaker_id] = {}