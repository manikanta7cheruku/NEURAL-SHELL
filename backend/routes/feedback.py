"""
backend/routes/feedback.py

Sends feedback from the Feedback page to a Google Form, whose responses land in
a Google Sheet. Sending from the backend (not the browser) means Seven can see
Google's answer: it only reports "sent" when Google accepted the entry, and
feedback written while offline is queued on disk and sent automatically later.

    POST /api/feedback          send one report (queued if it can't be sent now)
    GET  /api/feedback/status   is the form configured, how many are queued
    POST /api/feedback/retry    send anything still queued

==========================================================================
 SETUP: paste your Google Form here (see docs in the Feedback PR or below)
==========================================================================
 1. FORM_URL: open your form, click Send > link, copy the link. It looks like
    https://docs.google.com/forms/d/e/<LONG_ID>/viewform
    Paste it below; "viewform" is changed to "formResponse" automatically.
 2. FIELDS: each question has an id like "entry.123456789". In the form,
    open the three-dot menu > Get pre-filled link, fill every question, click
    Get link, copy it. The link contains entry.NNN=value for each question.
    The form has two questions, Email and Message; the page's category and severity are written at the start of the message.
 You can also set SEVEN_FEEDBACK_FORM_URL and SEVEN_FEEDBACK_FIELDS (a JSON
 object of the same shape) as environment variables instead of editing code.
"""

import json
import logging
import os
import platform
import threading
import time
import uuid
from typing import Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

_log = logging.getLogger("seven.feedback")
router = APIRouter()

FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSdwmjvMIDzJRGo2xTTqdcvUgzCiDzQV2wzsOBAZhd6Ea2lIuw/viewform"
FIELDS = {
    "email": "entry.1666026261",       # Short answer: email or "anonymous"
    "message": "entry.480930978",      # Paragraph: the category and severity, the description, app info if allowed
}


def compose_message(entry: dict) -> str:
    """The form has only Email and Message, so the category and severity lead the message: "[Bug Report, Critical]"."""
    severity = (entry.get("severity") or "").strip()
    tags = [entry["category"].strip()] + ([severity] if severity and severity.upper() != "N/A" else [])
    name = (entry.get("name") or "").strip()
    head = f"[{', '.join(tags)}]" + (f"\nFrom: {name}" if name else "")
    return f"{head}\n\n{entry['details']}"


_lock = threading.Lock()


def _form_url() -> str:
    url = (os.environ.get("SEVEN_FEEDBACK_FORM_URL") or FORM_URL).strip()
    for tail in ("/viewform", "/edit"):
        if tail in url:
            url = url.split(tail)[0] + "/formResponse"
    if not url.endswith("/formResponse"):
        url = url.rstrip("/") + "/formResponse"
    return url


def _fields() -> Dict[str, str]:
    raw = os.environ.get("SEVEN_FEEDBACK_FIELDS")
    if raw:
        try:
            return {**FIELDS, **json.loads(raw)}
        except ValueError:
            _log.warning("SEVEN_FEEDBACK_FIELDS is not valid JSON; using the built-in fields")
    return FIELDS


def _configured() -> bool:
    return "/forms/d/e/" in _form_url() and all(v.startswith("entry.") for v in _fields().values())


def _queue_path() -> str:
    try:
        from seven_paths import paths
        base = paths._seven_data
    except Exception:
        base = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "seven_data")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "feedback_queue.json")


def _load_queue() -> List[dict]:
    try:
        with open(_queue_path(), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _save_queue(items: List[dict]) -> None:
    with open(_queue_path(), "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)


def _post(entry: dict) -> bool:
    """True only when Google accepted the response."""
    import requests
    f = _fields()
    data = {f["email"]: entry.get("email") or "anonymous", f["message"]: compose_message(entry)}
    # Questions added to the form later get their own columns: list them in FIELDS (or SEVEN_FEEDBACK_FIELDS).
    extra = {"name": entry.get("name") or "anonymous", "category": entry["category"], "severity": entry.get("severity") or "N/A"}
    data.update({f[key]: value for key, value in extra.items() if f.get(key)})
    try:
        r = requests.post(_form_url(), data=data, timeout=8,
                          headers={"User-Agent": "Seven feedback", "Referer": _form_url().replace("formResponse", "viewform")})
    except requests.RequestException as exc:
        _log.info("feedback not sent yet (%s); queued", exc)
        return False
    # Google answers 200 with a confirmation page when the entry was recorded. A rejected entry comes back as
    # the form itself (with its FB_PUBLIC_LOAD_DATA_ payload) or as an error status.
    text = r.text or ""
    if r.status_code == 200 and ("response has been recorded" in text.lower() or "FB_PUBLIC_LOAD_DATA_" not in text):
        return True
    _log.warning("Google Forms rejected feedback: HTTP %s. Check FORM_URL and FIELDS in backend/routes/feedback.py",
                 r.status_code)
    return False


def _flush() -> int:
    """Send queued feedback. Returns how many are still queued."""
    with _lock:
        queue = _load_queue()
        remaining = [e for e in queue if not _post(e)]
        if len(remaining) != len(queue):
            _save_queue(remaining)
        return len(remaining)


def _app_info() -> str:
    try:
        from seven_utils.version import get_version
        version = get_version()
    except Exception:
        version = "unknown"
    try:
        from brain_modules.system_info import os_name
        os_text = os_name()
    except Exception:
        os_text = f"{platform.system()} {platform.release()}"
    return f"Seven {version} on {os_text}"


class FeedbackIn(BaseModel):
    category: str
    severity: str = ""
    details: str
    email: str = ""
    name: str = ""
    include_app_info: bool = True


@router.post("/api/feedback")
def send_feedback(req: FeedbackIn):
    details = req.details.strip()
    if not details or not req.category.strip():
        raise HTTPException(400, "Choose a category and describe the issue.")
    if not _configured():
        raise HTTPException(503, "Feedback isn't set up yet. Add your Google Form in backend/routes/feedback.py.")
    if req.include_app_info:
        details = f"{details}\n\n[{_app_info()}]"
    entry = {"id": uuid.uuid4().hex, "at": time.strftime("%Y-%m-%d %H:%M:%S"), "category": req.category.strip(),
             "severity": req.severity.strip(), "details": details[:8000], "email": req.email.strip()[:200],
             "name": req.name.strip()[:100]}
    sent = _post(entry)
    with _lock:
        queue = _load_queue()
        if not sent:
            queue.append(entry)
            _save_queue(queue)
    queued = _flush() if sent and queue else len(queue) if not sent else 0
    return {"sent": sent, "queued": queued}


_retry_started = False


def start_retry_loop(interval: int = 600) -> None:
    """Send queued feedback in the background: shortly after start, then every `interval` seconds."""
    global _retry_started
    if _retry_started or os.environ.get("SEVEN_TEST") == "1":
        return
    _retry_started = True

    def loop():
        time.sleep(30)
        while True:
            try:
                if _configured() and _load_queue():
                    left = _flush()
                    _log.info("feedback retry: %s still queued", left)
            except Exception as exc:
                _log.debug("feedback retry failed: %s", exc)
            time.sleep(interval)

    threading.Thread(target=loop, daemon=True, name="SevenFeedbackRetry").start()


@router.get("/api/feedback/status")
def feedback_status():
    return {"configured": _configured(), "queued": len(_load_queue())}


@router.post("/api/feedback/retry")
def retry_feedback():
    if not _configured():
        return {"configured": False, "queued": len(_load_queue())}
    return {"configured": True, "queued": _flush()}
