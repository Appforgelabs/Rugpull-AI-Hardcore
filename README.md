# Rugpull AI Hardcore

**Hardened, production-grade fork of Rugpull_AI**

Transparent, fundamentals-first stock decision-support engine with:
- Premium FMP support (higher rate limits, full endpoints, lower throttle)
- Clean architecture, de-duplicated code, proper error handling + logging
- Improved disk caching with size awareness
- Modular Streamlit structure (in progress)
- Unit tests + CI-ready
- Self-measuring prediction ledger + conviction-driven paper portfolio
- Rule-based entry/exit levels, honest volatility cones, DeMark TD Sequential
- Cloud sync (watchlist / starred / favorites / paper / ledger) via your Apps Script

> Not financial advice. Decision support only. Overbought can stay overbought. Tight risk control required.

## Design Philosophy (unchanged & amplified)
- **Fundamentals are the durable signal** (quality + value + transparent DCF with visible assumptions).
- Macro is a **filter / tilt**, never a thesis flipper.
- Sentiment is lightly weighted and noisy by design.
- Entry/exit = **rule-based levels** (VWAP bands, ATR stops, S/R) — inspectable, not predicted prices.
- Forecasts are **humble volatility cones**. The width is the lesson.
- Every score shows its work. Disagree with any leg openly.
- The app grades itself (prediction ledger re-weights signals by measured hit-rate).

## Quick Start (FMP Premium)

```bash
git clone https://github.com/Appforgelabs/Rugpull-AI-Hardcore.git
cd Rugpull-AI-Hardcore
python -m venv .venv && source .venv/bin/activate   # or Windows equivalent
pip install -r requirements.txt
export FMP_API_KEY="your_premium_key"
python analyze.py NVDA AMD PLTR TSLA
```

### Streamlit UI (local)
```bash
cp secrets.toml.example .streamlit/secrets.toml   # add FMP_API_KEY + optional APPS_SCRIPT_URL
streamlit run streamlit_app.py
```

### Streamlit Cloud
1. Push this repo.
2. share.streamlit.io → New app → this repo / main / streamlit_app.py
3. Secrets:
   ```toml
   FMP_API_KEY = "your_premium_key"
   APPS_SCRIPT_URL = "https://script.google.com/macros/s/.../exec"  # optional, has built-in default
   ```

## Key Improvements over original Rugpull_AI
1. **Error handling**: No more silent `except Exception: pass`. Logging + graceful degradation with visible warnings.
2. **Code de-duplication**: Single source of truth for PE distribution (price/earnings fallback), OHLCV helpers, etc.
3. **FMP client (Premium-tuned)**: Lower throttle (0.1s), better cache (TTL + max size / prune), clearer errors, history limit option, more robust endpoint handling.
4. **Quality score cleanup**: Fixed rev CAGR calculation (was always-true filter).
5. **DCF assumptions surfaced**: UI sliders + explicit in reports.
6. **Logging**: Centralized, levels for debug/info/warn/error. Easy to see rate-limits or data issues.
7. **Tests**: Unit tests for fundamentals, signals, swing core.
8. **Requirements**: Pinned + pytest, black, mypy-ready.
9. **Structure**: Ready for further modularization of the large Streamlit app.
10. **Premium features**: Ready for more endpoints (options, advanced ratios, etc.) without code changes.

## Architecture
```
fmp_client.py       # Cached, throttled, premium-friendly data access. All paths in ENDPOINTS.
fundamentals.py     # quality / value / simple_dcf / PE dist / NTM EPS (transparent).
technicals.py       # Momentum, VWAP bands, ATR, S/R, humble forecast.
trade_signals.py    # Multi-TF TA + de-duplicated trend votes + mean-reversion stretch (separate).
ta_engine.py        # Pure indicator math (no TA-Lib).
signals.py          # Macro regime + sentiment providers.
analyze.py          # Orchestrator — builds composite + zones + trading row.
streamlit_app.py    # Full multi-tab UI (Dashboard, Analyzer, Trading, Research, Paper, Report, Macro, Backtest, Learn, Corridor, Map, Seasonality, Settings).
snapshot_store.py   # On-disk snapshots so tabs are instant.
cloud_sync.py       # Apps Script namespace for cross-device state.
prediction_tracker.py # Self-grading ledger that re-weights signals.
paper_portfolio.py  # Conviction engine paper trading vs SPY.
...                 # zone_chart, report_engine, demark, volume_profile, etc.
```

## Extending
- Tune `WEIGHTS` in analyze.py or via Streamlit sliders.
- Add X sentiment: implement fetch_fn and pass to XSentiment.
- New endpoints: just add to `fmp_client.ENDPOINTS`.
- New signal: add vote in trade_signals, it will be learned by the ledger.

## License
MIT (same as original spirit).

---
*Built for hardcore first-principles traders who want the work shown, not black boxes.*
