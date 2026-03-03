"""
config.py — Central configuration for STAC Manager.
All environment-specific constants live here.
"""

from pathlib import Path

# ── Service URLs ─────────────────────────────────────────────────────────────
# Use LAN IP so all generated URLs (assets, tiles, STAC links) are reachable
# by everyone on the same network. localhost/127.0.0.1 only works locally.
LAN_IP           = "10.50.0.170"

FILE_SERVER_URL  = f"http://{LAN_IP}:8085"
TITILER_URL      = f"http://{LAN_IP}:8008"

# Public URL embedded in STAC item links (collection, parent, self, root)
STAC_API_URL     = f"http://{LAN_IP}:8082"

# Internal URL used by this app to POST/PUT/DELETE to the STAC API
# (the app runs locally, so localhost is fine for actual HTTP calls)
STAC_API_INTERNAL = "http://localhost:8082"

# ── Local paths ───────────────────────────────────────────────────────────────
FILE_SERVER_ROOT = Path.home()
COG_SAVE_DIR     = Path.home() / "Documents" / "serverimages"
LOG_DIR          = Path(__file__).parent / "logs"
LOG_FILE         = LOG_DIR / "stac_manager.log"

# ── Titiler config ────────────────────────────────────────────────────────────
TILE_MATRIX_SET  = "WebMercatorQuad"   # used in /cog/{tileMatrixSetId}/tilejson.json
