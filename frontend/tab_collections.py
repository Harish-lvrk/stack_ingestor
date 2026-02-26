"""frontend/tab_collections.py — Interactive Collections browser."""

import requests
import streamlit as st
import folium
from streamlit_folium import st_folium

from backend.stac_api import (
    fetch_collections, fetch_items, build_collection_payload,
    api_create_collection, api_update_collection, api_delete_collection,
)
from logger import get_logger

log = get_logger("tab_collections")


def _render_collection_map(collection):
    """Render a Folium map with the collection's bounding boxes."""
    extent = collection.get("extent", {})
    spatial = extent.get("spatial", {})
    bbox_list = spatial.get("bbox", [])
    
    # Flatten if it's a list of lists [[x,y,x,y]]
    if bbox_list and isinstance(bbox_list[0], list):
        bbox = bbox_list[0]
    elif bbox_list:
        bbox = bbox_list
    else:
        bbox = [-180, -90, 180, 90]

    # Create a cleaner base map (OpenStreetMap)
    m = folium.Map(
        location=[(bbox[1] + bbox[3])/2, (bbox[0] + bbox[2])/2],
        zoom_start=2,
        tiles='OpenStreetMap',
        no_wrap=True
    )
    
    # Optional Satellite Overlay
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Satellite Imagery',
        overlay=True,
        control=True
    ).add_to(m)

    # Add Collection Extent (Blue outline)
    folium.Rectangle(
        bounds=[[bbox[1], bbox[0]], [bbox[3], bbox[2]]],
        color="#2563eb",
        weight=2,
        fill=True,
        fill_color="#2563eb",
        fill_opacity=0.05,
        popup=f"Collection Extent: {collection.get('id')}"
    ).add_to(m)

    # Fetch items to show individual footprints
    items = fetch_items(collection.get("id"), limit=100)
    for item in items:
        ibbox = item.get("bbox")
        if ibbox and len(ibbox) == 4:
            folium.Rectangle(
                bounds=[[ibbox[1], ibbox[0]], [ibbox[3], ibbox[2]]],
                color="#f97316",
                weight=1.5,
                fill=True,
                fill_opacity=0.1,
                popup=f"Item: {item.get('id')}"
            ).add_to(m)

    m.fit_bounds([[bbox[1], bbox[0]], [bbox[3], bbox[2]]])
    folium.LayerControl().add_to(m)
    return m


def render_collections_tab() -> None:
    # ── State Management ─────────────────────────────────────────────────────
    if "selected_col_id" not in st.session_state:
        st.session_state.selected_col_id = None
    if "selected_item_id" not in st.session_state:
        st.session_state.selected_item_id = None

    all_cols = fetch_collections()
    
    # ── View Switcher ────────────────────────────────────────────────────────
    if st.session_state.selected_col_id and st.session_state.selected_item_id:
        render_item_detail_view(
            st.session_state.selected_col_id,
            st.session_state.selected_item_id,
            all_cols
        )
    elif st.session_state.selected_col_id:
        render_detail_view(st.session_state.selected_col_id, all_cols)
    else:
        render_grid_view(all_cols)


def render_grid_view(all_cols) -> None:
    hdr_col, btn_col = st.columns([6, 1])
    with hdr_col:
        st.markdown('<p class="section-title">📦 Data Collections</p>', unsafe_allow_html=True)
    with btn_col:
        if st.button("🔄 Refresh", key="refresh_grid"):
            st.rerun()

    search = st.text_input("🔍 Search collections...", placeholder="Filter by ID or title")
    filtered = all_cols
    if search:
        filtered = [c for c in all_cols if search.lower() in c.get("id","").lower() or search.lower() in c.get("title","").lower()]

    if not filtered:
        st.info("No collections found.")
    else:
        st.container() # Wrapper
        cols = st.columns(3)
        for idx, col in enumerate(filtered):
            cid = col.get("id")
            title = col.get("title") or cid
            desc = col.get("description") or "No description available."
            
            with cols[idx % 3]:
                st.markdown(f"""
                <div class="stcard">
                    <h3 style="margin-top:0; color:#4f46e5; font-size:1.1rem;">{title}</h3>
                    <p style="font-size:0.85rem; color:#64748b; height:60px; overflow:hidden;">{desc}</p>
                </div>
                """, unsafe_allow_html=True)
                if st.button(f"View {cid} →", key=f"view_btn_{cid}", use_container_width=True):
                    st.session_state.selected_col_id = cid
                    st.rerun()

    st.divider()
    with st.expander("➕ Create New Collection"):
        _render_create_form()


def render_detail_view(col_id, all_cols) -> None:
    collection = next((c for c in all_cols if c.get("id") == col_id), None)
    if not collection:
        st.session_state.selected_col_id = None
        st.rerun()

    # Breadcrumb-ish
    if st.button("← Back to Collections", key="back_to_grid"):
        st.session_state.selected_col_id = None
        st.rerun()

    st.markdown(f"""
    <div style="margin-bottom: 2rem;">
        <h1 style="font-size:1.8rem; margin-bottom:0.2rem;">{collection.get('title') or col_id}</h1>
        <code style="background:#f1f5f9; padding:2px 8px; border-radius:4px;">ID: {col_id}</code>
    </div>
    """, unsafe_allow_html=True)

    left_col, right_col = st.columns([6, 4])

    with left_col:
        st.markdown('<p style="font-weight:600; margin-bottom:0.8rem;">🌍 Collection Extent & Footprints</p>', unsafe_allow_html=True)
        try:
            m = _render_collection_map(collection)
            st_folium(m, width="100%", height=450, key=f"map_{col_id}")
        except Exception as e:
            st.error(f"Map rendering error: {e}")

    with right_col:
        st.markdown('<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem;"><p style="font-weight:600; margin:0;">📦 Items</p></div>', unsafe_allow_html=True)
        items = fetch_items(col_id, limit=20)
        
        if not items:
            st.info("No items in this collection yet.")
        else:
            i_cols = st.columns(2)
            for idx, item in enumerate(items):
                iid = item.get("id")
                preview_url = item.get("assets", {}).get("preview", {}).get("href")
                idt = item.get("properties", {}).get("datetime", "—")
                
                with i_cols[idx % 2]:
                    # Modern Item Card
                    st.markdown(f"""
                    <div class="stcard" style="padding:0.75rem; min-height:220px; display:flex; flex-direction:column;">
                        <div class="thumbnail-container" style="margin-bottom:0.5rem;">
                            <img src="{preview_url}" onerror="this.src='https://placehold.co/150x100?text=No+Preview'">
                        </div>
                        <div style="font-weight:700; font-size:0.8rem; color:#4f46e5; line-height:1.2; word-break:break-all;">{iid}</div>
                        <div style="font-size:0.7rem; color:#94a3b8; margin-top:auto;">{idt}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button("Details", key=f"det_{iid}", use_container_width=True):
                        st.session_state.selected_item_id = iid
                        st.rerun()

    st.divider()
    with st.expander("🛠️ Collection Management (Update/Delete)"):
        _render_management_tools(collection, all_cols)


def render_item_detail_view(col_id, item_id, all_cols) -> None:
    """Full item detail view matching STAC Browser layout."""
    from frontend.tab_items import _build_item_map, _metadata_section, _asset_list
    from backend.stac_api import fetch_items, api_delete_item

    # Breadcrumb navigation
    b1, b2 = st.columns([1, 1])
    with b1:
        if st.button("← Back to Collection", key="back_to_col_from_item"):
            st.session_state.selected_item_id = None
            st.rerun()
    with b2:
        if st.button("← Back to All Collections", key="back_to_grid_from_item"):
            st.session_state.selected_item_id = None
            st.session_state.selected_col_id = None
            st.rerun()

    # Fetch the specific item
    all_items = fetch_items(col_id, limit=100)
    item = next((i for i in all_items if i.get("id") == item_id), None)
    if not item:
        st.error(f"Item `{item_id}` not found.")
        return

    iid = item.get("id", "—")
    idt = item.get("properties", {}).get("datetime", "—")

    st.markdown(f"""<h2 style="font-size:1.4rem; font-weight:800; margin-bottom:0.5rem; word-break:break-all;">{iid}</h2>""",
                unsafe_allow_html=True)

    left, right = st.columns([5, 4], gap="large")

    with left:
        try:
            m, bbox = _build_item_map(item)
            lat_c = (bbox[1] + bbox[3]) / 2
            lng_c = (bbox[0] + bbox[2]) / 2
            st_folium(
                m,
                center=[lat_c, lng_c],
                zoom=13,
                width="100%",
                height=380,
                returned_objects=[],
                key=f"col_item_map_{iid}"
            )
        except Exception as e:
            st.error(f"Map error: {e}")
        _asset_list(item)

    with right:
        _metadata_section(item, col_id)
        if st.button("🗑️ Delete Item", key=f"col_del_{iid}", use_container_width=True):
            st.session_state[f"col_confirm_del_{iid}"] = True
        if st.session_state.get(f"col_confirm_del_{iid}"):
            st.warning("Permanently delete this item?")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ Yes", key=f"col_del_yes_{iid}", type="primary"):
                    ok, err = api_delete_item(col_id, iid)
                    if ok:
                        st.session_state.selected_item_id = None
                        st.rerun()
                    else:
                        st.error(err)
            with c2:
                if st.button("❌ Cancel", key=f"col_del_no_{iid}"):
                    del st.session_state[f"col_confirm_del_{iid}"]
                    st.rerun()
        with st.expander("📄 Raw JSON"):
            st.json(item)


def _render_create_form():
    with st.form("create_col_form", clear_on_submit=False):
        cc1, cc2 = st.columns(2)
        with cc1:
            new_id = st.text_input("Collection ID *", placeholder="e.g. my_satellite_collection")
            new_title = st.text_input("Title", placeholder="e.g. My Satellite Collection")
        with cc2:
            new_desc = st.text_area("Description", placeholder="Short description…", height=100)
            new_lic = st.selectbox("License", ["proprietary", "various", "CC-BY-4.0", "ODbL-1.0", "other"])

        col_prev, col_create = st.columns(2)
        with col_prev:
            preview_btn = st.form_submit_button("👁️ Preview JSON")
        with col_create:
            create_btn = st.form_submit_button("✅ Create Collection", type="primary")

    if (preview_btn or create_btn):
        if not new_id:
            st.warning("Collection ID is required.")
        else:
            payload = build_collection_payload(new_id, new_title, new_desc, new_lic)
            if create_btn:
                ok, err = api_create_collection(payload)
                if ok:
                    st.success(f"✅ Collection **{new_id}** created!")
                    st.rerun()
                else:
                    st.error(f"❌ {err}")
            else:
                st.json(payload)


def _render_management_tools(existing, all_cols):
    col_id = existing.get("id")
    
    tab_upd, tab_del = st.tabs(["✏️ Update", "🗑️ Delete"])
    
    with tab_upd:
        _LICENCES = ["proprietary", "various", "CC-BY-4.0", "ODbL-1.0", "other"]
        with st.form("update_col_form"):
            uc1, uc2 = st.columns(2)
            with uc1:
                upd_title = st.text_input("Title", value=existing.get("title", ""))
                cur_lic = existing.get("license", "proprietary")
                lic_idx = _LICENCES.index(cur_lic) if cur_lic in _LICENCES else 0
                upd_lic = st.selectbox("License", _LICENCES, index=lic_idx)
            with uc2:
                upd_desc = st.text_area("Description", value=existing.get("description", ""), height=100)

            if st.form_submit_button("💾 Save Changes", type="primary"):
                upd_payload = {**existing, "title": upd_title, "description": upd_desc, "license": upd_lic}
                ok, err = api_update_collection(col_id, upd_payload)
                if ok:
                    st.success("✅ Updated!")
                    st.rerun()
                else:
                    st.error(err)

    with tab_del:
        st.warning(f"⚠️ Permanently delete `{col_id}`?")
        if st.button("💥 Confirm Permanent Deletion", type="primary", key="del_confirm_btn"):
            ok, err = api_delete_collection(col_id)
            if ok:
                st.success("Deleted.")
                st.session_state.selected_col_id = None
                st.rerun()
            else:
                st.error(err)
