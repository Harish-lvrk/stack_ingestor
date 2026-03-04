"""frontend/mining/section_create_item.py — Create Survey Item section."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from backend.stac_api import (
    api_push_item,
    fetch_collections,
    local_to_url,
)
from config import COG_SAVE_DIR, STAC_API_URL, TITILER_URL, TILE_MATRIX_SET
from logger import get_logger

from .constants import GEOJSON_ASSETS, MINING_ROOT, ANALYTICS_FILE
from .utils import (
    _build_mining_item,
    _compute_rescale_local,
    _extract_image_date,
    _geojson_area_km2,
    _item_folder,
    _mining_collection_ids,
    _mining_collections,
    _section_header,
    _validate_geojson_bytes,
)

log = get_logger("tab_mining")

_LARGE_MB = 900


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

    # session_state key for per-item computed areas: {akey: km2}
    _area_sk = f"_gj_areas_{item_id_auto or 'new'}"
    if _area_sk not in st.session_state:
        st.session_state[_area_sk] = {}

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
                        raw = uploaded.read()
                        uploaded.seek(0)
                        gj       = json.loads(raw)
                        n_feat   = len(gj.get("features", []))
                        area_km2, area_err = _geojson_area_km2(raw)
                        st.session_state[_area_sk][akey] = area_km2
                        if area_err:
                            # Calculation failed — show the actual error
                            st.markdown(
                                f'<span style="background:#fef9c3;border:1px solid #ca8a04;'
                                f'color:#854d0e;font-size:0.72rem;font-weight:700;'
                                f'padding:2px 10px;border-radius:100px;">'
                                f'⚠️ {uploaded.name} · {n_feat} ft · area error: {area_err[:60]}</span>',
                                unsafe_allow_html=True,
                            )
                        else:
                            area_label = f'{area_km2:.4f} km²' if area_km2 > 0 else 'no polygon geometry'
                            st.markdown(
                                f'<span style="background:#dcfce7;border:1px solid #16a34a;'
                                f'color:#15803d;font-size:0.72rem;font-weight:700;'
                                f'padding:2px 10px;border-radius:100px;">'
                                f'✅ {uploaded.name} · {n_feat} feature{"s" if n_feat!=1 else ""} · <b>{area_label}</b></span>',
                                unsafe_allow_html=True,
                            )
                    except Exception as _e:
                        st.session_state[_area_sk].pop(akey, None)
                        st.markdown(
                            f'<span style="background:#fee2e2;border:1px solid #dc2626;'
                            f'color:#dc2626;font-size:0.72rem;font-weight:700;'
                            f'padding:2px 10px;border-radius:100px;">'
                            f'❌ {uploaded.name} · {str(_e)[:60]}</span>',
                            unsafe_allow_html=True,
                        )
                else:
                    st.session_state[_area_sk].pop(akey, None)

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

    _AKEY_TO_CLASS: dict[str, str | None] = {
        "boundary":             None,
        "mining_area":          "Mining Area",
        "new_mine_pit":         "New Mine Pit Area",
        "stockpile":            "Stockpile / Dumping Area",
        "reclamation":          "Reclamation",
        "haul_roads":           None,
        "temporary_water_pits": "Temporary Water Pits",
    }

    _computed_areas = st.session_state.get(_area_sk, {})

    # ─ % denominator = geodesic area of the selected collection's bbox ─────────
    # Manager requirement: % = layer_area / collection_bbox_area × 100
    _col_bbox_km2  = 0.0
    _col_bbox_info = ""
    _selected_col  = st.session_state.get("mining_selected_col", "")
    if _selected_col:
        try:
            from backend.stac_api import fetch_collection as _fc
            _col_data = _fc(_selected_col)
            _bbox = (
                _col_data.get("extent", {})
                         .get("spatial", {})
                         .get("bbox", [[]])[0]
            )
            if isinstance(_bbox, list) and len(_bbox) == 4:
                _min_lon, _min_lat, _max_lon, _max_lat = map(float, _bbox)
                _rect_ring = [
                    [_min_lon, _min_lat], [_max_lon, _min_lat],
                    [_max_lon, _max_lat], [_min_lon, _max_lat],
                    [_min_lon, _min_lat],
                ]
                try:
                    from pyproj import Geod as _G2
                    _g2  = _G2(ellps="WGS84")
                    _lons = [float(p[0]) for p in _rect_ring]
                    _lats = [float(p[1]) for p in _rect_ring]
                    _a2, _ = _g2.polygon_area_perimeter(_lons, _lats)
                    _col_bbox_km2 = abs(float(_a2)) / 1_000_000
                except ImportError:
                    import numpy as _npb
                    _R2 = 6_371_000.0
                    _lo = _npb.radians([float(p[0]) for p in _rect_ring])
                    _la = _npb.radians([float(p[1]) for p in _rect_ring])
                    _col_bbox_km2 = abs(float(
                        _npb.sum(_npb.diff(_lo) * (_npb.sin(_la[:-1]) + _npb.sin(_la[1:])))
                    )) * _R2 * _R2 / 2 / 1_000_000
                _col_bbox_info = (
                    f"**{_selected_col}** bbox area = **{_col_bbox_km2:.4f} km\u00b2**"
                )
        except Exception:
            pass

    # Fall back to uploaded boundary.geojson area when no collection bbox set
    _denom_km2 = _col_bbox_km2 if _col_bbox_km2 > 0 else _computed_areas.get("boundary", 0.0)

    # ─ Push computed areas into widget session_state keys (only on new uploads) ─
    _applied_key  = f"_gj_applied_{item_id_auto or 'new'}"
    _last_applied = st.session_state.get(_applied_key, {})
    if _computed_areas != _last_applied:
        for _akey, _mapped_cls in _AKEY_TO_CLASS.items():
            if _mapped_cls:
                _a = _computed_areas.get(_akey, 0.0)
                _p = round(_a / _denom_km2 * 100, 2) if (_denom_km2 > 0 and _a > 0) else 0.0
                st.session_state[f"analytics_area_{_mapped_cls}"] = round(_a, 4)
                st.session_state[f"analytics_pct_{_mapped_cls}"]  = _p
        st.session_state[_applied_key] = dict(_computed_areas)

    has_auto_fill = any(
        _computed_areas.get(k, 0.0) > 0
        for k, cls in _AKEY_TO_CLASS.items() if cls
    )
    if has_auto_fill:
        _denom_label = (
            f"Collection bbox area: {_col_bbox_info} used for % calculation."
            if _col_bbox_km2 > 0
            else "Set collection bbox or upload `boundary.geojson` to auto-calculate %."
        )
        st.caption(
            f"\U0001f9e0 **Areas auto-calculated from uploaded GeoJSON polygons.** "
            f"{_denom_label} Values are editable."
        )
    analytics_rows: list[dict] = []
    has_analytics = False

    header_cols = st.columns([3, 2, 2])
    header_cols[0].markdown("**Land Cover Class**")
    header_cols[1].markdown("**Area Covered (km²)**")
    header_cols[2].markdown("**% Covered**")

    for cls_name in _ANALYTIC_CLASSES:
        # Find the akey whose class matches this row
        auto_area = 0.0
        for akey, mapped_cls in _AKEY_TO_CLASS.items():
            if mapped_cls == cls_name:
                auto_area = _computed_areas.get(akey, 0.0)
                break

        auto_pct = round((auto_area / _denom_km2 * 100), 2) if (_denom_km2 > 0 and auto_area > 0) else 0.0

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
                value=round(auto_area, 4),
                min_value=0.0, step=0.001, format="%.4f",
                key=f"analytics_area_{cls_name}",
                label_visibility="collapsed",
            )
        with row_cols[2]:
            pct_val = st.number_input(
                f"% {cls_name}",
                value=round(auto_pct, 2),
                min_value=0.0, max_value=100.0, step=0.01, format="%.2f",
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
        do_preview = st.button("👁️ Preview STAC JSON", width="stretch")
    with sc:
        do_save = st.button("💾 Save & Push to STAC API",
                            type="primary", width="stretch")

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
        st.toast(f"✅ Survey item **{iid_clean}** saved!", icon="⛏️")
    else:
        st.error(f"❌ Files saved but API push failed: {err}")


