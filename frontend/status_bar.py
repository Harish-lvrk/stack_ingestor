"""frontend/status_bar.py — Service health indicator bar (Refined SaaS theme)."""

import requests
import streamlit as st

from config import STAC_API_INTERNAL, TITILER_URL, FILE_SERVER_URL, LAN_IP


def _check(url: str, timeout: float = 2.0) -> bool:
    try:
        requests.get(url, timeout=timeout)
        return True
    except Exception:
        return False


def render_status_bar() -> None:
    """Render three service-health cards in a row with refined SaaS styling."""
    stac_ok  = _check(STAC_API_INTERNAL)
    tit_ok   = _check(f"{TITILER_URL}/healthz")
    files_ok = _check(FILE_SERVER_URL)

    services = [
        ("STAC API",    f"{LAN_IP}:8082", stac_ok),
        ("Titiler",     f"{LAN_IP}:8008", tit_ok),
        ("File Server", f"{LAN_IP}:8085", files_ok),
    ]

    cols = st.columns(3)
    for col, (name, port, ok) in zip(cols, services):
        status_text  = "Operational" if ok else "Degraded"
        dot_color    = "#10b981" if ok else "#ef4444" # Emerald-500 / Red-500
        bg_color     = "#ffffff"
        border_color = "#f1f5f9"
        text_color   = "#059669" if ok else "#dc2626" # Emerald-600 / Red-600

        col.markdown(f"""
<div style="
    background:{bg_color};
    border:1px solid {border_color};
    border-radius:12px;
    padding:0.8rem 1.2rem;
    display:flex; align-items:center; gap:0.8rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
">
  <span style="
      width:10px; height:10px; border-radius:50%;
      background:{dot_color}; display:inline-block; flex-shrink:0;
      box-shadow: 0 0 8px {dot_color}66;
      {'animation:pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;' if ok else ''}
  "></span>
  <div>
    <div style="font-weight:700; font-size:0.85rem; color:#0f172a; margin-bottom:1px;">{name}</div>
    <div style="font-size:0.75rem; color:{text_color}; font-weight:500;">
        {status_text} · <span style="color:#64748b; font-weight:400;">{port}</span>
    </div>
  </div>
</div>
<style>
@keyframes pulse {{
  0%, 100% {{ opacity: 1; transform: scale(1); }}
  50% {{ opacity: 0.6; transform: scale(0.95); }}
}}
</style>
""", unsafe_allow_html=True)
