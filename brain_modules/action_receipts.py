"""
brain_modules/action_receipts.py

Receipts for actions. Seven may only say an action worked when a receipt says
so. A receipt is "success" (executed and, where checkable, verified),
"failed" (raised or returned False), or "unconfirmed" (ran, but could not be
verified). reconcile_reply() rewrites an optimistic reply ("Opening camera.")
into an honest one when the receipt failed.
"""

import time
from dataclasses import asdict, dataclass
from typing import Callable, List, Optional

PROCESS_ALIASES = {
    "camera": ("windowscamera", "camera"), "chrome": ("chrome",), "edge": ("msedge",),
    "firefox": ("firefox",), "notepad": ("notepad",), "calculator": ("calculator", "calculatorapp", "calc"),
    "spotify": ("spotify",), "code": ("code",), "vscode": ("code",), "word": ("winword",),
    "excel": ("excel",), "powerpoint": ("powerpnt",), "explorer": ("explorer",), "discord": ("discord",),
    "teams": ("teams", "ms-teams"), "slack": ("slack",), "vlc": ("vlc",), "paint": ("mspaint",),
}
_VERBS = {"OPEN": "open", "CLOSE": "close", "WINDOW": "change that window", "SYS": "change that setting",
          "SCHED": "set that reminder", "TASK": "update your tasks"}


@dataclass
class ActionReceipt:
    kind: str
    target: str
    status: str                 # success | failed | unconfirmed
    detail: str = ""
    duration_ms: int = 0
    verified: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def verify_running(target: str, expect: bool = True, timeout: float = 3.5) -> Optional[bool]:
    """True/False if a matching process is (not) running; None when it cannot be checked."""
    try:
        import psutil
    except ImportError:
        return None
    names = PROCESS_ALIASES.get(target.lower().strip())
    if names is None:
        return None   # only targets with a known process name are verified
    deadline = time.time() + timeout
    while True:
        try:
            running = {(p.info["name"] or "").lower().replace(".exe", "") for p in psutil.process_iter(["name"])}
        except Exception:
            return None
        present = any(any(n in r for r in running) for n in names)
        if present == expect:
            return True
        if time.time() >= deadline:
            return False
        time.sleep(0.2)


def run_action(kind: str, target: str, fn: Callable[[], object],
               verify: Optional[Callable[[], Optional[bool]]] = None) -> ActionReceipt:
    """Execute fn and produce a receipt. Never raises."""
    t0 = time.time()
    try:
        ret = fn()
    except Exception as exc:
        return ActionReceipt(kind, target, "failed", str(exc)[:160], int((time.time() - t0) * 1000))
    ms = int((time.time() - t0) * 1000)
    if ret is False:
        return ActionReceipt(kind, target, "failed", "the action reported failure", ms)
    if isinstance(ret, str):            # the action describes its own result ("Saved Study: 9 apps and 37 tabs.")
        return ActionReceipt(kind, target, "success", ret, ms, True)
    if verify is not None:
        try:
            ok = verify()
        except Exception:
            ok = None
        if ok is True:
            return ActionReceipt(kind, target, "success", "", ms, True)
        if ok is False:   # not seeing a process is not proof of failure (slow starts, URI apps)
            return ActionReceipt(kind, target, "unconfirmed", "I couldn't confirm it started", ms)
    return ActionReceipt(kind, target, "unconfirmed" if ret is None else "success", "", ms, False)


def reconcile_reply(text: str, receipts: List[ActionReceipt]) -> str:
    """Replace an optimistic reply with an honest one when any action failed."""
    failed = [r for r in receipts if r.status == "failed"]
    if not failed:
        return text
    parts = []
    for r in failed:
        verb = _VERBS.get(r.kind.upper(), "do that")
        tgt = f" {r.target}" if r.target and r.kind.upper() in ("OPEN", "CLOSE") else ""
        why = f" ({r.detail})" if r.detail else ""
        parts.append(f"I tried to {verb}{tgt}, but it didn't work{why}.")
    return " ".join(parts)


def summarize(receipts: List[dict]) -> str:
    """Answer 'did that work?' from the last receipts."""
    if not receipts:
        return "I haven't run anything for you in this chat yet."
    out = []
    for r in receipts:
        tgt = f" {r['target']}" if r.get("target") else ""
        if r["status"] == "success":
            out.append(f"{r['kind'].title()}{tgt}: it worked" + (" and I confirmed it." if r.get("verified") else "."))
        elif r["status"] == "failed":
            out.append(f"{r['kind'].title()}{tgt}: it failed" + (f" ({r['detail']})." if r.get("detail") else "."))
        else:
            out.append(f"{r['kind'].title()}{tgt}: I sent the command but couldn't confirm the result.")
    return " ".join(out)
