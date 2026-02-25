"""frontend/tab_items.py — Items browser tab."""

import streamlit as st

from backend.stac_api import fetch_collection_ids, fetch_items, api_delete_item
from logger import get_logger

log = get_logger("tab_items")


def render_items_tab() -> None:
    hdr_col, btn_col = st.columns([6, 1])
    with hdr_col:
        st.markdown('<p class="section-title">📋 Browse Items by Collection</p>',
                    unsafe_allow_html=True)
    with btn_col:
        if st.button("🔄 Refresh", key="refresh_items"):
            st.rerun()

    item_col_ids = fetch_collection_ids()
    if not item_col_ids:
        st.info("No collections found. Create one in the **Collections** tab first.")
        return

    sel_col = st.selectbox("Select collection", item_col_ids, key="items_col_sel")
    items   = fetch_items(sel_col)

    if not items:
        st.info(f"No items found in **{sel_col}**.")
        return

    st.caption(f"**{len(items)}** item(s) in `{sel_col}`")
    st.divider()

    for item in items:
        iid     = item.get("id", "—")
        idt     = item.get("properties", {}).get("datetime", "—")
        bbox    = item.get("bbox", [])
        bbox_str = (
            f"{bbox[0]:.4f}, {bbox[1]:.4f} → {bbox[2]:.4f}, {bbox[3]:.4f}"
            if bbox else "—"
        )

        with st.expander(f"**{iid}**  ·  {idt}  ·  {bbox_str}", expanded=False):
            top_left, top_right = st.columns([5, 1])
            with top_right:
                if st.button("🗑️", key=f"del_item_{iid}", help="Delete this item"):
                    st.session_state[f"confirm_del_item_{iid}"] = True

            if st.session_state.get(f"confirm_del_item_{iid}"):
                st.warning(f"⚠️ Permanently delete item **{iid}**?")
                dc1, dc2, _ = st.columns([1, 1, 3])
                with dc1:
                    if st.button("✅ Yes, delete",
                                 key=f"del_item_yes_{iid}", type="primary"):
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

            # Quick metadata summary
            props = item.get("properties", {})
            meta_cols = st.columns(3)
            if props.get("gsd"):
                meta_cols[0].metric("GSD", f"{props['gsd']} m")
            if props.get("proj:epsg"):
                meta_cols[1].metric("EPSG", props["proj:epsg"])
            n_assets = len(item.get("assets", {}))
            meta_cols[2].metric("Assets", n_assets)

            st.markdown("**Full STAC Item JSON:**")
            st.json(item)
