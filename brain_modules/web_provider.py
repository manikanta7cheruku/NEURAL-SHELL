"""
brain_modules/web_provider.py

Live web lookups with an explicit outcome, so Seven can say exactly why it has
no live data: offline, switched off, the search failed, or nothing was found.

The provider is injected (deps["web"]); tests use fakes, so a unit test never
depends on whether the real internet happens to be reachable.
"""

import logging
import socket
import time
from dataclasses import dataclass
from typing import Optional

_log = logging.getLogger("seven.web")


@dataclass
class WebOutcome:
    status: str                 # ok | offline | disabled | error | empty | not_needed
    text: str = ""
    query: str = ""
    needed: bool = False        # the question really needs fresh information
    detail: str = ""


_online_cache = {"ts": 0.0, "value": True}
_online_override: Optional[bool] = None


def set_online_override(value: Optional[bool]) -> None:
    """Force online/offline (tests, diagnostics). None restores real detection."""
    global _online_override
    _online_override = value
    _online_cache["ts"] = 0.0


def is_online(ttl: float = 15.0, timeout: float = 1.0) -> bool:
    """Cheap connectivity probe, cached. A TCP connect to public DNS, no data sent."""
    if _online_override is not None:
        return _online_override
    now = time.time()
    if now - _online_cache["ts"] < ttl:
        return _online_cache["value"]
    ok = False
    for host in ("1.1.1.1", "8.8.8.8"):
        try:
            with socket.create_connection((host, 53), timeout=timeout):
                ok = True
                break
        except OSError:
            continue
    _online_cache["ts"], _online_cache["value"] = now, ok
    return ok


_WEATHER = ("weather", "temperature", "forecast", "rain", "sunny", "cloudy", "humidity", "wind")
_NEWS = ("news", "latest", "happened", "breaking", "update")


class DefaultWebProvider:
    """Wraps the existing web.classifier / web.core modules."""

    def lookup(self, text: str, config) -> WebOutcome:
        try:
            from web.classifier import needs_web_search
            from web.core import web_news, web_search
        except Exception as exc:
            return WebOutcome("not_needed", detail=f"web module unavailable: {exc}")
        try:
            should, query = needs_web_search(text)
        except Exception as exc:
            return WebOutcome("not_needed", detail=str(exc))
        if not (should and query):
            return WebOutcome("not_needed")

        cfg = config.KEY.get("web", {}) if config else {}
        if not cfg.get("enabled", True):
            return WebOutcome("disabled", query=query, needed=True)
        if not is_online():
            return WebOutcome("offline", query=query, needed=True)

        low = query.lower()
        is_weather = any(w in low for w in _WEATHER)
        if is_weather and "in " not in low:
            city = (config.KEY.get("identity", {}).get("city") or config.KEY.get("identity", {}).get("location") or "")
            query = f"weather in {city} today" if city else "current weather today"
        timeout = cfg.get("timeout", 5)
        limit = 1 if is_weather else cfg.get("max_results", 2)
        try:
            use_news = any(w in text.lower() for w in _NEWS)
            result = (web_news(query, max_results=limit, timeout=timeout) if use_news
                      else web_search(query, max_results=limit, timeout=timeout))
        except Exception as exc:
            _log.warning("web search failed: %s", exc)
            return WebOutcome("error", query=query, needed=True, detail=str(exc))
        if not result or not str(result).strip():
            return WebOutcome("empty", query=query, needed=True)
        return WebOutcome("ok", text=str(result), query=query, needed=True)
