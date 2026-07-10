# Rugpull AI Hardcore — Current Status

**Repo**: https://github.com/Appforgelabs/Rugpull-AI-Hardcore

## What's done (Hardcore improvements)
- [x] New repo created under Appforgelabs
- [x] Hardened `fmp_client.py` (premium throttle 0.12s, size-aware cache prune, better errors/logging, history TTL)
- [x] Cleaned `fundamentals.py` (rev CAGR fixed, single PE-from-prices source of truth)
- [x] Improved `analyze.py` (no silent excepts, uses F.pe_distribution_from_prices, logging)
- [x] Hardened `signals.py`, `technicals.py`, `trade_signals.py` (v2 design preserved), `ta_engine.py`, `demark.py`
- [x] Centralized `logging_config.py`
- [x] Pinned `requirements.txt` + pytest + black + mypy
- [x] `.gitignore`, `secrets.toml.example`
- [x] Unit tests skeleton (`tests/`)
- [x] Comprehensive README explaining philosophy + improvements

## What's still needed for full Streamlit UI
Copy (or I can push next) from original Rugpull_AI:
- streamlit_app.py (large, works with Hardcore core after small import/logging tweaks)
- snapshot_store.py, cloud_sync.py, watchlist.py
- paper_portfolio.py, prediction_tracker.py, report_engine.py, research_screener.py
- scenario_engine.py, macro_engine.py, dashboard.py, zone_chart.py, prediction_zones.py
- volume_profile.py, backtest.py, learn_content.py, seasonality.py, quadrant_map.py
- corridor.html, Code.gs

Just say **"finish full copy + light harden"** and I will push the remaining files with the silent-except → log.warning treatment applied where appropriate.

## How to use right now (CLI)
```bash
export FMP_API_KEY=your_premium_key
pip install -r requirements.txt
python analyze.py NVDA PLTR TSLA AMD
```

Premium FMP is fully supported (higher limits, full history, lower throttle).
