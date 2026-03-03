"""
STAC Manager — Entry Point
──────────────────────────
Run:  streamlit run app.py

Tabs:
  🛰️  Ingest      Upload GeoTIFF → COG → STAC JSON → API push
  📦  Collections  CRUD for STAC collections
  📋  Items        Browse items, view JSON, delete
"""

import streamlit as st

from frontend.styles import inject_css
from frontend.status_bar import render_status_bar
from frontend.tab_ingest import render_ingest_tab
from frontend.tab_collections import render_collections_tab
from frontend.tab_items import render_items_tab
from frontend.tab_mining import render_mining_tab

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="STAC Manager",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Dark mode init (before inject_css so it reads session state) ───────────
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False

# ── Global styles ─────────────────────────────────────────────────────────
inject_css()

# ── Header ────────────────────────────────────────────────────────────────
_dark = st.session_state.dark_mode
_btn_label = "☀️ Light" if _dark else "🌙 Dark"
_title_color = "#f1f5f9" if _dark else "#0f172a"
_badge_bg    = "#312e81" if _dark else "#eef2ff"
_badge_border= "#4338ca" if _dark else "#c7d2fe"
_badge_color = "#c7d2fe" if _dark else "#4f46e5"

hcol, toggle_col = st.columns([10, 1])
with hcol:
    _sub_color = "#94a3b8" if _dark else "#64748b"
    st.markdown(f"""
<div style="padding: 1.5rem 0 0.8rem; margin-bottom: 0.5rem;">
  <h1 style="font-size: 2.25rem; font-weight: 800; margin: 0; line-height: 1.1;">
    🛰️ <span class="gradient-text">STAC Manager</span>
  </h1>
  <div style="margin-top:0.5rem; display:flex; gap:0.6rem; align-items:center;">
    <span style="background:{_badge_bg}; border:1px solid {_badge_border};
                 color:{_badge_color}; font-size:0.75rem; font-weight:700;
                 padding:3px 12px; border-radius:100px;">CORE 1.0.0</span>
    <span style="color:{_sub_color}; font-size:0.88rem; font-weight:500;">
        Ingest · Collections · Browse
    </span>
  </div>
</div>
""", unsafe_allow_html=True)



with toggle_col:
    st.write("")  # spacing
    if st.button(_btn_label, key="dark_mode_toggle", help="Switch between light and dark mode"):
        st.session_state.dark_mode = not st.session_state.dark_mode
        st.rerun()


# ── Service status bar ────────────────────────────────────────────────────────
render_status_bar()
st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_ingest, tab_collections, tab_items, tab_mining = st.tabs(
    ["🛰️  Ingest", "📦  Collections", "📋  Items", "⛏️  Mining Manager"]
)

with tab_ingest:
    render_ingest_tab()

with tab_collections:
    render_collections_tab()

with tab_items:
    render_items_tab()

with tab_mining:
    render_mining_tab()
