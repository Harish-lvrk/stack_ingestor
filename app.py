"""
STAC Manager
─────────────
Tab 1 — 🛰️  Ingest   : Upload GeoTIFF → Convert to COG → Generate STAC JSON → Push
Tab 2 — 📦  Collections : CRUD for STAC collections (JSON preview before every write)
Tab 3 — 📋  Items       : Browse items per collection, view JSON, delete
"""

import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import requests
import rasterio
from rasterio.warp import transform_bounds, transform_geom
import streamlit as st

# ─── Configuration ──────────────────────────────────────────────────────────
FILE_SERVER_URL = "http://127.0.0.1:8085"
FILE_SERVER_ROOT = Path.home()
COG_SAVE_DIR     = Path.home() / "Documents" / "serverimages"
TITILER_URL      = "http://localhost:8008"
STAC_API_URL     = "http://localhost:8082"

# ─── API helpers ────────────────────────────────────────────────────────────

def local_to_url(filepath: Path) -> str:
    rel = filepath.relative_to(FILE_SERVER_ROOT)
    return f"{FILE_SERVER_URL}/{rel}"


def convert_to_cog(input_path: Path, output_path: Path) -> tuple[bool, str]:
    result = subprocess.run(
        ["gdal_translate", "-of", "COG",
         "-co", "COMPRESS=LZW", "-co", "OVERVIEWS=AUTO",
         str(input_path), str(output_path)],
        capture_output=True, text=True,
    )
    return result.returncode == 0, result.stderr


def read_metadata(filepath: Path) -> dict:
    with rasterio.open(filepath) as src:
        bounds = src.bounds
        crs    = src.crs
        wgs84  = transform_bounds(crs, "EPSG:4326",
                                   bounds.left, bounds.bottom,
                                   bounds.right, bounds.top)
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
        return {
            "bbox":       [round(min_lon, 6), round(min_lat, 6),
                           round(max_lon, 6), round(max_lat, 6)],
            "geometry":   geometry,
            "epsg":       crs.to_epsg(),
            "band_count": src.count,
            "dtypes":     list(src.dtypes),
            "gsd":        round(abs(src.transform.a), 2),
        }


def fetch_titiler_stats(file_url: str) -> dict:
    try:
        r = requests.get(f"{TITILER_URL}/cog/statistics",
                         params={"url": file_url}, timeout=30)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {}


def compute_rescale(stats: dict, band_indices: list[int]) -> str:
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


def band_list(band_count: int) -> list[dict]:
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
    item_id, collection, dt_str, metadata, file_url, stats,
    title="", platform="", instruments=None
) -> dict:
    bc   = metadata["band_count"]
    bidx = [1, 2, 3] if bc == 3 else ([3, 2, 1] if bc >= 4 else [1])
    bidx_qs  = "&".join(f"bidx={i}" for i in bidx)
    rescale  = compute_rescale(stats, bidx)

    tile_url    = (f"{TITILER_URL}/cog/WebMercatorQuad/tilejson.json"
                   f"?url={file_url}&{bidx_qs}&rescale={rescale}")
    preview_url = (f"{TITILER_URL}/cog/preview.png"
                   f"?url={file_url}&{bidx_qs}&rescale={rescale}")

    properties = {
        "datetime":  dt_str,
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

    return {
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
            {"rel": "parent", "type": "application/json",
             "href": f"{STAC_API_URL}/collections/{collection}"},
            {"rel": "root", "type": "application/json",
             "href": f"{STAC_API_URL}/"},
            {"rel": "self", "type": "application/geo+json",
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


# ─── Collection API helpers ──────────────────────────────────────────────────

def fetch_collections() -> list[dict]:
    """Return list of raw collection dicts from the STAC API."""
    try:
        r = requests.get(f"{STAC_API_URL}/collections", timeout=5)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list):
                cols = data                          # bare list response
            elif isinstance(data, dict):
                cols = data.get("collections", [])   # {collections: [...], ...}
            else:
                cols = []
            return [c for c in cols if isinstance(c, dict)]
    except Exception:
        pass
    return []


def fetch_collection_ids() -> list[str]:
    return sorted(c["id"] for c in fetch_collections() if "id" in c)


def build_collection_payload(col_id: str, title: str,
                              description: str, license_: str) -> dict:
    return {
        "type":         "Collection",
        "id":           col_id,
        "stac_version": "1.0.0",
        "title":        title or col_id,
        "description":  description or col_id,
        "license":      license_,
        "links":        [],
        "extent": {
            "spatial":  {"bbox": [[-180.0, -90.0, 180.0, 90.0]]},
            "temporal": {"interval": [[None, None]]},
        },
    }


def api_create_collection(payload: dict) -> tuple[bool, str]:
    try:
        r = requests.post(f"{STAC_API_URL}/collections",
                          json=payload,
                          headers={"Content-Type": "application/json"},
                          timeout=10)
        if r.status_code in (200, 201):
            return True, ""
        if r.status_code == 409:
            return False, "409 — collection already exists."
        return False, f"HTTP {r.status_code}: {r.text[:300]}"
    except Exception as exc:
        return False, str(exc)


def api_update_collection(col_id: str, payload: dict) -> tuple[bool, str]:
    try:
        r = requests.put(f"{STAC_API_URL}/collections/{col_id}",
                         json=payload,
                         headers={"Content-Type": "application/json"},
                         timeout=10)
        if r.status_code in (200, 201, 204):
            return True, ""
        return False, f"HTTP {r.status_code}: {r.text[:300]}"
    except Exception as exc:
        return False, str(exc)


def api_delete_collection(col_id: str) -> tuple[bool, str]:
    try:
        r = requests.delete(f"{STAC_API_URL}/collections/{col_id}", timeout=10)
        if r.status_code in (200, 204):
            return True, ""
        return False, f"HTTP {r.status_code}: {r.text[:300]}"
    except Exception as exc:
        return False, str(exc)


# ─── Item API helpers ────────────────────────────────────────────────────────

def fetch_items(col_id: str, limit: int = 200) -> list[dict]:
    try:
        r = requests.get(f"{STAC_API_URL}/collections/{col_id}/items",
                         params={"limit": limit}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return data.get("features", data) if isinstance(data, dict) else data
    except Exception:
        pass
    return []


def api_delete_item(col_id: str, item_id: str) -> tuple[bool, str]:
    try:
        r = requests.delete(
            f"{STAC_API_URL}/collections/{col_id}/items/{item_id}", timeout=10)
        if r.status_code in (200, 204):
            return True, ""
        return False, f"HTTP {r.status_code}: {r.text[:300]}"
    except Exception as exc:
        return False, str(exc)


# ════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG & GLOBAL STYLES
# ════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="STAC Manager",
    page_icon="🛰️",
    layout="wide",
)

st.markdown("""
<style>
    .step-header { font-size:1.2rem; font-weight:700; margin-top:1.5rem; }
    div[data-testid="stJson"] { max-height:500px; overflow:auto; }
    .section-title {
        font-size: 1.15rem; font-weight: 700;
        border-left: 4px solid #4da6ff;
        padding-left: 0.6rem; margin: 1.2rem 0 0.6rem;
    }
</style>
""", unsafe_allow_html=True)

st.title("🛰️ STAC Manager")

# ─── Service status bar (shown on every tab) ────────────────────────────────
c1, c2, c3 = st.columns(3)
with c1:
    try:
        requests.get(STAC_API_URL, timeout=2)
        st.success("✅ STAC API  :8082")
    except Exception:
        st.error("❌ STAC API  :8082")
with c2:
    try:
        requests.get(f"{TITILER_URL}/healthz", timeout=2)
        st.success("✅ Titiler  :8008")
    except Exception:
        st.error("❌ Titiler  :8008")
with c3:
    try:
        requests.get(FILE_SERVER_URL, timeout=2)
        st.success("✅ File server  :8085")
    except Exception:
        st.error("❌ File server  :8085")

st.divider()

# ════════════════════════════════════════════════════════════════════════════
# TABS
# ════════════════════════════════════════════════════════════════════════════
tab_ingest, tab_collections, tab_items = st.tabs(
    ["🛰️  Ingest", "📦  Collections", "📋  Items"]
)

# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — INGEST
# ════════════════════════════════════════════════════════════════════════════
with tab_ingest:
    st.markdown('<p class="step-header">📤 Step 1 — Upload GeoTIFF</p>',
                unsafe_allow_html=True)
    uploaded = st.file_uploader("Choose a .tif / .tiff file", type=["tif", "tiff"])

    if not uploaded:
        st.info("Upload a GeoTIFF above to begin.")
    else:
        tmp_path = Path(tempfile.mkdtemp()) / uploaded.name
        with open(tmp_path, "wb") as f:
            f.write(uploaded.getbuffer())

        st.success(f"✅ Received **{uploaded.name}** — {uploaded.size / 1_000_000:.2f} MB")
        st.divider()

        # ── Step 2 ──────────────────────────────────────────────────────────
        st.markdown('<p class="step-header">📋 Step 2 — Item Details</p>',
                    unsafe_allow_html=True)

        col_a, col_b = st.columns(2)
        with col_a:
            _NEW_OPTION   = "＋ New collection…"
            existing_cols = fetch_collection_ids()
            dropdown_opts = existing_cols + [_NEW_OPTION]

            selected_col = st.selectbox(
                "Collection Name *",
                options=dropdown_opts,
                help="Pick an existing collection or create one in the Collections tab.",
            )

            if selected_col == _NEW_OPTION:
                collection = st.text_input(
                    "New collection name *",
                    placeholder="e.g. zone42n_visual_collection",
                )
                if collection:
                    if st.button("🗂️ Create collection (world bbox)", key="ingest_create_col"):
                        payload = build_collection_payload(collection, collection, collection, "proprietary")
                        ok, err = api_create_collection(payload)
                        if ok:
                            st.success(f"✅ Collection **{collection}** created!")
                            st.rerun()
                        else:
                            st.error(f"❌ {err}")
            else:
                collection = selected_col

            item_id = st.text_input(
                "Item ID *",
                value=Path(uploaded.name).stem.lower().replace(" ", "-"),
                placeholder="e.g. sn28-20250511-visual",
            )
            item_title = st.text_input(
                "Title (optional)",
                placeholder="e.g. SuperDove SN28 - 2025-05-11 Visual Capture",
            )

        with col_b:
            capture_dt = st.text_input(
                "Capture Datetime (UTC)",
                placeholder="2025-05-11T09:44:26Z  (leave blank = now)",
            )
            cog_filename = st.text_input(
                "COG output filename",
                value=Path(uploaded.name).stem.rstrip("_cog") + "_cog.tif",
            )
            platform = st.text_input(
                "Platform (optional)",
                placeholder="e.g. SuperDove-SN28",
            )
            instruments = st.text_input(
                "Instruments (optional, comma-separated)",
                placeholder="e.g. PSB.SD",
            )

        if not collection or not item_id:
            st.warning("Please fill in Collection Name and Item ID to continue.")
        else:
            st.divider()

            # ── Step 3 ──────────────────────────────────────────────────────
            st.markdown('<p class="step-header">⚙️ Step 3 — Convert to COG & Generate JSON</p>',
                        unsafe_allow_html=True)

            if st.button("🔄  Convert → Extract metadata → Generate STAC JSON", type="primary"):
                COG_SAVE_DIR.mkdir(parents=True, exist_ok=True)
                cog_path = COG_SAVE_DIR / cog_filename

                with st.spinner("Converting to Cloud Optimized GeoTIFF…"):
                    ok, err = convert_to_cog(tmp_path, cog_path)

                if not ok:
                    st.error(f"❌ COG conversion failed:\n```\n{err}\n```")
                else:
                    st.success(f"✅ COG saved → `{cog_path}`")
                    file_url = local_to_url(cog_path)
                    st.info(f"📡 File server URL: `{file_url}`")

                    with st.spinner("Reading image metadata…"):
                        try:
                            meta = read_metadata(cog_path)
                            meta_ok = True
                        except Exception as exc:
                            st.error(f"❌ Could not read metadata: {exc}")
                            meta_ok = False

                    if meta_ok:
                        with st.expander("🔍 Image metadata (from GeoTIFF)", expanded=False):
                            st.json(meta)

                        with st.spinner("Fetching band statistics from Titiler…"):
                            stats = fetch_titiler_stats(file_url)

                        if stats:
                            with st.expander("📊 Band statistics (from Titiler)", expanded=False):
                                st.json(stats)
                        else:
                            st.warning("⚠️  Could not reach Titiler — default rescale (0,255) used.")

                        dt_str = (capture_dt.strip() if capture_dt.strip()
                                  else datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))

                        stac_item = build_stac_item(
                            item_id, collection, dt_str, meta, file_url, stats,
                            title=item_title, platform=platform, instruments=instruments,
                        )
                        st.session_state["stac_item"]  = stac_item
                        st.session_state["collection"] = collection

            # ── Step 4 ──────────────────────────────────────────────────────
            if "stac_item" in st.session_state:
                st.divider()
                st.markdown('<p class="step-header">📄 Step 4 — Review Generated STAC JSON</p>',
                            unsafe_allow_html=True)

                item = st.session_state["stac_item"]
                col  = st.session_state["collection"]

                st.json(item)

                st.download_button(
                    label="⬇️ Download JSON",
                    data=json.dumps(item, indent=2),
                    file_name=f"{item['id']}.json",
                    mime="application/json",
                )

                st.divider()
                st.markdown('<p class="step-header">🚀 Step 5 — Push to STAC API</p>',
                            unsafe_allow_html=True)

                push_url = f"{STAC_API_URL}/collections/{col}/items"
                st.code(f"POST  {push_url}", language="text")

                if st.button("🚀  Push to STAC API", type="primary"):
                    with st.spinner("Posting item…"):
                        try:
                            r = requests.post(
                                push_url, json=item,
                                headers={"Content-Type": "application/json"},
                                timeout=15,
                            )
                            if r.status_code in (200, 201):
                                st.success(f"✅ Item **{item['id']}** added to **{col}**!")
                                st.balloons()
                            elif r.status_code == 409:
                                st.warning("⚠️  Item already exists. Use a different Item ID.")
                            else:
                                st.error(f"❌ HTTP {r.status_code}")
                                st.code(r.text)
                        except requests.exceptions.ConnectionError:
                            st.error("❌ Cannot connect to STAC API.")
                        except Exception as exc:
                            st.error(f"❌ {exc}")






# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — COLLECTIONS CRUD
# ════════════════════════════════════════════════════════════════════════════
with tab_collections:

    # ── Section: All collections ─────────────────────────────────────────────
    st.markdown('<p class="section-title">📋 Existing Collections</p>',
                unsafe_allow_html=True)

    if st.button("🔄 Refresh list", key="refresh_cols"):
        st.rerun()

    all_cols = fetch_collections()

    with st.expander("🐛 Debug — raw API response", expanded=not all_cols):
        try:
            raw_r = requests.get(f"{STAC_API_URL}/collections", timeout=5)
            st.caption(f"HTTP status: **{raw_r.status_code}**  |  URL: `{STAC_API_URL}/collections`")
            raw_data = raw_r.json()
            st.caption(f"Top-level keys: `{list(raw_data.keys()) if isinstance(raw_data, dict) else type(raw_data).__name__}`")
            st.caption(f"Collections parsed by app: **{len(all_cols)}**")
            st.json(raw_data)
        except Exception as exc:
            st.error(f"Could not reach STAC API: {exc}")

    if not all_cols:
        st.info("No collections found in the STAC API.")
    else:
        for col in all_cols:
            cid   = col.get("id", "—")
            ctitle = col.get("title", "—")
            cdesc  = col.get("description", "")
            with st.expander(f"**{cid}** — {ctitle}", expanded=False):
                sub1, sub2 = st.columns([3, 1])
                with sub1:
                    st.caption(f"Description: {cdesc}")
                with sub2:
                    # Delete button
                    if st.button("🗑️ Delete", key=f"del_col_{cid}"):
                        st.session_state[f"confirm_del_col_{cid}"] = True

                if st.session_state.get(f"confirm_del_col_{cid}"):
                    st.warning(
                        f"⚠️ Are you sure you want to delete **{cid}**? "
                        "This also removes all its items."
                    )
                    cc1, cc2 = st.columns(2)
                    with cc1:
                        if st.button("✅ Yes, delete", key=f"confirm_yes_{cid}"):
                            ok, err = api_delete_collection(cid)
                            if ok:
                                st.success(f"✅ Deleted **{cid}**.")
                                del st.session_state[f"confirm_del_col_{cid}"]
                                st.rerun()
                            else:
                                st.error(f"❌ {err}")
                    with cc2:
                        if st.button("❌ Cancel", key=f"confirm_no_{cid}"):
                            del st.session_state[f"confirm_del_col_{cid}"]
                            st.rerun()

                st.json(col)

    st.divider()

    # ── Section: Create Collection ───────────────────────────────────────────
    st.markdown('<p class="section-title">➕ Create New Collection</p>',
                unsafe_allow_html=True)

    with st.form("create_col_form", clear_on_submit=False):
        cc1, cc2 = st.columns(2)
        with cc1:
            new_col_id    = st.text_input("Collection ID *",
                                          placeholder="e.g. my_satellite_collection")
            new_col_title = st.text_input("Title",
                                          placeholder="e.g. My Satellite Collection")
        with cc2:
            new_col_desc  = st.text_area("Description",
                                         placeholder="Short description of this collection",
                                         height=100)
            new_col_lic   = st.selectbox(
                "License",
                ["proprietary", "various", "CC-BY-4.0", "ODbL-1.0", "other"],
            )

        preview_btn = st.form_submit_button("👁️ Preview JSON")
        create_btn  = st.form_submit_button("✅ Create Collection", type="primary")

    if (preview_btn or create_btn) and new_col_id:
        new_payload = build_collection_payload(
            new_col_id, new_col_title, new_col_desc, new_col_lic
        )
        st.markdown("**📄 JSON that will be sent to the API:**")
        st.json(new_payload)

        if create_btn:
            ok, err = api_create_collection(new_payload)
            if ok:
                st.success(f"✅ Collection **{new_col_id}** created with world-wide bbox!")
                st.rerun()
            else:
                st.error(f"❌ {err}")
    elif (preview_btn or create_btn) and not new_col_id:
        st.warning("Collection ID is required.")

    st.divider()

    # ── Section: Update Collection ───────────────────────────────────────────
    st.markdown('<p class="section-title">✏️ Update Existing Collection</p>',
                unsafe_allow_html=True)

    col_ids = [c.get("id") for c in all_cols if "id" in c]
    if not col_ids:
        st.info("No collections available to update.")
    else:
        upd_col_id = st.selectbox("Select collection to update",
                                  col_ids, key="upd_col_select")

        # Pre-fill with existing values
        existing = next((c for c in all_cols if c.get("id") == upd_col_id), {})

        with st.form("update_col_form", clear_on_submit=False):
            uc1, uc2 = st.columns(2)
            with uc1:
                upd_title = st.text_input("Title",
                                          value=existing.get("title", ""),
                                          key="upd_title")
                upd_lic = st.selectbox(
                    "License",
                    ["proprietary", "various", "CC-BY-4.0", "ODbL-1.0", "other"],
                    index=["proprietary", "various", "CC-BY-4.0", "ODbL-1.0", "other"].index(
                        existing.get("license", "proprietary")
                    ) if existing.get("license", "proprietary") in
                         ["proprietary", "various", "CC-BY-4.0", "ODbL-1.0", "other"] else 0,
                    key="upd_lic",
                )
            with uc2:
                upd_desc = st.text_area("Description",
                                        value=existing.get("description", ""),
                                        height=100, key="upd_desc")

            upd_preview_btn = st.form_submit_button("👁️ Preview Updated JSON")
            upd_save_btn    = st.form_submit_button("💾 Save Changes", type="primary")

        if upd_preview_btn or upd_save_btn:
            # Merge updates into existing dict to preserve spatial/temporal extent etc.
            upd_payload = {**existing,
                           "title": upd_title,
                           "description": upd_desc,
                           "license": upd_lic}
            st.markdown("**📄 JSON that will be sent to the API:**")
            st.json(upd_payload)

            if upd_save_btn:
                ok, err = api_update_collection(upd_col_id, upd_payload)
                if ok:
                    st.success(f"✅ Collection **{upd_col_id}** updated!")
                    st.rerun()
                else:
                    st.error(f"❌ {err}")


# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — ITEMS BROWSER
# ════════════════════════════════════════════════════════════════════════════
with tab_items:
    st.markdown('<p class="section-title">📋 Browse Items by Collection</p>',
                unsafe_allow_html=True)

    item_col_ids = fetch_collection_ids()
    if not item_col_ids:
        st.info("No collections found. Create one in the Collections tab first.")
    else:
        ic1, ic2 = st.columns([2, 1])
        with ic1:
            sel_col = st.selectbox("Select collection", item_col_ids, key="items_col_sel")
        with ic2:
            st.write("")
            st.write("")
            if st.button("🔄 Refresh", key="refresh_items"):
                st.rerun()

        items = fetch_items(sel_col)

        if not items:
            st.info(f"No items found in **{sel_col}**.")
        else:
            st.caption(f"Showing **{len(items)}** item(s) in `{sel_col}`")
            st.divider()

            for item in items:
                iid  = item.get("id", "—")
                idt  = item.get("properties", {}).get("datetime", "—")
                bbox = item.get("bbox", [])
                bbox_str = (f"{bbox[0]:.4f}, {bbox[1]:.4f} → "
                            f"{bbox[2]:.4f}, {bbox[3]:.4f}") if bbox else "—"

                with st.expander(f"**{iid}**  |  {idt}  |  bbox: {bbox_str}",
                                 expanded=False):
                    col_view, col_del = st.columns([5, 1])
                    with col_del:
                        if st.button("🗑️ Delete", key=f"del_item_{iid}"):
                            st.session_state[f"confirm_del_item_{iid}"] = True

                    if st.session_state.get(f"confirm_del_item_{iid}"):
                        st.warning(f"⚠️ Delete item **{iid}**?")
                        dc1, dc2 = st.columns(2)
                        with dc1:
                            if st.button("✅ Yes, delete", key=f"del_item_yes_{iid}"):
                                ok, err = api_delete_item(sel_col, iid)
                                if ok:
                                    st.success(f"✅ Deleted **{iid}**.")
                                    del st.session_state[f"confirm_del_item_{iid}"]
                                    st.rerun()
                                else:
                                    st.error(f"❌ {err}")
                        with dc2:
                            if st.button("❌ Cancel", key=f"del_item_no_{iid}"):
                                del st.session_state[f"confirm_del_item_{iid}"]
                                st.rerun()

                    st.markdown("**Full STAC Item JSON:**")
                    st.json(item)
