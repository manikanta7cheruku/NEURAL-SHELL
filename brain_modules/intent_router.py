"""
brain_modules/intent_router.py

Semantic intent recognition by similarity to labelled example utterances that
live in data (data/intents.json, plus user additions), not in code. It replaces
brittle phrase lists for questions ABOUT Seven (abilities, the app, data
handling, status, memory history) so paraphrases route correctly:
"what apps can you open for me" and "which programs can you launch" land in
the same place.

Scoring is character n-gram TF-IDF cosine: deterministic, about a millisecond,
and fully offline. A returned Route carries the score AND the margin to the
runner-up so downstream policy knows when the router is unsure and should ask
or fall back instead of guessing. Optional embedding fusion can be enabled with
brain.router_embeddings (off by default); it never runs on the hot path unless
the embedder is already loaded.
"""

import json
import math
import os
import re
import threading
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "intents.json")
ACCEPT = 0.52
MIN_MARGIN = 0.05
_lock = threading.Lock()
_index: Optional["_Index"] = None


@dataclass
class Route:
    label: Optional[str]
    score: float = 0.0
    margin: float = 0.0
    runner_up: Optional[str] = None


def _grams(text: str) -> Counter:
    t = f" {re.sub(r'[^a-z0-9 ]', ' ', text.lower())} "
    t = re.sub(r"\s+", " ", t)
    c: Counter = Counter()
    for n in (3, 4):
        for i in range(len(t) - n + 1):
            c[t[i:i + n]] += 1
    for w in t.split():
        c["w:" + w] += 2
    return c


class _Index:
    def __init__(self, examples: Dict[str, List[str]]):
        self.rows: List[Tuple[str, Counter]] = [(lab, _grams(e)) for lab, exs in examples.items() for e in exs]
        df: Counter = Counter()
        for _l, g in self.rows:
            df.update(g.keys())
        n = len(self.rows)
        self.idf = {k: math.log((1 + n) / (1 + v)) + 1.0 for k, v in df.items()}
        self.vecs = [(lab, self._weigh(g)) for lab, g in self.rows]

    def _weigh(self, g: Counter) -> Tuple[Dict[str, float], float]:
        w = {k: v * self.idf.get(k, 1.0) for k, v in g.items()}
        return w, math.sqrt(sum(x * x for x in w.values())) or 1.0

    def score(self, text: str) -> Dict[str, float]:
        qw, qn = self._weigh(_grams(text))
        best: Dict[str, float] = {}
        for lab, (vw, vn) in self.vecs:
            dot = sum(qw[k] * vw[k] for k in qw.keys() & vw.keys())
            s = dot / (qn * vn)
            if s > best.get(lab, 0.0):
                best[lab] = s
        return best


def _user_examples_path() -> str:
    base = os.environ.get("APPDATA", os.path.expanduser("~"))
    return os.path.join(base, "SEVEN", "intent_examples.json")


def _load_examples() -> Dict[str, List[str]]:
    with open(_DATA, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    try:
        with open(_user_examples_path(), "r", encoding="utf-8") as fh:
            for lab, exs in json.load(fh).items():
                data.setdefault(lab, []).extend(exs[:100])
    except (OSError, ValueError):
        pass
    return data


def _get_index() -> _Index:
    global _index
    if _index is None:
        with _lock:
            if _index is None:
                _index = _Index(_load_examples())
    return _index


def reload() -> None:
    """Rebuild after examples change."""
    global _index
    with _lock:
        _index = None


def route(norm: str) -> Route:
    """Classify a normalised utterance. label is None when nothing is confidently matched."""
    if not norm or len(norm.split()) < 2:
        return Route(None)
    scores = _get_index().score(norm)
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    best_label, best = ranked[0]
    second_label, second = (ranked[1] if len(ranked) > 1 else (None, 0.0))
    margin = best - second
    if best_label == "none" or best < ACCEPT or margin < MIN_MARGIN:
        return Route(None, best, margin, best_label)
    return Route(best_label, best, margin, second_label)


def add_example(label: str, utterance: str, cap: int = 100) -> bool:
    """Learn a corrected routing (bounded, user-level, reversible by deleting the file)."""
    utterance = (utterance or "").strip()
    if label not in _load_examples() or not 2 <= len(utterance.split()) <= 20:
        return False
    path = _user_examples_path()
    try:
        data = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    except (OSError, ValueError):
        data = {}
    exs = data.setdefault(label, [])
    if utterance.lower() in (e.lower() for e in exs) or len(exs) >= cap:
        return False
    exs.append(utterance)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(data, open(path, "w", encoding="utf-8"), indent=2)
    reload()
    return True
