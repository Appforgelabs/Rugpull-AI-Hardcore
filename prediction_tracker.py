"""
prediction_tracker.py — the app grading itself (Hardcore).
"""

from __future__ import annotations
import json
import time
import datetime as dt
from pathlib import Path

LEDGER_KEY = "predictions"
LOCAL_PATH = Path(__file__).parent / "snapshots" / "_predictions.json"
HORIZON_DAYS = 7
MIN_N_FOR_WEIGHT = 8
MAX_SCORED_KEEP = 300
CHUNK = 120
WEIGHT_FLOOR, WEIGHT_CEIL = 0.25, 1.75


def load_ledger(cloud_url: str | None = None) -> dict:
    if cloud_url:
        try:
            import cloud_sync as CS
            blob = CS.load_blob(cloud_url, LEDGER_KEY)
            if blob and blob.get("sharded"):
                preds = []
                for i in range(1, int(blob.get("n_chunks", 0)) + 1):
                    c = CS.load_blob(cloud_url, f"{LEDGER_KEY}_c{i}") or {}
                    preds.extend(c.get("chunk", []))
                blob = {k: v for k, v in blob.items()
                        if k not in ("sharded", "n_chunks")}
                blob["predictions"] = preds
            if blob:
                return blob
        except Exception:
            pass
    try:
        return json.loads(LOCAL_PATH.read_text())
    except Exception:
        return {"predictions": [], "stats": {}, "version": 1}


def _trim(ledger: dict) -> None:
    preds = ledger.get("predictions", [])
    for p in preds:
        if p.get("scored") and "votes" in p:
            del p["votes"]
    scored = [p for p in preds if p.get("scored")]
    unscored = [p for p in preds if not p.get("scored")]
    if len(scored) > MAX_SCORED_KEEP:
        scored.sort(key=lambda p: p.get("ts", 0))
        scored = scored[-MAX_SCORED_KEEP:]
    merged = unscored + scored
    merged.sort(key=lambda p: p.get("ts", 0))
    ledger["predictions"] = merged


def save_ledger(ledger: dict, cloud_url: str | None = None) -> dict:
    _trim(ledger)
    status = {"local": False, "cloud": False, "error": None}
    try:
        LOCAL_PATH.parent.mkdir(exist_ok=True)
        LOCAL_PATH.write_text(json.dumps(ledger))
        status["local"] = True
    except Exception as e:
        status["error"] = f"local write failed: {e}"
    if cloud_url:
        try:
            import cloud_sync as CS
            blob = json.dumps(ledger)
            if len(blob) <= 45000:
                CS.save_blob(cloud_url, LEDGER_KEY, ledger)
            else:
                preds = ledger.get("predictions", [])
                chunks = [preds[i:i + CHUNK] for i in range(0, len(preds), CHUNK)]
                meta = {k: v for k, v in ledger.items() if k != "predictions"}
                meta["sharded"] = True
                meta["n_chunks"] = len(chunks)
                for i, ch in enumerate(chunks, 1):
                    CS.save_blob(cloud_url, f"{LEDGER_KEY}_c{i}", {"chunk": ch})
                CS.save_blob(cloud_url, LEDGER_KEY, meta)
            status["cloud"] = True
        except Exception as e:
            status["error"] = f"CLOUD SAVE FAILED: {e}"
    else:
        status["error"] = "no cloud URL — ledger only in local file (LOST on reboot)"
    return status


def record(ledger: dict, sym: str, trading: dict) -> bool:
    if not trading or not trading.get("ok"):
        return False
    sg = trading.get("signal") or {}
    today = dt.date.today().isoformat()
    for p in ledger["predictions"]:
        if p["symbol"] == sym and p["date"] == today:
            return False
    votes = {v["signal"]: v["vote"]
             for v in sg.get("votes", []) if v.get("vote")}
    try:
        import demark as DM
        tdv = DM.td_vote(trading.get("demark") or {})
        if tdv:
            votes["TD Sequential"] = tdv
    except Exception:
        pass
    ledger["predictions"].append({
        "id": f"{sym}-{today}",
        "date": today, "ts": int(time.time()),
        "symbol": sym, "price": trading.get("price"),
        "direction": sg.get("direction"),
        "probability": sg.get("probability"),
        "votes": votes,
        "swing": (sg.get("swing") or {}).get("bias"),
        "day": (sg.get("day") or {}).get("bias"),
        "scored": False,
    })
    return True


def score_due(ledger: dict, latest_prices: dict[str, tuple[float, int]]) -> int:
    now = time.time()
    scored = 0
    stats = ledger.setdefault("stats", {})

    def bump(name, hit):
        s = stats.setdefault(name, {"n": 0, "hits": 0})
        s["n"] += 1
        s["hits"] += int(hit)

    for p in ledger["predictions"]:
        if p.get("scored"):
            continue
        if now - p["ts"] < HORIZON_DAYS * 86400:
            continue
        lp = latest_prices.get(p["symbol"])
        if not lp or not p.get("price"):
            continue
        new_price, fetched_at = lp
        if fetched_at - p["ts"] < HORIZON_DAYS * 86400 * 0.8:
            continue
        ret = (new_price - p["price"]) / p["price"]
        up = ret > 0
        p["realized_ret_pct"] = round(ret * 100, 2)
        p["scored"] = True
        scored += 1

        if p.get("direction") in ("LONG", "SHORT"):
            hit = (p["direction"] == "LONG") == up
            p["correct"] = bool(hit)
            bump("OVERALL", hit)
        for name, vote in (p.get("votes") or {}).items():
            bump(name, (vote > 0) == up)
        for lane in ("swing", "day"):
            b = p.get(lane)
            if b in ("LONG", "SHORT"):
                bump(lane.upper(), (b == "LONG") == up)
    return scored


def signal_weights(ledger: dict) -> dict[str, float]:
    weights = {}
    for name, s in (ledger.get("stats") or {}).items():
        if s["n"] < MIN_N_FOR_WEIGHT:
            continue
        hr = s["hits"] / s["n"]
        w = max(WEIGHT_FLOOR, min(WEIGHT_CEIL, 2 * hr))
        weights[name] = round(w, 2)
    return weights


def stats_table(ledger: dict) -> list[dict]:
    rows = []
    for name, s in sorted((ledger.get("stats") or {}).items()):
        hr = s["hits"] / s["n"] * 100 if s["n"] else 0
        rows.append({"Signal": name, "Scored": s["n"],
                     "Hit rate": f"{hr:.0f}%",
                     "Weight": signal_weights(ledger).get(name, 1.0)})
    return rows


def auto_cycle(syms: list[str], load_snapshot, cloud_url: str | None = None) -> dict:
    ledger = load_ledger(cloud_url)
    latest = {}
    trading_by_sym = {}
    for s in syms:
        snap = load_snapshot(s) or {}
        tr = snap.get("trading")
        if tr and tr.get("price"):
            latest[s] = (tr["price"], snap.get("fetched_at", 0))
            trading_by_sym[s] = tr
        elif (snap.get("result") or {}).get("price"):
            latest[s] = (snap["result"]["price"], snap.get("fetched_at", 0))

    n_scored = score_due(ledger, latest)
    n_recorded = sum(1 for s, tr in trading_by_sym.items()
                     if record(ledger, s, tr))
    save_status = save_ledger(ledger, cloud_url)
    pend = sum(1 for p in ledger["predictions"] if not p.get("scored"))
    return {"recorded": n_recorded, "scored": n_scored, "pending": pend,
            "total": len(ledger["predictions"]),
            "weights": signal_weights(ledger),
            "save": save_status}
