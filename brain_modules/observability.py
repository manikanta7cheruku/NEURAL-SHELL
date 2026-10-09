"""
=============================================================================
brain_modules/observability.py

Production Observability Layer.

Provides:
  - Structured JSON logging with size-based rotation
  - Per-layer latency tracking with percentile aggregation
  - Layer heatmap data source for dashboard telemetry
  - Zero-overhead capture (bounded deque, thread-safe)

Designed to run in both dev and packaged Electron environments.
Log files write to APPDATA/SEVEN/logs on Windows, XDG paths elsewhere.

BACKWARD COMPATIBILITY:
    brain_manager.record_latency() continues to work unchanged.
    This module supplements it with per-layer granularity.
=============================================================================
"""

import os
import sys
import json
import time
import threading
import logging
import logging.handlers
from collections import deque
from typing import Dict, List, Optional, Any

# -- Log directory resolution ---------------------------------------------

def _resolve_log_dir() -> str:
    """
    Resolve writable log directory for both dev and packaged environments.
    """
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        log_dir = os.path.join(base, "SEVEN", "logs")
    else:
        base = os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state"))
        log_dir = os.path.join(base, "seven", "logs")

    try:
        os.makedirs(log_dir, exist_ok=True)
    except Exception:
        # Fallback to temp if AppData not writable
        import tempfile
        log_dir = os.path.join(tempfile.gettempdir(), "seven_logs")
        os.makedirs(log_dir, exist_ok=True)

    return log_dir


LOG_DIR = _resolve_log_dir()
LOG_FILE = os.path.join(LOG_DIR, "seven.jsonl")

# Rotation policy: 10MB per file, keep 7 files (70MB total ceiling)
_MAX_BYTES = 10 * 1024 * 1024
_BACKUP_COUNT = 7


# -- JSON formatter -------------------------------------------------------

class JsonFormatter(logging.Formatter):
    """
    Emits structured JSON records. One JSON object per line.
    Downstream tools can tail and parse directly.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.time(),
            "iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }

        # Include structured extras injected via logger.info(msg, extra={...})
        for key, value in record.__dict__.items():
            if key in ("args", "asctime", "created", "exc_info", "exc_text",
                       "filename", "funcName", "levelname", "levelno",
                       "lineno", "module", "msecs", "msg", "message",
                       "name", "pathname", "process", "processName",
                       "relativeCreated", "stack_info", "thread", "threadName"):
                continue
            try:
                json.dumps(value)  # test serializability
                payload[key] = value
            except (TypeError, ValueError):
                payload[key] = str(value)

        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)

        try:
            return json.dumps(payload, ensure_ascii=False)
        except Exception:
            return json.dumps({"ts": time.time(), "level": "ERROR",
                               "msg": "log_serialization_failed"})


# -- Logger factory (singleton) -------------------------------------------

_logger_lock = threading.Lock()
_configured = False


def get_logger(name: str = "seven") -> logging.Logger:
    """
    Return the structured logger. Configures the root once, thread-safe.
    """
    global _configured
    logger = logging.getLogger(name)

    if _configured:
        return logger

    with _logger_lock:
        if _configured:
            return logger

        try:
            handler = logging.handlers.RotatingFileHandler(
                LOG_FILE,
                maxBytes=_MAX_BYTES,
                backupCount=_BACKUP_COUNT,
                encoding="utf-8",
            )
            handler.setFormatter(JsonFormatter())
            handler.setLevel(logging.INFO)

            root = logging.getLogger("seven")
            root.setLevel(logging.INFO)

            # Avoid duplicate handlers if repeatedly imported
            already = any(
                isinstance(h, logging.handlers.RotatingFileHandler)
                and getattr(h, "baseFilename", "") == handler.baseFilename
                for h in root.handlers
            )
            if not already:
                root.addHandler(handler)

            _configured = True
        except Exception as _e:
            # Never fail the app on logging init
            try:
                print(f"[OBSERVABILITY] Logger init warning: {_e}")
            except Exception:
                pass

    return logger


# -- Per-layer latency tracker --------------------------------------------

class LayerLatencyTracker:
    """
    Bounded per-layer latency sample store.
    Uses deque with fixed maxlen for O(1) append and constant memory.
    """

    _SAMPLE_LIMIT = 200

    def __init__(self):
        self._samples: Dict[str, deque] = {}
        self._lock = threading.Lock()

    def record(self, layer_name: str, duration_ms: float) -> None:
        """
        Store a latency sample for a given layer. Non-blocking on hot path.
        """
        if not layer_name or duration_ms is None:
            return
        try:
            duration_ms = float(duration_ms)
        except (TypeError, ValueError):
            return

        with self._lock:
            if layer_name not in self._samples:
                self._samples[layer_name] = deque(maxlen=self._SAMPLE_LIMIT)
            self._samples[layer_name].append(duration_ms)

    def _percentile(self, sorted_data: List[float], pct: float) -> float:
        """Compute percentile from pre-sorted data. Zero if empty."""
        if not sorted_data:
            return 0.0
        idx = int(round((pct / 100.0) * (len(sorted_data) - 1)))
        return round(sorted_data[idx], 2)

    def get_stats(self, layer_name: str) -> Dict[str, Any]:
        """
        Return aggregated stats for a specific layer.
        """
        with self._lock:
            data = list(self._samples.get(layer_name, []))

        if not data:
            return {
                "layer": layer_name,
                "count": 0,
                "avg": 0, "min": 0, "max": 0,
                "p50": 0, "p95": 0, "p99": 0,
            }

        srt = sorted(data)
        return {
            "layer": layer_name,
            "count": len(data),
            "avg": round(sum(data) / len(data), 2),
            "min": round(srt[0], 2),
            "max": round(srt[-1], 2),
            "p50": self._percentile(srt, 50),
            "p95": self._percentile(srt, 95),
            "p99": self._percentile(srt, 99),
        }

    def get_all_stats(self) -> List[Dict[str, Any]]:
        """
        Return stats for every tracked layer, sorted by average descending.
        Used by the telemetry dashboard endpoint.
        """
        with self._lock:
            layer_names = list(self._samples.keys())

        stats = [self.get_stats(name) for name in layer_names]
        stats.sort(key=lambda s: s["avg"], reverse=True)
        return stats

    def reset(self, layer_name: Optional[str] = None) -> None:
        """
        Clear samples. If layer_name is None, clears all.
        """
        with self._lock:
            if layer_name is None:
                self._samples.clear()
            else:
                self._samples.pop(layer_name, None)


# -- Singleton tracker ----------------------------------------------------

_tracker = LayerLatencyTracker()


def record_layer_latency(layer_name: str, duration_ms: float) -> None:
    """
    Public API. Record latency for a named layer.
    Called by the pipeline dispatcher after each layer executes.
    """
    _tracker.record(layer_name, duration_ms)


def get_layer_stats(layer_name: str) -> Dict[str, Any]:
    """Return aggregated stats for one layer."""
    return _tracker.get_stats(layer_name)


def get_all_layer_stats() -> List[Dict[str, Any]]:
    """Return aggregated stats for all tracked layers."""
    return _tracker.get_all_stats()


def reset_layer_stats(layer_name: Optional[str] = None) -> None:
    """Clear latency samples for one layer, or all if None."""
    _tracker.reset(layer_name)


# -- Convenience event logger --------------------------------------------

def log_event(event: str, **fields) -> None:
    """
    Emit a structured event to the JSON log.
    Usage: log_event("layer_timeout", layer="layer_05_memory", ms=1234)
    """
    try:
        logger = get_logger("seven.events")
        logger.info(event, extra=fields)
    except Exception:
        pass