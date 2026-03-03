"""
mining_app/app.py — Standalone Mining Manager
==============================================
A self-contained Streamlit app focused entirely on mining STAC
collection and item management.

Run:
    cd mining_app
    streamlit run app.py --server.address 0.0.0.0 --server.port 8503
"""

import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="⛏️ Mining Manager",
    page_icon="⛏️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Dark-mode toggle (mirrors the main app) ───────────────────────────────────
if "dark_mode" not in st.session_state:
    st.session_state["dark_mode"] = False

# ── Shared CSS ────────────────────────────────────────────────────────────────
_DARK  = st.session_state["dark_mode"]
_BG    = "#0f172a"       if _DARK else "#f8fafc"
_CARD  = "#1e293b"       if _DARK else "#ffffff"
_HEAD  = "#f1f5f9"       if _DARK else "#0f172a"
_MUTED = "#94a3b8"       if _DARK else "#64748b"
_BORD  = "#334155"       if _DARK else "#e2e8f0"
_ACC   = "#818cf8"       if _DARK else "#4f46e5"

st.markdown(f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
  html, body, [class*="css"] {{ font-family:'Inter',sans-serif; }}
  .stApp {{ background:{_BG}; }}
  .stcard {{
    background:{_CARD};border:1px solid {_BORD};border-radius:12px;
    padding:1rem;margin-bottom:0.75rem;
    box-shadow:0 1px 3px rgba(0,0,0,0.06);
  }}
  [data-testid="stSidebar"] {{ background:{_CARD}; }}
  h1,h2,h3,h4,h5,h6 {{ color:{_HEAD}; }}
  :root {{
    --text-head:{_HEAD};
    --text-muted:{_MUTED};
    --accent:{_ACC};
    --card:{_CARD};
    --border:{_BORD};
  }}
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
col_title, col_toggle = st.columns([8, 1])
with col_title:
    st.markdown(
        f'<h1 style="margin:0;font-size:2rem;font-weight:900;color:{_HEAD};">'
        f'⛏️ Mining Manager</h1>'
        f'<p style="color:{_MUTED};margin-top:0.2rem;font-size:0.88rem;">'
        f'Manage mining areas and survey items · STAC-based</p>',
        unsafe_allow_html=True,
    )
with col_toggle:
    if st.button("🌙" if not _DARK else "☀️", help="Toggle dark mode"):
        st.session_state["dark_mode"] = not _DARK
        st.rerun()

st.divider()

# ── Service status bar ────────────────────────────────────────────────────────
import requests as _req
from config import STAC_API_URL, TITILER_URL, FILE_SERVER_URL

def _ping(url: str, path: str = "/") -> bool:
    try:
        return _req.get(url + path, timeout=3).status_code < 500
    except Exception:
        return False

s1, s2, s3 = st.columns(3)
for col, name, url, path in [
    (s1, "STAC API",    STAC_API_URL,    "/"),
    (s2, "TiTiler",     TITILER_URL,     "/"),
    (s3, "File Server", FILE_SERVER_URL, "/"),
]:
    ok = _ping(url, path)
    dot = "🟢" if ok else "🔴"
    label = "Operational" if ok else "Unreachable"
    host = url.split("//")[-1]
    col.markdown(
        f'<div style="background:{_CARD};border:1px solid {_BORD};border-radius:8px;'
        f'padding:0.5rem 0.8rem;font-size:0.8rem;">'
        f'{dot} <b>{name}</b> · {label}<br>'
        f'<span style="color:{_MUTED};font-size:0.72rem;">{host}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

st.divider()

# ── Main content: Mining Manager ──────────────────────────────────────────────
from frontend.tab_mining import render_mining_tab

render_mining_tab()
