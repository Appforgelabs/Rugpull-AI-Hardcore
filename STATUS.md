# Rugpull AI Hardcore — Status (updated)

**Repo**: https://github.com/Appforgelabs/Rugpull-AI-Hardcore

## Done
- Full core hardened (fmp_client premium, fundamentals, analyze, trade_signals, ta_engine, demark, signals, technicals, prediction_zones, volume_profile, macro_engine, snapshot_store, watchlist, cloud_sync)
- Central logging
- **New: error_log.py** — persistent JSONL error collector + in-memory ring buffer
- Unit tests skeleton
- Pinned requirements, .gitignore, secrets example
- README updated

## Remaining large modules (copy from original Rugpull_AI and drop in)
These are still needed for the full multi-tab UI. They are compatible; just copy them and optionally add `from logging_config import log` + replace bare `except Exception:` with `log.warning(...)`.

```
paper_portfolio.py
prediction_tracker.py
report_engine.py
research_screener.py
scenario_engine.py
dashboard.py
zone_chart.py
backtest.py
learn_content.py
seasonality.py
quadrant_map.py
corridor.html
Code.gs
streamlit_app.py   <-- see below for how to add the Diagnostics tab
```

## How to add the new Error Log / Diagnostics tab

1. Copy the original `streamlit_app.py` into this repo.
2. At the top add:
   ```python
   from error_log import get_error_log
   from logging_config import log, setup_logging
   setup_logging("INFO")
   el = get_error_log()
   ```
3. Wrap risky calls (fetch_and_store, build_trading, etc.) with:
   ```python
   try:
       ...
   except Exception as e:
       el.record("streamlit_app", e, context=f"ticker={sym}")
       st.error(str(e))
   ```
4. Add "🔧 Diagnostics" to ALL_TABS and implement the tab body using the helper below (or import from diagnostics_tab.py if present).

The Diagnostics tab shows:
- Last 50 errors (newest first) with source, message, traceback snippet, timestamp
- Summary counts by level / source
- Clear button + Download JSON export
- Quick tips for common FMP / cloud / snapshot issues

This makes fixing production issues on Streamlit Cloud extremely fast — no more hunting Cloud logs.

## Quick start (CLI works now)
```bash
export FMP_API_KEY=your_premium_key
pip install -r requirements.txt
python analyze.py NVDA PLTR TSLA
```

Say “push remaining modules” if you want me to continue the full copy of the large files next turn.
