"""
paper_portfolio.py — automated 12-ticker equal-weight paper portfolio (Hardcore).
"""

from __future__ import annotations
import datetime as dt
import time

PAPER_KEY = "paper"
START_CASH = 100_000.0
N_HOLD = 12
DROP_RANK = 20
TARGET_N = 12
REBALANCE_DAYS = 7
COMMISSION = 0.0005


def new_portfolio() -> dict:
    return {
        "version": 1,
        "created": dt.date.today().isoformat(),
        "cash": START_CASH,
        "positions": {},
        "history": [],
        "activity": [],
        "last_rebalance": None,
        "spy_anchor": None,
        "spy_units": 0.0,
        "settings": {"n_hold": N_HOLD, "equal_weight": True,
                     "rebalance_days": REBALANCE_DAYS},
    }


def _log(p, action, symbol, shares, price, note=""):
    p.setdefault("activity", []).append({
        "date": dt.date.today().isoformat(),
        "action": action, "symbol": symbol,
        "shares": round(shares, 3) if shares else None,
        "price": round(price, 2) if price else None, "note": note,
    })


def portfolio_value(p, prices: dict) -> float:
    v = p["cash"]
    for sym, pos in p["positions"].items():
        px = prices.get(sym)
        if px:
            v += pos["shares"] * px
    return round(v, 2)


def _breakdown(sym: str, snap: dict | None, rank: dict) -> str | None:
    if not snap:
        return "no data visibility (removed/paused in the app)"
    trading = snap.get("trading") or {}
    result = snap.get("result") or {}
    fetched = trading.get("fetched_at") or result.get("fetched_at") or 0
    if fetched and (time.time() - fetched) > 7 * 86400:
        return "data stale >7 days — no visibility, no conviction"
    sg = trading.get("signal") or {}
    swing = (sg.get("swing") or {}).get("bias")
    prob = sg.get("probability") or 50
    if swing == "SHORT" and prob >= 60:
        return f"trend broke against it (SHORT @ {prob}% agreement)"
    comp = result.get("composite_score")
    if comp is not None and comp < 35:
        return f"quality collapsed (composite {comp})"
    sent = (result.get("sentiment") or {}).get("score")
    if sent is not None and sent < 30 and swing != "LONG":
        return f"sentiment collapsed ({sent:.0f}) with no trend support"
    r = rank.get(sym, 9999)
    if r > DROP_RANK and swing != "LONG":
        return f"fell out of leadership (rank {r}) and lost its trend"
    return None


def decide(p, ranked_syms: list[str], snaps: dict, macro: dict | None,
           prices: dict, force=False) -> dict:
    today = dt.date.today().isoformat()
    rank = {s: i + 1 for i, s in enumerate(ranked_syms)}
    mult = (macro or {}).get("risk_multiplier", 1.0)
    regime = (macro or {}).get("regime", "?")
    prev_mult = p.get("last_risk_mult")
    acted = False
    decisions = []

    def _note(kind, sym, why):
        decisions.append({"date": today, "kind": kind, "symbol": sym, "why": why})

    cooldown = p.setdefault("cooldown", {})
    def _cooling(sym):
        d0 = cooldown.get(sym)
        return bool(d0) and (dt.date.fromisoformat(today)
                             - dt.date.fromisoformat(d0)).days < 5

    for sym in list(p["positions"]):
        why = _breakdown(sym, snaps.get(sym), rank)
        if why:
            pos = p["positions"][sym]
            px = prices.get(sym) or pos.get("last_price") or pos["avg_cost"]
            proceeds = pos["shares"] * px * (1 - COMMISSION)
            p["cash"] += proceeds
            _log(p, "SELL", sym, pos["shares"], px, why)
            _note("EXIT", sym, why)
            cooldown[sym] = today
            del p["positions"][sym]
            acted = True

    if prev_mult is not None and mult < 1.0 <= prev_mult and p["positions"]:
        def _strength(sym):
            r0 = (snaps.get(sym) or {}).get("result") or {}
            return r0.get("composite_score") or 0
        weakest = sorted(p["positions"], key=_strength)[:2]
        for sym in weakest:
            pos = p["positions"][sym]
            px = prices.get(sym) or pos.get("last_price") or pos["avg_cost"]
            p["cash"] += pos["shares"] * px * (1 - COMMISSION)
            _log(p, "SELL", sym, pos["shares"], px, f"macro risk-off trim ({regime})")
            _note("TRIM", sym, f"macro turned risk-off ({regime}) — raising cash")
            cooldown[sym] = today
            del p["positions"][sym]
            acted = True
    p["last_risk_mult"] = mult

    open_slots = TARGET_N - len(p["positions"])
    if open_slots > 0 and (mult >= 1.0 or force):
        cands = []
        for sym in ranked_syms:
            if sym in p["positions"] or _cooling(sym) or sym not in prices:
                continue
            snap = snaps.get(sym) or {}
            res = snap.get("result") or {}
            sg = ((snap.get("trading") or {}).get("signal") or {})
            comp = res.get("composite_score") or 0
            swing = (sg.get("swing") or {}).get("bias")
            sent = (res.get("sentiment") or {}).get("score")
            if comp >= 45 and swing == "LONG" and (sent is None or sent >= 40):
                cands.append(sym)
            if len(cands) >= open_slots:
                break
        if cands:
            per = (p["cash"] * 0.98) / max(len(cands), 1)
            for sym in cands:
                px = prices[sym]
                shares = (per * (1 - COMMISSION)) / px
                if shares * px < 100:
                    continue
                p["cash"] -= shares * px * (1 + COMMISSION)
                pos = p["positions"].setdefault(sym, {"shares": 0.0, "avg_cost": px})
                pos["shares"] += shares
                pos["avg_cost"] = px
                pos["entry_date"] = today
                _log(p, "BUY", sym, shares, px,
                     f"qualified entry (rank {rank.get(sym)}, regime {regime})")
                _note("BUY", sym, f"rank {rank.get(sym)}, LONG trend, quality ok — deploying open capacity")
                acted = True

    if not acted:
        _note("HOLD", "—", f"no thesis broke, regime steady ({regime}) — sitting on hands")

    dl = p.setdefault("decisions", [])
    dl.extend(decisions)
    del dl[:-120]
    p["last_decide"] = today
    return {"acted": acted, "decisions": decisions, "roster": list(p["positions"])}


def rebalance(p, ranked_syms, prices, force=False):
    return decide(p, ranked_syms, {}, None, prices, force=force)


def snapshot_value(p, prices: dict) -> None:
    for _s, _pos in p.get("positions", {}).items():
        if prices.get(_s):
            _pos["last_price"] = prices[_s]
    today = dt.date.today().isoformat()
    val = portfolio_value(p, prices)
    spy_val = None
    spy_px = prices.get("SPY")
    if spy_px and p["spy_units"]:
        spy_val = round(p["spy_units"] * spy_px, 2)
    p["history"] = [h for h in p["history"] if h["date"] != today]
    p["history"].append({"date": today, "value": val, "spy_value": spy_val})
    p["history"].sort(key=lambda h: h["date"])


def performance(p, prices: dict) -> dict:
    val = portfolio_value(p, prices)
    total_ret = (val / START_CASH - 1) * 100
    spy_ret = None
    spy_px = prices.get("SPY")
    if spy_px and p["spy_units"]:
        spy_now = p["spy_units"] * spy_px
        spy_basis = p.get("spy_basis") or START_CASH
        spy_ret = (spy_now / spy_basis - 1) * 100

    def window_ret(days):
        if len(p["history"]) < 2:
            return None
        cutoff = (dt.date.today() - dt.timedelta(days=days)).isoformat()
        past = [h for h in p["history"] if h["date"] <= cutoff]
        if not past:
            return None
        base = past[-1]
        if not base["value"]:
            return None
        return round((val / base["value"] - 1) * 100, 2)

    return {
        "value": val, "total_return_pct": round(total_ret, 2),
        "spy_return_pct": round(spy_ret, 2) if spy_ret is not None else None,
        "vs_spy": round(total_ret - spy_ret, 2) if spy_ret is not None else None,
        "ret_7d": window_ret(7), "ret_30d": window_ret(30),
        "ret_ytd": window_ret((dt.date.today() - dt.date(dt.date.today().year, 1, 1)).days),
        "ret_1y": window_ret(365),
        "positions": len(p["positions"]),
        "cash_pct": round(p["cash"] / val * 100, 1) if val else 100,
    }


def load_portfolio(cloud_url: str | None):
    if not cloud_url:
        return None, "error"
    try:
        import cloud_sync as CS
        blob = CS.load_blob(cloud_url, PAPER_KEY)
    except Exception:
        return None, "error"
    if blob and blob.get("version"):
        return blob, "loaded"
    return None, "empty"


def save_portfolio(p, cloud_url: str | None) -> dict:
    status = {"cloud": False, "error": None}
    if cloud_url:
        try:
            import cloud_sync as CS
            CS.save_blob(cloud_url, PAPER_KEY, p)
            status["cloud"] = True
        except Exception as e:
            status["error"] = f"CLOUD SAVE FAILED: {e}"
    else:
        status["error"] = "no cloud URL"
    return status
