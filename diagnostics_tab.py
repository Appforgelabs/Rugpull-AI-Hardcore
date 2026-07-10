"""
diagnostics_tab.py — ready-to-paste Diagnostics / Error Log tab for streamlit_app.py

In streamlit_app.py:

    from diagnostics_tab import render_diagnostics
    ...
    if tab_diag is not None:
        with tab_diag:
            render_diagnostics()
"""

from __future__ import annotations
import streamlit as st
from error_log import get_error_log
from logging_config import log


def render_diagnostics():
    el = get_error_log()
    st.subheader("🔧 Diagnostics & Error Log")
    st.caption("Every exception and important warning is captured here so we can fix issues in minutes. "
               "Persistent across restarts (JSONL on disk). Not financial advice.")

    summary = el.summary()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total captured", summary["total"])
    c2.metric("ERROR", summary["levels"].get("ERROR", 0))
    c3.metric("WARNING", summary["levels"].get("WARNING", 0))
    c4.metric("INFO", summary["levels"].get("INFO", 0))

    if summary["top_sources"]:
        st.markdown("**Top sources**")
        st.write(", ".join(f"{s} ({n})" for s, n in summary["top_sources"]))

    st.divider()

    col_a, col_b, col_c = st.columns([2, 1, 1])
    with col_a:
        level_filter = st.selectbox("Filter level", ["ALL", "ERROR", "WARNING", "INFO"], index=0)
    with col_b:
        if st.button("🗑 Clear log", type="secondary"):
            el.clear()
            st.success("Error log cleared")
            st.rerun()
    with col_c:
        st.download_button(
            "⬇ Export JSON",
            data=el.export(),
            file_name="rugpull_error_log.json",
            mime="application/json",
            use_container_width=True,
        )

    level = None if level_filter == "ALL" else level_filter
    entries = el.recent(n=80, level=level)

    if not entries:
        st.info("No errors captured yet. Good. When something fails it will appear here automatically.")
        st.markdown("""
        **Common things that land here**
        - FMP 401 / 429 / 404 → key, plan, or endpoint change
        - Cloud sync unreachable / old script → redeploy Apps Script with the addon
        - Snapshot corrupt → delete the bad ticker json under `snapshots/`
        - Intraday empty → free plan or rate limit (Premium recommended)
        """)
        return

    st.markdown(f"**Showing {len(entries)} most recent** (newest first)")

    for e in entries:
        level_color = {"ERROR": "🔴", "WARNING": "🟠", "INFO": "🔵"}.get(e.get("level"), "⚪")
        with st.expander(
            f"{level_color} `{e.get('iso')}` · **{e.get('source')}** · {e.get('message')[:90]}"
        ):
            st.markdown(f"**Level**: {e.get('level')}")
            st.markdown(f"**Source**: `{e.get('source')}`")
            st.markdown(f"**Message**: {e.get('message')}")
            if e.get("context"):
                st.markdown(f"**Context**: {e.get('context')}")
            if e.get("traceback"):
                st.code(e["traceback"], language="text")
            if e.get("extra"):
                st.json(e["extra"])

    st.divider()
    st.markdown("### Quick fixes")
    st.markdown("""
    | Symptom | Likely cause | Fix |
    |---------|--------------|-----|
    | 401 bad key | Wrong / expired FMP key | Update secrets / env |
    | 429 rate limited | Too many calls | Raise throttle or wait; Premium helps |
    | 404 endpoint | FMP path change | Check ENDPOINTS in fmp_client.py |
    | Cloud "old script" | Apps Script missing namespace | Paste APPS_SCRIPT_ADDON into Code.gs & redeploy |
    | Empty trading data | Intraday unavailable | Use Premium or longer interval |
    | Corrupt snapshot | Partial write | Delete `snapshots/TICKER.json` and re-Update |
    """)

    # Manual test entry
    with st.expander("🧪 Inject a test error (for verification)"):
        if st.button("Record test ERROR"):
            el.record("diagnostics_tab", RuntimeError("Test error from Diagnostics"), context="manual test")
            st.rerun()
