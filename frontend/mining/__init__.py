"""frontend/mining/__init__.py — Mining Manager entry point."""
from __future__ import annotations

import streamlit as st

from .section_collections import _render_collections_section
from .section_create_item import _render_create_item_section
from .section_browse import _render_browse_items_section


def render_mining_tab() -> None:
    _dark = st.session_state.get("dark_mode", False)
    _tcol = "#f1f5f9" if _dark else "#0f172a"

    st.markdown(
        f"""
        <div style="padding:0.5rem 0 0.8rem;">
          <h2 style="font-size:1.75rem;font-weight:800;margin:0;color:{_tcol};">
            ⛏️ Mining Manager
          </h2>
          <p style="color:var(--text-muted,#64748b);margin-top:0.2rem;font-size:0.88rem;">
            Create and manage mining areas and their survey items
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Session-state-driven navigation (supports programmatic tab switching) ──
    active = st.session_state.get("mining_active_tab", 0)

    _NAV = [
        ("🗺️  Mining Areas",       0),
        ("📌  Create Survey Item",       1),
        ("📋  Browse Items",             2),
    ]

    nav_cols = st.columns(len(_NAV))
    for col, (label, idx) in zip(nav_cols, _NAV):
        _style = (
            "border-bottom:3px solid var(--accent,#4f46e5);"
            "background:transparent;font-weight:700;"
        ) if idx == active else ""
        if col.button(label, key=f"_mining_nav_{idx}",
                      use_container_width=True,  # noqa: we keep this for nav buttons
                      ):
            st.session_state["mining_active_tab"] = idx
            st.rerun()

    st.markdown(
        "<hr style=\"margin:0 0 1rem;border:none;border-top:1px solid "
        "var(--border,#e2e8f0);\">",
        unsafe_allow_html=True,
    )

    if active == 0:
        _render_collections_section()
    elif active == 1:
        _render_create_item_section()
    elif active == 2:
        _render_browse_items_section()


__all__ = ["render_mining_tab"]
