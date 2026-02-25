"""frontend/tab_collections.py — Collections CRUD tab."""

import streamlit as st

from backend.stac_api import (
    fetch_collections, build_collection_payload,
    api_create_collection, api_update_collection, api_delete_collection,
)
from logger import get_logger

log = get_logger("tab_collections")


def render_collections_tab() -> None:

    # ── Existing collections ─────────────────────────────────────────────────
    hdr_col, btn_col = st.columns([6, 1])
    with hdr_col:
        st.markdown('<p class="section-title">📋 Existing Collections</p>',
                    unsafe_allow_html=True)
    with btn_col:
        if st.button("🔄 Refresh", key="refresh_cols"):
            st.rerun()

    all_cols = fetch_collections()

    if not all_cols:
        st.info("No collections found in the STAC API.")
    else:
        st.caption(f"{len(all_cols)} collection(s) found")
        for col in all_cols:
            cid    = col.get("id", "—")
            ctitle = col.get("title", "—")
            cdesc  = col.get("description", "")

            with st.expander(f"**{cid}** — {ctitle}", expanded=False):
                info_col, del_col = st.columns([5, 1])
                with info_col:
                    if cdesc:
                        st.caption(f"📝 {cdesc}")
                with del_col:
                    if st.button("🗑️", key=f"del_col_{cid}", help="Delete this collection"):
                        st.session_state[f"confirm_del_col_{cid}"] = True

                if st.session_state.get(f"confirm_del_col_{cid}"):
                    st.warning(
                        f"⚠️ Delete **{cid}**? This also removes **all its items**."
                    )
                    cc1, cc2, _ = st.columns([1, 1, 3])
                    with cc1:
                        if st.button("✅ Yes, delete", key=f"confirm_yes_{cid}", type="primary"):
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

    # ── Create Collection ────────────────────────────────────────────────────
    st.markdown('<p class="section-title">➕ Create New Collection</p>',
                unsafe_allow_html=True)

    with st.form("create_col_form", clear_on_submit=False):
        cc1, cc2 = st.columns(2)
        with cc1:
            new_id    = st.text_input("Collection ID *",
                                      placeholder="e.g. my_satellite_collection")
            new_title = st.text_input("Title",
                                      placeholder="e.g. My Satellite Collection")
        with cc2:
            new_desc = st.text_area("Description",
                                    placeholder="Short description…",
                                    height=100)
            new_lic  = st.selectbox("License",
                                    ["proprietary", "various",
                                     "CC-BY-4.0", "ODbL-1.0", "other"])

        col_prev, col_create = st.columns(2)
        with col_prev:
            preview_btn = st.form_submit_button("👁️ Preview JSON")
        with col_create:
            create_btn  = st.form_submit_button("✅ Create Collection", type="primary")

    if (preview_btn or create_btn):
        if not new_id:
            st.warning("Collection ID is required.")
        else:
            payload = build_collection_payload(new_id, new_title, new_desc, new_lic)
            st.markdown("**📄 JSON to be submitted:**")
            st.json(payload)
            if create_btn:
                ok, err = api_create_collection(payload)
                if ok:
                    st.success(f"✅ Collection **{new_id}** created!")
                    st.rerun()
                else:
                    st.error(f"❌ {err}")

    st.divider()

    # ── Update Collection ────────────────────────────────────────────────────
    st.markdown('<p class="section-title">✏️ Update Existing Collection</p>',
                unsafe_allow_html=True)

    col_ids = [c.get("id") for c in all_cols if "id" in c]
    if not col_ids:
        st.info("No collections available to update.")
        return

    upd_col_id = st.selectbox("Select collection to update",
                               col_ids, key="upd_col_select")
    existing   = next((c for c in all_cols if c.get("id") == upd_col_id), {})

    _LICENCES = ["proprietary", "various", "CC-BY-4.0", "ODbL-1.0", "other"]

    with st.form("update_col_form", clear_on_submit=False):
        uc1, uc2 = st.columns(2)
        with uc1:
            upd_title = st.text_input("Title",
                                      value=existing.get("title", ""),
                                      key="upd_title")
            cur_lic = existing.get("license", "proprietary")
            lic_idx = _LICENCES.index(cur_lic) if cur_lic in _LICENCES else 0
            upd_lic = st.selectbox("License", _LICENCES,
                                   index=lic_idx, key="upd_lic")
        with uc2:
            upd_desc = st.text_area("Description",
                                    value=existing.get("description", ""),
                                    height=100, key="upd_desc")

        upd_prev, upd_save = st.columns(2)
        with upd_prev:
            upd_preview_btn = st.form_submit_button("👁️ Preview Updated JSON")
        with upd_save:
            upd_save_btn = st.form_submit_button("💾 Save Changes", type="primary")

    if upd_preview_btn or upd_save_btn:
        upd_payload = {**existing,
                       "title": upd_title,
                       "description": upd_desc,
                       "license": upd_lic}
        st.markdown("**📄 JSON to be submitted:**")
        st.json(upd_payload)
        if upd_save_btn:
            ok, err = api_update_collection(upd_col_id, upd_payload)
            if ok:
                st.success(f"✅ Collection **{upd_col_id}** updated!")
                st.rerun()
            else:
                st.error(f"❌ {err}")
