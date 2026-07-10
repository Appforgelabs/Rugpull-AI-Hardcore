"""
demark.py — unofficial TD Sequential (Hardcore). Same solid implementation as original.
"""

from __future__ import annotations
import pandas as pd


def td_state(df: pd.DataFrame, lookback_report: int = 6) -> dict:
    if df is None or len(df) < 20:
        return {"ok": False, "note": "need >=20 daily bars"}
    d = df.reset_index(drop=True)
    c, h, l = d["close"].values, d["high"].values, d["low"].values
    n = len(d)
    dates = [str(x)[:10] for x in d["date"]] if "date" in d else [str(i) for i in range(n)]

    buy_count = [0] * n
    sell_count = [0] * n
    completions = []
    for i in range(4, n):
        if c[i] < c[i - 4]:
            buy_count[i] = buy_count[i - 1] + 1 if buy_count[i - 1] < 9 else 1
            sell_count[i] = 0
        elif c[i] > c[i - 4]:
            sell_count[i] = sell_count[i - 1] + 1 if sell_count[i - 1] < 9 else 1
            buy_count[i] = 0
        else:
            buy_count[i] = sell_count[i] = 0

        if buy_count[i] == 9:
            s0 = i - 8
            perf = (l[i] <= min(l[i - 3], l[i - 2])
                    or l[i - 1] <= min(l[i - 3], l[i - 2]))
            tdst = round(float(max(h[s0], c[s0 - 1] if s0 else h[s0])), 2)
            completions.append((i, "BUY", bool(perf), tdst))
        if sell_count[i] == 9:
            s0 = i - 8
            perf = (h[i] >= max(h[i - 3], h[i - 2])
                    or h[i - 1] >= max(h[i - 3], h[i - 2]))
            tdst = round(float(min(l[s0], c[s0 - 1] if s0 else l[s0])), 2)
            completions.append((i, "SELL", bool(perf), tdst))

    countdown = None
    if completions:
        ci, side, perf, tdst = completions[-1]
        cnt = 0
        complete_at = None
        for j in range(ci + 1, n):
            if side == "BUY" and sell_count[j] == 9:
                cnt = -1
                break
            if side == "SELL" and buy_count[j] == 9:
                cnt = -1
                break
            if j < 2:
                continue
            if side == "BUY" and c[j] <= l[j - 2]:
                cnt += 1
            elif side == "SELL" and c[j] >= h[j - 2]:
                cnt += 1
            if cnt == 13:
                complete_at = j
                break
        if cnt >= 0:
            countdown = {"side": side, "count": min(cnt, 13),
                         "complete": complete_at is not None,
                         "completed_date": dates[complete_at] if complete_at else None}

    recent = [{"side": s, "date": dates[i], "bars_ago": n - 1 - i,
               "perfected": p, "tdst": t}
              for i, s, p, t in completions if n - 1 - i <= 30][-4:]

    cur_side = "BUY" if buy_count[-1] > 0 else "SELL" if sell_count[-1] > 0 else None
    cur_count = buy_count[-1] or sell_count[-1] or 0

    read = None
    last = completions[-1] if completions else None
    if last:
        i, side, perf, tdst = last
        ago = n - 1 - i
        if ago <= lookback_report:
            read = (f"TD {side} Setup 9{' (perfected)' if perf else ''} "
                    f"{ago} bar{'s' if ago != 1 else ''} ago — "
                    f"{'downside' if side == 'BUY' else 'upside'} exhaustion flag")
    if countdown and countdown["count"] >= 11:
        read = (read + " · " if read else "") + \
               f"TD {countdown['side']} Countdown {countdown['count']}/13"

    return {
        "ok": True,
        "setup_side": cur_side, "setup_count": int(cur_count),
        "recent_setups": recent,
        "countdown": countdown,
        "read": read,
        "note": "Unofficial TD Sequential (published rules; countdown "
                "cancellation simplified). Exhaustion flags, not commands — "
                "the ledger measures whether they work on your names.",
    }


def td_vote(state: dict, max_age: int = 5) -> int:
    if not state.get("ok"):
        return 0
    v = 0
    for s in state.get("recent_setups", []):
        if s["bars_ago"] <= max_age:
            v = 1 if s["side"] == "BUY" else -1
    cd = state.get("countdown")
    if cd and cd.get("complete"):
        v = 1 if cd["side"] == "BUY" else -1
    return v
