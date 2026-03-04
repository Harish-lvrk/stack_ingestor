"""frontend/tab_mining.py — backward-compat shim.
The mining tab logic has moved to frontend/mining/.
"""
from frontend.mining import render_mining_tab  # noqa: F401

__all__ = ["render_mining_tab"]
