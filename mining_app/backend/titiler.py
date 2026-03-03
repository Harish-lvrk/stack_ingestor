"""backend/titiler.py — Titiler interactions: band stats and URL building."""

import time

import requests

from config import TITILER_URL, TILE_MATRIX_SET
from logger import get_logger

log = get_logger("titiler")


def fetch_titiler_stats(file_url: str) -> dict:
    """Fetch per-band statistics from Titiler /cog/statistics."""
    url = f"{TITILER_URL}/cog/statistics"
    t0 = time.monotonic()
    try:
        r = requests.get(url, params={"url": file_url}, timeout=30)
        ms = int((time.monotonic() - t0) * 1000)
        log.info("GET /cog/statistics → %d (%dms)", r.status_code, ms)
        if r.status_code == 200:
            return r.json()
        log.warning("Titiler stats non-200: %s", r.text[:200])
    except Exception as exc:
        log.error("Titiler stats error: %s", exc)
    return {}


def compute_rescale(stats: dict, band_indices: list[int]) -> str:
    """Compute rescale string (min,max) from Titiler band stats."""
    if not stats:
        return "0,255"
    lo, hi = [], []
    for i in band_indices:
        key = f"b{i}"
        if key in stats:
            b = stats[key]
            lo.append(b.get("percentile_2",  b.get("min", 0)))
            hi.append(b.get("percentile_98", b.get("max", 255)))
    if lo and hi:
        return f"{int(min(lo))},{int(max(hi))}"
    return "0,255"


def build_tile_url(file_url: str, bidx_qs: str, rescale: str) -> str:
    return (
        f"{TITILER_URL}/cog/{TILE_MATRIX_SET}/tilejson.json"
        f"?url={file_url}&{bidx_qs}&rescale={rescale}"
    )


def build_preview_url(file_url: str, bidx_qs: str, rescale: str) -> str:
    return (
        f"{TITILER_URL}/cog/preview.png"
        f"?url={file_url}&{bidx_qs}&rescale={rescale}"
    )
