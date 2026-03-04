"""frontend/mining/section_collections.py — Mining Areas (Collections) section."""
from __future__ import annotations

import streamlit as st

from backend.stac_api import (
    api_create_collection,
    api_delete_collection,
    api_update_collection,
    build_collection_payload,
    fetch_items,
)

from .constants import GEOJSON_ASSETS, MINING_ROOT
from .utils import _section_header, _mining_collections

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
                # Read area from summaries (set on create/edit) or fall back to bbox calc
                _area_km2 = col.get("summaries", {}).get("area_km2", 0.0)
                _bbox_raw = (
                    col.get("extent", {}).get("spatial", {}).get("bbox", [[]])[0]
                )
                if not _area_km2 and isinstance(_bbox_raw, list) and len(_bbox_raw) == 4:
                    # Quick on-the-fly calc for older collections without summaries
                    try:
                        from pyproj import Geod as _GC
                        _gc = _GC(ellps="WGS84")
                        _mn, _ms, _mx, _my = map(float, _bbox_raw)
                        _ring = [[_mn,_ms],[_mx,_ms],[_mx,_my],[_mn,_my],[_mn,_ms]]
                        _ac, _ = _gc.polygon_area_perimeter(
                            [float(p[0]) for p in _ring], [float(p[1]) for p in _ring]
                        )
                        _area_km2 = round(abs(float(_ac)) / 1_000_000, 4)
                    except Exception:
                        pass
                _area_badge = (
                    f'<span style="font-size:0.72rem;color:#10b981;font-weight:700;">'
                    f'📐 {_area_km2:.2f} km²</span>'
                    if _area_km2 > 0 else ""
                )

                st.markdown(f"""
                <div class="stcard" style="min-height:120px;">
                  <div style="font-weight:800;font-size:0.95rem;
                       color:var(--accent,#4f46e5);">{title}</div>
                  <code style="font-size:0.7rem;color:var(--text-muted);">{cid}</code>
                  <p style="font-size:0.78rem;color:var(--text-muted);
                     margin:0.35rem 0 0.3rem;min-height:32px;
                     overflow:hidden;">{desc[:80] or "—"}</p>
                  <div style="font-size:0.73rem;color:var(--text-muted);display:flex;gap:0.75rem;align-items:center;">
                    📋 {len(items)} survey item{"s" if len(items) != 1 else ""}
                    {_area_badge}
                  </div>
                </div>
                """, unsafe_allow_html=True)


                bc1, bc2, bc3, bc4 = st.columns([3, 1, 1, 1])
                with bc1:
                    if st.button("Browse Items →",
                                 key=f"mine_browse_{cid}",
                                 width="stretch"):
                        st.session_state["mining_selected_col"] = cid
                        st.session_state["mining_active_tab"] = 2
                        st.rerun()
                with bc2:
                    if st.button("✏️", key=f"mine_edit_col_{cid}",
                                 help=f"Edit {cid}"):
                        st.session_state[f"mine_editing_col_{cid}"] = not st.session_state.get(f"mine_editing_col_{cid}", False)
                        st.session_state.pop(f"mine_viewjson_{cid}", None)
                with bc3:
                    if st.button("📄", key=f"mine_json_col_{cid}",
                                 help=f"View STAC JSON for {cid}"):
                        st.session_state[f"mine_viewjson_{cid}"] = not st.session_state.get(f"mine_viewjson_{cid}", False)
                        st.session_state.pop(f"mine_editing_col_{cid}", None)
                with bc4:
                    if st.button("🗑️", key=f"mine_del_col_{cid}",
                                 help=f"Delete {cid}"):
                        st.session_state[f"mine_confirm_del_col_{cid}"] = True

                # ─ View Raw STAC JSON (standalone, no edit required) ──────────
                if st.session_state.get(f"mine_viewjson_{cid}"):
                    with st.expander(f"👁️ Raw STAC JSON — {cid}", expanded=True):
                        st.json(col)

                # ─ Edit Collection form ─────────────────────────────────────
                if st.session_state.get(f"mine_editing_col_{cid}"):
                    with st.form(key=f"edit_col_form_{cid}"):
                        st.markdown(f"**✏️ Edit Mining Area: `{cid}`**")

                        # ── Collection ID (read-only) ─────────────────────────
                        st.text_input(
                            "Collection ID (cannot be changed)",
                            value=cid,
                            disabled=True,
                            help="The Collection ID is set at creation time and is permanent. "
                                 "Changing it would break all items linked to this collection.",
                            key=f"edit_col_id_ro_{cid}",
                        )

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

                        # ── Bounding Box ────────────────────────────────────────
                        st.markdown(
                            "**Spatial Bounding Box** "
                            "<span style='font-size:0.78rem;color:#64748b;'>"
                            "(any rectangle — does not need to be square)</span>",
                            unsafe_allow_html=True,
                        )
                        _cur_bbox = (
                            col.get("extent", {})
                               .get("spatial", {})
                               .get("bbox", [[77.2, 15.8, 81.3, 19.9]])[0]
                        )
                        # Defaults if bbox is missing or malformed
                        _def = _cur_bbox if (isinstance(_cur_bbox, list) and len(_cur_bbox) == 4) \
                               else [77.2, 15.8, 81.3, 19.9]

                        _b1, _b2 = st.columns(2)
                        _b3, _b4 = st.columns(2)
                        with _b1:
                            new_min_lon = st.number_input(
                                "Min Longitude (West)", value=float(_def[0]),
                                min_value=-180.0, max_value=180.0, step=0.01, format="%.4f",
                                key=f"edit_col_min_lon_{cid}"
                            )
                        with _b2:
                            new_min_lat = st.number_input(
                                "Min Latitude (South)", value=float(_def[1]),
                                min_value=-90.0, max_value=90.0, step=0.01, format="%.4f",
                                key=f"edit_col_min_lat_{cid}"
                            )
                        with _b3:
                            new_max_lon = st.number_input(
                                "Max Longitude (East)", value=float(_def[2]),
                                min_value=-180.0, max_value=180.0, step=0.01, format="%.4f",
                                key=f"edit_col_max_lon_{cid}"
                            )
                        with _b4:
                            new_max_lat = st.number_input(
                                "Max Latitude (North)", value=float(_def[3]),
                                min_value=-90.0, max_value=90.0, step=0.01, format="%.4f",
                                key=f"edit_col_max_lat_{cid}"
                            )

                        cancel_col, save_col = st.columns(2)
                        with cancel_col:
                            cancelled = st.form_submit_button("❌ Cancel")
                        with save_col:
                            saved = st.form_submit_button("✅ Save Changes", type="primary")

                    # ── View raw STAC JSON (outside form so it stays expanded) ─
                    with st.expander(f"👁️ View Raw STAC JSON — {cid}"):
                        st.json(col)


                    if cancelled:
                        del st.session_state[f"mine_editing_col_{cid}"]
                        st.rerun()
                    if saved:
                        # Preserve original created timestamp
                        orig_created = col.get("created")
                        new_bbox     = [new_min_lon, new_min_lat, new_max_lon, new_max_lat]
                        payload = build_collection_payload(
                            cid, new_title, new_desc, new_lic,
                            created=orig_created,
                            bbox=new_bbox,
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

        # ─ Bounding Box ──────────────────────────────────────────────────────────
        st.markdown(
            '<p style="font-size:0.82rem;color:var(--text-muted,#64748b);margin:0.4rem 0 0.2rem;">'
            '🗺️ <b>Spatial Bounding Box</b> — drag the corner values to cover your mining region.'
            ' Defaults to Telangana.</p>',
            unsafe_allow_html=True,
        )
        _TGNA = [77.2, 15.8, 81.3, 19.9]   # Telangana: min_lon, min_lat, max_lon, max_lat
        bb1, bb2, bb3, bb4 = st.columns(4)
        with bb1:
            bb_min_lon = st.number_input(
                "Min Lon (W)", value=_TGNA[0], min_value=-180.0, max_value=180.0,
                step=0.01, format="%.4f", key="cc_bb_min_lon")
        with bb2:
            bb_min_lat = st.number_input(
                "Min Lat (S)", value=_TGNA[1], min_value=-90.0, max_value=90.0,
                step=0.01, format="%.4f", key="cc_bb_min_lat")
        with bb3:
            bb_max_lon = st.number_input(
                "Max Lon (E)", value=_TGNA[2], min_value=-180.0, max_value=180.0,
                step=0.01, format="%.4f", key="cc_bb_max_lon")
        with bb4:
            bb_max_lat = st.number_input(
                "Max Lat (N)", value=_TGNA[3], min_value=-90.0, max_value=90.0,
                step=0.01, format="%.4f", key="cc_bb_max_lat")

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
        bbox    = [bb_min_lon, bb_min_lat, bb_max_lon, bb_max_lat]
        payload = build_collection_payload(col_id, col_title, col_desc, col_lic, bbox=bbox)

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

