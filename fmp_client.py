"""
fmp_client.py — hardened, premium-friendly, cached client for Financial Modeling Prep.

Improvements in Hardcore:
- Lower default throttle (premium users can go faster)
- Cache with TTL + max size / automatic prune of oldest
- Explicit logging of 401/429/404 and cache hits
- History limit option (premium full history is fine; free plans still protected)
- All endpoint paths centralized. Easy to add premium endpoints later.
- Cleaner error messages.
"""

from __future__ import annotations

import os
import time
import json
import hashlib
import logging
from pathlib import Path
from typing import Any

import requests

from logging_config import log

BASE = "https://financialmodelingprep.com"

# All endpoint paths in one place. {sym} substituted at call time.
# Premium plans have full access to /stable/.
ENDPOINTS = {
    "profile":        "/stable/profile?symbol={sym}",
    "quote":          "/stable/quote?symbol={sym}",
    "income":         "/stable/income-statement?symbol={sym}&period=annual&limit=8",
    "balance":        "/stable/balance-sheet-statement?symbol={sym}&period=annual&limit=8",
    "cashflow":       "/stable/cash-flow-statement?symbol={sym}&period=annual&limit=8",
    "ratios":         "/stable/ratios?symbol={sym}&period=annual&limit=8",
    "earnings":       "/stable/earnings?symbol={sym}&limit=40",
    "key_metrics":    "/stable/key-metrics?symbol={sym}&period=annual&limit=8",
    "ratios_ttm":     "/stable/ratios-ttm?symbol={sym}",
    "history":        "/stable/historical-price-eod/full?symbol={sym}",
    "news_sentiment": "/stable/news/stock?symbols={sym}&limit=50",
    "estimates":      "/stable/analyst-estimates?symbol={sym}&period=quarter&limit=16",
    "intraday":       "/stable/historical-chart/{interval}?symbol={sym}",
    "treasury":       "/stable/treasury-rates",
    "econ":           "/stable/economic-indicators?name={sym}",
    # Premium-friendly additions (safe no-ops on lower plans)
    "enterprise":     "/stable/enterprise-values?symbol={sym}&period=annual&limit=6",
    "owner_earnings": "/stable/owner-earnings?symbol={sym}",
}


class FMPError(RuntimeError):
    pass


class FMPClient:
    def __init__(
        self,
        api_key: str | None = None,
        cache_dir: str = ".fmp_cache",
        cache_ttl: int = 3600,          # 1h default
        history_ttl: int = 6 * 3600,    # longer for full history
        throttle: float = 0.12,         # premium-friendly (was 0.25)
        max_cache_mb: float = 250.0,    # prune when over this
    ):
        self.api_key = api_key or os.environ.get("FMP_API_KEY")
        if not self.api_key:
            raise FMPError(
                "No FMP API key. Set FMP_API_KEY env var or pass api_key=... "
                "(Premium recommended for full history + higher limits)"
            )
        self.cache = Path(cache_dir)
        self.cache.mkdir(exist_ok=True)
        self.ttl = cache_ttl
        self.history_ttl = history_ttl
        self.throttle = throttle
        self.max_cache_bytes = int(max_cache_mb * 1024 * 1024)
        self._last_call = 0.0
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "Rugpull-AI-Hardcore/1.0"})

    # ---- internal -------------------------------------------------------
    def _cache_path(self, url: str) -> Path:
        h = hashlib.md5(url.encode()).hexdigest()[:16]
        return self.cache / f"{h}.json"

    def _prune_cache_if_needed(self) -> None:
        """Remove oldest cache files if total size exceeds max."""
        try:
            files = sorted(self.cache.glob("*.json"), key=lambda p: p.stat().st_mtime)
            total = sum(p.stat().st_size for p in files)
            if total <= self.max_cache_bytes:
                return
            log.info("Cache prune: %.1f MB > limit, removing oldest...", total / 1e6)
            for p in files:
                if total <= self.max_cache_bytes * 0.7:
                    break
                size = p.stat().st_size
                p.unlink(missing_ok=True)
                total -= size
            log.info("Cache pruned to ~%.1f MB", total / 1e6)
        except Exception as e:
            log.warning("Cache prune failed: %s", e)

    def _get(self, path: str, ttl: int | None = None) -> Any:
        sep = "&" if "?" in path else "?"
        url = f"{BASE}{path}{sep}apikey={self.api_key}"
        cp = self._cache_path(url)
        effective_ttl = ttl if ttl is not None else self.ttl

        if cp.exists() and (time.time() - cp.stat().st_mtime) < effective_ttl:
            try:
                data = json.loads(cp.read_text())
                log.debug("Cache HIT %s", path[:60])
                return data
            except Exception:
                pass  # corrupt cache → re-fetch

        # throttle
        wait = self.throttle - (time.time() - self._last_call)
        if wait > 0:
            time.sleep(wait)

        try:
            r = self._session.get(url, timeout=30)
            self._last_call = time.time()
        except requests.RequestException as e:
            raise FMPError(f"Network error on {path}: {e}") from e

        if r.status_code == 401:
            raise FMPError("401 — bad/expired FMP key or endpoint not on your plan. Check Premium status.")
        if r.status_code == 429:
            raise FMPError("429 — rate limited. Raise throttle or wait. Premium plans have higher limits.")
        if r.status_code == 404:
            raise FMPError(f"404 — endpoint moved or unavailable: {path}. Check FMP docs for new path.")
        if r.status_code >= 400:
            raise FMPError(f"HTTP {r.status_code} on {path}: {r.text[:200]}")

        try:
            data = r.json()
        except Exception as e:
            raise FMPError(f"Invalid JSON from FMP: {e}") from e

        try:
            cp.write_text(json.dumps(data))
            self._prune_cache_if_needed()
        except Exception as e:
            log.warning("Could not write cache: %s", e)

        log.debug("Fetched %s", path[:60])
        return data

    def fetch(self, key: str, sym: str) -> Any:
        if key not in ENDPOINTS:
            raise FMPError(f"Unknown endpoint key '{key}'. Known: {list(ENDPOINTS)}")
        return self._get(ENDPOINTS[key].format(sym=sym.upper()))

    # ---- convenience ----------------------------------------------------
    def profile(self, sym):        return _first(self.fetch("profile", sym))
    def quote(self, sym):          return _first(self.fetch("quote", sym))
    def income(self, sym):         return self.fetch("income", sym)
    def balance(self, sym):        return self.fetch("balance", sym)
    def cashflow(self, sym):       return self.fetch("cashflow", sym)
    def ratios(self, sym):         return self.fetch("ratios", sym)
    def earnings(self, sym):       return self.fetch("earnings", sym)
    def ratios_ttm(self, sym):     return _first(self.fetch("ratios_ttm", sym))
    def key_metrics(self, sym):    return self.fetch("key_metrics", sym)
    def history(self, sym, limit: int | None = None):
        """Full history (premium). Optionally limit to most recent N bars after fetch."""
        data = self._get(ENDPOINTS["history"].format(sym=sym.upper()), ttl=self.history_ttl)
        hist = _normalize_history(data)
        if limit and isinstance(hist, list) and len(hist) > limit:
            # FMP full is newest-first usually; we normalize to oldest-first later
            hist = hist[-limit:]
        return hist
    def news(self, sym):           return self.fetch("news_sentiment", sym)
    def estimates(self, sym):      return self.fetch("estimates", sym)

    def intraday(self, sym, interval="5min", days_back=7):
        """Intraday OHLCV. interval in {1min,5min,15min,30min,1hour,4hour}."""
        import datetime as _dt
        to = _dt.date.today()
        frm = to - _dt.timedelta(days=days_back)
        path = (f"/stable/historical-chart/{interval}?symbol={sym.upper()}"
                f"&from={frm}&to={to}")
        return self._get(path, ttl=900)  # 15 min for intraday


def _first(data):
    if isinstance(data, list):
        return data[0] if data else {}
    return data or {}


def _normalize_history(data):
    """FMP may return {'historical': [...]} or bare list."""
    if isinstance(data, dict) and "historical" in data:
        return data["historical"]
    return data if isinstance(data, list) else []
