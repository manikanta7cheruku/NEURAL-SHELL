"""
brain_modules/response_filter.py

Everything that happens to model output between Ollama and the user.

WHY THIS EXISTS:
    Small local models sometimes emit role prefixes ("Seven:"), echo our
    delimiter tags, or invent action tags ("###OPEN: chrome"). None of that
    may ever reach the user or the action executor. The sanitizer works on
    the token stream, so it does not delay the first token (only the first
    dozen characters are held to check for a role prefix).

    The chunker turns the token stream into speakable sentences for the voice
    pipeline and flushes the FIRST chunk early at a clause boundary, so the
    mouth can start talking before the first full sentence is finished.
"""

import re
from typing import List

_TAG_RE = re.compile(
    r"</?(?:reference_only|memory_context|identity|character|behavioral_rules|web_results|"
    r"knowledge_context|capabilities|recent_action|suggestion_opportunity|clock|plan_info|user_message)>",
    re.IGNORECASE,
)
_HEAD_PREFIX_RE = re.compile(r"^\s*(?:seven|assistant)\s*:\s*", re.IGNORECASE)
_PARTIAL_TAG_RE = re.compile(r"</?[a-z_]*$")
_TRAILING_HASH_RE = re.compile(r"#{1,2}$")

_ABBREVIATIONS = frozenset({
    "dr", "mr", "mrs", "ms", "prof", "sr", "jr", "vs", "etc", "eg", "ie", "st", "no", "inc",
})

_TRAILER_SENTENCES = frozenset({
    "go ahead", "what do you need", "whats your next request", "how can i help",
    "how can i help you", "is there anything else", "anything else",
    "what would you like", "whats next", "what can i do for you",
    "ready when you are", "standing by", "let me know if you need anything",
    "feel free to ask", "just let me know",
})

_APOLOGY_OPENERS = (
    r"^you'?re absolutely right,?\s*", r"^i apologize,?\s*", r"^my apologies,?\s*",
    r"^sorry (?:about|for) (?:that|the confusion),?\s*",
)


def is_trailer(sentence: str) -> bool:
    """True for assistant-style filler sentences like 'Anything else?'."""
    key = re.sub(r"[^a-z ]", "", sentence.lower().replace("'", "")).strip()
    return key in _TRAILER_SENTENCES


class StreamSanitizer:
    """
    Incremental cleaner for a token stream.

    feed(token) returns the text that is safe to show now (possibly "").
    Once an action tag ("###") appears, `stopped` becomes True and nothing
    further is emitted. Call flush() when the stream ends.
    """

    def __init__(self) -> None:
        self._head = ""
        self._head_done = False
        self._carry = ""
        self.stopped = False

    @staticmethod
    def _strip_head(text: str) -> str:
        text = _HEAD_PREFIX_RE.sub("", text)
        return text.lstrip('"\u201c') if text.startswith(('"', "\u201c")) else text

    def _emit(self, buf: str, final: bool) -> str:
        cut = len(buf)
        if not final:
            m = _TRAILING_HASH_RE.search(buf)
            if m:
                cut = min(cut, m.start())
            lt = buf.rfind("<")
            if lt != -1 and ">" not in buf[lt:] and len(buf) - lt <= 24 and _PARTIAL_TAG_RE.match(buf[lt:]):
                cut = min(cut, lt)
        self._carry = buf[cut:]
        return _TAG_RE.sub("", buf[:cut])

    def feed(self, token: str) -> str:
        if self.stopped or not token:
            return ""
        if not self._head_done:
            self._head += token
            if len(self._head) < 12 and "\n" not in self._head:
                return ""
            self._head_done = True
            token = self._strip_head(self._head)
            self._head = ""
        buf = self._carry + token
        self._carry = ""
        idx = buf.find("###")
        if idx != -1:
            self.stopped = True
            return self._emit(buf[:idx], final=True)
        return self._emit(buf, final=False)

    def flush(self) -> str:
        """Release anything still held back when the stream ends."""
        if self.stopped:
            return ""
        out = ""
        if not self._head_done:
            self._head_done = True
            out = self._strip_head(self._head)
            self._head = ""
        tail = self._carry + out
        self._carry = ""
        tail = re.sub(r"#{1,}$", "", tail)
        return _TAG_RE.sub("", tail)


class SentenceChunker:
    """
    Splits streamed text into sentences for text-to-speech.

    The first chunk is flushed early at a comma/colon/dash once it is long
    enough, which lowers the time to first spoken word.
    """

    def __init__(self, first_flush_chars: int = 48) -> None:
        self._buf = ""
        self._first_done = False
        self._first_flush = first_flush_chars

    def _boundary(self) -> int:
        """Index just after the first usable sentence end, or -1."""
        for m in re.finditer(r"[.!?]+(?=\s)", self._buf):
            prior = re.search(r"([A-Za-z0-9]+)$", self._buf[: m.start()])
            word = prior.group(1).lower() if prior else ""
            if word in _ABBREVIATIONS or word.isdigit() or (len(word) == 1 and word.isalpha()):
                continue
            return m.end()
        return -1

    def feed(self, text: str) -> List[str]:
        self._buf += text
        out: List[str] = []
        while True:
            end = self._boundary()
            if end == -1:
                break
            sentence = self._buf[:end].strip()
            self._buf = self._buf[end:].lstrip()
            if sentence:
                out.append(sentence)
                self._first_done = True
        if not self._first_done and len(self._buf) >= self._first_flush:
            cut = max(self._buf.rfind(", "), self._buf.rfind("; "),
                      self._buf.rfind(": "), self._buf.rfind(" - "))
            if cut >= 20:
                out.append(self._buf[: cut + 1].strip())
                self._buf = self._buf[cut + 1:].lstrip()
                self._first_done = True
        return out

    def flush(self) -> List[str]:
        rest = self._buf.strip()
        self._buf = ""
        return [rest] if rest else []


def clean_final(text: str) -> str:
    """Final cleanup for non-streamed replies."""
    if not text:
        return text
    t = _HEAD_PREFIX_RE.sub("", text)
    t = t.split("###", 1)[0]
    t = _TAG_RE.sub("", t).strip()
    for pattern in _APOLOGY_OPENERS:
        t = re.sub(pattern, "", t, flags=re.IGNORECASE).strip()
    parts = re.split(r"(?<=[.!?])\s+", t)
    while len(parts) > 1 and is_trailer(parts[-1]):
        parts.pop()
    t = " ".join(parts).strip()
    return t or "Understood."
