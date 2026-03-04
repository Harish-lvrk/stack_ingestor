"""frontend/mining/section_browse.py — Browse Items section."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from backend.stac_api import (
    api_delete_item,
    api_update_item,
    fetch_item,
    fetch_items,
    local_to_url,
)
from config import COG_SAVE_DIR, STAC_API_URL, TITILER_URL, TILE_MATRIX_SET
from logger import get_logger

from .constants import GEOJSON_ASSETS, MINING_ROOT, ANALYTICS_FILE, STATUS_COLORS
from .utils import (
    _badge,
    _compute_rescale_local,
    _geojson_area_km2,
    _item_folder,
    _mining_collection_ids,
    _mining_collections,
    _section_header,
)

log = get_logger("tab_mining")

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
            assets = item.get("assets", {})
            preview_href = assets.get("preview", {}).get("href", "")

            img_col, meta_col = st.columns([2, 3])

            with img_col:
                if preview_href:
                    try:
                        st.image(preview_href, caption=iid, width="stretch")
                    except Exception:
                        st.markdown(
                            f'<div style="background:#f1f5f9;border-radius:8px;'
                            f'height:120px;display:flex;align-items:center;'
                            f'justify-content:center;color:#94a3b8;font-size:0.8rem;">'
                            f'🖼️ Preview unavailable</div>',
                            unsafe_allow_html=True,
                        )
                else:
                    st.markdown(
                        '<div style="background:#f1f5f9;border-radius:8px;'
                        'height:120px;display:flex;align-items:center;'
                        'justify-content:center;color:#94a3b8;font-size:0.8rem;">'
                        '📷 No preview</div>',
                        unsafe_allow_html=True,
                    )

            with meta_col:
                gsd  = props.get("gsd", "")
                epsg = props.get("proj:epsg", "")
                bands = props.get("eo:bands", [])
                band_names = " · ".join(b.get("common_name", b.get("name", "")) for b in bands) if bands else ""

                meta_html = (
                    f"<b>Location:</b> {loc}<br>"
                    f"<b>Region ID:</b> {props.get('region_id', '—')}<br>"
                    f"<b>Survey Date:</b> {dt}<br>"
                )
                if gsd:
                    meta_html += f"<b>GSD:</b> {gsd} m<br>"
                if epsg:
                    meta_html += f"<b>EPSG:</b> {epsg}<br>"
                if band_names:
                    meta_html += f"<b>Bands:</b> {band_names}<br>"
                st.markdown(meta_html, unsafe_allow_html=True)

                if assets:
                    st.markdown("**Assets:**")
                    for akey, aval in assets.items():
                        atitle = aval.get("title") or akey
                        href   = aval.get("href", "#")
                        st.markdown(f"- [{atitle}]({href})")

            st.markdown("")
            r1, r2, r3 = st.columns(3)
            with r1:
                with st.expander("📄 Raw STAC JSON"):
                    st.json(item)
            with r2:
                if st.button(f"✏️ Edit `{iid}`", key=f"mine_edit_{iid}"):
                    st.session_state[f"mine_editing_{iid}"] = not st.session_state.get(f"mine_editing_{iid}", False)
            with r3:
                if st.button(f"🗑️ Delete `{iid}`", key=f"mine_del_{iid}"):
                    st.session_state[f"mine_del_confirm_{iid}"] = True

            # ─ Edit Item form ────────────────────────────────────────────
            if st.session_state.get(f"mine_editing_{iid}"):
                st.markdown(f"**✏️ Editing item `{iid}`**")

                # Pre-fill date from existing STAC datetime
                _cur_dt_str = props.get("datetime", "")
                try:
                    _cur_date = datetime.fromisoformat(
                        _cur_dt_str.replace("Z", "+00:00")
                    ).date()
                except Exception:
                    _cur_date = datetime.now(tz=timezone.utc).date()

                _edit_date = st.date_input(
                    "🗓️ Survey Date",
                    value=_cur_date,
                    key=f"edit_date_{iid}",
                )

                # Analytics editor — pre-fill from existing analytics.json if present
                st.markdown("**Analytics Data** (leave at 0 to keep unchanged)")
                _EDIT_CLASSES = [
                    "Mining Area", "New Mine Pit Area", "Stockpile / Dumping Area",
                    "Reclamation", "Extended Land", "Temporary Water Pits",
                ]

                # Try to load existing analytics.json for pre-fill
                _analytics_folder = MINING_ROOT / picked / iid
                _existing_analytics: dict = {}
                _analytics_path = _analytics_folder / ANALYTICS_FILE
                if _analytics_path.exists():
                    try:
                        _raw = json.loads(_analytics_path.read_text())
                        for row in _raw.get("structures_made", []):
                            _existing_analytics[row["name"]] = row
                    except Exception:
                        pass

                _year_key = list((
                    _existing_analytics.get(_EDIT_CLASSES[0], {})
                    .get("area_covered_sq_km", {"2019": 0})
                ).keys())[0] if _existing_analytics else "2019"

                _edit_year = st.text_input(
                    "Year Label", value=_year_key, key=f"edit_year_{iid}"
                )

                _hdr = st.columns([3, 2, 2])
                _hdr[0].markdown("**Land Cover Class**")
                _hdr[1].markdown("**Area (km²)**")
                _hdr[2].markdown("**% Covered**")

                _edit_rows: list[dict] = []
                _edit_has_data = False
                for _cls in _EDIT_CLASSES:
                    _prev = _existing_analytics.get(_cls, {})
                    _prev_area = float(
                        list(_prev.get("area_covered_sq_km", {"_": 0}).values())[0]
                    ) if _prev else 0.0
                    _prev_pct = float(
                        list(_prev.get("percentage_covered", {"_": 0}).values())[0]
                    ) if _prev else 0.0

                    _rc = st.columns([3, 2, 2])
                    with _rc[0]:
                        st.markdown(
                            f'<div style="padding:0.4rem 0;font-size:0.85rem;">{_cls}</div>',
                            unsafe_allow_html=True,
                        )
                    with _rc[1]:
                        _area = st.number_input(
                            f"area {_cls}", value=_prev_area,
                            min_value=0.0, step=0.001, format="%.3f",
                            key=f"edit_area_{iid}_{_cls}",
                            label_visibility="collapsed",
                        )
                    with _rc[2]:
                        _pct = st.number_input(
                            f"pct {_cls}", value=_prev_pct,
                            min_value=0.0, max_value=100.0, step=0.1, format="%.1f",
                            key=f"edit_pct_{iid}_{_cls}",
                            label_visibility="collapsed",
                        )
                    _edit_rows.append({
                        "name": _cls,
                        "area_covered_sq_km": {_edit_year: _area},
                        "percentage_covered":  {_edit_year: _pct},
                    })
                    if _area > 0 or _pct > 0:
                        _edit_has_data = True

                # ─ GeoJSON layer files ────────────────────────────────────────
                st.markdown("**🗺️ Vector Change Layers** (upload to replace, skip to keep existing)")
                _edit_geojson_uploads: dict[str, object] = {}
                for _akey, (_alabel, _afilename) in GEOJSON_ASSETS.items():
                    _apath = _analytics_folder / _afilename
                    _exists = _apath.exists()
                    _col_info, _col_up = st.columns([2, 3])
                    with _col_info:
                        if _exists:
                            _sz    = _apath.stat().st_size
                            _mtime = datetime.fromtimestamp(
                                _apath.stat().st_mtime, tz=timezone.utc
                            ).strftime("%Y-%m-%d %H:%M UTC")
                            try:
                                _gj_data  = json.loads(_apath.read_bytes())
                                _n_f      = len(_gj_data.get("features", []))
                                _feat_str = f" · <b>{_n_f} features</b>"
                            except Exception:
                                _gj_data  = None
                                _feat_str = ""
                            st.markdown(
                                f'<div style="font-size:0.8rem;padding:0.2rem 0;">'
                                f'✅ <b>{_alabel}</b><br>'
                                f'<code style="font-size:0.67rem;color:#64748b;">{_apath.name}</code><br>'
                                f'<span style="color:#64748b;font-size:0.7rem;">'
                                f'{_sz/1024:.1f} KB{_feat_str}<br>'
                                f'🕒 saved {_mtime}</span>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )
                            with st.expander(f"👁️ View {_alabel} content"):
                                if _gj_data is not None:
                                    st.json(_gj_data)
                                else:
                                    st.warning("Could not parse as GeoJSON.")
                        else:
                            st.markdown(
                                f'<div style="font-size:0.8rem;padding:0.3rem 0;color:#94a3b8;">'
                                f'— <b>{_alabel}</b> — not uploaded yet</div>',
                                unsafe_allow_html=True,
                            )
                    with _col_up:
                        _uf = st.file_uploader(
                            f"Replace {_alabel}",
                            type=["geojson", "json"],
                            key=f"edit_gj_{iid}_{_akey}",
                            label_visibility="collapsed",
                        )
                        _edit_geojson_uploads[_akey] = _uf
                        if _uf is not None:
                            try:
                                _uf.seek(0)
                                _gj_staged = json.loads(_uf.read())
                                _uf.seek(0)
                                _n_feat = len(_gj_staged.get("features", []))
                                st.markdown(
                                    f'<span style="background:#dcfce7;border:1px solid #16a34a;'
                                    f'color:#15803d;font-size:0.7rem;font-weight:700;'
                                    f'padding:1px 8px;border-radius:100px;">✅ {_uf.name} · {_n_feat} features — will replace on Save</span>',
                                    unsafe_allow_html=True,
                                )
                            except Exception:
                                st.markdown(
                                    f'<span style="background:#fee2e2;border:1px solid #dc2626;'
                                    f'color:#dc2626;font-size:0.7rem;font-weight:700;'
                                    f'padding:1px 8px;border-radius:100px;">❌ Invalid GeoJSON</span>',
                                    unsafe_allow_html=True,
                                )

                _cancel_edit, _save_edit = st.columns(2)
                with _cancel_edit:
                    if st.button("❌ Cancel", key=f"edit_cancel_{iid}"):
                        del st.session_state[f"mine_editing_{iid}"]
                        st.rerun()
                with _save_edit:
                    if st.button("✅ Save Changes", key=f"edit_save_{iid}", type="primary"):
                        # 1. Fetch current item from STAC API
                        _current = fetch_item(picked, iid)
                        if _current is None:
                            st.error("❌ Could not fetch current item from STAC API.")
                        else:
                            # 2. Update datetime
                            _new_dt = datetime(
                                _edit_date.year, _edit_date.month, _edit_date.day,
                                tzinfo=timezone.utc
                            ).strftime("%Y-%m-%dT%H:%M:%SZ")
                            _current["properties"]["datetime"] = _new_dt

                            # 3. Save updated analytics.json
                            if _edit_has_data:
                                _analytics_folder.mkdir(parents=True, exist_ok=True)
                                _analytics_path.write_text(
                                    json.dumps({"structures_made": _edit_rows}, indent=2),
                                    encoding="utf-8"
                                )
                                if "analytics" not in _current.get("assets", {}):
                                    _current.setdefault("assets", {})["analytics"] = {
                                        "href":  local_to_url(_analytics_path),
                                        "type":  "application/json",
                                        "roles": ["data", "analytics"],
                                        "title": "Analytics Data",
                                    }

                            # 4. Save any uploaded GeoJSON replacements
                            _analytics_folder.mkdir(parents=True, exist_ok=True)
                            for _akey, _uf in _edit_geojson_uploads.items():
                                if _uf is not None:
                                    _uf.seek(0)
                                    _dest = _analytics_folder / GEOJSON_ASSETS[_akey][1]
                                    _dest.write_bytes(_uf.read())
                                    # Update or add asset URL in the STAC item
                                    _current.setdefault("assets", {})[_akey] = {
                                        "href":  local_to_url(_dest),
                                        "type":  "application/geo+json",
                                        "roles": ["data"],
                                        "title": GEOJSON_ASSETS[_akey][0],
                                    }

                            # 5. PUT updated item
                            ok, err = api_update_item(picked, iid, _current)
                            if ok:
                                st.success(f"✅ Item **{iid}** updated!")
                                del st.session_state[f"mine_editing_{iid}"]
                                st.rerun()
                            else:
                                st.error(f"❌ {err}")

            # ─ Delete confirmation ───────────────────────────────────────
            if st.session_state.get(f"mine_del_confirm_{iid}"):
                st.warning("Permanently delete this item?")
                y, n = st.columns(2)
                with y:
                    if st.button("✅ Yes", key=f"mine_del_yes_{iid}"):
                        ok, err = api_delete_item(picked, iid)
                        if ok:
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


