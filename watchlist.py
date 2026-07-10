"""
watchlist.py — single shared ticker list (Hardcore).
"""

from __future__ import annotations
import json
from pathlib import Path

from logging_config import log

WATCHLIST_PATH = Path(__file__).parent / "tickers.json"

DEFAULT = [
    {"symbol": "NVDA", "name": "NVIDIA"},
    {"symbol": "AMD",  "name": "AMD"},
    {"symbol": "INTC", "name": "Intel"},
    {"symbol": "TSLA", "name": "Tesla"},
    {"symbol": "PLTR", "name": "Palantir"},
    {"symbol": "HOOD", "name": "Robinhood"},
]


def _normalize(items) -> list[dict]:
    out, seen = [], set()
    for it in items or []:
        sym = str(it.get("symbol", "")).upper().strip()
        if sym and sym not in seen:
            seen.add(sym)
            out.append({"symbol": sym, "name": (it.get("name") or sym).strip()})
    return out


def load_watchlist() -> list[dict]:
    try:
        data = json.loads(WATCHLIST_PATH.read_text())
        items = _normalize(data.get("watchlist", []))
        return items or list(DEFAULT)
    except Exception as e:
        log.debug("Watchlist load failed, using default: %s", e)
        return list(DEFAULT)


def save_watchlist(items) -> list[dict]:
    norm = _normalize(items)
    try:
        WATCHLIST_PATH.write_text(json.dumps({"watchlist": norm}, indent=2) + "\n")
    except Exception as e:
        log.error("Could not save watchlist: %s", e)
    return norm


def symbols() -> list[str]:
    return [it["symbol"] for it in load_watchlist()]
