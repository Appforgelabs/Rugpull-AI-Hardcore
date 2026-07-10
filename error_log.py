"""
error_log.py — lightweight, persistent error collection for the Diagnostics tab.

Captures exceptions, warnings, and custom messages so you can fix issues
quickly without digging through Streamlit Cloud logs.

Usage in Streamlit:
    from error_log import ErrorLog
    el = ErrorLog()
    try:
        ...
    except Exception as e:
        el.record("module_name", e, context="optional note")
        raise   # or show st.error

The Diagnostics tab calls el.recent() / el.clear() / el.export().
"""

from __future__ import annotations
import json
import time
import traceback
from pathlib import Path
from typing import Any
from collections import deque

from logging_config import log

LOG_PATH = Path(__file__).parent / "snapshots" / "_error_log.jsonl"
MAX_MEMORY = 200
MAX_FILE = 500


class ErrorLog:
    def __init__(self):
        self._buf: deque[dict] = deque(maxlen=MAX_MEMORY)
        self._load_from_disk()

    def _load_from_disk(self):
        if not LOG_PATH.exists():
            return
        try:
            lines = LOG_PATH.read_text(encoding="utf-8").strip().splitlines()
            for line in lines[-MAX_MEMORY:]:
                try:
                    self._buf.append(json.loads(line))
                except Exception:
                    continue
        except Exception as e:
            log.debug("Could not load error log: %s", e)

    def record(
        self,
        source: str,
        exc: BaseException | str | None = None,
        context: str = "",
        level: str = "ERROR",
        extra: dict | None = None,
    ) -> dict:
        """Append one entry. Returns the entry dict."""
        tb = ""
        msg = ""
        if isinstance(exc, BaseException):
            msg = f"{type(exc).__name__}: {exc}"
            tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        elif isinstance(exc, str):
            msg = exc
        else:
            msg = context or "(no message)"

        entry = {
            "ts": int(time.time()),
            "iso": time.strftime("%Y-%m-%d %H:%M:%S"),
            "level": level.upper(),
            "source": source,
            "message": msg[:2000],
            "context": (context or "")[:500],
            "traceback": tb[-4000:] if tb else "",
            "extra": extra or {},
        }
        self._buf.append(entry)
        self._append_disk(entry)
        log.error("[%s] %s | %s", source, msg, context)
        return entry

    def _append_disk(self, entry: dict):
        try:
            LOG_PATH.parent.mkdir(exist_ok=True)
            with LOG_PATH.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            # prune if too large
            if LOG_PATH.stat().st_size > 2_000_000:  # ~2 MB
                lines = LOG_PATH.read_text(encoding="utf-8").splitlines()
                keep = lines[-MAX_FILE:]
                LOG_PATH.write_text("\n".join(keep) + "\n", encoding="utf-8")
        except Exception as e:
            log.debug("Error log disk write failed: %s", e)

    def recent(self, n: int = 50, level: str | None = None) -> list[dict]:
        items = list(self._buf)[-n:]
        if level:
            items = [e for e in items if e.get("level") == level.upper()]
        return list(reversed(items))  # newest first

    def clear(self):
        self._buf.clear()
        try:
            if LOG_PATH.exists():
                LOG_PATH.unlink()
        except Exception:
            pass

    def export(self) -> str:
        return json.dumps(list(self._buf), indent=2, ensure_ascii=False)

    def count(self) -> int:
        return len(self._buf)

    def summary(self) -> dict:
        from collections import Counter
        levels = Counter(e.get("level", "?") for e in self._buf)
        sources = Counter(e.get("source", "?") for e in self._buf)
        return {
            "total": len(self._buf),
            "levels": dict(levels),
            "top_sources": sources.most_common(8),
        }


# Singleton for easy import
_error_log: ErrorLog | None = None

def get_error_log() -> ErrorLog:
    global _error_log
    if _error_log is None:
        _error_log = ErrorLog()
    return _error_log
