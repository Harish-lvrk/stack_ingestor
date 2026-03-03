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

def _build_mining_item(
    item_id: str,
    collection: str,
    datetime_str: str,
    region_id: int,
    location_name: str,
    bbox: list[float],
    geometry: dict,
    asset_urls: dict[str, str],
) -> dict:
    assets: dict = {}

    _ASSET_SCHEMA = {
        "visual":  ("image/tiff; application=geotiff; profile=cloud-optimized",
                    ["data", "visual"], "COG Image"),
        "tiles":   ("application/json",  ["tiles"],    "TiTiler RGB Tile Service"),
        "preview": ("image/png",         ["overview"], "RGB Preview Image"),
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
        "properties": {
            "datetime":             datetime_str,
            "region_id":            region_id,
            "mining_location_name": location_name,
        },
        "assets": assets,
        "stac_extensions": [
            "https://stac-extensions.github.io/projection/v1.1.0/schema.json",
            "https://stac-extensions.github.io/eo/v1.1.0/schema.json",
            "https://stac-extensions.github.io/view/v1.0.0/schema.json",
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

    # ── 2 · Upload GeoTIFF → auto-converted to COG ───────────────────────────
    st.markdown("##### 2 · Upload GeoTIFF")
    st.caption(
        "Upload any GeoTIFF — it will be **converted to COG** automatically. "
        "Item ID, bounding box and geometry are extracted from the COG."
    )
    tif_file = st.file_uploader(
        "GeoTIFF File (.tif / .tiff) *",
        type=["tif", "tiff"],
        key="mining_tif_upload",
    )

    tif_meta: dict | None     = None
    item_id_auto: str         = ""
    cog_tmp_path: Path | None = None

    if tif_file is not None:
        from backend.cog import convert_to_cog, read_metadata
        import tempfile, shutil as _shutil

        item_id_auto = Path(tif_file.name).stem
        st.info(f"📛 Item ID will be: **`{item_id_auto}`**")

        # Cache key based on filename — only reconvert when a NEW file is uploaded
        cache_key = f"mining_cog_{tif_file.name}"
        cached    = st.session_state.get(cache_key)

        # Invalidate cache if the temp COG was cleaned up
        if cached and not Path(cached["cog_path"]).exists():
            del st.session_state[cache_key]
            cached = None

        if cached is None:
            # ── First upload: convert to COG and cache the result ──
            try:
                tif_file.seek(0)          # ensure stream is at start
                with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as raw_tmp:
                    _shutil.copyfileobj(tif_file, raw_tmp)
                    raw_path = Path(raw_tmp.name)

                cog_path = raw_path.with_name(raw_path.stem + "_cog.tif")
                with st.spinner("⚙️ Converting to Cloud-Optimized GeoTIFF (COG)…"):
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

    # ── 3 · GeoJSON layers ────────────────────────────────────────────────────
    st.markdown("##### 4 · Vector Change Layers — Paste GeoJSON")
    st.caption("Paste the GeoJSON for each layer. Leave blank to skip.")

    geojson_texts: dict[str, str] = {}
    keys         = list(GEOJSON_ASSETS.items())
    left_assets  = keys[: len(keys) // 2 + len(keys) % 2]
    right_assets = keys[len(keys) // 2 + len(keys) % 2 :]

    col_l, col_r = st.columns(2)
    for col_widget, asset_group in [(col_l, left_assets), (col_r, right_assets)]:
        with col_widget:
            for akey, (alabel, _) in asset_group:
                geojson_texts[akey] = st.text_area(
                    alabel,
                    placeholder='{"type":"FeatureCollection","features":[...]}',
                    height=130,
                    key=f"mining_json_{akey}",
                )

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
    if tif_file is None:
        errors.append("GeoTIFF file is required.")
    if tif_meta is None and tif_file is not None:
        errors.append("GeoTIFF could not be read — check the file and try again.")
    for akey, text in geojson_texts.items():
        valid, msg = _validate_geojson_text(akey, text)
        if not valid:
            errors.append(msg)

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

    # GeoJSON asset URLs (project the path even in preview mode)
    for akey, (_, filename) in GEOJSON_ASSETS.items():
        text = geojson_texts.get(akey, "").strip()
        if text:
            asset_urls[akey] = local_to_url(folder / filename)

    if do_save:
        import shutil, requests as _req

        # ── 1. Save original TIF ─────────────────────────────────────────────
        tif_file.seek(0)
        orig_dest.write_bytes(tif_file.read())

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

        # ── 5. Save GeoJSONs ─────────────────────────────────────────────────
        for akey, (_, filename) in GEOJSON_ASSETS.items():
            text = geojson_texts.get(akey, "").strip()
            if text:
                (folder / filename).write_text(text, encoding="utf-8")

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
