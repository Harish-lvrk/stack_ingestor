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

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="STAC Manager",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Global styles ─────────────────────────────────────────────────────────────
inject_css()

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="
    padding: 1.5rem 0 0.8rem;
    margin-bottom: 1.5rem;
">
  <h1 style="
      font-size: 2.25rem; font-weight: 800; margin: 0; line-height: 1.1;
      color: #0f172a;
      letter-spacing: -0.02em;
  ">🛰️ <span style="
      background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 30%, #4f46e5 100%);
      -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  ">STAC Manager</span></h1>
  <div style="margin-top:0.6rem; display:flex; gap:0.6rem; align-items:center;">
    <span style="
        background:#eef2ff; border:1px solid #c7d2fe;
        color:#4f46e5; font-size:0.75rem; font-weight:700;
        padding:3px 12px; border-radius:100px; letter-spacing:0.02em;
    ">CORE 1.0.0</span>
    <span style="color:#64748b; font-size:0.88rem; font-weight:500;">
        Ingest · Collections · Browse
    </span>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Service status bar ────────────────────────────────────────────────────────
render_status_bar()
st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_ingest, tab_collections, tab_items = st.tabs(
    ["🛰️  Ingest", "📦  Collections", "📋  Items"]
)

with tab_ingest:
    render_ingest_tab()

with tab_collections:
    render_collections_tab()

with tab_items:
    render_items_tab()
