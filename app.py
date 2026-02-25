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
    padding: 1.2rem 0 0.4rem;
    border-bottom: 1px solid #1e2740;
    margin-bottom: 1.2rem;
">
  <h1 style="
      font-size: 2rem; font-weight: 800; margin: 0; line-height: 1.2;
      background: linear-gradient(90deg, #58a6ff 0%, #00d4ff 60%, #79c0ff 100%);
      -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  ">🛰️ STAC Manager</h1>
  <div style="margin-top:0.4rem; display:flex; gap:0.5rem; align-items:center;">
    <span style="
        background: rgba(88,166,255,0.1); border:1px solid rgba(88,166,255,0.3);
        color:#58a6ff; font-size:0.72rem; font-weight:600;
        padding:2px 10px; border-radius:20px; letter-spacing:0.05em;
    ">STAC 1.0.0</span>
    <span style="color:#6b7590; font-size:0.82rem;">
        Ingest · Manage Collections · Browse Items
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
