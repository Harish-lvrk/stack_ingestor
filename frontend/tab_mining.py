"""
frontend/tab_mining.py — Mining Manager
========================================
Dedicated tab for creating and managing mining-specific STAC
collections and items.

Folder convention on the file server:
  <COG_SAVE_DIR>/mining/<collection_id>/<item_id>/
      boundary.geojson
      mining_area.geojson
      new_mine_pit.geojson
      reclamation.geojson
      stockpile.geojson
      water_pits.geojson
      haul_roads.geojson
      stats.json
      <item_id>.json   ← the full STAC item JSON

Rules:
  - Only collections that have a folder under MINING_ROOT are shown
    as "mining collections".
  - Items carry only GeoJSON + analytics assets (no TIF references).
  - GeoJSON data is entered by pasting raw JSON text into text areas.
  - region_id is auto-set to the collection's index in the list
    (user can override).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from backend.stac_api import (
    api_create_collection,
    api_delete_collection,
    api_delete_item,
    api_push_item,
    api_update_collection,
    api_update_item,
    build_collection_payload,
    fetch_collections,
    fetch_item,
    fetch_items,
    local_to_url,
)
from config import COG_SAVE_DIR, STAC_API_URL, TITILER_URL, TILE_MATRIX_SET
from logger import get_logger

log = get_logger("tab_mining")

# ── Constants ─────────────────────────────────────────────────────────────────
MINING_ROOT: Path = COG_SAVE_DIR / "mining"

# Asset key → (display label, filename, placeholder hint)
GEOJSON_ASSETS: dict[str, tuple[str, str]] = {
    "boundary":             ("Mining Boundary",         "boundary.geojson"),
    "mining_area":          ("Active Mining Area",      "mining_area.geojson"),
    "new_mine_pit":         ("New Mine Pit",            "new_mine_pit.geojson"),
    "reclamation":          ("Reclamation Area",        "reclamation.geojson"),
    "stockpile":            ("Stockpile / Dumping Area","stockpile.geojson"),
    "temporary_water_pits": ("Temporary Water Pits",   "water_pits.geojson"),
    "haul_roads":           ("Haul Roads",             "haul_roads.geojson"),
}

# Single analytics asset
ANALYTICS_FILE = "analytics.json"

STATUS_COLORS = {"active": "#10b981", "critical": "#ef4444", "monitoring": "#f59e0b"}


# ── Folder helpers ─────────────────────────────────────────────────────────────

def _item_folder(col_id: str, item_id: str) -> Path:
    p = MINING_ROOT / col_id / item_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def _mining_collection_ids() -> list[str]:
    """Return collection IDs that have a folder under MINING_ROOT."""
    if not MINING_ROOT.exists():
        return []
    return sorted(p.name for p in MINING_ROOT.iterdir() if p.is_dir())


def _mining_collections() -> list[dict]:
    """Return full collection dicts where the ID is a known mining folder."""
    ids = set(_mining_collection_ids())
    return [c for c in fetch_collections() if c.get("id") in ids]


# ── STAC item builder ──────────────────────────────────────────────────────────
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


# ── Section 1: Collections browser + create ────────────────────────────────────

def _render_collections_section() -> None:
    _section_header("🗺️", "Mining Areas (Collections)",
                    "Each collection represents one geographic mining area.")

    mining_cols = _mining_collections()

    if not mining_cols:
        st.info("No mining areas yet. Use the form below to create one.")
    else:
        grid = st.columns(3)
        for i, col in enumerate(mining_cols):
            cid   = col.get("id", "")
            title = col.get("title") or cid
            desc  = col.get("description", "")
            items = fetch_items(cid, limit=200)

            with grid[i % 3]:
                st.markdown(f"""
                <div class="stcard" style="min-height:120px;">
                  <div style="font-weight:800;font-size:0.95rem;
                       color:var(--accent,#4f46e5);">{title}</div>
                  <code style="font-size:0.7rem;color:var(--text-muted);">{cid}</code>
                  <p style="font-size:0.78rem;color:var(--text-muted);
                     margin:0.35rem 0 0.3rem;min-height:32px;
                     overflow:hidden;">{desc[:80] or "—"}</p>
                  <div style="font-size:0.73rem;color:var(--text-muted);">
                    📋 {len(items)} survey item{"s" if len(items) != 1 else ""}
                  </div>
                </div>
                """, unsafe_allow_html=True)

                bc1, bc2, bc3 = st.columns([3, 1, 1])
                with bc1:
                    if st.button("Browse Items →",
                                 key=f"mine_browse_{cid}",
                                 use_container_width=True):
                        st.session_state["mining_selected_col"] = cid
                        st.session_state["mining_active_tab"] = 2
                        st.rerun()
                with bc2:
                    if st.button("✏️", key=f"mine_edit_col_{cid}",
                                 help=f"Edit {cid}"):
                        st.session_state[f"mine_editing_col_{cid}"] = not st.session_state.get(f"mine_editing_col_{cid}", False)
                with bc3:
                    if st.button("🗑️", key=f"mine_del_col_{cid}",
                                 help=f"Delete {cid}"):
                        st.session_state[f"mine_confirm_del_col_{cid}"] = True

                # ─ Edit Collection form ─────────────────────────────────────
                if st.session_state.get(f"mine_editing_col_{cid}"):
                    with st.form(key=f"edit_col_form_{cid}"):
                        st.markdown(f"**✏️ Edit Mining Area: `{cid}`**")
                        new_title = st.text_input(
                            "Area Name", value=col.get("title", cid),
                            key=f"edit_col_title_{cid}"
                        )
                        new_desc = st.text_area(
                            "Description", value=col.get("description", ""),
                            height=80, key=f"edit_col_desc_{cid}"
                        )
                        new_lic = st.selectbox(
                            "License",
                            ["proprietary", "various", "CC-BY-4.0", "ODbL-1.0"],
                            index=["proprietary", "various", "CC-BY-4.0", "ODbL-1.0"].index(
                                col.get("license", "proprietary")
                            ) if col.get("license") in ["proprietary", "various", "CC-BY-4.0", "ODbL-1.0"] else 0,
                            key=f"edit_col_lic_{cid}"
                        )
                        cancel_col, save_col = st.columns(2)
                        with cancel_col:
                            cancelled = st.form_submit_button("❌ Cancel")
                        with save_col:
                            saved = st.form_submit_button("✅ Save Changes", type="primary")

                    if cancelled:
                        del st.session_state[f"mine_editing_col_{cid}"]
                        st.rerun()
                    if saved:
                        # Preserve original created timestamp
                        orig_created = col.get("created")
                        payload = build_collection_payload(
                            cid, new_title, new_desc, new_lic,
                            created=orig_created
                        )
                        ok, err = api_update_collection(cid, payload)
                        if ok:
                            st.success(f"✅ Mining area **{cid}** updated!")
                            del st.session_state[f"mine_editing_col_{cid}"]
                            st.rerun()
                        else:
                            st.error(f"❌ {err}")

                # ─ Delete confirmation ───────────────────────────────────────
                if st.session_state.get(f"mine_confirm_del_col_{cid}"):
                    st.warning(f"Delete **{cid}**?")
                    y, n = st.columns(2)
                    with y:
                        if st.button("✅ Yes", key=f"mine_del_col_yes_{cid}"):
                            ok, err = api_delete_collection(cid)
                            if ok:
                                st.success("Deleted.")
                                st.rerun()
                            else:
                                st.error(err)
                    with n:
                        if st.button("❌ No", key=f"mine_del_col_no_{cid}"):
                            del st.session_state[f"mine_confirm_del_col_{cid}"]
                            st.rerun()

    st.divider()
    with st.expander("➕ Create New Mining Area", expanded=not bool(mining_cols)):
        _render_create_collection_form()


def _render_create_collection_form() -> None:
    with st.form("mining_create_col_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            col_id    = st.text_input(
                "Area ID *",
                placeholder="e.g. mancherial   (lowercase, no spaces)")
            col_title = st.text_input(
                "Area Name *",
                placeholder="e.g. Mancherial Mining Area")
        with c2:
            col_desc = st.text_area(
                "Description",
                placeholder="Brief description of this geographic mining area…",
                height=104)
            col_lic  = st.selectbox(
                "License",
                ["proprietary", "various", "CC-BY-4.0", "ODbL-1.0"])

        pr, cr = st.columns(2)
        with pr:
            preview = st.form_submit_button("👁️ Preview JSON")
        with cr:
            create  = st.form_submit_button("✅ Create Mining Area", type="primary")

    if preview or create:
        if not col_id or not col_title:
            st.warning("Area ID and Area Name are required.")
            return
        col_id  = col_id.strip().lower().replace(" ", "-")
        payload = build_collection_payload(col_id, col_title, col_desc, col_lic)

        if preview:
            st.json(payload)
        else:
            ok, err = api_create_collection(payload)
            if ok:
                folder = MINING_ROOT / col_id
                folder.mkdir(parents=True, exist_ok=True)
                st.success(
                    f"✅ Mining area **{col_id}** created!  \n"
                    f"📁 Folder: `{folder}`")
                st.rerun()
            else:
                st.error(f"❌ {err}")


# ── Section 2: Create mining item ─────────────────────────────────────────────

def _render_create_item_section() -> None:
    _section_header("📌", "Create Survey Item",
                    "Add a new survey record under a mining area.")

    mining_col_ids = _mining_collection_ids()
    if not mining_col_ids:
        st.warning("Create a Mining Area first before adding survey items.")
        return

    # ── 1 · Select collection ─────────────────────────────────────────────────
    st.markdown("##### 1 · Select Mining Area")
    selected_col   = st.selectbox("Mining Area *", mining_col_ids, key="item_col_select")
    auto_region_id = mining_col_ids.index(selected_col) + 1
    st.markdown(
        f'<p style="font-size:0.8rem;color:var(--text-muted,#64748b);">'
        f'🔗 Region ID auto-set to <code>{auto_region_id}</code> '
        f'(linked to <code>{selected_col}</code>)</p>',
        unsafe_allow_html=True,
    )

    st.divider()

    # ── 2 · GeoTIFF input (path or upload) ───────────────────────────────────
    st.markdown("##### 2 · Upload GeoTIFF")

    _LARGE_MB = 1024   # > 1 GB → force path mode

    input_mode = st.radio(
        "Input method",
        ["📂 Local file path (large files / any size)",
         "⬆️  Browser upload (< 1 GB)"],
        horizontal=True,
        key="mining_input_mode",
        help="Use **Local file path** for files > 1 GB. The file is read directly from disk — no memory limit.",
    )
    use_path_mode = input_mode.startswith("📂")

    tif_meta: dict | None     = None
    item_id_auto: str         = ""
    cog_tmp_path: Path | None = None
    raw_src_path: Path | None = None   # set only in path mode (original file location)
    tif_file                  = None   # set only in upload mode

    if use_path_mode:
        # ── Path mode: read directly from disk, no Streamlit memory ──────────
        st.caption(
            "Enter the **absolute path** to the GeoTIFF on this server. "
            "The file is read from disk — works for 2 GB+ files."
        )
        raw_path_str = st.text_input(
            "Absolute file path *",
            placeholder="/home/hareesh/Documents/survey/image.tif",
            key="mining_path_input",
        )
        if not raw_path_str:
            st.warning("⚠️ Enter the file path above to continue.")
        else:
            p = Path(raw_path_str.strip())
            if not p.exists():
                st.error(f"❌ File not found: `{p}`")
            elif p.suffix.lower() not in {".tif", ".tiff"}:
                st.error("❌ Must be a `.tif` or `.tiff` file.")
            else:
                raw_src_path = p
                item_id_auto = p.stem
                st.info(f"📛 Item ID will be: **`{item_id_auto}`**")

                cache_key = f"mining_cog_path_{p}"
                cached    = st.session_state.get(cache_key)
                if cached and not Path(cached["cog_path"]).exists():
                    del st.session_state[cache_key]
                    cached = None

                if cached is None:
                    from backend.cog import convert_to_cog, read_metadata
                    import tempfile
                    try:
                        cog_path = Path(tempfile.mkdtemp()) / (p.stem + "_cog.tif")
                        with st.spinner("⚙️ Converting to COG… (this may take a while for large files)"):
                            ok, err = convert_to_cog(p, cog_path)
                        if not ok:
                            st.error(f"❌ COG conversion failed: {err}")
                        else:
                            meta = read_metadata(cog_path)
                            st.session_state[cache_key] = {"cog_path": str(cog_path), "meta": meta}
                            cached = st.session_state[cache_key]
                    except Exception as e:
                        st.error(f"❌ Error processing GeoTIFF: {e}")

                if cached:
                    tif_meta     = cached["meta"]
                    cog_tmp_path = Path(cached["cog_path"])
                    st.success(
                        f"✅ COG ready — "
                        f"**Bbox:** `{tif_meta['bbox']}`  ·  "
                        f"**Bands:** {tif_meta['band_count']}  ·  "
                        f"**GSD:** {tif_meta['gsd']} m  ·  "
                        f"**EPSG:** {tif_meta['epsg']}"
                    )

    else:
        # ── Browser upload mode ───────────────────────────────────────────────
        st.caption(
            "Upload any GeoTIFF < 1 GB — it will be **converted to COG** automatically. "
            "For larger files, switch to **Local file path** above."
        )
        tif_file = st.file_uploader(
            "GeoTIFF File (.tif / .tiff) *",
            type=["tif", "tiff"],
            key="mining_tif_upload",
        )

        if tif_file is not None:
            file_size_mb = tif_file.size / 1_000_000
            if file_size_mb > _LARGE_MB:
                st.error(
                    f"❌ File is **{file_size_mb:.0f} MB** — too large for browser upload.  \n"
                    "Switch to **📂 Local file path** mode above."
                )
                tif_file = None   # prevent further processing
            else:
                from backend.cog import convert_to_cog, read_metadata
                import tempfile, shutil as _shutil

                item_id_auto = Path(tif_file.name).stem
                st.info(f"📛 Item ID will be: **`{item_id_auto}`**")

                cache_key = f"mining_cog_{tif_file.name}"
                cached    = st.session_state.get(cache_key)
                if cached and not Path(cached["cog_path"]).exists():
                    del st.session_state[cache_key]
                    cached = None

                if cached is None:
                    try:
                        CHUNK = 64 * 1024 * 1024
                        tif_file.seek(0)
                        with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as raw_tmp:
                            raw_path = Path(raw_tmp.name)
                            pb = st.progress(0, text="📥 Streaming upload to disk…")
                            written = 0
                            while True:
                                chunk = tif_file.read(CHUNK)
                                if not chunk:
                                    break
                                raw_tmp.write(chunk)
                                written += len(chunk)
                                pb.progress(
                                    min(written / (1024**3), 0.99),
                                    text=f"📥 {written / 1024**2:.0f} MB written…"
                                )
                            pb.empty()

                        cog_path = raw_path.with_name(raw_path.stem + "_cog.tif")
                        with st.spinner("⚙️ Converting to COG…"):
                            ok, err = convert_to_cog(raw_path, cog_path)
                        raw_path.unlink(missing_ok=True)

                        if not ok:
                            st.error(f"❌ COG conversion failed: {err}")
                        else:
                            meta = read_metadata(cog_path)
                            st.session_state[cache_key] = {"cog_path": str(cog_path), "meta": meta}
                            cached = st.session_state[cache_key]
                    except Exception as e:
                        st.error(f"❌ Error processing GeoTIFF: {e}")

                if cached:
                    tif_meta     = cached["meta"]
                    cog_tmp_path = Path(cached["cog_path"])
                    st.success(
                        f"✅ COG ready — "
                        f"**Bbox:** `{tif_meta['bbox']}`  ·  "
                        f"**Bands:** {tif_meta['band_count']}  ·  "
                        f"**GSD:** {tif_meta['gsd']} m  ·  "
                        f"**EPSG:** {tif_meta['epsg']}"
                    )

    # ── Survey date picker (shown as soon as COG is ready) ────────────────────
    if tif_meta is not None and cog_tmp_path is not None:
        st.divider()
        _auto_dt_str, _dt_source = _extract_image_date(cog_tmp_path, item_id_auto)
        _auto_date = datetime.fromisoformat(_auto_dt_str.replace("Z", "+00:00")).date()

        st.markdown("##### 🗓️ Survey Date")
        st.caption(
            f"Detected from **{_dt_source}**. Edit if the auto-detected date is wrong."
        )
        _user_date = st.date_input(
            "Survey Date *",
            value=_auto_date,
            key="mining_survey_date",
            label_visibility="visible",
        )
        # Store confirmed ISO datetime back in session state for use at save time
        st.session_state["_mining_confirmed_dt"] = (
            datetime(_user_date.year, _user_date.month, _user_date.day,
                     tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        )
    else:
        st.session_state.pop("_mining_confirmed_dt", None)

    st.divider()

    # ── 3 · GeoJSON layers — File Upload ─────────────────────────────────────
    st.markdown("##### 3 · Vector Change Layers — Upload GeoJSON Files")
    st.caption("Upload a `.geojson` file for each layer. Leave blank to skip.")

    geojson_files: dict[str, object] = {}  # akey → UploadedFile or None
    keys         = list(GEOJSON_ASSETS.items())
    left_assets  = keys[: len(keys) // 2 + len(keys) % 2]
    right_assets = keys[len(keys) // 2 + len(keys) % 2 :]

    col_l, col_r = st.columns(2)
    for col_widget, asset_group in [(col_l, left_assets), (col_r, right_assets)]:
        with col_widget:
            for akey, (alabel, filename) in asset_group:
                uploaded = st.file_uploader(
                    alabel,
                    type=["geojson", "json"],
                    key=f"mining_gjson_{akey}",
                    label_visibility="visible",
                )
                geojson_files[akey] = uploaded
                if uploaded is not None:
                    try:
                        gj = json.loads(uploaded.read())
                        uploaded.seek(0)
                        n_feat = len(gj.get("features", []))
                        st.markdown(
                            f'<span style="background:#dcfce7;border:1px solid #16a34a;'
                            f'color:#15803d;font-size:0.72rem;font-weight:700;'
                            f'padding:2px 10px;border-radius:100px;">'
                            f'✅ {uploaded.name} · {n_feat} feature{"s" if n_feat!=1 else ""}</span>',
                            unsafe_allow_html=True,
                        )
                    except Exception:
                        st.markdown(
                            f'<span style="background:#fee2e2;border:1px solid #dc2626;'
                            f'color:#dc2626;font-size:0.72rem;font-weight:700;'
                            f'padding:2px 10px;border-radius:100px;">'
                            f'❌ {uploaded.name} · Invalid GeoJSON</span>',
                            unsafe_allow_html=True,
                        )

    st.divider()

    # ── 4 · Analytics — Structured Form ───────────────────────────────────────
    st.markdown("##### 4 · Analytics Data")
    st.caption(
        "Fill in the area statistics for each land-cover class. "
        "This will be saved as a structured analytics JSON file."
    )

    # Fixed class rows matching the analytics schema
    _ANALYTIC_CLASSES = [
        "Mining Area",
        "New Mine Pit Area",
        "Stockpile / Dumping Area",
        "Reclamation",
        "Extended Land",
        "Temporary Water Pits",
    ]

    import re as _re
    _yr_match = _re.search(r'\b(19|20)\d{2}\b', item_id_auto) if item_id_auto else None
    _auto_year = _yr_match.group() if _yr_match else str(datetime.now(tz=timezone.utc).year)

    year_label = st.text_input(
        "Year / Survey Label",
        value=_auto_year,
        placeholder="e.g. 2019  or  2026",
        key="mining_analytics_year",
        help="Auto-detected from the image filename. Edit if needed.",
    )

    analytics_rows: list[dict] = []
    has_analytics = False

    header_cols = st.columns([3, 2, 2])
    header_cols[0].markdown("**Land Cover Class**")
    header_cols[1].markdown("**Area Covered (km²)**")
    header_cols[2].markdown("**% Covered**")

    for cls_name in _ANALYTIC_CLASSES:
        row_cols = st.columns([3, 2, 2])
        with row_cols[0]:
            st.markdown(
                f'<div style="padding:0.45rem 0;font-size:0.85rem;'
                f'color:var(--text-head,#0f172a);">{cls_name}</div>',
                unsafe_allow_html=True,
            )
        with row_cols[1]:
            area_val = st.number_input(
                f"km² {cls_name}",
                min_value=0.0, step=0.001, format="%.3f",
                key=f"analytics_area_{cls_name}",
                label_visibility="collapsed",
            )
        with row_cols[2]:
            pct_val = st.number_input(
                f"% {cls_name}",
                min_value=0.0, max_value=100.0, step=0.1, format="%.1f",
                key=f"analytics_pct_{cls_name}",
                label_visibility="collapsed",
            )
        analytics_rows.append({
            "name": cls_name,
            "area_covered_sq_km": {year_label: area_val},
            "percentage_covered":  {year_label: pct_val},
        })
        if area_val > 0 or pct_val > 0:
            has_analytics = True

    # Build the analytics JSON string for saving
    analytics_payload = {"structures_made": analytics_rows} if has_analytics else None

    st.divider()

    # ── Actions ───────────────────────────────────────────────────────────────
    pc, sc = st.columns(2)
    with pc:
        do_preview = st.button("👁️ Preview STAC JSON", use_container_width=True)
    with sc:
        do_save = st.button("💾 Save & Push to STAC API",
                            type="primary", use_container_width=True)

    if not (do_preview or do_save):
        return

    # ── Validation ────────────────────────────────────────────────────────────
    errors: list[str] = []
    if tif_file is None and raw_src_path is None:
        errors.append("GeoTIFF is required (file path or upload).")
    if tif_meta is None and (tif_file is not None or raw_src_path is not None):
        errors.append("GeoTIFF could not be read — check the file and try again.")
    # Validate uploaded GeoJSON files using _validate_geojson_bytes
    for akey, uploaded in geojson_files.items():
        if uploaded is not None:
            uploaded.seek(0)
            valid, msg = _validate_geojson_bytes(GEOJSON_ASSETS[akey][0], uploaded.read())
            uploaded.seek(0)
            if not valid:
                errors.append(msg)

    if errors:
        for e in errors:
            st.error(f"❌ {e}")
        return

    # ── Compute paths ──────────────────────────────────────────────────────────
    iid_clean  = item_id_auto.replace(" ", "-")
    # Use user-confirmed date from the survey date picker (set above after COG ready)
    dt_str = st.session_state.get(
        "_mining_confirmed_dt",
        datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    bbox       = tif_meta["bbox"]
    geometry   = tif_meta["geometry"]
    band_count = tif_meta["band_count"]
    folder     = _item_folder(selected_col, iid_clean)

    orig_dest = folder / f"{iid_clean}.tif"         # original raw TIF
    cog_dest  = folder / f"{iid_clean}_cog.tif"    # COG TIF
    cog_url   = local_to_url(cog_dest)             # HTTP URL for TiTiler

    # ── Compute bidx + rescale ────────────────────────────────────────────────
    from backend.titiler import (fetch_titiler_stats, compute_rescale,
                                  build_tile_url, build_preview_url)
    bidx    = [1, 2, 3] if band_count == 3 else ([3, 2, 1] if band_count >= 4 else [1])
    bidx_qs = "&".join(f"bidx={i}" for i in bidx)

    # ── Build asset_urls ───────────────────────────────────────────────────────
    asset_urls: dict[str, str] = {}

    # Compute rescale from temp COG (accurate for both preview and save modes).
    # In save mode this is later overridden by TiTiler stats for the final server copy.
    rescale = (
        _compute_rescale_local(cog_tmp_path, bidx)
        if cog_tmp_path and cog_tmp_path.exists()
        else "&".join(f"rescale=0,255" for _ in bidx)
    )

    asset_urls["visual"] = cog_url

    # Analytics asset URL (projected if data entered)
    if analytics_payload:
        asset_urls["analytics"] = local_to_url(folder / ANALYTICS_FILE)

    # GeoJSON asset URLs (projected based on uploaded files)
    for akey, (_, filename) in GEOJSON_ASSETS.items():
        if geojson_files.get(akey) is not None:
            asset_urls[akey] = local_to_url(folder / filename)

    if do_save:
        import shutil, requests as _req

        # ── 1. Save original TIF ─────────────────────────────────────────────
        if raw_src_path:
            # Path mode: copy directly from source (disk-to-disk, no RAM)
            with st.spinner(f"💾 Copying original TIF from `{raw_src_path.name}`…"):
                shutil.copy2(raw_src_path, orig_dest)
        else:
            # Upload mode: stream in 64 MB chunks
            tif_file.seek(0)
            CHUNK = 64 * 1024 * 1024
            pb_orig = st.progress(0, text="💾 Saving original TIF…")
            written = 0
            with open(orig_dest, "wb") as fout:
                while True:
                    chunk = tif_file.read(CHUNK)
                    if not chunk:
                        break
                    fout.write(chunk)
                    written += len(chunk)
                    pb_orig.progress(
                        min(written / (1024**3), 0.99),
                        text=f"💾 Original TIF: {written / 1024**2:.0f} MB saved…"
                    )
            pb_orig.empty()

        # ── 2. Save COG TIF ──────────────────────────────────────────────────
        if cog_tmp_path and cog_tmp_path.exists():
            shutil.copy2(cog_tmp_path, cog_dest)
            cog_tmp_path.unlink(missing_ok=True)

        # ── 3. Fetch TiTiler stats for accurate rescale ──────────────────────
        stats   = fetch_titiler_stats(cog_url)
        rescale = compute_rescale(stats, bidx)

        # ── 4. Download preview PNG from TiTiler and save to server ──────────
        preview_tiler_url = build_preview_url(cog_url, bidx_qs, rescale)
        preview_dest = folder / "preview.png"
        try:
            resp = _req.get(preview_tiler_url, timeout=30)
            if resp.status_code == 200:
                preview_dest.write_bytes(resp.content)
                st.info(f"🖼️ Preview PNG saved → `{preview_dest.name}`")
                asset_urls["preview"] = local_to_url(preview_dest)
            else:
                st.warning(f"⚠️ TiTiler preview returned HTTP {resp.status_code} — using TiTiler URL as fallback.")
                asset_urls["preview"] = preview_tiler_url
        except Exception as _e:
            st.warning(f"⚠️ Could not download preview PNG: {_e}")
            asset_urls["preview"] = preview_tiler_url

        # ── 5. Save Analytics JSON ──────────────────────────────────────────
        if analytics_payload:
            (folder / ANALYTICS_FILE).write_text(
                json.dumps(analytics_payload, indent=2), encoding="utf-8"
            )

        # ── 6. Save GeoJSONs ─────────────────────────────────────────────────
        for akey, (_, filename) in GEOJSON_ASSETS.items():
            uploaded = geojson_files.get(akey)
            if uploaded is not None:
                uploaded.seek(0)
                (folder / filename).write_bytes(uploaded.read())

    # Add tile + preview URLs to asset_urls (for both preview and save)
    tile_url = build_tile_url(cog_url, bidx_qs, rescale)
    asset_urls["tiles"] = tile_url
    if "preview" not in asset_urls:
        asset_urls["preview"] = build_preview_url(cog_url, bidx_qs, rescale)

    # ── Build STAC item ────────────────────────────────────────────────────────
    stac_item = _build_mining_item(
        item_id       = iid_clean,
        collection    = selected_col,
        datetime_str  = dt_str,
        region_id     = auto_region_id,
        location_name = iid_clean,
        bbox          = bbox,
        geometry      = geometry,
        asset_urls    = asset_urls,
        tif_meta      = tif_meta,
    )

    if do_preview:
        st.subheader("📄 STAC Item Preview")
        st.json(stac_item)
        return

    # ── Save STAC item JSON + push ─────────────────────────────────────────────
    (folder / f"{iid_clean}.json").write_text(
        json.dumps(stac_item, indent=2), encoding="utf-8"
    )

    ok, err = api_push_item(selected_col, stac_item)
    if ok:
        st.success(
            f"✅ Survey item **{iid_clean}** saved and pushed!  \n"
            f"📁 `{folder}`  \n"
            f"Files: `{iid_clean}.tif`, `{iid_clean}_cog.tif`, `preview.png`, GeoJSONs"
        )
        st.balloons()
    else:
        st.error(f"❌ Files saved but API push failed: {err}")


# ── Section 3: Browse items ────────────────────────────────────────────────────

def _render_browse_items_section() -> None:
    mining_col_ids = _mining_collection_ids()
    selected_col   = st.session_state.get("mining_selected_col")

    if not mining_col_ids:
        st.info("No mining areas yet.")
        return

    # Collection picker
    _section_header("📋", "Browse Survey Items",
                    "Select a mining area to view its survey items.")
    picked = st.selectbox(
        "Mining Area",
        mining_col_ids,
        index=mining_col_ids.index(selected_col) if selected_col in mining_col_ids else 0,
        key="mine_browse_picker",
    )
    st.session_state["mining_selected_col"] = picked

    items = fetch_items(picked, limit=200)
    if not items:
        st.info(f"No survey items in **{picked}** yet.")
        return

    for item in items:
        iid   = item.get("id", "—")
        props = item.get("properties", {})
        loc   = props.get("mining_location_name", "—")
        dt    = props.get("datetime", "—")[:10]
        st8   = props.get("status", "—")
        col   = STATUS_COLORS.get(st8, "#64748b")

        with st.expander(f"🪨  {loc}  ·  `{iid}`  ·  {dt}"):
            lc, rc = st.columns([3, 2])

            with lc:
                st.markdown(
                    f"**Location:** {loc}<br>"
                    f"**Region ID:** {props.get('region_id','—')}<br>"
                    f"**Survey Date:** {dt}",
                    unsafe_allow_html=True,
                )

            with rc:
                assets = item.get("assets", {})
                if assets:
                    st.markdown("**Assets:**")
                    for akey, aval in assets.items():
                        atitle = aval.get("title") or akey
                        href   = aval.get("href", "#")
                        st.markdown(f"- [{atitle}]({href})")

            st.markdown("")
            r1, r2, r3 = st.columns(3)
            with r1:
                with st.expander("📄 Raw STAC JSON"):
                    st.json(item)
            with r2:
                if st.button(f"✏️ Edit `{iid}`", key=f"mine_edit_{iid}"):
                    st.session_state[f"mine_editing_{iid}"] = not st.session_state.get(f"mine_editing_{iid}", False)
            with r3:
                if st.button(f"🗑️ Delete `{iid}`", key=f"mine_del_{iid}"):
                    st.session_state[f"mine_del_confirm_{iid}"] = True

            # ─ Edit Item form ────────────────────────────────────────────
            if st.session_state.get(f"mine_editing_{iid}"):
                st.markdown(f"**✏️ Editing item `{iid}`**")

                # Pre-fill date from existing STAC datetime
                _cur_dt_str = props.get("datetime", "")
                try:
                    _cur_date = datetime.fromisoformat(
                        _cur_dt_str.replace("Z", "+00:00")
                    ).date()
                except Exception:
                    _cur_date = datetime.now(tz=timezone.utc).date()

                _edit_date = st.date_input(
                    "🗓️ Survey Date",
                    value=_cur_date,
                    key=f"edit_date_{iid}",
                )

                # Analytics editor — pre-fill from existing analytics.json if present
                st.markdown("**Analytics Data** (leave at 0 to keep unchanged)")
                _EDIT_CLASSES = [
                    "Mining Area", "New Mine Pit Area", "Stockpile / Dumping Area",
                    "Reclamation", "Extended Land", "Temporary Water Pits",
                ]

                # Try to load existing analytics.json for pre-fill
                _analytics_folder = MINING_ROOT / picked / iid
                _existing_analytics: dict = {}
                _analytics_path = _analytics_folder / ANALYTICS_FILE
                if _analytics_path.exists():
                    try:
                        _raw = json.loads(_analytics_path.read_text())
                        for row in _raw.get("structures_made", []):
                            _existing_analytics[row["name"]] = row
                    except Exception:
                        pass

                _year_key = list((
                    _existing_analytics.get(_EDIT_CLASSES[0], {})
                    .get("area_covered_sq_km", {"2019": 0})
                ).keys())[0] if _existing_analytics else "2019"

                _edit_year = st.text_input(
                    "Year Label", value=_year_key, key=f"edit_year_{iid}"
                )

                _hdr = st.columns([3, 2, 2])
                _hdr[0].markdown("**Land Cover Class**")
                _hdr[1].markdown("**Area (km²)**")
                _hdr[2].markdown("**% Covered**")

                _edit_rows: list[dict] = []
                _edit_has_data = False
                for _cls in _EDIT_CLASSES:
                    _prev = _existing_analytics.get(_cls, {})
                    _prev_area = float(
                        list(_prev.get("area_covered_sq_km", {"_": 0}).values())[0]
                    ) if _prev else 0.0
                    _prev_pct = float(
                        list(_prev.get("percentage_covered", {"_": 0}).values())[0]
                    ) if _prev else 0.0

                    _rc = st.columns([3, 2, 2])
                    with _rc[0]:
                        st.markdown(
                            f'<div style="padding:0.4rem 0;font-size:0.85rem;">{_cls}</div>',
                            unsafe_allow_html=True,
                        )
                    with _rc[1]:
                        _area = st.number_input(
                            f"area {_cls}", value=_prev_area,
                            min_value=0.0, step=0.001, format="%.3f",
                            key=f"edit_area_{iid}_{_cls}",
                            label_visibility="collapsed",
                        )
                    with _rc[2]:
                        _pct = st.number_input(
                            f"pct {_cls}", value=_prev_pct,
                            min_value=0.0, max_value=100.0, step=0.1, format="%.1f",
                            key=f"edit_pct_{iid}_{_cls}",
                            label_visibility="collapsed",
                        )
                    _edit_rows.append({
                        "name": _cls,
                        "area_covered_sq_km": {_edit_year: _area},
                        "percentage_covered":  {_edit_year: _pct},
                    })
                    if _area > 0 or _pct > 0:
                        _edit_has_data = True

                _cancel_edit, _save_edit = st.columns(2)
                with _cancel_edit:
                    if st.button("❌ Cancel", key=f"edit_cancel_{iid}"):
                        del st.session_state[f"mine_editing_{iid}"]
                        st.rerun()
                with _save_edit:
                    if st.button("✅ Save Changes", key=f"edit_save_{iid}", type="primary"):
                        # 1. Fetch current item from STAC API
                        _current = fetch_item(picked, iid)
                        if _current is None:
                            st.error("❌ Could not fetch current item from STAC API.")
                        else:
                            # 2. Update properties
                            _new_dt = datetime(
                                _edit_date.year, _edit_date.month, _edit_date.day,
                                tzinfo=timezone.utc
                            ).strftime("%Y-%m-%dT%H:%M:%SZ")
                            _current["properties"]["datetime"] = _new_dt

                            # 3. Save updated analytics.json to disk
                            if _edit_has_data:
                                _analytics_folder.mkdir(parents=True, exist_ok=True)
                                _analytics_path.write_text(
                                    json.dumps({"structures_made": _edit_rows}, indent=2),
                                    encoding="utf-8"
                                )
                                # Make sure analytics asset is in the item
                                if "analytics" not in _current.get("assets", {}):
                                    _current.setdefault("assets", {})["analytics"] = {
                                        "href":  local_to_url(_analytics_path),
                                        "type":  "application/json",
                                        "roles": ["data", "analytics"],
                                        "title": "Analytics Data",
                                    }

                            # 4. PUT updated item to STAC API
                            ok, err = api_update_item(picked, iid, _current)
                            if ok:
                                st.success(f"✅ Item **{iid}** updated!")
                                del st.session_state[f"mine_editing_{iid}"]
                                st.rerun()
                            else:
                                st.error(f"❌ {err}")

            # ─ Delete confirmation ───────────────────────────────────────
                with y:
                    if st.button("✅ Yes", key=f"mine_del_yes_{iid}"):
                        ok, err = api_delete_item(picked, iid)
                        if ok:
                            # Also remove the item folder from disk
                            import shutil as _shutil
                            item_folder = MINING_ROOT / picked / iid
                            if item_folder.exists():
                                _shutil.rmtree(item_folder)
                            st.success(f"Deleted item **{iid}** and its files.")
                            st.rerun()
                        else:
                            st.error(err)
                with n:
                    if st.button("❌ Cancel", key=f"mine_del_no_{iid}"):
                        del st.session_state[f"mine_del_confirm_{iid}"]
                        st.rerun()


# ── Main entry point ───────────────────────────────────────────────────────────

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

    tab_areas, tab_item, tab_browse = st.tabs([
        "🗺️  Mining Areas",
        "📌  Create Survey Item",
        "📋  Browse Items",
    ])

    with tab_areas:
        _render_collections_section()

    with tab_item:
        _render_create_item_section()

    with tab_browse:
        _render_browse_items_section()
