# 🛰️ STAC Item Ingestor

A Streamlit app that automates the full workflow:
**Upload GeoTIFF → Convert to COG → Generate STAC JSON → Push to STAC API**

---

## Prerequisites

Make sure these 3 services are running before launching the app:

| Service             | How to start                                                                               |
| ------------------- | ------------------------------------------------------------------------------------------ |
| STAC API `:8082`    | `docker compose up database app` (in `stac-fastapi-pgstac/`)                               |
| File server `:8085` | `cd ~ && http-server . -p 8085 --cors`                                                     |
| Titiler `:8008`     | `/home/hareesh/.local/bin/uvicorn titiler.application.main:app --host 0.0.0.0 --port 8008` |

---

## Install & Run

```bash
cd stac-ingestor

# Install dependencies (once)
pip install -r requirements.txt

# Run the app
streamlit run app.py
```

Then open **http://localhost:8501** in your browser.

---

## App Workflow

1. **Upload** your `.tif` file
2. **Fill in** Collection name, Item ID, and Capture datetime
3. Click **Convert → Generate** — the app will:
   - Convert your image to COG (saved to `~/Documents/serverimages/`)
   - Read bbox, geometry, band info, GSD from the file
   - Fetch real band statistics from Titiler (for accurate rescale)
   - Build the complete STAC item JSON
4. **Review** the generated JSON on screen
5. Click **Push to STAC API** — done! ✅

---

## Notes

- COGs are saved to `~/Documents/serverimages/` by default
- The file server **must be running from `~`** (home dir) for URLs to resolve correctly
- If the item already exists in the collection, delete it first with:
  ```bash
  curl -X DELETE http://localhost:8082/collections/<collection>/items/<item-id>
  ```
