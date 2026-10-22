"""
brain_modules/decision_policy.py

Adaptive reasoning and uncertainty. Given the evidence the earlier layers
gathered, decide HOW to answer:

    chat      ordinary conversational answer
    grounded  answer from retrieved evidence (web, documents, memory)
    deep      a hard question: more room, lower temperature, careful wording
    clarify   the request is ambiguous; ask one short question

The decision also records what is UNCERTAIN so the model is told, in plain
text, what it must not guess (no stored evidence, live data unavailable,
unclear intent). Cheap by design: pure functions over data already computed.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional

_DEEP_MARKERS = (
    "compare", "versus", " vs ", "trade-off", "tradeoff", "pros and cons", "step by step", "plan ", "design ",
    "architecture", "debug", "why does", "why is", "how would", "explain how", "algorithm", "optimize",
    "difference between", "should i", "analyze", "analyse", "strategy", "root cause",
)


@dataclass
class Decision:
    mode: str = "chat"
    reasons: List[str] = field(default_factory=list)
    uncertainty: List[str] = field(default_factory=list)
    token_multiplier: float = 1.0
    temperature_cap: Optional[float] = None
    clarify: Optional[str] = None


def complexity(raw: str) -> float:
    """0..1 estimate of how much reasoning a message needs."""
    t = f" {(raw or '').lower()} "
    score = 0.0
    words = len(t.split())
    if words > 30:
        score += 0.3
    elif words > 18:
        score += 0.15
    score += min(0.5, 0.25 * sum(1 for m in _DEEP_MARKERS if m in t))
    if "```" in t or re.search(r"\b(error|exception|traceback|stack trace|bug)\b", t):
        score += 0.2
    if t.count("?") > 1:
        score += 0.1
    return min(1.0, score)


def decide(ctx, config=None) -> Decision:
    d = Decision()
    outcome = getattr(ctx, "web_outcome", None)

    if getattr(ctx, "ambiguity", None):
        names = ctx.ambiguity
        d.mode, d.clarify = "clarify", f"Do you mean {' or '.join(names[:3])}?"
        d.reasons.append("ambiguous reference")
        return d

    if outcome is not None and outcome.status == "ok":
        d.mode = "grounded"
        d.reasons.append("live results retrieved")
        d.temperature_cap = 0.2
    elif outcome is not None and outcome.needed:
        d.uncertainty.append(
            f"Live information is unavailable ({outcome.status}). Do not guess current facts; say plainly what "
            "you cannot verify and answer only from general knowledge, labelled as possibly out of date.")
    if getattr(ctx, "knowledge_context", ""):
        d.mode = "grounded"
        d.temperature_cap = 0.2
        d.reasons.append("document evidence retrieved")
    if getattr(ctx, "memory_facts", None):
        d.reasons.append("personal memory retrieved")
    elif getattr(ctx, "recall_query", None) is not None:
        d.uncertainty.append("The user asked about themselves but nothing is stored. Say you don't know yet.")

    intent = getattr(ctx, "intent", None)
    if intent is not None and getattr(intent, "label", None) and intent.margin < 0.05:
        d.uncertainty.append("The request could mean more than one thing. If it matters, ask one short question.")

    if d.mode == "chat" and complexity(ctx.prompt_text) >= 0.5:
        d.mode = "deep"
        d.token_multiplier, d.temperature_cap = 1.6, 0.3
        d.reasons.append("complex request")
        d.uncertainty.append("Work through this carefully before answering. If you are not sure of a step, say so.")
    return d


_CLAIM = re.compile(r"\byou (?:told me|said|mentioned|chose|picked|decided|switched|prefer(?:red)?|love[ds]?|like[ds]?)\b"
                    r"|\bbecause you\b|\byour (?:reason|motivation) (?:is|was)\b", re.IGNORECASE)


def unsupported_personal_claim(reply: str, ctx) -> bool:
    """
    True when the reply asserts something about the user's history or motives
    but no stored fact, retrieved snippet or in-chat statement supports it.
    Used to refuse such a reply (text mode) and to record the failure (streams).
    """
    if not _CLAIM.search(reply or ""):
        return False
    evidence = bool(getattr(ctx, "memory_facts", None)) or bool(getattr(ctx, "hints", None))
    st = getattr(ctx, "state", None)
    if evidence or (st is not None and getattr(st, "last_recalled", None)):
        return False
    return len([m for m in (getattr(ctx, "history_len", 0),) if m]) == 0 and not getattr(ctx, "had_history", False)
