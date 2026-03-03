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
        dot_color    = "#10b981" if ok else "#ef4444" 
        text_color_cls = "color:#10b981;" if ok else "color:#ef4444;"

        col.markdown(f"""
<div class="status-card">
  <span class="status-dot" style="
      background:{dot_color};
      box-shadow: 0 0 8px {dot_color}66;
      {'animation:pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;' if ok else ''}
  "></span>
  <div>
    <div class="status-name">{name}</div>
    <div style="font-size:0.75rem; {text_color_cls} font-weight:500;">
        {status_text} · <span style="color:var(--text-muted); font-weight:400;">{port}</span>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

