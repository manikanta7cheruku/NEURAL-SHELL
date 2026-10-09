"""
brain_modules/ollama_client.py

The only module that talks to Ollama.

WHAT CHANGED:
    - Real token streaming through /api/chat (structured roles) instead of
      one hand-built "User:/Seven:" text prompt through /api/generate.
    - One pooled requests.Session, so each turn reuses the TCP connection
      instead of paying a new handshake.
    - keep_alive="24h" on EVERY path (the old non-streaming path omitted it,
      so the model unloaded after Ollama's idle window and the next message
      paid a multi-second cold load).
    - Typed errors (OllamaError) so callers produce a clear, friendly message
      instead of sending an error string through the memory system.
    - warmup() loads the model into memory before the first message.

The legacy call_ollama() and stream_sentences() are kept for other callers.
"""

import json
import logging
import threading
from typing import Iterator

import requests
from requests.adapters import HTTPAdapter

_log = logging.getLogger("seven.ollama")

OLLAMA_BASE = "http://127.0.0.1:11434"
OLLAMA_URL = f"{OLLAMA_BASE}/api/generate"
OLLAMA_CHAT_URL = f"{OLLAMA_BASE}/api/chat"
OLLAMA_PS_URL = f"{OLLAMA_BASE}/api/ps"
KEEP_ALIVE = "24h"
CONNECT_TIMEOUT = 3.05
READ_TIMEOUT = 120

_session = requests.Session()
_session.mount("http://", HTTPAdapter(pool_connections=2, pool_maxsize=4))


class OllamaError(Exception):
    """kind is one of: unavailable, timeout, model_missing, http, model."""

    def __init__(self, kind: str, message: str = ""):
        super().__init__(message or kind)
        self.kind = kind
        self.message = message


def _try_recover() -> bool:
    """Ask the recovery daemon to restart Ollama once. Never raises."""
    try:
        from brain_modules.recovery_daemon import restart_ollama_service
        return bool(restart_ollama_service())
    except Exception as exc:
        _log.warning("Ollama recovery failed: %s", exc)
        return False


def _open_stream(url: str, body: dict) -> requests.Response:
    """POST with streaming enabled. Retries once after an automatic restart."""
    for attempt in (0, 1):
        try:
            resp = _session.post(url, json=body, stream=True, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
        except requests.exceptions.ConnectionError:
            if attempt == 0 and _try_recover():
                continue
            raise OllamaError("unavailable")
        except requests.exceptions.Timeout:
            raise OllamaError("timeout")
        if resp.status_code == 404:
            detail = ""
            try:
                detail = resp.json().get("error", "")
            except Exception:
                pass
            resp.close()
            raise OllamaError("model_missing", detail)
        if resp.status_code != 200:
            code = resp.status_code
            resp.close()
            raise OllamaError("http", f"status {code}")
        return resp
    raise OllamaError("unavailable")


def stream_chat(payload: dict) -> Iterator[str]:
    """
    Yield tokens from /api/chat as they are generated.

    payload: {"model", "messages", "options", ...}. stream and keep_alive are
    filled in. Raises OllamaError before or during the stream.
    """
    body = dict(payload)
    body["stream"] = True
    body.setdefault("keep_alive", KEEP_ALIVE)
    resp = _open_stream(OLLAMA_CHAT_URL, body)
    try:
        for line in resp.iter_lines():
            if not line:
                continue
            try:
                chunk = json.loads(line)
            except ValueError:
                continue
            if chunk.get("error"):
                raise OllamaError("model", str(chunk["error"]))
            token = (chunk.get("message") or {}).get("content", "")
            if token:
                yield token
            if chunk.get("done"):
                break
    except requests.exceptions.ConnectionError:
        raise OllamaError("unavailable")
    except requests.exceptions.Timeout:
        raise OllamaError("timeout")
    finally:
        resp.close()


def chat_once(payload: dict) -> str:
    """Collect a whole reply as one string."""
    return "".join(stream_chat(payload)).strip()


def warmup(model: str) -> None:
    """Load the model into memory in the background so the first message is fast."""
    if not model:
        return

    def _worker():
        try:
            _session.post(OLLAMA_CHAT_URL,
                          json={"model": model, "messages": [], "keep_alive": KEEP_ALIVE},
                          timeout=(CONNECT_TIMEOUT, 180))
            _log.info("Model %s warmed", model)
        except Exception as exc:
            _log.debug("warmup skipped: %s", exc)

    threading.Thread(target=_worker, daemon=True, name="OllamaWarmup").start()


def loaded_models() -> list:
    """Models currently resident in memory (Ollama /api/ps). [] on failure."""
    try:
        r = _session.get(OLLAMA_PS_URL, timeout=(1.5, 2.5))
        if r.status_code == 200:
            return [m.get("name", "") for m in r.json().get("models", [])]
    except Exception:
        pass
    return []


def friendly_error(err: OllamaError, model: str = "") -> str:
    """Human message for an OllamaError. Never stored in memory."""
    if err.kind == "unavailable":
        try:
            from backend.bootstrap import is_ollama_installed
            if not is_ollama_installed():
                return ("The AI engine isn't installed yet. Open Settings, scroll to the bottom "
                        "and click Repair Installation.")
        except Exception:
            pass
        return "My AI engine isn't running. Open Ollama from the Start menu and try again."
    if err.kind == "timeout":
        return "The model is taking too long. It may still be loading. Give it a moment and try again."
    if err.kind == "model_missing":
        name = model or "the selected model"
        return f"The model {name} isn't installed. Pick another in Settings, or run: ollama pull {name}"
    return "Something went wrong with my thinking. Try again."


# ---------------------------------------------------------------------------
# Legacy API (kept for callers that still use /api/generate)
# ---------------------------------------------------------------------------

def call_ollama(payload: dict) -> str:
    """Non-streaming /api/generate call. Returns text or a friendly error string."""
    body = {**payload, "stream": False}
    body.setdefault("keep_alive", KEEP_ALIVE)
    try:
        r = _session.post(OLLAMA_URL, json=body, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
        if r.status_code == 200:
            return r.json().get("response", "").strip() or "Listening."
        return "My brain hiccupped. Try again."
    except requests.exceptions.ConnectionError:
        if _try_recover():
            try:
                r = _session.post(OLLAMA_URL, json=body, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
                if r.status_code == 200:
                    return r.json().get("response", "").strip() or "Listening."
            except Exception as exc:
                _log.warning("retry failed: %s", exc)
        return friendly_error(OllamaError("unavailable"))
    except requests.exceptions.Timeout:
        return friendly_error(OllamaError("timeout"))
    except Exception as exc:
        _log.error("call_ollama failed: %s", exc)
        return friendly_error(OllamaError("http"))


def stream_sentences(prompt: str, payload: dict) -> Iterator[str]:
    """Legacy: stream /api/generate output as sentences."""
    from brain_modules.response_filter import SentenceChunker
    body = {**payload, "stream": True}
    body.setdefault("keep_alive", KEEP_ALIVE)
    chunker = SentenceChunker()
    try:
        resp = _open_stream(OLLAMA_URL, body)
    except OllamaError as err:
        yield friendly_error(err)
        return
    try:
        for line in resp.iter_lines():
            if not line:
                continue
            try:
                chunk = json.loads(line)
            except ValueError:
                continue
            for sentence in chunker.feed(chunk.get("response", "")):
                yield sentence
            if chunk.get("done"):
                break
        for sentence in chunker.flush():
            yield sentence
    except requests.exceptions.RequestException:
        yield friendly_error(OllamaError("unavailable"))
    finally:
        resp.close()
