"""
signals.py — macro regime + sentiment (Hardcore).

Macro = regime filter / tilt. Sentiment = small-weight, noisy, pluggable.
Hardened: proper logging instead of silent failures.
"""

from __future__ import annotations
import logging
import numpy as np

from logging_config import log


def macro_regime(client) -> dict:
    """Yield-curve based regime. Returns tilt multiplier for required margin of safety."""
    try:
        rates = client.fetch("treasury", "")
        latest = rates[0] if isinstance(rates, list) and rates else {}
        y2  = float(latest.get("year2", latest.get("month2", "nan")) or "nan")
        y10 = float(latest.get("year10", "nan") or "nan")
    except Exception as e:
        log.warning("Treasury data unavailable: %s", e)
        return {"regime": "unknown", "tilt": 1.0, "note": "treasury data unavailable"}

    if y2 != y2 or y10 != y10:
        return {"regime": "unknown", "tilt": 1.0}

    spread = y10 - y2
    if spread < -0.2:
        regime, tilt = "inverted / late-cycle caution", 1.25
    elif spread < 0.3:
        regime, tilt = "flat / neutral", 1.05
    else:
        regime, tilt = "steep / risk-on friendly", 0.95
    return {
        "regime": regime, "tilt": tilt,
        "10y": round(y10, 2), "2y": round(y2, 2),
        "spread_10y_2y": round(spread, 2),
        "note": "tilt multiplies the margin of safety you demand at entry",
    }


class SentimentProvider:
    def score(self, sym: str) -> dict:
        raise NotImplementedError


class FMPNewsSentiment(SentimentProvider):
    POS = {"beat", "beats", "surge", "soar", "record", "upgrade", "bullish",
           "growth", "strong", "raises", "outperform", "rally", "wins", "tops"}
    NEG = {"miss", "misses", "plunge", "drop", "downgrade", "bearish", "weak",
           "cuts", "lawsuit", "probe", "recall", "falls", "slump", "warns"}

    def __init__(self, client):
        self.client = client

    def score(self, sym: str) -> dict:
        try:
            items = self.client.news(sym) or []
        except Exception as e:
            log.warning("FMP news for %s failed: %s", sym, e)
            return {"score": 50.0, "n": 0, "source": "fmp_news (unavailable)"}
        if not isinstance(items, list) or not items:
            return {"score": 50.0, "n": 0, "source": "fmp_news (empty)"}

        vals = []
        for it in items[:50]:
            s = it.get("sentiment")
            if isinstance(s, (int, float)):
                vals.append(_norm_sentiment(float(s)))
            else:
                text = f"{it.get('title','')} {it.get('text','')}".lower()
                p = sum(w in text for w in self.POS)
                n = sum(w in text for w in self.NEG)
                if p or n:
                    vals.append((p - n) / (p + n))
        if not vals:
            return {"score": 50.0, "n": len(items), "source": "fmp_news (no signal)"}
        mean = float(np.mean(vals))
        return {"score": round((mean + 1) / 2 * 100, 1), "n": len(vals),
                "source": "fmp_news"}


class XSentiment(SentimentProvider):
    def __init__(self, fetch_fn=None):
        self.fetch_fn = fetch_fn

    def score(self, sym: str) -> dict:
        if self.fetch_fn is None:
            return {"score": 50.0, "n": 0, "source": "x (disabled)"}
        try:
            posts = self.fetch_fn(sym) or []
        except Exception as e:
            log.warning("X sentiment fetch failed: %s", e)
            return {"score": 50.0, "n": 0, "source": "x (error)"}
        lex = FMPNewsSentiment(None)
        vals = []
        for t in posts:
            t = (t or "").lower()
            p = sum(w in t for w in lex.POS)
            n = sum(w in t for w in lex.NEG)
            if p or n:
                vals.append((p - n) / (p + n))
        if not vals:
            return {"score": 50.0, "n": len(posts), "source": "x (no signal)"}
        return {"score": round((float(np.mean(vals)) + 1) / 2 * 100, 1),
                "n": len(vals), "source": "x"}


def _norm_sentiment(s: float) -> float:
    if 0 <= s <= 1:
        return s * 2 - 1
    return max(-1.0, min(1.0, s))
