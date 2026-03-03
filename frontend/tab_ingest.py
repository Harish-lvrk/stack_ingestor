"""frontend/tab_ingest.py — Ingest tab UI (Steps 1-5)."""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from config import COG_SAVE_DIR
from backend.cog import convert_to_cog, read_metadata
from backend.titiler import fetch_titiler_stats
from backend.stac_builder import build_stac_item
from backend.stac_api import (
    fetch_collection_ids, build_collection_payload,
    api_create_collection, api_push_item, local_to_url,
)
from logger import get_logger

log = get_logger("tab_ingest")

_NEW_OPTION = "＋ New collection…"
_LARGE_FILE_MB = 500  # files above this threshold should use path mode


def _save_uploaded(uploaded) -> Path:
    """Stream a Streamlit UploadedFile to a temp file in 64 MB chunks."""
    CHUNK = 64 * 1024 * 1024
    tmp_path = Path(tempfile.mkdtemp()) / uploaded.name
    with open(tmp_path, "wb") as f:
        uploaded.seek(0)
        while True:
            chunk = uploaded.read(CHUNK)
            if not chunk:
                break
            f.write(chunk)
    return tmp_path


def render_ingest_tab() -> None:
    st.markdown('<p class="step-header">📤 Step 1 — Select GeoTIFF</p>',
                unsafe_allow_html=True)

    # ── Input mode selector ───────────────────────────────────────────────────
    input_mode = st.radio(
        "Input method",
        ["📂 Local file path (recommended for large files)",
         "⬆️  Browser upload (< 500 MB only)"],
        horizontal=True,
        help="Use the local path option for files > 500 MB to avoid out-of-memory errors.",
    )
    use_path_mode = input_mode.startswith("📂")

    tmp_path: Path | None = None
    file_name: str = ""
    file_size_mb: float = 0.0

    if use_path_mode:
        # ── Path mode: no file data passes through Streamlit memory ──────────
        st.info(
            "Enter the **absolute path** to the GeoTIFF on this machine. "
            "The file is read directly from disk — no memory limit applies.",
            icon="💡",
        )
        raw_path = st.text_input(
            "Absolute file path",
            placeholder="/home/user/data/image.tif",
        )
        if not raw_path:
            st.warning("⚠️  Enter a file path above to continue.")
            return
        p = Path(raw_path.strip())
        if not p.exists():
            st.error(f"❌ File not found: `{p}`")
            return
        if p.suffix.lower() not in {".tif", ".tiff"}:
            st.error("❌ File must have a `.tif` or `.tiff` extension.")
            return
        tmp_path = p          # use the file in-place — no copy needed
        file_name = p.name
        file_size_mb = p.stat().st_size / 1_000_000
    else:
        # ── Browser upload mode ───────────────────────────────────────────────
        if file_size_mb > _LARGE_FILE_MB:
            st.warning(
                f"⚠️  This file is **{file_size_mb:.0f} MB**. "
                "Switch to **Local file path** mode to avoid out-of-memory errors."
            )
        uploaded = st.file_uploader("Choose a .tif / .tiff file", type=["tif", "tiff"])
        if not uploaded:
            st.info("🗂️  Upload a GeoTIFF file above to begin the ingestion workflow.")
            return
        file_size_mb = uploaded.size / 1_000_000
        if file_size_mb > _LARGE_FILE_MB:
            st.error(
                f"❌ File is **{file_size_mb:.0f} MB** — too large for browser upload. "
                "Please switch to **Local file path** mode."
            )
            return
        with st.spinner("Saving uploaded file to disk…"):
            tmp_path = _save_uploaded(uploaded)
        file_name = uploaded.name

    log.info("File selected: %s (%.2f MB)", file_name, file_size_mb)
    st.success(f"✅ Received **{file_name}** — {file_size_mb:.2f} MB")
    st.divider()

    # ── Step 2: Item Details ─────────────────────────────────────────────────
    st.markdown('<p class="step-header">📋 Step 2 — Item Details</p>',
                unsafe_allow_html=True)

    col_a, col_b = st.columns(2)
    collection = ""
    item_id = ""

    with col_a:
        existing_cols = fetch_collection_ids()
        dropdown_opts = existing_cols + [_NEW_OPTION]

        selected_col = st.selectbox(
            "Collection Name *",
            options=dropdown_opts,
            help="Pick an existing collection or type a new name below.",
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
            value=Path(file_name).stem.lower().replace(" ", "-"),
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
            value=Path(file_name).stem.rstrip("_cog") + "_cog.tif",
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
        st.warning("⚠️  Please fill in **Collection Name** and **Item ID** to continue.")
        return

    st.divider()

    # ── Step 3: Convert & Generate ───────────────────────────────────────────
    st.markdown('<p class="step-header">⚙️ Step 3 — Convert to COG & Generate JSON</p>',
                unsafe_allow_html=True)

    if st.button("🔄  Convert → Extract metadata → Generate STAC JSON", type="primary"):
        COG_SAVE_DIR.mkdir(parents=True, exist_ok=True)
        cog_path = COG_SAVE_DIR / cog_filename

        with st.spinner("Converting to Cloud Optimized GeoTIFF…"):
            ok, err = convert_to_cog(tmp_path, cog_path)

        if not ok:
            st.error(f"❌ COG conversion failed:\n```\n{err}\n```")
            return

        st.success(f"✅ COG saved → `{cog_path}`")
        file_url = local_to_url(cog_path)
        st.info(f"📡 File server URL: `{file_url}`")

        with st.spinner("Reading image metadata…"):
            try:
                meta = read_metadata(cog_path)
            except Exception as exc:
                st.error(f"❌ Could not read metadata: {exc}")
                log.error("read_metadata failed: %s", exc)
                return

        with st.expander("🔍 Image metadata", expanded=False):
            st.json(meta)

        with st.spinner("Fetching band statistics from Titiler…"):
            stats = fetch_titiler_stats(file_url)

        if stats:
            with st.expander("📊 Band statistics", expanded=False):
                st.json(stats)
        else:
            st.warning("⚠️  Could not reach Titiler — default rescale (0,255) used.")

        dt_str = capture_dt.strip() or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        stac_item = build_stac_item(
            item_id, collection, dt_str, meta, file_url, stats,
            title=item_title, platform=platform, instruments=instruments,
        )
        st.session_state["stac_item"]  = stac_item
        st.session_state["collection"] = collection

    # ── Step 4: Review JSON ──────────────────────────────────────────────────
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

        # ── Step 5: Push ─────────────────────────────────────────────────────
        st.markdown('<p class="step-header">🚀 Step 5 — Push to STAC API</p>',
                    unsafe_allow_html=True)

        push_url = f"POST  {col}/items"
        st.code(push_url, language="text")

        if st.button("🚀  Push to STAC API", type="primary"):
            with st.spinner("Posting item…"):
                ok, err = api_push_item(col, item)

            if ok:
                st.success(f"✅ Item **{item['id']}** added to **{col}**!")
                st.balloons()
            elif "409" in err:
                st.warning("⚠️  Item already exists. Use a different Item ID.")
            else:
                st.error(f"❌ {err}")
