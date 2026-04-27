# ASTRA — Aerial Surveillance & Threat Recognition Assistant

> **Sovereign, explainable, adversarial-aware aerial-recognition platform — runs end-to-end on a 6 GB laptop GPU. Round 1 selected; Round 2 ships fine-grained military airframe ID, federated learning with Sybil resistance, dual-operator engagement workflow, tamper-evident audit chain, and on-phone alerts.**

Built for the **ASTRA Defence-Tech Expo 2026, BMSIT&M Bengaluru** (Apr 30).
Track: *AI & Machine Learning in Defence Technology*.

**Status: Round 2 shipped.** All 10 features verified end-to-end via
`python scripts/e2e_regression.py` — see [docs/RELEASE-R2.md](docs/RELEASE-R2.md)
for the full feature matrix and [docs/pitch-content-r2.md](docs/pitch-content-r2.md)
for the pitch deck content.

## Round 2 highlights — what's new since Round 1
- **Stage-2 cascade classifier** — fine-grained military airframe ID (20 airframes incl. F-22, Su-35, B-52, P-3C). 89.03% top-1 / 99.32% top-5 on MAR20.
- **Federated learning + FoolsGold** — in-process FedAvg orchestrator across N nodes with cosine-similarity Sybil reweighting. 2 colluding attackers → weight 0.000.
- **Adversarial A/B** — v1 vs v1-hardened model picker, FGSM with measured retention curve. Helipad scene: v1 0% → v1-hardened 80% retention at ε=0.05.
- **Operational realism** — WebSocket live push, mission diff, dual-operator engagement (2 distinct ops), Telegram phone alerts, SHA-256 hash-chained audit.
- **Out-of-distribution gatekeeper** — flag dets with low conf / bad aspect / flat region as `?` instead of false-class.

---

## What's in the box

### Detection model
- **YOLOv11-nano** fine-tuned on DOTA-v1.5 aerial imagery
- 8 defence-relevant classes: small/large vehicle, fixed/rotor aircraft, ship, storage-depot, harbor, bridge
- **mAP@0.5 = 0.515** overall, **0.915 on aircraft-fixed-wing**
- **22.3 ms/frame GPU** (RTX 4050 FP32) · **36 ms CPU** (Ryzen 7, ONNX)
- **5.5 MB model** post-ONNX export — fits on a Jetson Nano
- Trained in **1h 53m** on a 6GB consumer laptop GPU

### Pipeline
- **Live inference** (`/predict`) — upload image, 41 ms warm, canvas overlay with class-coded boxes
- **Full ingest pipeline** (`/ingest`) — save Mission, run detection, geo-reference per AOI corners, compute threat scores, create ranked alerts, write audit trail
- **URL / RTSP streaming** (`/ingest/url`) — accepts `rtsp://`, `http(s)://`, `file://` sources; captures frames via FFmpeg, runs full pipeline
- **Video tracking** via Ultralytics ByteTrack (`persist=True`) — stable `track_id` across frames with movement trails on Map
- **Grad-CAM explainability** (`/explain`) — EigenCAM heatmap on last backbone layer, box-masked for focal visualization
- **FGSM adversarial attack** (`/adversarial`) — proper gradient-based attack with measured degradation curve

### Front-end (8 pages — 2 new in R2)
| Page | Purpose |
|---|---|
| **Mission** | Upload image or video, live detection with canvas overlay, Grad-CAM click, video playback with synced tracked boxes. **R2:** airframe sub-class label (`E-8 0.90`), OOD detections render dashed-grey with `?` |
| **Map** | Leaflet map with geo-referenced detections, friendly-force markers, dashed AOI polygon, track polylines. **R2:** WebSocket LIVE indicator, pins POP in real time, popups show airframe sub-class |
| **Alerts** | Ranked threat queue with NL narratives, client-side weight-slider re-ranking. **R2:** dual-operator engage workflow (2/2 confirms badge → ENGAGED) |
| **Audit** | Append-only event log with filter + search, signed PDF export. **R2:** SHA-256 hash chain + `verify chain` button (green/red badge) |
| **Benchmark** | Real training metrics, per-class mAP bar chart, latency by target |
| **Adversarial** | FGSM attack with epsilon slider. **R2:** v1 / v1-hardened A/B model picker + retention comparison strip |
| **Federated** ⭐NEW R2 | 4-panel dashboard: global accuracy curve, per-client accuracy, FoolsGold weight bars, quarantine status |
| **Diff** ⭐NEW R2 | Side-by-side mission diff (Leaflet) — added/removed/moved tracks with arrow polylines |

### Infra
- **FastAPI** backend · **Postgres** (missions, detections, alerts, audit) · **Redis** (reserved for multi-worker)
- **React 18 + Vite + Tailwind + Leaflet + Recharts** front-end
- **Docker Compose** for infra containers; backend runs native for direct CUDA access

---

## Quick start

Prerequisites: **Windows 11**, **Python 3.13** (via `py` launcher), **Node 22+**, **Docker Desktop**, **CUDA-capable GPU** (tested on RTX 4050 6GB).

### 1. Create data directory (out of OneDrive sync path)

```bash
mkdir C:\astra-data
mkdir C:\astra-data\datasets C:\astra-data\weights C:\astra-data\runs C:\astra-data\tiles C:\astra-data\uploads
```

(Substitute `D:\astra-data` if you have a larger/separate drive — the paths are configurable via `.env`.)

### 2. Python env + deps

```bash
py -3.13 -m venv /d/astra-data/venvs/astra
. /d/astra-data/venvs/astra/Scripts/activate
pip install --upgrade pip
pip install -r backend/requirements-cuda.txt   # torch 2.6.0+cu124 (~2 GB)
pip install -r backend/requirements.txt        # ultralytics, fastapi, reportlab, grad-cam, etc.
```

Verify CUDA is visible:
```bash
python -c "import torch; print('CUDA:', torch.cuda.is_available(), '|', torch.cuda.get_device_name(0))"
# Expected: CUDA: True | NVIDIA GeForce RTX 4050 Laptop GPU
```

### 3. Frontend

```bash
cd frontend && npm install
```

### 4. Env config

```bash
cp .env.example .env
```

Adjust paths in `.env` if your data drive differs from the default.

### 5. Infra (Postgres + Redis)

```bash
docker compose up -d
```

### 6. Train a model (or use your own)

```bash
# Download DOTA-v1.5 manually (registration required: https://captain-whu.github.io/DOTA/)
# Drop train/val zips into /d/astra-data/datasets/dota-staging/{traning,validation}/
python scripts/setup_dota.py        # unpacks + sorts into dota-raw/
python training/prepare_dota.py     # tiles to 1024² with OBB->AABB, YOLO format
python training/train.py --config training/configs/astra-v1.yaml   # ~2 hours on 4050
python training/export_onnx.py --weights D:/astra-data/runs/astra-v1/weights/best.pt
```

Or skip training and drop your own `.pt` at `D:/astra-data/weights/astra-v1.pt`.

### 7. Run

Three terminals:

```bash
# Terminal 1 — backend
. /d/astra-data/venvs/astra/Scripts/activate
cd backend && uvicorn app.main:app --reload

# Terminal 2 — frontend
cd frontend && npm run dev

# Terminal 3 — (already running from Step 5) docker compose logs -f
```

Open **http://localhost:5173** → upload an image → see boxes.

---

## Feature walk-through

### Live detection + Grad-CAM
Upload an aerial image on the **Mission** page. Detection runs in ~40 ms. Click any bounding box → a heatmap overlay shows the exact pixels that drove that classification. Uses EigenCAM on YOLO11's C2PSA backbone layer (gradient-free, ~1 s on CPU).

### Video tracking with ByteTrack
Upload a video (or paste a URL via the **Stream** button). The pipeline samples up to 30 frames, runs ByteTrack with `persist=True`, and stores stable track IDs. Playing back the video shows boxes moving in sync with the timestamp, with fading polyline trails behind each track. The **Map** page renders the same tracks as geo-referenced polylines.

### Threat scoring + narrator
Each detection becomes an `Alert` with a transparent 5-term score: class weight, proximity to friendly assets, motion-toward score, same-class density, detection confidence. A deterministic template-based narrator produces a 1-sentence summary per alert (*"CRITICAL THREAT: 41 heavy vehicle units 0.12km from FOB Delta (confidence 73%). Possible convoy formation."*). The **Alerts** page lets the commander drag sliders to re-rank the queue client-side — every weight change is logged.

### Signed PDF reports
The **Audit** page has a mission selector + **PDF** button. Generates a 2-page mission report via reportlab: cover metadata, AOI corners, class distribution, top 15 threats with narratives, full audit trail, and a SHA-256 hash of the report body as the integrity footer. Offline-generated, court-admissible.

### Adversarial robustness testing
The **Adversarial** page runs a real FGSM attack against the YOLO model. Upload an image, drag the epsilon slider, click *Run attack*. Measured results on the airfield sample:

| ε | detections retained | signal |
|---|---|---|
| 0.00 | 100% | baseline |
| 0.02 | 77% | light degradation |
| **0.05** | **46%** | **vehicle classes collapse** |
| 0.08 | 54% | class confusion |
| 0.12 | catastrophic | false-positive bloom |

We measure our model's weakness instead of hiding it.

---

## API surface

| Endpoint | Purpose |
|---|---|
| `GET /health` | model + device status |
| `POST /api/v1/ingest` | multipart file ingest, fires background pipeline |
| `POST /api/v1/ingest/url` | RTSP/HTTP/HTTPS URL ingest |
| `GET /api/v1/ingest` | list missions (for dropdowns) |
| `GET /api/v1/ingest/{id}` | one mission |
| `POST /api/v1/predict` | one-shot image → detections JSON |
| `POST /api/v1/explain` | image + bbox → Grad-CAM PNG |
| `POST /api/v1/adversarial` | image + epsilon + method → original vs perturbed JSON |
| `GET /api/v1/detections` | list detections (filter by mission/class/track) |
| `GET /api/v1/tracks` | detections grouped by ByteTrack track_id |
| `GET /api/v1/alerts` | ranked alerts |
| `PATCH /api/v1/alerts/{id}` | confirm / reject / escalate / reclassify |
| `GET /api/v1/audit` | tamper-evident event log |
| `GET /api/v1/reports/mission/{id}.pdf` | SHA-256-signed mission report |
| `WS /ws/live` | placeholder for live push (multi-worker wire-up) |

Open `http://localhost:8000/docs` for the live Swagger UI with all schemas.

---

## Architecture

See **[docs/architecture.md](docs/architecture.md)** for the full technical overview.

**Four layers:**
1. **Ingest** — file upload · RTSP stream · satellite tiles
2. **Inference** — YOLOv11n (ONNX exportable)
3. **Fusion & reasoning** — ByteTrack · geo-ref · threat scoring · Grad-CAM · narrator
4. **Command & control** — 6-view React dashboard · PDF reports · audit trail

**Four principles:** sovereign · explainable · human-in-the-loop · robustness-tested.

---

## Repo layout

```
astra/
├── backend/                      FastAPI · SQLAlchemy · Ultralytics
│   ├── app/
│   │   ├── api/                  route modules (ingest, predict, explain, adversarial, …)
│   │   ├── db/                   SQLAlchemy models + session
│   │   ├── fusion/               scoring, georef, narrator
│   │   ├── inference/            detector, gradcam, adversarial
│   │   ├── services/             pipeline, audit, reports
│   │   └── schemas/              Pydantic DTOs
│   └── requirements{,-cuda}.txt
│
├── frontend/                     React + Vite + Tailwind + Leaflet
│   └── src/
│       ├── pages/                Mission, MapView, Alerts, Audit, Benchmark, Adversarial
│       ├── lib/api.ts            typed client
│       └── App.tsx               routing + sidebar
│
├── training/                     prepare, train, export, benchmark
│
├── scripts/                      setup_dota (one-shot data sorter)
│
├── docs/                         all the writing
│   ├── pitch-deck.md             3-minute pitch script + Q&A bank
│   ├── demo-video-script.md      9-shot recording script
│   ├── rehearsal-guide.md        day-of-pitch prep
│   ├── slide-build-guide.md      zero-experience Google Slides tutorial
│   ├── architecture.md           technical architecture
│   └── v2-roadmap.md             post-v1 feature backlog
│
├── docker-compose.yml            postgres + redis
├── .env.example                  path + port config
└── PROJECT_SPEC.md               original locked specification
```

---

## Credits + honest disclosures

- Model: **YOLOv11** (Ultralytics, AGPLv3)
- Training data: **DOTA-v1.5** (Xia et al., Wuhan University — aerial imagery aggregated from Google Earth and WorldView satellite)
- Tracker: **ByteTrack** (Zhang et al., 2022)
- Explainability: **EigenCAM** (Muhammad & Yeasin, 2020)
- Attack: **FGSM** (Goodfellow et al., 2015)
- PDF: **reportlab** · Maps: **Leaflet + OpenStreetMap**
- Local LLM narrator hook stubbed for **Phi-3.5-mini** (Microsoft) — currently uses deterministic templates

**This is a hackathon project, not a cleared product.** Training used public academic data only; no classified imagery touched this system. Productionization requires operational data validation, MIL-STD-882 safety case, and integration testing against deployed drone platforms. See [docs/v2-roadmap.md](docs/v2-roadmap.md) for the path.

---

## License

AGPLv3 (inherited from Ultralytics YOLO). Contact the author for alternative licensing.
