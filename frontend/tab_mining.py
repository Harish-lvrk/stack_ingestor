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
    build_collection_payload,
    fetch_collections,
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


def _validate_geojson_text(key: str, text: str) -> tuple[bool, str]:
    """Return (is_valid, error_message). Empty text is considered valid (optional)."""
    if not text.strip():
        return True, ""
    try:
        json.loads(text)
        return True, ""
    except json.JSONDecodeError as e:
        return False, f"{key}: Invalid JSON — {e}"


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

                bc1, bc2 = st.columns([3, 1])
                with bc1:
                    if st.button("Browse Items →",
                                 key=f"mine_browse_{cid}",
                                 use_container_width=True):
                        st.session_state["mining_selected_col"] = cid
                        st.session_state["mining_active_tab"] = 2
                        st.rerun()
                with bc2:
                    if st.button("🗑️", key=f"mine_del_col_{cid}",
                                 help=f"Delete {cid}"):
                        st.session_state[f"mine_confirm_del_col_{cid}"] = True

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

    year_label = st.text_input(
        "Year / Survey Label",
        value="2019",
        placeholder="e.g. 2019  or  2026",
        key="mining_analytics_year",
        help="This label is used as the key in the analytics JSON (e.g. \"2019\").",
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
    # Validate uploaded GeoJSON files
    for akey, uploaded in geojson_files.items():
        if uploaded is not None:
            try:
                uploaded.seek(0)
                json.loads(uploaded.read())
                uploaded.seek(0)
            except Exception as _ve:
                errors.append(f"{GEOJSON_ASSETS[akey][0]}: Invalid GeoJSON — {_ve}")

    if errors:
        for e in errors:
            st.error(f"❌ {e}")
        return

    # ── Compute paths ──────────────────────────────────────────────────────────
    iid_clean  = item_id_auto.replace(" ", "-")
    dt_str     = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
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

    # For preview mode: use default rescale (COG not on server yet)
    if do_preview:
        rescale = "0,255"
    else:
        # Fetch real stats from TiTiler (COG will be on server after copy below)
        rescale = "0,255"   # filled in after COG is saved

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
            r1, r2 = st.columns(2)
            with r1:
                with st.expander("📄 Raw STAC JSON"):
                    st.json(item)
            with r2:
                if st.button(f"🗑️ Delete `{iid}`", key=f"mine_del_{iid}"):
                    st.session_state[f"mine_del_confirm_{iid}"] = True

            if st.session_state.get(f"mine_del_confirm_{iid}"):
                st.warning("Permanently delete this item?")
                y, n = st.columns(2)
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
