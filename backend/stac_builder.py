"""backend/stac_builder.py — Build STAC item and band metadata."""

from datetime import datetime, timezone

from config import STAC_API_URL
from backend.titiler import build_tile_url, build_preview_url, compute_rescale
from logger import get_logger

log = get_logger("stac_builder")


def band_list(band_count: int) -> list[dict]:
    """Return eo:bands list based on band count."""
    if band_count == 3:
        return [
            {"name": "Red",   "common_name": "red"},
            {"name": "Green", "common_name": "green"},
            {"name": "Blue",  "common_name": "blue"},
        ]
    if band_count == 4:
        return [
            {"name": "Blue",  "common_name": "blue"},
            {"name": "Green", "common_name": "green"},
            {"name": "Red",   "common_name": "red"},
            {"name": "NIR",   "common_name": "nir"},
        ]
    return [{"name": f"Band {i+1}"} for i in range(band_count)]


def build_stac_item(
    item_id: str,
    collection: str,
    dt_str: str,
    metadata: dict,
    file_url: str,
    stats: dict,
    title: str = "",
    platform: str = "",
    instruments: str = "",
) -> dict:
    """Assemble and return a complete STAC 1.0.0 item dictionary."""
    bc   = metadata["band_count"]
    bidx = [1, 2, 3] if bc == 3 else ([3, 2, 1] if bc >= 4 else [1])
    bidx_qs = "&".join(f"bidx={i}" for i in bidx)
    rescale = compute_rescale(stats, bidx)

    tile_url    = build_tile_url(file_url, bidx_qs, rescale)
    preview_url = build_preview_url(file_url, bidx_qs, rescale)

    properties: dict = {
        "datetime":  dt_str or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "gsd":       metadata["gsd"],
        "proj:epsg": metadata["epsg"],
        "eo:bands":  band_list(bc),
    }
    if title:
        properties["title"] = title
    if platform:
        properties["platform"] = platform
    if instruments:
        properties["instruments"] = [i.strip() for i in instruments.split(",") if i.strip()]

    item = {
        "type":          "Feature",
        "stac_version":  "1.0.0",
        "stac_extensions": [
            "https://stac-extensions.github.io/eo/v1.1.0/schema.json",
            "https://stac-extensions.github.io/projection/v1.1.0/schema.json",
        ],
        "id":         item_id,
        "collection": collection,
        "bbox":       metadata["bbox"],
        "geometry":   metadata["geometry"],
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
        "assets": {
            "visual": {
                "href":  file_url,
                "type":  "image/tiff; application=geotiff; profile=cloud-optimized",
                "roles": ["data", "visual"],
                "title": "COG Image",
            },
            "tiles": {
                "href":  tile_url,
                "type":  "application/json",
                "roles": ["tiles"],
                "title": "TiTiler RGB Tile Service",
            },
            "preview": {
                "href":  preview_url,
                "type":  "image/png",
                "roles": ["overview"],
                "title": "RGB Preview Image",
            },
        },
        "properties": properties,
    }
    log.info("Built STAC item id=%s collection=%s", item_id, collection)
    return item
