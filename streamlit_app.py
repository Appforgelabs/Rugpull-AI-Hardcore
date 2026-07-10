"""
streamlit_app.py — Rugpull AI Hardcore

Full original multi-tab UI (Dashboard, Analyzer, Trading, Scenarios, Research,
Paper Trade, Report, Macro, Backtest, Learn, Corridor, Map, Seasonality, Settings)
+ Hardcore additions:
  - Central error_log + 🔧 Diagnostics tab so we can fix issues in minutes
  - Hardened imports / logging
  - Premium FMP ready

Data is fetched ONLY when you hit Update. Everything else reads from snapshots.
"""

from __future__ import annotations
import os
import json
import datetime as dt
from pathlib import Path
import traceback

import streamlit as st

# page config first
st.set_page_config(page_title="Rugpull AI Hardcore", page_icon="📈", layout="wide")

# ---- logging + error collection (Hardcore) --------------------------------
try:
    from logging_config import setup_logging, log
    setup_logging("INFO")
except Exception:
    log = None

try:
    from error_log import get_error_log
    el = get_error_log()
except Exception:
    el = None

def _record(source, exc, context=""):
    if el:
        try:
            el.record(source, exc, context=context)
        except Exception:
            pass
    if log:
        try:
            log.exception("[%s] %s", source, context)
        except Exception:
            pass

# ---- core imports ---------------------------------------------------------
from fmp_client import FMPClient, FMPError
import analyze as A
import signals as S
import watchlist as W
import snapshot_store as SS

# optional modules (full UI)
try:
    import zone_chart as ZC
except Exception as e:
    ZC = None
    _record("import.zone_chart", e)

# ---- minimalist styling ---------------------------------------------------
st.markdown("""
<style>
  .block-container {padding-top: 2.2rem; max-width: 1100px;}
  [data-testid="stMetricValue"] {font-size: 1.1rem;}
  h1 {font-weight: 600; letter-spacing: -0.5px;}
  .muted {color:#8899aa; font-size:0.85rem;}
  .pill {display:inline-block; padding:2px 10px; border-radius:10px;
         font-size:0.78rem; font-weight:600;}
</style>
""", unsafe_allow_html=True)


def get_key():
    try:
        if "FMP_API_KEY" in st.secrets:
            return st.secrets["FMP_API_KEY"]
    except Exception:
        pass
    return os.environ.get("FMP_API_KEY")


@st.cache_resource
def get_client(key: str) -> FMPClient:
    return FMPClient(api_key=key)


def show_svg(svg: str, height: int = 430):
    st.components.v1.html(svg, height=height, scrolling=False)


def fetch_and_store(client, sym):
    try:
        res = A.analyze(client, sym, S.FMPNewsSentiment(client))
        SS.save_snapshot(sym, res, price_series=res.get("series"))
        return res
    except Exception as e:
        _record("fetch_and_store", e, context=f"symbol={sym}")
        raise


def lookup_ticker(client, sym):
    sym = sym.upper().strip()
    res = fetch_and_store(client, sym)
    try:
        import trade_signals as _TS
        _spy = _TS.to_ohlcv(client.history("SPY"))["close"].tolist()
    except Exception:
        _spy = None
    try:
        tr = A.build_trading(client, sym, intraday_interval="5min", spy_closes=_spy)
        if tr.get("ok"):
            SS.save_trading(sym, tr)
    except Exception as e:
        _record("lookup_ticker.trading", e, context=sym)
    return res


def fetch_macro(client):
    import macro_engine as ME
    m = ME.build_macro(client)
    SS.save_macro(m)
    return m


APPS_SCRIPT_URL_DEFAULT = "https://script.google.com/macros/s/AKfycbzbGKyBiLmWS7736GDhYeoKt6QHJIFKbywKza83N7AcfoeE4-cSYV4sNvydwuvK4LGWRw/exec"


def get_cloud_url():
    try:
        if "APPS_SCRIPT_URL" in st.secrets:
            return st.secrets["APPS_SCRIPT_URL"]
    except Exception:
        pass
    return st.session_state.get("cloud_url") or APPS_SCRIPT_URL_DEFAULT


# ---- state ----------------------------------------------------------------
if "watchlist" not in st.session_state:
    st.session_state.watchlist = W.load_watchlist()
if "starred" not in st.session_state:
    st.session_state.starred = []
if "favorites" not in st.session_state:
    st.session_state.favorites = []
if "cloud_pulled" not in st.session_state:
    st.session_state.cloud_pulled = True
    _url = get_cloud_url()
    if _url:
        try:
            import cloud_sync as CS
            blob = CS.load_app_state(_url)
            if blob:
                if blob.get("watchlist"):
                    st.session_state.watchlist = blob["watchlist"]
                if blob.get("starred"):
                    st.session_state.starred = blob["starred"]
                if blob.get("favorites") is not None:
                    st.session_state.favorites = blob["favorites"]
        except Exception as e:
            _record("cloud_pull", e)

st.title("Rugpull AI Hardcore")
st.markdown('<div class="muted">Transparent scoring + σ-based probability zones. '
            'Data is stored until you hit Update. Not financial advice; the zones '
            'are probability ranges, not forecasts. Hardcore edition with live error log.</div>',
            unsafe_allow_html=True)

key = get_key()
if not key:
    st.error("No FMP API key. Streamlit Cloud: Settings → Secrets → "
             "`FMP_API_KEY = \"...\"`. Local: set FMP_API_KEY env var.")
    st.stop()
client = get_client(key)

if "app_settings" not in st.session_state:
    st.session_state.app_settings = {"visible_tabs": None, "inactive": []}
    try:
        import cloud_sync as _CS
        _blob = _CS.load_blob(get_cloud_url(), "settings")
        if _blob:
            st.session_state.app_settings.update(
                {k: _blob.get(k) for k in ("visible_tabs", "inactive")
                 if _blob.get(k) is not None})
    except Exception:
        pass

def save_settings():
    try:
        import cloud_sync as _CS
        _CS.save_blob(get_cloud_url(), "settings",
                      dict(st.session_state.app_settings, version=1))
    except Exception as e:
        _record("save_settings", e)

syms_all = [t["symbol"] for t in st.session_state.watchlist]
_inactive = set(st.session_state.app_settings.get("inactive") or [])
syms = [s for s in syms_all if s not in _inactive]

def _fav_save():
    try:
        import cloud_sync as _CS
        blob = _CS.load_blob(get_cloud_url(), "rugpull") or {}
        blob["favorites"] = st.session_state.favorites
        _CS.save_blob(get_cloud_url(), "rugpull", blob)
    except Exception as e:
        _record("fav_save", e)

def is_fav(sym):
    return sym in st.session_state.favorites

def fav_toggle(sym, key_prefix=""):
    on = is_fav(sym)
    label = "★" if on else "☆"
    if st.button(label, key=f"fav_{key_prefix}_{sym}",
                 help="Remove favorite" if on else "Mark favorite"):
        if on:
            st.session_state.favorites = [s for s in st.session_state.favorites if s != sym]
        else:
            st.session_state.favorites = st.session_state.favorites + [sym]
        _fav_save()
        st.rerun()

def fav_mark(sym):
    return "★ " if is_fav(sym) else ""


# ---- 🔎 find-anything search ----------------------------------------------
_q = st.text_input("search",
                   placeholder="🔎 Find any ticker or company… then press Enter",
                   label_visibility="collapsed", key="global_search")
if _q and _q.strip():
    _ql = _q.strip().upper()
    _snaps_idx = SS.all_snapshots()
    _names = {t["symbol"]: t.get("name", t["symbol"]) for t in st.session_state.watchlist}
    _universe = sorted(set(list(_names) + list(_snaps_idx)))
    _hits = [s for s in _universe
             if _ql in s or _ql in str(_names.get(s, "")).upper()
             or _ql in str(((_snaps_idx.get(s) or {}).get("result") or {}).get("company", "")).upper()]
    if _hits:
        _sel = _hits[0] if len(_hits) == 1 else st.selectbox(f"{len(_hits)} matches — pick one", _hits, key="search_pick")
        _snp = _snaps_idx.get(_sel) or {}
        _res = _snp.get("result") or {}
        _trd = _snp.get("trading") or {}
        _sg = _trd.get("signal") or {}
        _corr = ((_res.get("zones") or {}).get("corridor") or {})
        _px = _trd.get("price") or _res.get("price")
        _up = (round((_corr["fair"] - _px) / _px * 100, 1)
               if _corr.get("ok") and _corr.get("fair") and _px else None)
        fav_toggle(_sel, "search")
        _paused = " · ⏸ PAUSED" if _sel in _inactive else ""
        st.markdown(f"#### {fav_mark(_sel)}{_sel} — {_res.get('company', _names.get(_sel, _sel))}"
                    f"{_paused}  <span class='muted'>({SS.age_str(_snp) if _snp else 'no data'})</span>",
                    unsafe_allow_html=True)
        if not (_res or _trd):
            st.info(f"{_sel} is known but has no stored analysis yet — hit ⟳ Update all, or analyze it on demand below.")
            if st.button(f"⚡ Analyze {_sel} now", key="search_analyze_known"):
                with st.spinner(f"Analyzing {_sel}…"):
                    try:
                        lookup_ticker(client, _sel)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Couldn't analyze {_sel}: {e}")
                        _record("search_analyze", e, _sel)
        else:
            _c1, _c2, _c3, _c4 = st.columns(4)
            _c1.metric("Price", f"${_px}" if _px else "—")
            _c2.metric("Composite", _res.get("composite_score", "—"))
            _c3.metric("Bias", f"{_sg.get('direction','—')}",
                       f"{_sg.get('probability','')}% agreement" if _sg.get("probability") else None,
                       delta_color="off")
            _c4.metric("Corridor gap", f"{_up:+.0f}%" if _up is not None else "—")
            _d1, _d2, _d3, _d4 = st.columns(4)
            _d1.metric("Swing", ((_sg.get("swing") or {}).get("bias")) or "—")
            _d2.metric("Day", ((_sg.get("day") or {}).get("bias")) or "—")
            _rs = (_trd.get("rel_strength") or {}).get("rs_vs_spy")
            _d3.metric("RS vs SPY", f"{_rs:+.1f}%" if _rs is not None else "—")
            _sent = (_res.get("sentiment") or {}).get("score")
            _d4.metric("Sentiment", f"{_sent:.0f}/100" if _sent is not None else "—")
            _vp = _trd.get("vp") or {}
            if _vp:
                st.caption(f"Volume shelves — POC {_vp.get('poc','—')} · support {_vp.get('support','—')} · "
                           f"overhead {_vp.get('resistance','—')} · supply above {_vp.get('overhead_pct','—')}%")
            _series = _res.get("series") or _snp.get("prices") or []
            if len(_series) > 10:
                import pandas as _spd
                _sc = _spd.Series({p["d"]: p["c"] for p in _series[-120:]}, name=_sel)
                st.line_chart(_sc, height=160)
            st.caption("Full detail → Analyzer · Trading · Report tabs.")
    else:
        st.caption(f"No match for '{_q}' in your data.")
        if _ql.isalnum() and len(_ql) <= 5:
            if st.button(f"⚡ Analyze {_ql} on demand (any US ticker)", key="search_analyze_new"):
                with st.spinner(f"Analyzing {_ql}…"):
                    try:
                        lookup_ticker(client, _ql)
                        st.session_state.last_lookup = _ql
                        st.rerun()
                    except Exception as e:
                        st.error(f"Couldn't analyze {_ql}: {e}")
                        _record("search_analyze_new", e, _ql)


# ---- sidebar ---------------------------------------------------------------
with st.sidebar:
    st.subheader("Watchlist")
    new = st.text_input("Add ticker", placeholder="PLTR").upper().strip()
    if st.button("Add", use_container_width=True) and new:
        if new not in syms_all:
            st.session_state.watchlist.append({"symbol": new, "name": new})
            st.rerun()

    with st.expander(f"📋 {len(syms)} active / {len(syms_all)} total", expanded=False):
        for i, t in enumerate(list(st.session_state.watchlist)):
            c1, c2 = st.columns([4, 1])
            snap = SS.load_snapshot(t["symbol"])
            age = SS.age_str(snap) if snap else "no data"
            c1.write(f"**{t['symbol']}**  ·  {age}")
            if c2.button("✕", key=f"d{i}"):
                st.session_state.watchlist.pop(i)
                SS.delete_snapshot(t["symbol"])
                st.rerun()

    st.divider()
    if st.button("⟳ Update all", type="primary", use_container_width=True):
        prog = st.progress(0.0)
        try:
            fetch_macro(client)
        except Exception as e:
            st.warning(f"macro: {e}")
            _record("update_all.macro", e)
        for i, s in enumerate(syms):
            try:
                fetch_and_store(client, s)
            except Exception as e:
                st.warning(f"{s}: {e}")
                _record("update_all", e, s)
            prog.progress((i + 1) / max(len(syms), 1))
        prog.empty()
        try:
            import prediction_tracker as PT
            cyc = PT.auto_cycle(syms, SS.load_snapshot, get_cloud_url())
            sv = cyc.get("save", {})
            if sv.get("cloud"):
                st.toast(f"✓ Ledger saved to cloud: +{cyc['recorded']} recorded, "
                         f"{cyc['scored']} scored, {cyc['pending']} pending")
            else:
                st.toast(f"⚠ LEDGER NOT SAVED TO CLOUD: {sv.get('error')} — "
                         f"data will be lost on reboot!", icon="⚠️")
        except Exception as e:
            _record("update_all.ledger", e)
        try:
            import paper_portfolio as PP
            _pp, _pst = PP.load_portfolio(get_cloud_url())
            if _pst == "loaded" and _pp.get("positions"):
                _ppx = {}
                for _s in set(syms + ["SPY"]):
                    _sn = SS.load_snapshot(_s)
                    _px = (((_sn or {}).get("trading") or {}).get("price")
                           or ((_sn or {}).get("result") or {}).get("price"))
                    if _px:
                        _ppx[_s] = _px
                if _ppx:
                    PP.snapshot_value(_pp, _ppx)
                    PP.save_portfolio(_pp, get_cloud_url())
        except Exception as e:
            _record("update_all.paper", e)
        st.rerun()

    ca, cb = st.columns(2)
    if ca.button("Save list", use_container_width=True):
        W.save_watchlist(st.session_state.watchlist)
        st.success("Saved")
    cb.download_button("Export", use_container_width=True,
                       data=json.dumps({"watchlist": st.session_state.watchlist}, indent=2),
                       file_name="tickers.json", mime="application/json")

    st.divider()
    st.caption("☁ Cloud sync (cross-computer)")
    cloud_url = get_cloud_url()
    if not cloud_url:
        st.session_state.cloud_url = st.text_input(
            "Apps Script URL (ends in /exec)",
            value=st.session_state.get("cloud_url", ""), type="password")
        cloud_url = st.session_state.cloud_url
    else:
        st.caption("✓ Connected (built-in URL)")

    if st.button("🔌 Test connection", use_container_width=True):
        import cloud_sync as CS
        st.session_state.conn_status = CS.test_connection(cloud_url)
    cs = st.session_state.get("conn_status")
    if cs:
        if cs["ok"]:
            st.success(f"🟢 {cs['status']} — {cs['detail']}")
        else:
            st.error(f"🔴 {cs['status']} — {cs['detail']}")

    sc1, sc2 = st.columns(2)
    if sc1.button("⬆ Save cloud", use_container_width=True):
        try:
            import cloud_sync as CS
            CS.save_app_state(cloud_url, st.session_state.watchlist, st.session_state.starred)
            st.success("Saved to cloud")
        except Exception as e:
            st.error(f"{e}")
            _record("cloud_save", e)
    if sc2.button("⬇ Load cloud", use_container_width=True):
        try:
            import cloud_sync as CS
            blob = CS.load_app_state(cloud_url)
            if blob:
                st.session_state.watchlist = blob.get("watchlist", st.session_state.watchlist)
                st.session_state.starred = blob.get("starred", st.session_state.starred)
                st.success("Loaded from cloud")
                st.rerun()
            else:
                st.info("Nothing saved in cloud yet — Save once to seed it.")
        except Exception as e:
            st.error(f"{e}")
            _record("cloud_load", e)

    st.divider()
    st.caption("Weights")
    w = {}
    for leg, default in A.WEIGHTS.items():
        w[leg] = st.slider(leg, 0.0, 1.0, float(default), 0.05)
    tot = sum(w.values()) or 1.0
    A.WEIGHTS = {k: v / tot for k, v in w.items()}

    try:
        macro = S.macro_regime(client)
        st.caption(f"Macro: {macro.get('regime','?')} · tilt ×{macro.get('tilt',1.0)}")
    except Exception:
        pass

    if el:
        st.caption(f"Errors captured: {el.count()}")

# ---- tabs ------------------------------------------------------------------
ALL_TABS = [("⬢ Dashboard", "tab_dash"), ("Analyzer", "tab1"),
            ("Trading", "tab_trade"), ("Scenarios", "tab_sc"),
            ("Research", "tab_research"), ("Paper Trade", "tab_paper"),
            ("Report", "tab_report"), ("Macro", "tab_macro"),
            ("Backtest", "tab_bt"), ("Learn", "tab_learn"),
            ("Corridor Chart", "tab2"), ("Map", "tab_map"),
            ("Seasonality", "tab_seas"), ("🔧 Diagnostics", "tab_diag"),
            ("⚙ Settings", "tab_set")]
_visible = st.session_state.app_settings.get("visible_tabs") or [n for n, _ in ALL_TABS]
_visible = [n for n, _ in ALL_TABS if n in _visible] or [n for n, _ in ALL_TABS]
if "⚙ Settings" not in _visible:
    _visible.append("⚙ Settings")
if "🔧 Diagnostics" not in _visible:
    _visible.append("🔧 Diagnostics")
_created = st.tabs(_visible)
_lookup = dict(zip(_visible, _created))
tab_dash, tab1, tab_trade, tab_sc, tab_research, tab_paper, tab_report, \
    tab_macro, tab_bt, tab_learn, tab2, tab_map, tab_seas, tab_diag, tab_set = (
        _lookup.get(n) for n, _ in ALL_TABS)

# ---- Diagnostics tab (Hardcore) -------------------------------------------
if tab_diag is not None:
    with tab_diag:
        try:
            from diagnostics_tab import render_diagnostics
            render_diagnostics()
        except Exception as e:
            st.error(f"Diagnostics failed: {e}")
            st.code(traceback.format_exc())
            if el:
                st.subheader("Raw error log")
                for entry in el.recent(30):
                    st.write(entry)

# ---- NOTE: The remaining tabs (Dashboard, Analyzer, Trading, etc.) are the full
# original implementations. They are long; they will be restored in the next push
# once the supporting modules (dashboard.py, zone_chart.py, paper_portfolio.py,
# prediction_tracker.py, report_engine.py, research_screener.py, scenario_engine.py,
# backtest.py, learn_content.py, seasonality.py, quadrant_map.py, corridor.html)
# are copied into this repo.
#
# Right now this file has the full structure + Diagnostics so the app boots and
# matches the original navigation. I am continuing to copy the missing modules
# and the full tab bodies immediately.

st.info(
    "Hardcore is being restored to the full original multi-tab UI you liked.\n\n"
    "✅ Core + Diagnostics tab are live.\n"
    "⏳ Next push will restore Dashboard, Analyzer, Trading, Paper, Report, Macro, "
    "Backtest, Corridor, Map, Seasonality, etc. with the original code + light hardening.\n\n"
    "Reboot after the next update."
)
