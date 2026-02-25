"""frontend/status_bar.py — Service health indicator bar."""

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
    """Render three service-health cards in a row using Streamlit metric-style HTML."""
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
        dot_color    = "#3fb950" if ok else "#f85149"
        bg_color     = "rgba(35,134,54,0.12)" if ok else "rgba(218,54,51,0.12)"
        border_color = "rgba(35,134,54,0.4)"  if ok else "rgba(218,54,51,0.4)"
        text_color   = "#3fb950" if ok else "#f85149"

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
      background:{dot_color}; display:inline-block;
      flex-shrink:0;
      {'animation:pulse 2s infinite;' if ok else ''}
  "></span>
  <div>
    <div style="font-weight:700; font-size:0.82rem; color:#c9d1d9;">{name}</div>
    <div style="font-size:0.72rem; color:{text_color}; margin-top:1px;">
        {status_text} · <span style="color:#6b7590;">{port}</span>
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
