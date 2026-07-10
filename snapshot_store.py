"""
snapshot_store.py — freeze analysis to disk (Hardcore).
No re-fetch on every Streamlit rerun. Hardened with logging.
"""

from __future__ import annotations
import json
import time
from pathlib import Path

from logging_config import log

SNAP_DIR = Path(__file__).parent / "snapshots"
SNAP_DIR.mkdir(exist_ok=True)


def _path(sym: str) -> Path:
    return SNAP_DIR / f"{sym.upper()}.json"


def has_snapshot(sym: str) -> bool:
    return _path(sym).exists()


def load_snapshot(sym: str) -> dict | None:
    p = _path(sym)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception as e:
        log.warning("Corrupt snapshot for %s: %s", sym, e)
        return None


def save_snapshot(sym: str, result: dict | None = None, price_series: list | None = None,
                  trading: dict | None = None) -> dict:
    existing = load_snapshot(sym) or {}
    payload = {
        "symbol": sym.upper(),
        "fetched_at": int(time.time()),
        "result": result if result is not None else existing.get("result"),
        "prices": price_series if price_series is not None else existing.get("prices", []),
        "trading": trading if trading is not None else existing.get("trading"),
    }
    try:
        _path(sym).write_text(json.dumps(payload))
    except Exception as e:
        log.error("Failed to write snapshot %s: %s", sym, e)
        raise
    return payload


def save_trading(sym: str, trading: dict) -> dict:
    return save_snapshot(sym, result=None, price_series=None, trading=trading)


MACRO_PATH = SNAP_DIR / "_macro.json"


def save_macro(macro: dict) -> dict:
    payload = {"fetched_at": int(time.time()), "macro": macro}
    try:
        MACRO_PATH.write_text(json.dumps(payload))
    except Exception as e:
        log.error("Failed to write macro snapshot: %s", e)
    return payload


def load_macro() -> dict | None:
    if not MACRO_PATH.exists():
        return None
    try:
        return json.loads(MACRO_PATH.read_text())
    except Exception as e:
        log.warning("Corrupt macro snapshot: %s", e)
        return None


def age_str(snap: dict) -> str:
    if not snap or "fetched_at" not in snap:
        return "never"
    secs = int(time.time()) - snap["fetched_at"]
    if secs < 90:
        return "just now"
    mins = secs // 60
    if mins < 60:
        return f"{mins}m ago"
    hrs = mins // 60
    if hrs < 24:
        return f"{hrs}h ago"
    return f"{hrs // 24}d ago"


def all_snapshots() -> dict[str, dict]:
    out = {}
    for p in SNAP_DIR.glob("*.json"):
        if p.name.startswith("_"):
            continue
        try:
            out[p.stem] = json.loads(p.read_text())
        except Exception as e:
            log.debug("Skip bad snapshot %s: %s", p.name, e)
            continue
    return out


def delete_snapshot(sym: str) -> None:
    p = _path(sym)
    if p.exists():
        p.unlink()
