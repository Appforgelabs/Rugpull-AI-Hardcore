"""
streamlit_app.py — Rugpull AI Hardcore
Minimal + Diagnostics first version. Designed to boot cleanly on Streamlit Cloud.
"""

from __future__ import annotations
import os
import traceback

import streamlit as st

# ---- page config MUST be first Streamlit call ----
st.set_page_config(
    page_title="Rugpull AI Hardcore",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  .block-container {padding-top: 2.2rem; max-width: 1100px;}
  [data-testid="stMetricValue"] {font-size: 1.1rem;}
  h1 {font-weight: 600; letter-spacing: -0.5px;}
  .muted {color:#8899aa; font-size:0.85rem;}
</style>
""", unsafe_allow_html=True)

# ---- safe imports with error surface ----
boot_errors = []

try:
    from logging_config import setup_logging, log
    setup_logging("INFO")
except Exception as e:
    boot_errors.append(f"logging_config: {e}")
    log = None

try:
    from fmp_client import FMPClient, FMPError
except Exception as e:
    boot_errors.append(f"fmp_client: {e}")
    FMPClient = None

try:
    import analyze as A
except Exception as e:
    boot_errors.append(f"analyze: {e}")
    A = None

try:
    import signals as S
except Exception as e:
    boot_errors.append(f"signals: {e}")
    S = None

try:
    import watchlist as W
except Exception as e:
    boot_errors.append(f"watchlist: {e}")
    W = None

try:
    import snapshot_store as SS
except Exception as e:
    boot_errors.append(f"snapshot_store: {e}")
    SS = None

try:
    from error_log import get_error_log
    el = get_error_log()
except Exception as e:
    boot_errors.append(f"error_log: {e}")
    el = None

try:
    from diagnostics_tab import render_diagnostics
except Exception as e:
    boot_errors.append(f"diagnostics_tab: {e}")
    render_diagnostics = None


def get_key():
    try:
        if hasattr(st, "secrets") and "FMP_API_KEY" in st.secrets:
            return st.secrets["FMP_API_KEY"]
    except Exception:
        pass
    return os.environ.get("FMP_API_KEY") or os.environ.get("FMP_KEY")


# ---- header ----
st.title("Rugpull AI Hardcore")
st.markdown(
    '<div class="muted">Transparent scoring + σ-based zones + live error log. Not financial advice.</div>',
    unsafe_allow_html=True,
)

if boot_errors:
    st.error("Boot-time import errors (the app still loaded so we can diagnose):")
    for err in boot_errors:
        st.code(err)
    st.info("Check the **🔧 Diagnostics** tab and the Manage app → Logs for full traceback.")

# ---- secrets check ----
key = get_key()
if not key:
    st.warning(
        "⚠️ **No FMP API key found.**\n\n"
        "Go to **Manage app → Settings → Secrets** and add:\n\n"
        "```toml\nFMP_API_KEY = \"your_premium_key_here\"\n```\n\n"
        "Then reboot the app."
    )

# ---- main UI (only if core imports worked) ----
if FMPClient is None or A is None or W is None or SS is None:
    st.stop()

if "watchlist" not in st.session_state:
    try:
        st.session_state.watchlist = W.load_watchlist()
    except Exception:
        st.session_state.watchlist = [
            {"symbol": "NVDA", "name": "NVIDIA"},
            {"symbol": "PLTR", "name": "Palantir"},
            {"symbol": "TSLA", "name": "Tesla"},
        ]

syms = [t["symbol"] for t in st.session_state.watchlist]

@st.cache_resource
def get_client(api_key: str):
    return FMPClient(api_key=api_key)

def fetch_and_store(client, sym):
    try:
        sentiment = None
        if S is not None and hasattr(S, "FMPNewsSentiment"):
            sentiment = S.FMPNewsSentiment(client)
        res = A.analyze(client, sym, sentiment)
        SS.save_snapshot(sym, res, price_series=res.get("series"))
        return res
    except Exception as e:
        if el:
            el.record("fetch_and_store", e, context=f"symbol={sym}")
        raise

# ---- sidebar ----
with st.sidebar:
    st.subheader("Watchlist")
    new = st.text_input("Add ticker", placeholder="PLTR").upper().strip()
    if st.button("Add", use_container_width=True) and new:
        if new not in syms:
            st.session_state.watchlist.append({"symbol": new, "name": new})
            try:
                W.save_watchlist(st.session_state.watchlist)
            except Exception:
                pass
            st.rerun()

    for i, t in enumerate(list(st.session_state.watchlist)):
        c1, c2 = st.columns([4, 1])
        try:
            snap = SS.load_snapshot(t["symbol"])
            age = SS.age_str(snap) if snap else "no data"
        except Exception:
            age = "?"
        c1.write(f"**{t['symbol']}** · {age}")
        if c2.button("✕", key=f"d{i}"):
            st.session_state.watchlist.pop(i)
            try:
                SS.delete_snapshot(t["symbol"])
                W.save_watchlist(st.session_state.watchlist)
            except Exception:
                pass
            st.rerun()

    st.divider()
    if key and st.button("⟳ Update all", type="primary", use_container_width=True):
        client = get_client(key)
        prog = st.progress(0.0)
        for i, s in enumerate(syms):
            try:
                fetch_and_store(client, s)
            except Exception as e:
                st.warning(f"{s}: {e}")
            prog.progress((i + 1) / max(len(syms), 1))
        prog.empty()
        st.rerun()

    if el:
        st.caption(f"Errors captured: {el.count()}")

# ---- tabs ----
tabs = st.tabs(["⬢ Overview", "Analyzer", "🔧 Diagnostics"])
tab_dash, tab1, tab_diag = tabs

with tab_dash:
    st.caption("Quick status of your watchlist (from snapshots). Hit ⟳ Update all to refresh.")
    rows = []
    for s in syms:
        try:
            snap = SS.load_snapshot(s)
            res = (snap or {}).get("result") or {}
            rows.append({
                "Symbol": s,
                "Price": res.get("price"),
                "Composite": res.get("composite_score"),
                "Age": SS.age_str(snap) if snap else "never",
            })
        except Exception:
            rows.append({"Symbol": s, "Price": None, "Composite": None, "Age": "error"})
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("No data yet. Hit **⟳ Update all** in the sidebar (after adding your FMP key).")

with tab1:
    st.caption("Fundamentals + composite + legs. Data only refreshes on Update.")
    rows = []
    for s in syms:
        try:
            snap = SS.load_snapshot(s)
            if snap and snap.get("result"):
                rows.append(snap["result"])
        except Exception:
            continue
    if not rows:
        st.info("No stored data. Hit **⟳ Update all** after setting the FMP key.")
    else:
        rows.sort(key=lambda r: r.get("composite_score") or 0, reverse=True)
        table = [{
            "Symbol": r.get("symbol"),
            "Price": r.get("price"),
            "Score": r.get("composite_score"),
            "P/E": (r.get("multiples") or {}).get("P/E"),
            "P/FCF": (r.get("multiples") or {}).get("P/FCF"),
        } for r in rows]
        st.dataframe(table, use_container_width=True, hide_index=True)

        for r in rows:
            with st.expander(f"{r.get('symbol')} — {r.get('company')} · {r.get('composite_score')}/100"):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Price", r.get("price"))
                c2.metric("Composite", r.get("composite_score"))
                c3.metric("P/E", (r.get("multiples") or {}).get("P/E"))
                c4.metric("P/E hist median", (r.get("pe_distribution") or {}).get("median"))

                st.markdown("**Legs**")
                for k, v in (r.get("legs") or {}).items():
                    st.write(f"{k}: {v}")

                if key and st.button(f"⟳ Update {r.get('symbol')}", key=f"u_{r.get('symbol')}"):
                    try:
                        client = get_client(key)
                        fetch_and_store(client, r["symbol"])
                        st.rerun()
                    except Exception as ex:
                        st.error(str(ex))

with tab_diag:
    if render_diagnostics:
        try:
            render_diagnostics()
        except Exception as e:
            st.error(f"Diagnostics tab failed: {e}")
            st.code(traceback.format_exc())
    else:
        st.warning("diagnostics_tab failed to import.")
        if boot_errors:
            st.write(boot_errors)
