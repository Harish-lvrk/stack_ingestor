"""backend/cog.py — COG conversion and GeoTIFF metadata extraction."""

import subprocess
from pathlib import Path

import rasterio
from rasterio.warp import transform_bounds, transform_geom

from logger import get_logger

log = get_logger("cog")


def convert_to_cog(input_path: Path, output_path: Path) -> tuple[bool, str]:
    """Convert a GeoTIFF to Cloud-Optimized GeoTIFF using gdal_translate."""
    log.info("Converting %s → %s", input_path.name, output_path.name)
    result = subprocess.run(
        [
            "gdal_translate", "-of", "COG",
            "-co", "COMPRESS=LZW",
            "-co", "OVERVIEWS=AUTO",
            str(input_path), str(output_path),
        ],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        log.info("COG conversion successful → %s", output_path)
        return True, ""
    log.error("COG conversion failed: %s", result.stderr[:400])
    return False, result.stderr


def read_metadata(filepath: Path) -> dict:
    """Read spatial metadata from a COG/GeoTIFF file."""
    log.debug("Reading metadata: %s", filepath.name)
    with rasterio.open(filepath) as src:
        bounds = src.bounds
        crs    = src.crs
        wgs84  = transform_bounds(
            crs, "EPSG:4326",
            bounds.left, bounds.bottom,
            bounds.right, bounds.top,
        )
        min_lon, min_lat, max_lon, max_lat = wgs84
        native_poly = {
            "type": "Polygon",
            "coordinates": [[
                [bounds.left,  bounds.bottom],
                [bounds.right, bounds.bottom],
                [bounds.right, bounds.top],
                [bounds.left,  bounds.top],
                [bounds.left,  bounds.bottom],
            ]],
        }
        geometry = transform_geom(crs.to_wkt(), "EPSG:4326", native_poly)
        meta = {
            "bbox":       [round(min_lon, 6), round(min_lat, 6),
                           round(max_lon, 6), round(max_lat, 6)],
            "geometry":   geometry,
            "epsg":       crs.to_epsg(),
            "band_count": src.count,
            "dtypes":     list(src.dtypes),
            "gsd":        round(abs(src.transform.a), 2),
        }
        log.debug(
            "Metadata: bands=%d, epsg=%s, gsd=%.2f",
            meta["band_count"], meta["epsg"], meta["gsd"],
        )
        return meta
