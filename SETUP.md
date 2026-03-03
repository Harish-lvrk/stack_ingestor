# 📡 STAC Ingestor — Complete Setup Guide

> Follow this guide on a **fresh device** to get everything running from scratch.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                         Your Machine                         │
│                                                              │
│  ┌──────────────────┐     ┌───────────────────────────────┐  │
│  │  STAC Ingestor   │     │  Supporting Services          │  │
│  │  (Streamlit)     │     │                               │  │
│  │  Port: 8502      │────▶│  STAC API    → port 8082      │  │
│  │                  │     │  TiTiler     → port 8008      │  │
│  │                  │     │  File Server → port 8085      │  │
│  └──────────────────┘     └───────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

---

## Step 1 — System Requirements

```bash
# Python 3.10+
python3 --version

# GDAL (required by rasterio)
sudo apt update
sudo apt install -y gdal-bin libgdal-dev python3-dev python3-venv git

# Node.js (for file server)
sudo apt install -y nodejs npm

# Docker + Docker Compose (for STAC API)
sudo apt install -y docker.io docker-compose-plugin
sudo usermod -aG docker $USER   # then log out and back in
```

---

## Step 2 — Clone the Repository

```bash
git clone git@github.com:Harish-lvrk/stack_ingestor.git
cd stack_ingestor
```

---

## Step 3 — Python Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

## Step 4 — Configure LAN IP

Edit **`config.py`** in the project root with **your machine's LAN IP**.

```bash
# Find your LAN IP
hostname -I | awk '{print $1}'
```

Then update `config.py`:

```python
LAN_IP = "YOUR_LAN_IP_HERE"    # e.g. "192.168.1.50"  ← change this

FILE_SERVER_URL   = f"http://{LAN_IP}:8085"
TITILER_URL       = f"http://{LAN_IP}:8008"
STAC_API_URL      = f"http://{LAN_IP}:8082"
STAC_API_INTERNAL = "http://localhost:8082"
COG_SAVE_DIR      = Path.home() / "Documents" / "serverimages"
```

---

## Step 5 — Start Supporting Services

> Open a **separate terminal** for each service and keep them running.

### 5a — STAC API (Docker Compose) — Port 8082

```bash
# Clone the stac-fastapi-pgstac repo once
git clone https://github.com/stac-utils/stac-fastapi-pgstac.git
cd stac-fastapi-pgstac

# Start only the database and app services
docker compose up database app
```

Verify: `curl http://localhost:8082/`

### 5b — TiTiler — Port 8008

```bash
# Install TiTiler (once, inside the venv or globally)
pip install uvicorn titiler.application

# Run TiTiler
uvicorn titiler.application.main:app --host 0.0.0.0 --port 8008 --reload
```

Verify: `curl http://localhost:8008/`

### 5c — File Server — Port 8085

Serves images, GeoJSON, and previews over HTTP. Must be run from `~` (home directory).

```bash
# Install http-server globally (once)
npm install -g http-server

# Run from your home directory
cd ~
http-server . -p 8085 --cors
```

Verify: `curl http://localhost:8085/`

---

## Step 6 — Create Storage Directory

```bash
mkdir -p ~/Documents/serverimages/mining
```

---

## Step 7 — Run STAC Ingestor

```bash
cd ~/stack_ingestor
source venv/bin/activate
streamlit run app.py --server.address 0.0.0.0 --server.port 8502
```

Open: `http://<YOUR_LAN_IP>:8502`

---

## Quick Reference — All Commands

| Service       | Command                                                                    | Port |
| ------------- | -------------------------------------------------------------------------- | ---- |
| STAC API      | `docker compose up database app` (in `stac-fastapi-pgstac/`)               | 8082 |
| TiTiler       | `uvicorn titiler.application.main:app --host 0.0.0.0 --port 8008 --reload` | 8008 |
| File Server   | `http-server . -p 8085 --cors` (run from `~`)                              | 8085 |
| STAC Ingestor | `streamlit run app.py --server.address 0.0.0.0 --server.port 8502`         | 8502 |

---

## Streamlit Config

`.streamlit/config.toml` is already committed — no changes needed:

```toml
[server]
maxUploadSize = 4096   # supports up to 4 GB uploads
address = "0.0.0.0"
port = 8502
```

---

## Directory Structure

```
stack_ingestor/
├── app.py                ← Streamlit entry point
├── config.py             ← ⚠️ Edit LAN_IP here first!
├── requirements.txt
├── .streamlit/
│   └── config.toml       ← Upload size + theme
├── backend/
│   ├── stac_api.py       ← STAC API helpers (fetch/push/update/delete)
│   └── stac_builder.py   ← STAC item payload builder
├── frontend/
│   ├── tab_mining.py     ← Mining Manager tab
│   ├── tab_ingest.py     ← General ingestion tab
│   └── styles.py         ← CSS/theme helpers
└── logs/
```

---

## Troubleshooting

| Problem                         | Fix                                                        |
| ------------------------------- | ---------------------------------------------------------- |
| `ModuleNotFoundError: rasterio` | `pip install -r requirements.txt` inside venv              |
| Preview images not loading      | TiTiler not running — check port 8008                      |
| Asset links broken              | File server not running — check port 8085                  |
| STAC push fails                 | STAC API not running — check port 8082                     |
| `LAN_IP` still `10.50.0.170`    | Edit `config.py` with `hostname -I \| awk '{print $1}'`    |
| Upload size limit error         | `maxUploadSize = 4096` already in `.streamlit/config.toml` |
