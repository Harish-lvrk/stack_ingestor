"""frontend/status_bar.py — Service health indicator bar (light theme)."""

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
    """Render three service-health cards in a row."""
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
        status_text  = "Online"  if ok else "Offline"
        dot_color    = "#16a34a" if ok else "#dc2626"
        bg_color     = "#f0fdf4" if ok else "#fef2f2"
        border_color = "#86efac" if ok else "#fca5a5"
        text_color   = "#15803d" if ok else "#dc2626"

        col.markdown(f"""
<div style="
    background:{bg_color};
    border:1px solid {border_color};
    border-radius:10px;
    padding:0.65rem 1rem;
    display:flex; align-items:center; gap:0.6rem;
">
  <span style="
      width:9px; height:9px; border-radius:50%;
      background:{dot_color}; display:inline-block; flex-shrink:0;
      {'animation:pulse 2s infinite;' if ok else ''}
  "></span>
  <div>
    <div style="font-weight:700; font-size:0.82rem; color:#1e293b;">{name}</div>
    <div style="font-size:0.72rem; color:{text_color}; margin-top:1px;">
        {status_text} · <span style="color:#94a3b8;">{port}</span>
    </div>
  </div>
</div>
<style>
@keyframes pulse {{
  0%,100% {{ opacity:1; }}
  50% {{ opacity:0.4; }}
}}
</style>
""", unsafe_allow_html=True)
