"""
streamlit_app.py — Rugpull AI Hardcore (minimal + Diagnostics first)

This is a clean Hardcore entry point that:
  • Uses the hardened core (fmp_client, analyze, error_log, etc.)
  • Has a full 🔧 Diagnostics / Error Log tab so you can fix issues instantly
  • Includes a working Analyzer tab
  • Is ready for you to paste the remaining original tabs (Trading, Paper, Report, etc.) from Rugpull_AI

To get the full original multi-tab experience:
  1. Copy the remaining modules listed in STATUS.md
  2. Replace this file with the original streamlit_app.py
  3. Add the 4 lines for error_log + the Diagnostics tab body (see diagnostics_tab.py)
"""

from __future__ import annotations
import os
import json
from pathlib import Path

import streamlit as st

from logging_config import setup_logging, log
setup_logging("INFO")

from fmp_client import FMPClient, FMPError
import analyze as A
import signals as S
import watchlist as W
import snapshot_store as SS
from error_log import get_error_log
from diagnostics_tab import render_diagnostics

el = get_error_log()

st.set_page_config(page_title="Rugpull AI Hardcore", page_icon="📈", layout="wide")

st.markdown("""
<style>
  .block-container {padding-top: 2.2rem; max-width: 1100px;}
  [data-testid="stMetricValue"] {font-size: 1.1rem;}
  h1 {font-weight: 600; letter-spacing: -0.5px;}
  .muted {color:#8899aa; font-size:0.85rem;}
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


def fetch_and_store(client, sym):
    try:
        res = A.analyze(client, sym, S.FMPNewsSentiment(client))
        SS.save_snapshot(sym, res, price_series=res.get("series"))
        return res
    except Exception as e:
        el.record("fetch_and_store", e, context=f"symbol={sym}")
        raise


# ---- state ----
if "watchlist" not in st.session_state:
    st.session_state.watchlist = W.load_watchlist()

st.title("Rugpull AI Hardcore")
st.markdown('<div class="muted">Transparent scoring + σ-based zones + live error log. "
            "Not financial advice.</div>', unsafe_allow_html=True)

key = get_key()
if not key:
    st.error("No FMP API key. Set FMP_API_KEY env or Streamlit Secrets.")
    st.stop()
client = get_client(key)

syms = [t["symbol"] for t in st.session_state.watchlist]

# ---- sidebar ----
with st.sidebar:
    st.subheader("Watchlist")
    new = st.text_input("Add ticker", placeholder="PLTR").upper().strip()
    if st.button("Add", use_container_width=True) and new:
        if new not in syms:
            st.session_state.watchlist.append({"symbol": new, "name": new})
            W.save_watchlist(st.session_state.watchlist)
            st.rerun()

    for i, t in enumerate(list(st.session_state.watchlist)):
        c1, c2 = st.columns([4, 1])
        snap = SS.load_snapshot(t["symbol"])
        age = SS.age_str(snap) if snap else "no data"
        c1.write(f"**{t['symbol']}** · {age}")
        if c2.button("✕", key=f"d{i}"):
            st.session_state.watchlist.pop(i)
            SS.delete_snapshot(t["symbol"])
            W.save_watchlist(st.session_state.watchlist)
            st.rerun()

    st.divider()
    if st.button("⟳ Update all", type="primary", use_container_width=True):
        prog = st.progress(0.0)
        for i, s in enumerate(syms):
            try:
                fetch_and_store(client, s)
            except Exception as e:
                st.warning(f"{s}: {e}")
            prog.progress((i + 1) / max(len(syms), 1))
        prog.empty()
        st.rerun()

    st.caption(f"Errors captured: {el.count()}")

# ---- tabs ----
tab_dash, tab1, tab_diag = st.tabs(["⬢ Overview", "Analyzer", "🔧 Diagnostics"])

with tab_dash:
    st.caption("Quick status of your watchlist (from snapshots). Hit ⟳ Update all to refresh.")
    rows = []
    for s in syms:
        snap = SS.load_snapshot(s)
        res = (snap or {}).get("result") or {}
        rows.append({
            "Symbol": s,
            "Price": res.get("price"),
            "Composite": res.get("composite_score"),
            "Age": SS.age_str(snap) if snap else "never",
        })
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("No data yet. Hit **⟳ Update all** in the sidebar.")

with tab1:
    st.caption("Fundamentals + composite + legs. Data only refreshes on Update.")
    rows = []
    for s in syms:
        snap = SS.load_snapshot(s)
        if snap and snap.get("result"):
            rows.append(snap["result"])
    if not rows:
        st.info("No stored data. Hit **⟳ Update all**.")
    else:
        rows.sort(key=lambda r: r.get("composite_score", 0), reverse=True)
        table = [{
            "Symbol": r["symbol"], "Price": r.get("price"),
            "Score": r.get("composite_score"),
            "P/E": (r.get("multiples") or {}).get("P/E"),
            "P/FCF": (r.get("multiples") or {}).get("P/FCF"),
        } for r in rows]
        st.dataframe(table, use_container_width=True, hide_index=True)

        for r in rows:
            with st.expander(f"{r['symbol']} — {r.get('company')} · {r.get('composite_score')}/100"):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Price", r.get("price"))
                c2.metric("Composite", r.get("composite_score"))
                c3.metric("P/E", (r.get("multiples") or {}).get("P/E"))
                c4.metric("P/E hist median", (r.get("pe_distribution") or {}).get("median"))

                st.markdown("**Legs**")
                legs = r.get("legs", {})
                for k, v in legs.items():
                    st.write(f"{k}: {v}")

                if st.button(f"⟳ Update {r['symbol']}", key=f"u_{r['symbol']}"):
                    try:
                        fetch_and_store(client, r["symbol"])
                        st.rerun()
                    except Exception as ex:
                        st.error(str(ex))

with tab_diag:
    render_diagnostics()
