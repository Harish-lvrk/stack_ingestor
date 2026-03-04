"""frontend/mining/constants.py — shared constants for the Mining Manager tab."""
from __future__ import annotations
from pathlib import Path
from config import COG_SAVE_DIR

# ── Constants ──────────────────────────────────────────────────────────────────
MINING_ROOT: Path = COG_SAVE_DIR / "mining"

# Asset key → (display label, filename)
GEOJSON_ASSETS: dict[str, tuple[str, str]] = {
    "boundary":             ("Mining Boundary",          "boundary.geojson"),
    "mining_area":          ("Active Mining Area",       "mining_area.geojson"),
    "new_mine_pit":         ("New Mine Pit",             "new_mine_pit.geojson"),
    "reclamation":          ("Reclamation Area",         "reclamation.geojson"),
    "stockpile":            ("Stockpile / Dumping Area", "stockpile.geojson"),
    "temporary_water_pits": ("Temporary Water Pits",     "water_pits.geojson"),
    "haul_roads":           ("Haul Roads",               "haul_roads.geojson"),
}

ANALYTICS_FILE  = "analytics.json"
STATUS_COLORS   = {"active": "#10b981", "critical": "#ef4444", "monitoring": "#f59e0b"}
