

## Infrastructure (already running locally)

| Service     | URL                     | Role                                               |
| ----------- | ----------------------- | -------------------------------------------------- |
| STAC API    | `http://localhost:8082` | Stores & serves metadata JSON                      |
| File server | `http://127.0.0.1:8085` | Serves raw `.tif` files — runs from `~` (home dir) |
| Titiler     | `http://localhost:8008` | Renders COG images into map tiles                  |

**File server root = `~` (home directory)**
So `~/Documents/serverimages/file.tif` → `http://127.0.0.1:8085/Documents/serverimages/file.tif`

**COG storage folder = `~/Documents/serverimages/`**
All converted COG files must be saved here so the file server can serve them.

---

## App Workflow (5 Steps)

### Step 1 — Upload

User uploads a `.tif` satellite image via `st.file_uploader`.

### Step 2 — Fill in Item Details

Show a form with:

- **Collection name** (text input, required)
- **Item ID** (auto-filled from filename, editable)
- **Capture datetime** (text input, optional — default to now)
- **COG output filename** (auto-filled as `<stem>_cog.tif`, editable)

### Step 3 — Convert & Generate (single button click)

On button click, the app must:

1. **Convert to COG** using `gdal_translate`:

   ```bash
   gdal_translate -of COG -co COMPRESS=LZW -co OVERVIEWS=AUTO input.tif ~/Documents/serverimages/output_cog.tif
   ```

2. **Build file server URL**:

   ```
   http://127.0.0.1:8085/Documents/serverimages/<cog_filename>
   ```

3. **Read metadata from COG** using `rasterio`:
   - `bbox` → transform bounds to WGS84
   - `geometry` → actual footprint polygon in WGS84
   - `proj:epsg` → CRS EPSG code
   - `band_count` → number of bands
   - `gsd` → pixel size in metres

4. **Fetch band statistics from Titiler**:

   ```
   GET http://localhost:8008/cog/statistics?url=<file_url>
   ```

   Use `percentile_2` (min) and `percentile_98` (max) across all RGB bands for rescale.

5. **Determine band indices**:
   - 3-band image → `bidx=1&bidx=2&bidx=3` (R, G, B)
   - 4-band image → `bidx=3&bidx=2&bidx=1` (R, G, B from analytic)

6. **Build STAC item JSON** (see format below)

### Step 4 — Review JSON

Display the generated JSON with `st.json()`.
Provide a `st.download_button` to download it as a `.json` file.

### Step 5 — Push to STAC API

Show the target POST URL, then a **"🚀 Push to STAC API"** button.
On click:

```
POST http://localhost:8082/collections/{collection}/items
Content-Type: application/json
Body: <generated JSON>
```

Show `st.success` + `st.balloons()` on success.
Handle 409 (already exists) with a clear warning.

---

## Valid STAC Item JSON Format

The app must generate JSON that exactly matches this structure:

```json
{
  "id": "sn28-20250511-zone42n-visual",
  "bbox": [68.0071, 25.2048, 68.0471, 25.2412],
  "type": "Feature",
  "links": [
    {
      "rel": "collection",
      "type": "application/json",
      "href": "http://localhost:8082/collections/zone42n_visual_collection"
    },
    {
      "rel": "parent",
      "type": "application/json",
      "href": "http://localhost:8082/collections/zone42n_visual_collection"
    },
    {
      "rel": "root",
      "type": "application/json",
      "href": "http://localhost:8082/"
    },
    {
      "rel": "self",
      "type": "application/geo+json",
      "href": "http://localhost:8082/collections/zone42n_visual_collection/items/sn28-20250511-zone42n-visual"
    }
  ],
  "assets": {
    "tiles": {
      "href": "http://localhost:8008/cog/tilejson.json?url=http://127.0.0.1:8085/Documents/serverimages/file.tif&bidx=1&bidx=2&bidx=3&rescale=114,230",
      "type": "application/json",
      "roles": ["tiles"],
      "title": "TiTiler RGB Tile Service"
    },
    "preview": {
      "href": "http://localhost:8008/cog/preview.png?url=http://127.0.0.1:8085/Documents/serverimages/file.tif&bidx=1&bidx=2&bidx=3&rescale=114,230",
      "type": "image/png",
      "roles": ["overview"],
      "title": "RGB Preview Image"
    },
    "visual": {
      "href": "http://127.0.0.1:8085/Documents/serverimages/file.tif",
      "type": "image/tiff; application=geotiff; profile=cloud-optimized",
      "roles": ["data", "visual"],
      "title": "COG Image"
    }
  },
  "geometry": {
    "type": "Polygon",
    "coordinates": [
      [
        [68.0071, 25.2048],
        [68.0471, 25.2048],
        [68.0471, 25.2412],
        [68.0071, 25.2412],
        [68.0071, 25.2048]
      ]
    ]
  },
  "collection": "zone42n_visual_collection",
  "properties": {
    "gsd": 0.7,
    "title": "SuperDove SN28 - 2025-05-11 Visual Capture",
    "datetime": "2025-05-11T09:44:26Z",
    "eo:bands": [
      { "name": "Red", "common_name": "red" },
      { "name": "Green", "common_name": "green" },
      { "name": "Blue", "common_name": "blue" }
    ],
    "platform": "SuperDove-SN28",
    "proj:epsg": 32642,
    "instruments": ["PSB.SD"]
  },
  "stac_version": "1.0.0",
  "stac_extensions": [
    "https://stac-extensions.github.io/eo/v1.1.0/schema.json",
    "https://stac-extensions.github.io/projection/v1.1.0/schema.json"
  ]
}
```

---

## Key Rules

- **`tiles` asset** → must use `/cog/tilejson.json` endpoint (NOT `{z}/{x}/{y}` template)
- **`rescale`** → must come from Titiler percentile_2/percentile_98, never hardcoded
- **COG storage** → always `~/Documents/serverimages/` so file server can reach it
- **Service status bar** → show at top of app whether each service is reachable (green ✅ / red ❌)
- **UI** → modern, premium look using Streamlit

---

## Files to Create

```
stac-ingestor/
├── app.py              ← Main Streamlit app
├── requirements.txt    ← streamlit, rasterio, requests
└── README.md           ← How to run
```
