"""
=============================================================================
LAYER 5.3: DOCUMENTS

Finds passages in the user's document library for the model to answer from (knowledge/core.py builds the
block and its formatting rules: tables, lists, page citations).

Two cases:
    - The chat has documents attached (the paperclip in the Console, or "Ask Seven" on the Knowledge page).
      Every question in that chat is about them, so we always search them. Summaries and outlines get
      passages from across the whole document.
    - No attachment: search the whole library only when the question looks like study material or points at
      a document, and keep only passages that clearly match.
=============================================================================
"""

import re

from colorama import Fore
from brain_modules.layer_result import LayerResult

_DOC_REFERENCE = re.compile(
    r"\b(?:in|from|according to|based on) (?:the|my|this|that) (?:file|document|doc|pdf|notes|book|textbook|paper|"
    r"slides?|deck|sheet|spreadsheet|chapter|syllabus)\b|\b(?:my|the|this|uploaded) (?:notes|pdf|document|textbook|"
    r"syllabus|slides)\b|\bsummari[sz]e\b|\buploaded\b", re.I)

_STUDY = re.compile(
    r"\b(?:explain|define|definition|describe|difference between|compare|summari[sz]e|what (?:is|are|was|were) (?:a |an |the )?"
    r"\w+|how (?:does|do|is|are)|why (?:does|do|is|are)|list (?:the|all)|types of|advantages|disadvantages|formula|"
    r"theorem|derive|example of|steps|chapter|unit \d|question \d|mcq|quiz me|important questions)\b", re.I)

_NOT_FOR_DOCS = re.compile(
    r"^(?:open|close|play|pause|mute|unmute|set|turn|remind|schedule|launch|start|stop)\b|\b(?:volume|brightness|"
    r"weather|what time|what day|battery)\b", re.I)


def _context_tokens(deps) -> int:
    try:
        from brain_modules import model_catalog
        return model_catalog.context_window(deps.get("model_name") or "")
    except Exception:
        return 4096


def process(ctx, deps):
    if ctx.is_command or ctx.is_greeting or ctx.is_action_cmd or "VISUAL_REPORT:" in ctx.prompt_text:
        return LayerResult.pass_through()
    if _NOT_FOR_DOCS.search(ctx.clean_in):
        return LayerResult.pass_through()
    try:
        from knowledge import core, store
    except Exception:
        return LayerResult.pass_through()

    attached = store.attached(ctx.conversation_id) + [d for d in getattr(ctx, "documents", []) if d]
    attached = list(dict.fromkeys(i for i in attached if (store.get(i) or {}).get("status") == "ready"))
    query = ctx.resolved_text or ctx.prompt_text
    if attached:
        found = core.context_for(query, attached, _context_tokens(deps), scoped=True)
    else:
        if not store.has_documents() or len(ctx.words) < 3:
            return LayerResult.pass_through()
        if not (_DOC_REFERENCE.search(query) or _STUDY.search(query)):
            return LayerResult.pass_through()
        found = core.context_for(query, None, _context_tokens(deps), scoped=bool(_DOC_REFERENCE.search(query)))

    if found["text"]:
        ctx.knowledge_context = found["text"]
        ctx.knowledge_hits = [{"name": h["name"], "label": h.get("label") or h.get("section") or ""}
                              for h in found["hits"] if found["whole"] or h["keyword"] > 0 or h["score"] >= 0.35]
        ctx.knowledge_whole = found["whole"]
        print(Fore.CYAN + f"[BRAIN] Documents: {len(found['hits'])} passages"
                          f"{' across the whole document' if found['whole'] else ''}")
    return LayerResult.pass_through()
