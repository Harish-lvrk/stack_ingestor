"""backend/stac_api.py — STAC API + file-server helpers with structured logging."""

import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from config import STAC_API_URL, STAC_API_INTERNAL, FILE_SERVER_URL, FILE_SERVER_ROOT
from logger import get_logger

log = get_logger("stac_api")


# ── Utility ───────────────────────────────────────────────────────────────────

def local_to_url(filepath: Path) -> str:
    """Convert an absolute local path to a file-server URL."""
    rel = filepath.relative_to(FILE_SERVER_ROOT)
    return f"{FILE_SERVER_URL}/{rel}"


def _get(path: str, **params) -> requests.Response:
    url = f"{STAC_API_INTERNAL}{path}"
    t0  = time.monotonic()
    r   = requests.get(url, params=params or None, timeout=10)
    ms  = int((time.monotonic() - t0) * 1000)
    log.info("GET %s → %d (%dms)", path, r.status_code, ms)
    return r


def _post(path: str, payload: dict) -> requests.Response:
    url = f"{STAC_API_INTERNAL}{path}"
    t0  = time.monotonic()
    r   = requests.post(url, json=payload,
                        headers={"Content-Type": "application/json"}, timeout=10)
    ms  = int((time.monotonic() - t0) * 1000)
    log.info("POST %s → %d (%dms)", path, r.status_code, ms)
    return r


def _put(path: str, payload: dict) -> requests.Response:
    url = f"{STAC_API_INTERNAL}{path}"
    t0  = time.monotonic()
    r   = requests.put(url, json=payload,
                       headers={"Content-Type": "application/json"}, timeout=10)
    ms  = int((time.monotonic() - t0) * 1000)
    log.info("PUT %s → %d (%dms)", path, r.status_code, ms)
    return r


def _delete(path: str) -> requests.Response:
    url = f"{STAC_API_INTERNAL}{path}"
    t0  = time.monotonic()
    r   = requests.delete(url, timeout=10)
    ms  = int((time.monotonic() - t0) * 1000)
    log.info("DELETE %s → %d (%dms)", path, r.status_code, ms)
    return r


# ── Collections ───────────────────────────────────────────────────────────────

def fetch_collections() -> list[dict]:
    """Return list of collection dicts from the STAC API."""
    try:
        r = _get("/collections")
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list):
                cols = data
            elif isinstance(data, dict):
                cols = data.get("collections", [])
            else:
                cols = []
            return [c for c in cols if isinstance(c, dict)]
    except Exception as exc:
        log.error("fetch_collections error: %s", exc)
    return []


def fetch_collection_ids() -> list[str]:
    return sorted(c["id"] for c in fetch_collections() if "id" in c)


def build_collection_payload(
    col_id: str, title: str, description: str, license_: str,
    created: str | None = None,
) -> dict:
    """Build a STAC Collection payload.

    `created` is an ISO datetime string.  If not provided, the current UTC time
    is used.  The `updated` field is always set to now.
    """
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "type":         "Collection",
        "id":           col_id,
        "stac_version": "1.0.0",
        "title":        title or col_id,
        "description":  description or col_id,
        "license":      license_,
        "created":      created or now,
        "updated":      now,
        "links":        [],
        "extent": {
            "spatial":  {"bbox": [[-180.0, -90.0, 180.0, 90.0]]},
            "temporal": {"interval": [[None, None]]},
        },
    }


def api_create_collection(payload: dict) -> tuple[bool, str]:
    try:
        r = _post("/collections", payload)
        if r.status_code in (200, 201):
            log.info("Collection created: %s", payload.get("id"))
            return True, ""
        if r.status_code == 409:
            return False, "409 — collection already exists."
        return False, f"HTTP {r.status_code}: {r.text[:300]}"
    except Exception as exc:
        log.error("api_create_collection error: %s", exc)
        return False, str(exc)


def api_update_collection(col_id: str, payload: dict) -> tuple[bool, str]:
    try:
        r = _put(f"/collections/{col_id}", payload)
        if r.status_code in (200, 201, 204):
            log.info("Collection updated: %s", col_id)
            return True, ""
        return False, f"HTTP {r.status_code}: {r.text[:300]}"
    except Exception as exc:
        log.error("api_update_collection error: %s", exc)
        return False, str(exc)


def api_delete_collection(col_id: str) -> tuple[bool, str]:
    try:
        r = _delete(f"/collections/{col_id}")
        if r.status_code in (200, 204):
            log.info("Collection deleted: %s", col_id)
            return True, ""
        return False, f"HTTP {r.status_code}: {r.text[:300]}"
    except Exception as exc:
        log.error("api_delete_collection error: %s", exc)
        return False, str(exc)


# ── Items ─────────────────────────────────────────────────────────────────────

def fetch_items(col_id: str, limit: int = 200) -> list[dict]:
    try:
        r = _get(f"/collections/{col_id}/items", limit=limit)
        if r.status_code == 200:
            data = r.json()
            return data.get("features", data) if isinstance(data, dict) else data
    except Exception as exc:
        log.error("fetch_items error: %s", exc)
    return []


def fetch_item(col_id: str, item_id: str) -> dict | None:
    """Fetch a single item from the STAC API. Returns None on failure."""
    try:
        r = _get(f"/collections/{col_id}/items/{item_id}")
        if r.status_code == 200:
            return r.json()
        log.warning("fetch_item %s/%s → HTTP %d", col_id, item_id, r.status_code)
    except Exception as exc:
        log.error("fetch_item error: %s", exc)
    return None


def api_push_item(col_id: str, item: dict) -> tuple[bool, str]:
    try:
        r = _post(f"/collections/{col_id}/items", item)
        if r.status_code in (200, 201):
            log.info("Item pushed: %s → %s", item.get("id"), col_id)
            return True, ""
        if r.status_code == 409:
            return False, "409 — item already exists. Use a different Item ID."
        return False, f"HTTP {r.status_code}: {r.text[:300]}"
    except Exception as exc:
        log.error("api_push_item error: %s", exc)
        return False, str(exc)


def api_update_item(col_id: str, item_id: str, item: dict) -> tuple[bool, str]:
    """Update an existing STAC item via PUT."""
    try:
        r = _put(f"/collections/{col_id}/items/{item_id}", item)
        if r.status_code in (200, 201, 204):
            log.info("Item updated: %s in %s", item_id, col_id)
            return True, ""
        return False, f"HTTP {r.status_code}: {r.text[:300]}"
    except Exception as exc:
        log.error("api_update_item error: %s", exc)
        return False, str(exc)


def api_delete_item(col_id: str, item_id: str) -> tuple[bool, str]:
    try:
        r = _delete(f"/collections/{col_id}/items/{item_id}")
        if r.status_code in (200, 204):
            log.info("Item deleted: %s from %s", item_id, col_id)
            return True, ""
        return False, f"HTTP {r.status_code}: {r.text[:300]}"
    except Exception as exc:
        log.error("api_delete_item error: %s", exc)
        return False, str(exc)
