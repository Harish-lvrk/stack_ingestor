"""frontend/mining/utils.py — shared utility functions for the Mining Manager tab."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from backend.stac_api import fetch_collections, local_to_url
from config import STAC_API_URL, TITILER_URL, TILE_MATRIX_SET
from logger import get_logger

from .constants import MINING_ROOT, GEOJSON_ASSETS

log = get_logger("tab_mining")


# ── Folder helpers ──────────────────────────────────────────────────────────────

def _item_folder(col_id: str, item_id: str) -> Path:
    from .constants import MINING_ROOT
    p = MINING_ROOT / col_id / item_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def _mining_collection_ids() -> list[str]:
    """Return collection IDs that have a folder under MINING_ROOT."""
    from .constants import MINING_ROOT
    if not MINING_ROOT.exists():
        return []
    return sorted(p.name for p in MINING_ROOT.iterdir() if p.is_dir())


def _mining_collections() -> list[dict]:
    """Return full collection dicts where the ID is a known mining folder."""
    ids = set(_mining_collection_ids())
    return [c for c in fetch_collections() if c.get("id") in ids]



# NOTE: All TiTiler URL computation and preview PNG download happen in the
# _render_create_item_section save block BEFORE this function is called.
# This function just assembles whatever is in asset_urls into STAC format.

_BAND_NAMES = {
    1: [{"name": "Grey",  "common_name": "gray"}],
    3: [{"name": "Blue",  "common_name": "blue"},
        {"name": "Green", "common_name": "green"},
        {"name": "Red",   "common_name": "red"}],
    4: [{"name": "Blue",  "common_name": "blue"},
        {"name": "Green", "common_name": "green"},
        {"name": "Red",   "common_name": "red"},
        {"name": "NIR",   "common_name": "nir"}],
}


def _build_mining_item(
    item_id: str,
    collection: str,
    datetime_str: str,
    region_id: int,
    location_name: str,
    bbox: list[float],
    geometry: dict,
    asset_urls: dict[str, str],
    tif_meta: dict | None = None,
) -> dict:
    assets: dict = {}
    meta = tif_meta or {}

    _ASSET_SCHEMA = {
        "visual":  ("image/tiff; application=geotiff; profile=cloud-optimized",
                    ["data", "visual"], "COG Image"),
        "tiles":   ("application/json",  ["tiles"],    "TiTiler RGB Tile Service"),
        "preview": ("image/png",         ["overview", "thumbnail"], "RGB Preview Image"),
    }

    for key, url in asset_urls.items():
        if key in _ASSET_SCHEMA:
            mime, roles, title = _ASSET_SCHEMA[key]
            assets[key] = {"href": url, "type": mime, "roles": roles, "title": title}
        elif key in GEOJSON_ASSETS:
            label = GEOJSON_ASSETS[key][0]
            assets[key] = {
                "href":  url,
                "type":  "application/geo+json",
                "roles": ["data"],
                "title": label,
            }
        elif key == "analytics":
            assets[key] = {
                "href":  url,
                "type":  "application/json",
                "roles": ["data", "analytics"],
                "title": "Analytics Data",
            }

    # ── Build properties ───────────────────────────────────────────────────────
    band_count = meta.get("band_count")
    eo_bands   = _BAND_NAMES.get(band_count, [{"name": f"Band{i+1}"} for i in range(band_count or 0)])

    properties: dict = {
        "datetime":             datetime_str,
        "region_id":            region_id,
        "mining_location_name": location_name,
    }
    if meta.get("gsd"):
        properties["gsd"] = meta["gsd"]
    if meta.get("epsg"):
        properties["proj:epsg"] = meta["epsg"]
    if eo_bands:
        properties["eo:bands"] = eo_bands

    return {
        "type":         "Feature",
        "stac_version": "1.0.0",
        "id":           item_id,
        "collection":   collection,
        "geometry":     geometry,
        "bbox":         bbox,
        "links": [
            {"rel": "collection", "type": "application/json",
             "href": f"{STAC_API_URL}/collections/{collection}"},
            {"rel": "parent",     "type": "application/json",
             "href": f"{STAC_API_URL}/collections/{collection}"},
            {"rel": "root",       "type": "application/json",
             "href": f"{STAC_API_URL}/"},
            {"rel": "self",       "type": "application/geo+json",
             "href": f"{STAC_API_URL}/collections/{collection}/items/{item_id}"},
        ],
        "properties": properties,
        "assets": assets,
        "stac_extensions": [
            "https://stac-extensions.github.io/projection/v1.1.0/schema.json",
            "https://stac-extensions.github.io/eo/v1.1.0/schema.json",
        ],
    }


# ── Shared UI helpers ─────────────────────────────────────────────────────────

def _section_header(icon: str, title: str, subtitle: str = "") -> None:
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:0.6rem;margin:0.6rem 0 0.2rem;">
          <span style="font-size:1.3rem;">{icon}</span>
          <span style="font-size:1.15rem;font-weight:800;
                color:var(--text-head,#0f172a);">{title}</span>
        </div>
        {"" if not subtitle else
          f'<p style="color:var(--text-muted,#64748b);font-size:0.83rem;'
          f'margin:0 0 0.6rem;">{subtitle}</p>'}
        """,
        unsafe_allow_html=True,
    )


def _badge(text: str, color: str) -> str:
    return (
        f'<span style="background:{color}22;border:1px solid {color};'
        f'color:{color};font-size:0.7rem;font-weight:700;padding:2px 10px;'
        f'border-radius:100px;">{text}</span>'
    )


def _validate_geojson_bytes(key: str, data: bytes) -> tuple[bool, str]:
    """Validate GeoJSON bytes from an uploaded file. Returns (is_valid, error_message)."""
    try:
        json.loads(data)
        return True, ""
    except json.JSONDecodeError as e:
        return False, f"{key}: Invalid GeoJSON — {e}"


def _geojson_area_km2(geojson_bytes: bytes) -> tuple[float, str]:
    """Calculate total geodesic area of all features in a GeoJSON file (km²).

    Uses pyproj.Geod when available; falls back to numpy spherical formula.
    Returns (area_km2, error_msg).  error_msg is "" on success.
    """
    try:
        import json as _json
        import numpy as _np

        gj       = _json.loads(geojson_bytes)
        features = gj.get("features", [])
        total_m2 = 0.0

        # ── Choose calculation backend ────────────────────────────────────────
        try:
            from pyproj import Geod as _Geod
            _geod = _Geod(ellps="WGS84")

            def _ring_area(ring: list) -> float:
                lons = [float(p[0]) for p in ring]
                lats = [float(p[1]) for p in ring]
                a, _ = _geod.polygon_area_perimeter(lons, lats)
                return abs(float(a))

        except ImportError:
            # numpy-only fallback: spherical trapezoid formula
            # area = R² × |Σ(λ₂−λ₁)(sin φ₁ + sin φ₂)| / 2
            _R = 6_371_000.0

            def _ring_area(ring: list) -> float:  # type: ignore[misc]
                lons = _np.radians([float(p[0]) for p in ring])
                lats = _np.radians([float(p[1]) for p in ring])
                dlons = _np.diff(lons)
                s     = _np.sin(lats[:-1]) + _np.sin(lats[1:])
                return abs(float(_np.sum(dlons * s))) * _R * _R / 2.0

        # ── Sum area over all features ────────────────────────────────────────
        for feat in features:
            geom   = feat.get("geometry") or {}
            gtype  = geom.get("type", "")
            coords = geom.get("coordinates", [])

            if gtype == "Polygon":
                total_m2 += _ring_area(coords[0])
                for hole in coords[1:]:
                    total_m2 -= _ring_area(hole)

            elif gtype == "MultiPolygon":
                for poly in coords:
                    total_m2 += _ring_area(poly[0])
                    for hole in poly[1:]:
                        total_m2 -= _ring_area(hole)
            # LineString / Point → no area

        return max(total_m2, 0.0) / 1_000_000, ""

    except Exception as _e:
        return 0.0, str(_e)



def _extract_image_date(cog_path: Path, filename_stem: str) -> tuple[str, str]:
    """Try to extract acquisition date from rasterio tags or filename.

    Returns (iso_datetime_str, source_hint) where source_hint explains how the
    date was found, e.g. 'EXIF metadata', 'filename', or 'today (fallback)'.
    """
    import re as _re
    # 1. Try rasterio TIFF tags
    try:
        import rasterio
        with rasterio.open(cog_path) as src:
            tags = src.tags()
            raw = (
                tags.get("TIFFTAG_DATETIME") or
                tags.get("ACQUISITIONDATETIME") or
                tags.get("acquisition_date") or
                tags.get("date") or
                tags.get("datetime") or
                ""
            )
        if raw:
            # Common format: "YYYY:MM:DD HH:MM:SS"
            raw = raw.replace(":", "-", 2).replace(" ", "T")[:19]
            dt = datetime.fromisoformat(raw)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ"), "EXIF metadata"
    except Exception:
        pass

    # 2. Try filename for a 4-digit year
    match = _re.search(r'\b(19|20)(\d{2})\b', filename_stem)
    if match:
        year = match.group()
        return f"{year}-01-01T00:00:00Z", f"filename ({filename_stem})"

    # 3. Fallback to today
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "today (fallback)"


def _compute_rescale_local(cog_path: Path, bidx: list[int]) -> str:
    """Compute per-band p2/p98 rescale directly from a local COG file using rasterio.

    Returns the rescale string in TiTiler format, e.g.
    'rescale=100,2500&rescale=120,2400&rescale=90,2300'
    """
    try:
        import numpy as np
        import rasterio
        parts = []
        with rasterio.open(cog_path) as src:
            for b in bidx:
                data = src.read(b).astype(float)
                valid = data[data > 0]          # exclude nodata (0)
                if valid.size == 0:
                    parts.append("0,255")
                    continue
                p2  = int(np.percentile(valid, 2))
                p98 = int(np.percentile(valid, 98))
                parts.append(f"{p2},{p98}")
        return "&".join(f"rescale={r}" for r in parts)
    except Exception:
        # Safe fallback
        return "&".join(f"rescale=0,255" for _ in bidx)


