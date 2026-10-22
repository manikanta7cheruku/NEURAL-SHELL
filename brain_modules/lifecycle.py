"""
brain_modules/lifecycle.py

ONE place that understands "I finished X", "forget X", "complete my X task",
"check off X" and decides WHICH record the user means.

Why this exists
---------------
Seven keeps two different kinds of things the user wants done:

    goals   what the user is trying to achieve. Stored by Seven in learning.db
            (memory/learning_store.py). Only ever created from something the
            user explicitly said.
    tasks   concrete to-do items. Stored in the tasks database owned by the
            Dashboard / task API (backend/routes/tasks.py). Created only by an
            explicit "add task ...".

Before this module, a goal layer and a task layer each had their own pattern for
"I finished X". Whichever sat earlier in the pipeline answered, whether or not
it had anything to update, and the task layer replied "Got it." before any
task had been touched. This module replaces both with one resolver:

    1. parse       what does the user want (complete / drop), which words point
                   at the record, did they say "task" or "goal" explicitly
    2. resolve     look the reference up in BOTH stores (the Dashboard's tasks and
                   Seven's goals) and score every candidate
    3. decide      explicit "task"/"goal" wording wins; one clear match acts;
                   a goal and a task that both fit is a QUESTION, not a guess;
                   no match means saying nothing false (or passing on)
    4. act         goals are updated here and re-read before Seven says so;
                   tasks are handed to the task executor as a tag that names the
                   exact row (id), and the console/voice executor confirms only
                   after its own database check (see action_receipts.py)

What is deterministic, what is not
----------------------------------
    Deterministic   parsing, scoring, the decision table, state changes,
                    verification, and every reply that claims something changed.
                    Nothing a language model says can change a record.
    Semantic        paraphrases that the verb patterns miss are recognised by the
                    offline intent router (brain_modules/intent_router.py,
                    char n-gram similarity over data/intents.json). That is
                    still no LLM, and it only counts when a real record matches.
    Persistent      goals (learning.db), tasks (tasks db), clarifying questions
                    (conversation_state, this chat only), outcomes
                    (learning_store.outcomes).
    LLM             never used to decide or change state. The model only writes
                    ordinary conversation when this module passes.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from brain_modules import conversation_state as cs, intent_router, speech_acts
from brain_modules.goals import GOAL_VERBS
from memory import learning_store

_log = logging.getLogger("seven.lifecycle")

COMPLETE, DROP = "complete", "drop"
PENDING_TYPE = "lifecycle_choice"

# ----------------------------------------------------------------------------
# parsing
# ----------------------------------------------------------------------------
_PREFIX = r"(?:(?:please|kindly|go ahead and|just) )*(?:(?:can|could|would|will) you )?(?:(?:please|kindly) )*"
_ADV = r"(?:(?:have|had|just|already|finally|now|really|all) )*"
_DONE_VERBS = (r"(?:finished|completed|wrapped up|shipped|launched|published|submitted|delivered|accomplished|"
               r"achieved|passed|nailed|knocked out)")

_PATTERNS: List[Tuple[str, str, bool]] = [
    # (regex over the normalised text, action, explicit_command)
    (rf"^(?:i|we) {_ADV}{_DONE_VERBS}(?: with)? (?P<ref>.+)$", COMPLETE, False),
    (rf"^(?:i|we) (?:am|are) (?:now |finally |all )?(?:done|finished|through)(?: with)? (?P<ref>.+)$", COMPLETE, False),
    (rf"^(?:finally |just )?(?:finished|completed|done|through)(?: with)? (?P<ref>.+)$", COMPLETE, False),
    (rf"^(?P<ref>.+?) (?:is|are|was|were|got|has been|have been) (?:now |finally |all |already )?"
     rf"(?:done|complete|completed|finished|shipped|launched|submitted|delivered)(?: now| already)?$", COMPLETE, False),
    (rf"^{_PREFIX}(?:mark|set|tick|check|cross|strike) (?P<ref>.+?)(?: as| to)? (?:done|complete|completed|finished)"
     rf"(?: for me)?$", COMPLETE, True),
    (rf"^{_PREFIX}(?:check off|tick off|cross off|strike off|mark off|knock off|tick) (?P<ref>.+)$", COMPLETE, True),
    (rf"^{_PREFIX}(?:complete|finish|close out) (?P<ref>.+)$", COMPLETE, True),
    (rf"^{_PREFIX}(?:forget about|forget|drop|cancel|remove|delete|scrap|abandon|discard|stop tracking|get rid of)"
     rf" (?P<ref>.+)$", DROP, True),
    (rf"^(?:i|we) {_ADV}(?:gave up on|give up on|quit|abandoned|dropped|scrapped|am no longer "
     rf"(?:working on|doing|building|making|planning)|no longer want to|do not want to)"
     rf" (?P<ref>.+?)(?: anymore| any more)?$", DROP, False),
]
_COMPILED = [(re.compile(p), a, e) for p, a, e in _PATTERNS]

_TASK_WORDS = {"task", "tasks", "todo", "todos"}
_GOAL_WORDS = {"goal", "goals", "objective", "objectives"}
# Words that never help identify a record.
_NOISE = {
    "a", "an", "the", "my", "our", "your", "that", "this", "those", "these", "it", "them", "one", "ones",
    "of", "to", "for", "in", "on", "at", "by", "off", "from", "as", "with", "about", "up", "out", "and",
    "list", "item", "items", "please", "now", "already", "finally", "just", "all", "done", "complete",
    "completed", "finished", "do", "is", "are", "was", "were", "be", "i", "we", "also", "still", "anymore",
    "today", "tomorrow", "tonight", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
}
# Things that belong to other parts of Seven (reminders, window control ...): never ours.
_OTHER_DOMAIN = {"reminder", "reminders", "timer", "timers", "alarm", "alarms", "schedule", "schedules",
                 "trigger", "triggers", "hotkey", "hotkeys", "window", "windows", "volume", "brightness",
                 "wifi", "bluetooth", "app", "apps", "file", "files", "folder", "tab", "tabs", "chat", "conversation"}
# A statement of intent, a condition or a negation is not a report that something is done.
_NOT_A_REPORT = {"not", "never", "cannot", "cant", "yet", "nearly", "almost", "barely", "hardly", "want", "wanna",
                 "need", "plan", "hope", "wish", "going", "gonna", "will", "would", "should", "might", "maybe",
                 "if", "when", "once", "after", "before", "until", "because", "while", "unless", "whether"}
_ORDINALS = {"first": 0, "1": 0, "one": 0, "second": 1, "2": 1, "two": 1, "third": 2, "3": 2, "three": 2, "last": -1}
_DEADLINE_TAIL = re.compile(r"\b(?:by|before|until|due|on)\s+\w+(?:\s+\w+)?$")


@dataclass
class Intent:
    action: str                       # complete | drop
    reference: str                    # words that point at the record
    kind: Optional[str] = None        # task | goal | None (user did not say)
    explicit: bool = False            # an instruction ("mark X done"), not a report ("I finished X")
    via: str = "pattern"              # pattern | semantic


@dataclass
class Candidate:
    kind: str                         # goal | task
    id: int
    title: str
    score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": self.kind, "id": self.id, "title": self.title}


def _stem(tok: str) -> str:
    for suf in ("ing", "ed", "es", "s"):
        if tok.endswith(suf) and len(tok) - len(suf) >= 3:
            tok = tok[:-len(suf)]
            break
    return tok[:-1] if tok.endswith("e") and len(tok) > 3 else tok


def content_tokens(text: str) -> List[str]:
    """Meaningful, stemmed words of a phrase, in order, without filler."""
    n = _DEADLINE_TAIL.sub("", speech_acts.normalize(text))
    out = []
    for t in n.split():
        if t in _NOISE or t in _TASK_WORDS or t in _GOAL_WORDS:
            continue
        out.append(_stem(t))
    return out


def _record_tokens(title: str) -> set:
    toks = content_tokens(title)
    first = speech_acts.normalize(title).split(" ", 1)[0] if title else ""
    if len(toks) > 1 and first in GOAL_VERBS:
        toks = toks[1:]               # "finish the report" is about "report"; the verb is the goal's intent
    return set(toks)


def _score(ref: set, rec: set) -> float:
    inter = ref & rec
    if not inter or not any(len(t) > 3 for t in inter):
        return 0.0
    cov_ref, cov_rec = len(inter) / len(ref), len(inter) / len(rec)
    if cov_ref < 0.6 and cov_rec < 0.99:
        return 0.0
    return (cov_ref + cov_rec) / 2


def _strip_polite(n: str) -> str:
    return re.sub(rf"^{_PREFIX}", "", n)


def parse(text: str) -> Optional[Intent]:
    """Turn a message into an Intent, or None when it is not a complete/drop request."""
    raw = (text or "").strip()
    n = speech_acts.normalize(raw)
    if not n or len(n.split()) > 22:
        return None
    polite = _strip_polite(n)
    if speech_acts.is_question(raw, n) and polite == n:
        return None                    # "did I finish the report?" is a question, not a report
    for rx, action, explicit in _COMPILED:
        m = rx.match(n)
        if not m:
            continue
        if action == COMPLETE and (_NOT_A_REPORT & set(n.split())):
            return None
        words = set(n.split())
        kind = ("task" if words & _TASK_WORDS else "goal" if words & _GOAL_WORDS else None)
        if words & _TASK_WORDS and words & _GOAL_WORDS:
            kind = None
        ref = m.group("ref")
        ref_tokens = content_tokens(ref)
        if not ref_tokens:
            return Intent(action, "", kind, explicit)       # "mark it done": a command with no usable reference
        if kind is None and (_OTHER_DOMAIN & set(ref.split())):
            return None
        return Intent(action, " ".join(ref_tokens), kind, explicit)
    return _semantic(n)


def _semantic(n: str) -> Optional[Intent]:
    """Paraphrases the patterns miss ("got the report out the door"), via the offline intent router."""
    words = n.split()
    if not 3 <= len(words) <= 14 or (_NOT_A_REPORT & set(words)):
        return None
    try:
        route = intent_router.route(n)
    except Exception as exc:
        _log.debug("semantic lifecycle routing skipped: %s", exc)
        return None
    action = {"record_complete": COMPLETE, "record_drop": DROP}.get(route.label or "")
    if not action:
        return None
    ref = content_tokens(n)
    return Intent(action, " ".join(ref), None, False, via="semantic") if ref else None


def is_narrative(clean_in: str) -> bool:
    """True for "I finished X" (a report), false for "mark X done" (an instruction)."""
    return bool(re.match(r"^(?:i|we|ive|i've|im|i'm)\b", (clean_in or "").strip().lower()))


# ----------------------------------------------------------------------------
# task store
# ----------------------------------------------------------------------------
class TaskStoreError(Exception):
    """The task database could not be read."""


class SqliteTaskStore:
    """The Dashboard's tasks database (backend/routes/tasks.py). Reads for resolving, writes for the executor."""

    @staticmethod
    def _mod():
        try:
            from backend.routes import tasks
            return tasks
        except Exception as exc:
            raise TaskStoreError(str(exc)) from exc

    def pending(self) -> List[Dict[str, Any]]:
        m = self._mod()
        try:
            return [{"id": t["id"], "text": t["text"]} for t in m.db_get_pending_list()]
        except Exception as exc:
            raise TaskStoreError(str(exc)) from exc

    def get(self, task_id: int) -> Optional[Dict[str, Any]]:
        m = self._mod()
        with m._get_conn() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return m._row_to_dict(row) if row else None

    def find(self, search: str) -> Optional[Dict[str, Any]]:
        return self._mod().db_find_task_by_text(search)

    def complete(self, task_id: int) -> None:
        from datetime import datetime
        m = self._mod()
        with m._get_conn() as conn:
            conn.execute("UPDATE tasks SET completed = 1, completed_at = ? WHERE id = ?",
                         (datetime.now().isoformat(), task_id))
            conn.commit()

    def delete(self, task_id: int) -> None:
        m = self._mod()
        with m._get_conn() as conn:
            conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()


def _decode(value: str) -> str:
    return (value or "").replace("|||", " ").replace("_", " ").strip()


def execute_task_action(params: Dict[str, str], store=None) -> str:
    """
    The ONE place a ###TASK complete/delete tag changes anything. Used by the console executor
    (backend/routes/chat.py). Returns the task's text on verified success; raises on anything else,
    so the receipt is 'failed' and the reply is corrected instead of claiming success.
    """
    action = params.get("action", "")
    if action not in ("complete", "delete"):
        raise ValueError(f"unsupported task action {action!r}")
    store = store or SqliteTaskStore()
    task, tid = None, params.get("id", "")
    if tid.isdigit():
        task = store.get(int(tid))               # an id is exact: never fall back to a fuzzy search
        if task is None:
            raise LookupError("that task no longer exists")
    else:
        search = _decode(params.get("search", ""))
        task = store.find(search) if search else None
        if task is None:
            raise LookupError(f"no pending task matches '{search}'")
    if action == "complete":
        store.complete(task["id"])
        after = store.get(task["id"])
        if not after or not after.get("completed"):
            raise RuntimeError("the task is still open after the update")
    else:
        store.delete(task["id"])
        if store.get(task["id"]) is not None:
            raise RuntimeError("the task is still there after the delete")
    return task["text"]


def _store(deps) -> Any:
    return (deps or {}).get("tasks") or SqliteTaskStore()


# ----------------------------------------------------------------------------
# resolution
# ----------------------------------------------------------------------------
def find_candidates(speaker_key: str, ref_tokens: List[str], kind: Optional[str], deps) -> Tuple[List[Candidate], str]:
    """Every goal and pending task the reference could mean, best first. Second value: store error text."""
    ref, found, error = set(ref_tokens), [], ""
    if not ref:
        return [], error
    if kind in (None, "goal"):
        for g in learning_store.list_goals(speaker_key):
            s = _score(ref, _record_tokens(g["title"]))
            if s:
                found.append(Candidate("goal", g["id"], g["title"], s))
    if kind in (None, "task"):
        try:
            for t in _store(deps).pending():
                s = _score(ref, _record_tokens(t["text"]))
                if s:
                    found.append(Candidate("task", t["id"], t["text"], s))
        except TaskStoreError as exc:
            error = str(exc)
    found.sort(key=lambda c: -c.score)
    return found, error


def list_pending_tasks(deps) -> List[Dict[str, Any]]:
    try:
        return _store(deps).pending()
    except TaskStoreError:
        return []


# ----------------------------------------------------------------------------
# acting
# ----------------------------------------------------------------------------
def _set_goal_verified(goal_id: int, status: str) -> bool:
    """Write the status, read it back, report whether the change is really stored."""
    try:
        learning_store.set_goal_status(goal_id, status)
        row = learning_store.get_goal(goal_id)
    except Exception as exc:
        _log.warning("goal update failed: %s", exc)
        return False
    return bool(row and row["status"] == status)


def _tag(c: Candidate, action: str) -> str:
    text = re.sub(r"[#=]+", " ", c.title)
    text = re.sub(r"\s+", " ", text).strip().replace(" ", "|||")
    return f"###TASK: action={'complete' if action == COMPLETE else 'delete'} search={text} id={c.id}"


def _act(ctx, chosen: List[Candidate], action: str) -> str:
    """Apply the decision. Goals are changed and verified here; tasks are handed to the executor."""
    key = ctx.speaker_key
    said, tags = [], []
    for c in chosen:
        if c.kind == "goal":
            status = "done" if action == COMPLETE else "dropped"
            if _set_goal_verified(c.id, status):
                learning_store.record_outcome(key, "action", f"goal:{action}", "success", c.title,
                                              getattr(ctx, "conversation_id", None))
                said.append(f'Nice. I\'ve marked "{c.title}" as done.' if action == COMPLETE
                            else f'Okay. I\'ve dropped "{c.title}".')
            else:
                learning_store.record_outcome(key, "action", f"goal:{action}", "failed", c.title,
                                              getattr(ctx, "conversation_id", None))
                verb = "mark" if action == COMPLETE else "drop"
                said.append(f'I tried to {verb} "{c.title}", but I couldn\'t save the change.')
        else:
            said.append(f'Marking "{c.title}" as done.' if action == COMPLETE else f'Removing "{c.title}".')
            tags.append(_tag(c, action))
    if tags:
        ctx.is_command = True
    return " ".join(said + tags)


def _ask(ctx, action: str, cands: List[Candidate], reference: str) -> str:
    st = getattr(ctx, "state", None)
    if st is not None:
        cs.set_pending(st, PENDING_TYPE, {"action": action, "candidates": [c.to_dict() for c in cands[:4]]}, ttl=3)
    verb = "finished" if action == COMPLETE else "mean to drop"
    kinds = {c.kind for c in cands}
    if kinds == {"goal", "task"} and len(cands) == 2:
        g = next(c for c in cands if c.kind == "goal")
        t = next(c for c in cands if c.kind == "task")
        return (f'"{reference}" matches both a goal ("{g.title}") and a task ("{t.title}"). '
                f"Which did you {'finish' if action == COMPLETE else 'mean'}: the goal, the task, or both?")
    names = "; ".join(f'{c.kind} "{c.title}"' for c in cands[:3])
    return f"Which one did you {verb}? I have {names}."


def _decide(ctx, intent: Intent, cands: List[Candidate]) -> Optional[str]:
    """The decision table. Returns the reply, or None when nothing matched."""
    if not cands:
        return None
    kinds = {c.kind for c in cands}
    if len(kinds) > 1:                                   # a goal AND a task both fit: ask, never guess
        return _ask(ctx, intent.action, cands, intent.reference)
    if len(cands) == 1 or cands[0].score - cands[1].score >= 0.25:
        return _act(ctx, cands[:1], intent.action)
    return _ask(ctx, intent.action, cands, intent.reference)


def _not_found(intent: Intent, others: List[Candidate], deps) -> str:
    what = intent.kind or "goal or task"
    hint = ""
    if others:
        o = others[0]
        hint = f' You do have a {o.kind}, "{o.title}". Did you mean that one?'
    elif intent.kind == "task":
        hint = ' Say "show my tasks" to see what\'s on the list.'
    return f'I couldn\'t find a {"pending " if intent.kind == "task" else ""}{what} matching "{intent.reference}".{hint}'


def _ask_which_task(ctx, intent: Intent, deps) -> Optional[str]:
    tasks = list_pending_tasks(deps)
    if not tasks:
        return "You don't have any pending tasks to update."
    cands = [Candidate("task", t["id"], t["text"]) for t in tasks[:4]]
    st = getattr(ctx, "state", None)
    if st is not None:
        cs.set_pending(st, PENDING_TYPE, {"action": intent.action, "candidates": [c.to_dict() for c in cands]}, ttl=3)
    return "Which task do you mean? You have: " + "; ".join(c.title for c in cands) + "."


# ----------------------------------------------------------------------------
# entry points
# ----------------------------------------------------------------------------
def handle(ctx, deps) -> Optional[str]:
    """Called by layer_035. Returns a reply to stop the pipeline, or None to let other layers continue."""
    st = getattr(ctx, "state", None)
    pend = cs.active_pending(st) if st is not None else None
    if pend and pend.type == PENDING_TYPE:
        answered = _answer_choice(ctx, st, pend)
        if answered is not None:
            return answered
    text = ctx.resolved_text or ctx.prompt_text
    intent = parse(text)
    if intent is None:
        return None
    return resolve_and_act(ctx, deps, intent)


def resolve_and_act(ctx, deps, intent: Intent) -> Optional[str]:
    if not intent.reference:
        if intent.explicit and intent.kind in (None, "task"):
            return _ask_which_task(ctx, intent, deps)
        return None
    cands, error = find_candidates(ctx.speaker_key, intent.reference.split(), intent.kind, deps)
    reply = _decide(ctx, intent, cands)
    if reply is not None:
        return reply
    # Nothing matched.
    if intent.kind in ("task", "goal") or intent.explicit:
        # An instruction we cannot carry out must say so. If the task list could not even be read, hand the
        # command to the executor, which checks the database itself and reports honestly through its receipt.
        if error and intent.kind in (None, "task") and intent.action:
            return None
        others, _ = find_candidates(ctx.speaker_key, intent.reference.split(),
                                    "goal" if intent.kind == "task" else "task" if intent.kind == "goal" else None, deps)
        return _not_found(intent, others, deps)
    ctx.lifecycle_declined = True       # a plain report ("I finished my run") with nothing to update: carry on
    return None


def handle_task_command(ctx, deps, action: str, search: str, narrative: bool) -> Optional[str]:
    """For the task layer's legacy triggers ("mark it done", "remove task X"). Same resolver, same guarantees."""
    if narrative and getattr(ctx, "lifecycle_declined", False):
        return None                     # already looked, nothing to update: do not claim anything
    intent = Intent(COMPLETE if action == "complete" else DROP, " ".join(content_tokens(search)),
                    "task", explicit=not narrative)
    reply = resolve_and_act(ctx, deps, intent)
    if reply is None and not intent.reference:
        return None
    return reply


def _answer_choice(ctx, st, pend) -> Optional[str]:
    cands = [Candidate(c["kind"], c["id"], c["title"]) for c in pend.data.get("candidates", [])]
    action = pend.data.get("action", COMPLETE)
    words = set(speech_acts.normalize(ctx.prompt_text).split())
    if words & {"neither", "none", "nothing", "nevermind", "cancel"} or {"never", "mind"} <= words:
        st.pending = None
        return "Okay, I'll leave them as they are."
    if words & {"both", "all", "everything", "each"}:
        chosen = cands
    else:
        chosen = cands
        if words & _TASK_WORDS and not words & _GOAL_WORDS:
            chosen = [c for c in cands if c.kind == "task"]
        elif words & _GOAL_WORDS and not words & _TASK_WORDS:
            chosen = [c for c in cands if c.kind == "goal"]
        if len(chosen) > 1:
            pick = next((_ORDINALS[w] for w in speech_acts.normalize(ctx.prompt_text).split() if w in _ORDINALS), None)
            if pick is not None:
                chosen = [chosen[pick]] if -len(chosen) <= pick < len(chosen) else chosen
            else:
                said = set(content_tokens(ctx.prompt_text))
                scored = sorted(((len(said & _record_tokens(c.title)), c) for c in chosen), key=lambda x: -x[0])
                if scored and scored[0][0] > 0 and (len(scored) == 1 or scored[0][0] > scored[1][0]):
                    chosen = [scored[0][1]]
        if len(chosen) == len(cands) and len(cands) > 1:
            st.pending = None            # the user moved on to something else
            return None
    if not chosen:
        st.pending = None
        return None
    if len(chosen) > 1 and len({c.kind for c in chosen}) == 1:
        return _ask(ctx, action, chosen, "that")           # still ambiguous inside one kind: ask again
    st.pending = None
    return _act(ctx, chosen, action)
