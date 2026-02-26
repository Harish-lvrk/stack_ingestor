# 🛰️ STAC Manager

A professional, modular Streamlit application for managing SpatioTemporal Asset Catalogs (STAC). It automates the workflow of converting satellite imagery to Cloud-Optimized GeoTIFFs (COG), generating metadata-rich STAC items, and pushing them to a central API.

---

## 🏗️ System Architecture

The application is built with a clear separation between frontend UI components and backend processing logic.

### 🧩 Frontend (`frontend/`)

- **`styles.py`**: Custom CSS for a clean, professional light theme with Inter typography. Hides Streamlit's default anchor links for a premium look.
- **`status_bar.py`**: Real-time service health monitoring for STAC API, Titiler, and File Server with pulse animation icons.
- **`tab_ingest.py`**: A 5-step guided workflow for uploading GeoTIFFs, configuring metadata, and pushing to the catalog.
- **`tab_collections.py`**: Full CRUD (Create, Read, Update, Delete) management for STAC collections.
- **`tab_items.py`**: A visual browser for items within collections, supporting JSON inspection and deletion.

### ⚙️ Backend (`backend/`)

- **`cog.py`**: Handles COG conversion via `gdal_translate` and extracts spatial/band metadata using `rasterio`.
- **`titiler.py`**: Interacts with the Titiler dynamic tiler to fetch band statistics (for image normalization) and build preview/tile URLs.
- **`stac_builder.py`**: The "engine" that assembles raw metadata and service URLs into valid STAC 1.0.0 JSON objects.
- **`stac_api.py`**: Centralized logic for all STAC API interactions (POST/PUT/DELETE) and file-server path conversions.

### 📜 Core

- **`app.py`**: Lightweight entry point that wires all frontend modules into a tabbed layout.
- **`config.py`**: Centralized constants, including LAN IP (`10.50.0.170`) to ensure items are network-accessible.
- **`logger.py`**: Structured logging with colored terminal output and a rotating file log in `logs/stac_manager.log`.

---

## 🌐 Networking & Services

To allow multiple users on the same network to access the data, the system uses a fixed LAN IP and a 3-service infrastructure:

| Service          | Port   | Description                                                   |
| :--------------- | :----- | :------------------------------------------------------------ |
| **STAC Manager** | `8502` | This Streamlit app (accessible via `http://10.50.0.170:8502`) |
| **STAC API**     | `8082` | The central STAC Fastapi + PGSTAC database                    |
| **Titiler**      | `8008` | Dynamic tiler for map rendering and metadata extraction       |
| **File Server**  | `8085` | Serves the actual `.tif` files from your local drive          |

> [!IMPORTANT]
> All generated URLs (Assets, Tiles, Previews) use the LAN IP `10.50.0.170`. This ensures that items created on your machine can be visualized by anyone on the network (or in Docker containers).

---

## 🚀 Getting Started

### 1. Prerequisites

Ensure your 3 backend services are running. You can verify their status in the STAC Manager's top header.

### 2. Run the App

```bash
# Navigate to project
cd ~/Projects/stac-ingestor

# Activate environment
source venv/bin/activate

# Launch
streamlit run app.py
```

Streamlit will automatically bind to `0.0.0.0:8502` as configured in `.streamlit/config.toml`, making it available on your local network.

---

## 🛠️ Maintenance Tools

### `patch_item_urls.py`

If your LAN IP changes, or you accidentally ingested items with `localhost` URLs, you can run this patch script to update a whole collection in seconds:

```bash
python3 patch_item_urls.py <collection_id>
```

It will fetch every item, replace `localhost/127.0.0.1` with the IP in `config.py`, and update the STAC API.
