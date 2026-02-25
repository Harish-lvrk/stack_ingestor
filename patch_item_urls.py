#!/usr/bin/env python3
"""
patch_item_urls.py
──────────────────
One-shot script: fetch every item in a STAC collection, replace
localhost / 127.0.0.1 URLs with the LAN IP, and PUT them back.

Usage:
    python3 patch_item_urls.py                       # patches 'whole_world'
    python3 patch_item_urls.py my_other_collection   # any collection
"""

import json
import sys
import time
import requests

# ── Config ────────────────────────────────────────────────────────────────────
STAC_API   = "http://localhost:8082"      # internal: used for HTTP calls
LAN_IP     = "10.50.0.170"
OLD_HOSTS  = ["localhost", "127.0.0.1"]   # patterns to replace inside item JSON
COLLECTION = sys.argv[1] if len(sys.argv) > 1 else "whole_world"


def replace_hosts(text: str) -> str:
    for old in OLD_HOSTS:
        text = text.replace(f"http://{old}:", f"http://{LAN_IP}:")
    return text


def patch_item(item: dict) -> dict:
    """Deep-replace all asset hrefs and links in the item."""
    raw   = json.dumps(item)
    fixed = replace_hosts(raw)
    return json.loads(fixed)


def main():
    print(f"\n🔍  Fetching items from collection: {COLLECTION}")
    r = requests.get(
        f"{STAC_API}/collections/{COLLECTION}/items",
        params={"limit": 500},
        timeout=15,
    )
    r.raise_for_status()
    data  = r.json()
    items = data.get("features", data) if isinstance(data, dict) else data
    print(f"   Found {len(items)} item(s)")

    ok_count  = 0
    err_count = 0

    for item in items:
        item_id = item.get("id", "?")
        patched = patch_item(item)

        # Check if anything actually changed
        if patched == item:
            print(f"   ⏭  {item_id}  (no localhost URLs — skipped)")
            continue

        t0 = time.monotonic()
        resp = requests.put(
            f"{STAC_API}/collections/{COLLECTION}/items/{item_id}",
            json=patched,
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        ms = int((time.monotonic() - t0) * 1000)

        if resp.status_code in (200, 201, 204):
            print(f"   ✅  {item_id}  → HTTP {resp.status_code} ({ms}ms)")
            ok_count += 1
        else:
            print(f"   ❌  {item_id}  → HTTP {resp.status_code}: {resp.text[:200]}")
            err_count += 1

    print(f"\n{'─'*50}")
    print(f"Done.  ✅ {ok_count} patched   ❌ {err_count} errors")
    print(f"All asset/tile/preview URLs now use  http://{LAN_IP}:xxxx")


if __name__ == "__main__":
    main()
