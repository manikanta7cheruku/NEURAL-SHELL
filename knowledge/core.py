"""
knowledge/core.py

Turns passages from the document library (knowledge/store.py) into the <knowledge_context> block the model reads,
with the formatting rules for document answers: lead with the answer, tables for comparisons, lists for steps,
a page citation after each fact, and a plain "the document doesn't say" when it doesn't.
"""

from typing import List, Optional

from knowledge import store

_RULES = (
    "Answer from these passages of the user's documents. They may be a student's notes or textbook, so be accurate "
    "and clear.\n"
    "- Lead with the direct answer, then the detail.\n"
    "- Use a markdown table when comparing things or listing items with attributes (definitions, formulas, dates, "
    "differences, pros and cons). Use a numbered list for steps and a bulleted list for several points.\n"
    "- Use **bold** for key terms. Never use # headings.\n"
    "- After a fact, cite where it is, like (p. 4) or (slide 3); with several documents add the name: "
    "(notes.pdf, p. 4).\n"
    "- If the passages don't contain the answer, say the document doesn't cover it. Do not fill gaps from memory "
    "unless you say that part is general knowledge.\n"
    "- Quote formulas, numbers and definitions exactly as written.")


def _cite(hit: dict, many: bool) -> str:
    where = hit.get("label") or hit.get("section") or ""
    if many:
        return f"{hit['name']}, {where}" if where else hit["name"]
    return where or hit["name"]


def build_context(hits: List[dict], whole: bool = False) -> str:
    """The text placed inside <knowledge_context>, or "" when there is nothing to show."""
    if not hits:
        return ""
    names = list(dict.fromkeys(h["name"] for h in hits))
    many = len(names) > 1
    head = []
    for doc_id in dict.fromkeys(h["doc_id"] for h in hits):
        doc = store.get(doc_id) or {}
        line = f"Document: {doc.get('name', '')} ({doc.get('unit') or doc.get('pages', '')})"
        if whole and doc.get("headings"):
            line += "\nIts sections: " + "; ".join(
                h["title"] + (f" ({h['label']})" if h.get("label") else "") for h in doc["headings"][:30])
        head.append(line)
    hits = sorted(hits, key=lambda h: (names.index(h["name"]), h["index"])) if whole else hits
    body = []
    for h in hits:
        section = f" | {h['section']}" if h.get("section") and h.get("label") else ""
        body.append(f"[{_cite(h, many)}{section}]\n{h['text']}")
    note = ("These passages are spread across the whole document, so cover it from start to end."
            if whole else "These are the passages that best match the question.")
    return f"{_RULES}\n\n" + "\n".join(head) + f"\n{note}\n\n" + "\n\n".join(body)


def budget_chars(context_tokens: int) -> int:
    """Room for passages: the context window minus the system prompt, history and the answer."""
    return max(3000, min(22000, (context_tokens - 2000) * 3))


def fit(hits: List[dict], limit: int) -> List[dict]:
    out, used = [], 0
    for h in hits:
        if used + len(h["text"]) > limit and out:
            break
        out.append(h)
        used += len(h["text"])
    return out


def context_for(query: str, doc_ids: Optional[List[str]] = None, context_tokens: int = 4096,
                scoped: bool = False) -> dict:
    """Retrieve and format. scoped=True means the user attached or named these documents, so every question
    in that chat is about them and no relevance gate applies. Returns {"text", "hits", "whole"}."""
    limit = budget_chars(context_tokens)
    ids = doc_ids or store.ready_ids()
    whole = scoped and store.wants_whole_document(query)
    if whole:
        hits = store.spread(ids, limit)
    else:
        hits = store.search(query, ids, k=10)
        if scoped:                                 # keep the top few, then only passages that match at all
            hits = hits[:3] + [h for h in hits[3:] if h["keyword"] > 0 or h["score"] >= 0.25]
        else:
            hits = store.relevant(hits)
    hits = fit(hits, limit)
    return {"text": build_context(hits, whole), "hits": hits, "whole": whole}


# ── Kept for older callers (slash commands, the old routes) ───────────────

def search_knowledge(query, top_k=None):
    return context_for(query)["text"]


def get_knowledge_stats():
    s = store.stats()
    docs = store.documents()
    return {"total_chunks": s["passages"], "sources": [d["name"] for d in docs],
            "source_count": len(docs), "storage_mb": s["size_mb"]}


def clear_knowledge():
    store.clear()
    return True
