"""frontend/tab_items.py — Items browser matching STAC Browser layout exactly."""

import streamlit as st
import requests
import folium
import folium.plugins
from streamlit_folium import st_folium

from backend.stac_api import fetch_collection_ids, fetch_items, api_delete_item
from logger import get_logger

log = get_logger("tab_items")


def _build_item_map(item):
    """
    Build a Folium map for a STAC item.
    • Shows OSM base tiles (clean, neutral)
    • Overlays the COG colour tiles from Titiler (the actual satellite data)
    • Fits the viewport tightly to the item bounding box
    """
    bbox = item.get("bbox", [])
    if not bbox or len(bbox) < 4:
        bbox = [-180, -90, 180, 90]

    lat_center = (bbox[1] + bbox[3]) / 2
    lng_center = (bbox[0] + bbox[2]) / 2

    # ── Multiple switchable base tile layers ─────────────────────────────────
    # OpenStreetMap (default)
    m = folium.Map(
        location=[lat_center, lng_center],
        zoom_start=13,
        tiles="OpenStreetMap",
        prefer_canvas=True,
    )

    # Esri World Imagery (Satellite)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery",
        name="🛩️ Satellite",
        overlay=False,
        control=True,
        show=False,
    ).add_to(m)

    # CartoDB Positron (Light)
    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
        attr="CartoDB",
        name="☀️ Light (CartoDB)",
        overlay=False,
        control=True,
        show=False,
    ).add_to(m)

    # CartoDB Dark Matter
    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        attr="CartoDB",
        name="🌑 Dark (CartoDB)",
        overlay=False,
        control=True,
        show=False,
    ).add_to(m)

    # Esri World Terrain
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Topo Map",
        name="🌍 Terrain (Esri)",
        overlay=False,
        control=True,
        show=False,
    ).add_to(m)

    # Fullscreen button
    folium.plugins.Fullscreen(
        position="topright",
        title="Fullscreen",
        title_cancel="Exit Fullscreen",
        force_separate_button=True,
    ).add_to(m)

    # Fetch TileJSON from Titiler and add as a WMTSLayer
    assets = item.get("assets", {})
    tiles_asset = assets.get("tiles")
    visual_asset = assets.get("visual")

    tile_template = None
    assets = item.get("assets", {})
    tiles_asset = assets.get("tiles")

    if tiles_asset:
        tilejson_href = tiles_asset.get("href", "")
        try:
            # Fetch TileJSON once — Titiler caches this quickly after first load.
            resp = requests.get(tilejson_href, timeout=8)
            if resp.ok:
                tdata = resp.json()
                tile_urls = tdata.get("tiles", [])
                if tile_urls:
                    # TileJSON uses localhost — replace with LAN IP so the
                    # browser (not the server) can reach Titiler
                    from config import LAN_IP
                    tile_template = tile_urls[0].replace("localhost", LAN_IP)
        except Exception as e:
            log.warning(f"TileJSON fetch failed for {item.get('id')}: {e}")

    if tile_template:
        folium.TileLayer(
            tiles=tile_template,
            attr="TiTiler",
            name="🛰️ COG Imagery",
            overlay=True,
            control=True,
            show=True,
            opacity=1.0,
        ).add_to(m)


    # Blue footprint rectangle
    folium.Rectangle(
        bounds=[[bbox[1], bbox[0]], [bbox[3], bbox[2]]],
        color="#2563eb",
        weight=2,
        fill=False,
        popup=f"Item: {item.get('id')}",
    ).add_to(m)

    # Do NOT call m.fit_bounds() here — it's ignored inside st.expanders.
    # Return the bbox so st_folium can apply center + zoom directly.
    folium.LayerControl(collapsed=True, position="topright").add_to(m)
    return m, bbox




def _metadata_section(item, col_id):
    """Render the right-hand metadata panel matching STAC Browser."""
    props = item.get("properties", {})
    eo_bands = props.get("eo:bands") or [
        b
        for a in item.get("assets", {}).values()
        for b in a.get("eo:bands", [])
    ]

    # Collection info
    st.markdown(f"""
<div style="margin-bottom:1.5rem;">
  <p style="font-weight:700; font-size:1.05rem; color:#0f172a; margin-bottom:0.6rem;">🗂️ Collection</p>
  <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:0.8rem 1rem;">
    <span style="font-weight:600; color:#2563eb;">{col_id}</span>
  </div>
</div>
""", unsafe_allow_html=True)

    # General metadata
    st.markdown('<p style="font-weight:700; font-size:1.05rem; color:#0f172a; margin-bottom:0.6rem;">📊 Metadata</p>', unsafe_allow_html=True)
    st.markdown("<p style='font-weight:600; font-size:0.9rem; color:#475569;'>General</p>", unsafe_allow_html=True)
    
    general = []
    if props.get("gsd"):
        general.append(("GSD", f"{props['gsd']} m"))
    if props.get("datetime"):
        general.append(("Time of Data", props["datetime"].replace("T", " ").replace("Z", " UTC")))
    if props.get("platform"):
        general.append(("Platform", props["platform"]))
    if props.get("proj:epsg"):
        general.append(("EPSG", str(props["proj:epsg"])))

    if general:
        rows = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in general)
        st.markdown(f'<table class="stac-table">{rows}</table>', unsafe_allow_html=True)

    # Bands
    if eo_bands:
        st.markdown("<p style='font-weight:600; font-size:0.9rem; color:#475569; margin-top:1rem;'>Bands</p>", unsafe_allow_html=True)
        header = "<tr><td style='font-weight:700;'>Name</td><td style='font-weight:700;'>Common Name</td></tr>"
        rows = "".join(
            f"<tr><td>{b.get('name','—')}</td><td>{b.get('common_name','—')}</td></tr>"
            for b in eo_bands
        )
        st.markdown(f'<table class="stac-table">{header}{rows}</table>', unsafe_allow_html=True)

    # Projection
    if props.get("proj:epsg"):
        st.markdown("<p style='font-weight:600; font-size:0.9rem; color:#475569; margin-top:1rem;'>Projection</p>", unsafe_allow_html=True)
        st.markdown(f"""
<table class="stac-table">
  <tr><td>Code</td><td><a href="https://epsg.io/{props['proj:epsg']}" target="_blank" style="color:#2563eb;">EPSG:{props['proj:epsg']}</a></td></tr>
</table>""", unsafe_allow_html=True)

    # Delete
    st.markdown('<p style="font-weight:700; font-size:0.9rem; color:#0f172a; margin-top:1.5rem; margin-bottom:0.5rem;">🛠️ Actions</p>', unsafe_allow_html=True)
    return props  # return so caller can use for delete logic


def _asset_list(item):
    """Render a compact asset list matching STAC Browser."""
    assets = item.get("assets", {})
    st.markdown('<p style="font-weight:700; font-size:1rem; color:#0f172a; margin-top:1.5rem; margin-bottom:0.5rem;">🔗 Assets</p>', unsafe_allow_html=True)
    for key, val in assets.items():
        roles = val.get("roles", [])
        title = val.get("title") or key.capitalize()
        href = val.get("href", "#")
        badges = " ".join(
            f'<span style="background:#334155; color:#fff; border-radius:4px; padding:1px 7px; font-size:0.7rem; font-weight:600;">{r.upper()}</span>'
            for r in roles
        )
        with st.expander(f"**{title}**"):
            st.markdown(f"{badges}", unsafe_allow_html=True)
            st.markdown(f'<a href="{href}" target="_blank" style="font-size:0.8rem; color:#2563eb;">Open Asset URL ↗</a>', unsafe_allow_html=True)


def render_items_tab() -> None:
    hdr_col, btn_col = st.columns([6, 1])
    with hdr_col:
        st.markdown('<p class="section-title">📋 Browse Items by Collection</p>', unsafe_allow_html=True)
    with btn_col:
        if st.button("🔄 Refresh", key="refresh_items"):
            st.rerun()

    item_col_ids = fetch_collection_ids()
    if not item_col_ids:
        st.info("No collections found. Create one in the **Collections** tab first.")
        return

    sel_col = st.selectbox("Select collection", item_col_ids, key="items_col_sel")
    items = fetch_items(sel_col)

    if not items:
        st.info(f"No items found in **{sel_col}**.")
        return

    st.caption(f"**{len(items)}** item(s) in `{sel_col}`")

    for item in items:
        iid = item.get("id", "—")
        idt = item.get("properties", {}).get("datetime", "—")

        with st.expander(f"**{iid}**  ·  {idt}", expanded=False):
            # ── STAC Browser–style split layout ──────────────────────────────
            left, right = st.columns([5, 4], gap="large")

            with left:
                # Map
                try:
                    m, bbox = _build_item_map(item)
                    lat_c = (bbox[1] + bbox[3]) / 2
                    lng_c = (bbox[0] + bbox[2]) / 2
                    # Pass center + zoom directly — this overrides fit_bounds
                    # which is unreliable inside Streamlit expanders
                    st_folium(
                        m,
                        center=[lat_c, lng_c],
                        zoom=13,
                        width="100%",
                        height=380,
                        returned_objects=[],
                        key=f"map_{iid}"
                    )
                except Exception as e:
                    st.error(f"Map error: {e}")

                # Assets below the map
                _asset_list(item)

            with right:
                # Metadata panel
                _metadata_section(item, sel_col)

                # Delete button
                if st.button("🗑️ Delete Item", key=f"del_{iid}", use_container_width=True):
                    st.session_state[f"confirm_del_{iid}"] = True

                if st.session_state.get(f"confirm_del_{iid}"):
                    st.warning(f"⚠️ Permanently delete **{iid}**?")
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("✅ Yes", key=f"yes_del_{iid}", type="primary"):
                            ok, err = api_delete_item(sel_col, iid)
                            if ok:
                                st.success("Deleted.")
                                st.rerun()
                            else:
                                st.error(err)
                    with c2:
                        if st.button("❌ Cancel", key=f"no_del_{iid}"):
                            del st.session_state[f"confirm_del_{iid}"]
                            st.rerun()

                # Raw JSON
                with st.expander("📄 Raw JSON"):
                    st.json(item)
