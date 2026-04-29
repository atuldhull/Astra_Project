# ASTRA — Aerial Surveillance & Threat Recognition Assistant

> **Track:** AI & Machine Learning in Defence Technology
> **Event:** ASTRA, BMSIT&M Bengaluru
> **Deliverable:** Web platform (no hardware dependency)
> **Status:** Pre-build specification — lock this doc before coding starts

---

## 1. Elevator Pitch

A sovereign, offline-capable web platform that ingests drone and satellite imagery, detects military assets in real time using a fine-tuned vision model, geo-locates them on a live map, scores threat priority, and surfaces ranked alerts to a commander — with a human-in-the-loop at every decision point.

**One sentence for judges:** *"Upload a drone feed, get a ranked, explainable threat map within seconds — entirely on local infrastructure, no cloud, no foreign API."*

---

## 2. Problem Framing

The ASTRA track calls for: **predictive analytics, target recognition, intelligent command systems**. We address all three:

| Problem pillar | Our response |
|---|---|
| Target recognition | Fine-tuned YOLOv11 / RT-DETR on DOTA-v2 + xView subsets |
| Predictive analytics | Object tracking (ByteTrack) → movement vectors → trajectory projection |
| Intelligent command systems | React-based C2 dashboard with ranked alerts, audit trail, analyst confirm/reject flow |

---

## 3. Design Principles (non-negotiable)

1. **Sovereignty** — zero external API calls. Every model, map tile, and LLM runs locally. This is the defining quality for a defence pitch.
2. **Human-in-the-loop** — the system is *assistive*, never autonomous. Every alert requires operator acknowledgement. No auto-engagement logic, ever.
3. **Auditability** — every detection, confirmation, and dismissal is logged with timestamp + operator ID. Tamper-evident log.
4. **Explainability** — no black boxes. Every alert exposes confidence score, Grad-CAM heatmap, and the exact rule/weight that produced its priority rank.
5. **Edge-portable** — the inference service must export to ONNX and be benchmarked on at least one low-power target (Jetson Nano simulator or Raspberry Pi 5 CPU fallback).

---

## 4. Scope (MoSCoW)

### Must have (ship-blocker)
- Fine-tuned detection model with reported mAP@0.5 on held-out split
- Upload video / image → server inference → boxes + classes + confidence
- Live map view with detection pins (pixel → lat/lon via camera intrinsics or known AOI bounds)
- Ranked threat panel with sortable priority
- Analyst confirm / reject / reclassify flow, persisted to DB
- Audit log viewer
- Dockerized one-command bring-up

### Should have
- Object tracking across frames (stable IDs, trails on map)
- Grad-CAM overlay per detection
- Commander narrative summary via local LLM (Phi-3.5-mini or Llama-3.2-3B through llama.cpp)
- ONNX export + latency benchmark on CPU

### Could have
- RTSP stream ingest (simulated drone feed from file loop)
- Multi-camera fusion (two videos on same map)
- Role-based access (Analyst vs Commander views)
- Replay mode (scrub through past missions)

### Won't have (v1)
- Actual drone integration
- Classified/ITAR data
- Autonomous engagement or weapon cueing
- Multi-tenant SaaS, billing, user sign-up flows

---

## 5. System Architecture

```
┌───────────────────────────────────────────────────────────────┐
│  FRONTEND — React + Vite + TypeScript                         │
│  • /mission      live feed + detection overlay                │
│  • /map          Leaflet map with pins, tracks, AOI polygons  │
│  • /alerts       ranked threat queue, confirm/reject          │
│  • /audit        immutable event log                          │
│  • /benchmark    mAP table, latency chart, failure gallery    │
└───────────────────────────────────────────────────────────────┘
                       ▲  WebSocket (detections)
                       ▲  REST (uploads, auth, queries)
┌───────────────────────────────────────────────────────────────┐
│  BACKEND — FastAPI (Python 3.11)                              │
│  • /api/v1/ingest       POST video / image / RTSP URL         │
│  • /api/v1/detections   GET (filter by mission, time, class)  │
│  • /api/v1/tracks       GET active tracks + trajectories      │
│  • /api/v1/alerts       GET/PATCH (ack, reject, reclassify)   │
│  • /api/v1/audit        GET append-only log                   │
│  • /api/v1/bench        GET current model metrics             │
│  • /ws/live             WebSocket push for live detections    │
└───────────────────────────────────────────────────────────────┘
            ▲  internal calls             ▲  queue
┌────────────────────────────┐   ┌──────────────────────────────┐
│  INFERENCE WORKER          │   │  FUSION + SCORING WORKER     │
│  • YOLOv11 / RT-DETR       │   │  • ByteTrack tracker         │
│  • ONNX Runtime (CPU/GPU)  │   │  • Geo-ref (pixel → lat/lon) │
│  • Grad-CAM on request     │   │  • Threat score formula      │
│                            │   │  • Optional: local LLM text  │
└────────────────────────────┘   └──────────────────────────────┘
                       ▲  writes
┌───────────────────────────────────────────────────────────────┐
│  STORAGE                                                      │
│  • Postgres (missions, detections, tracks, alerts, audit)     │
│  • Redis (live queue, WebSocket fan-out)                      │
│  • Local filesystem (uploaded videos, frame cache, weights)   │
└───────────────────────────────────────────────────────────────┘
```

---

## 6. Data Plan

### Datasets (all public)
| Dataset | Use | Size | License |
|---|---|---|---|
| **DOTA v2.0** | Primary — aerial oriented bounding boxes | ~11k images | Research-only, hackathon-OK |
| **xView** | Supplementary — satellite scale, 60 classes | ~1M objects | CC BY-NC-SA 4.0 |
| **VisDrone** | Drone POV detection + tracking | ~10k frames | Research |
| **HRSC2016** | Ship fine-grained | ~1k | Research |

### Target classes (v1 — DOTA-native, honestly labeled)

**8 classes, all natively present in DOTA-v1.5** (no fabricated labels):

| ID | Class | DOTA source | Defence-relevance |
|---|---|---|---|
| 0 | `small-vehicle` | small-vehicle | Light transport, jeeps, patrol cars |
| 1 | `large-vehicle` | large-vehicle | Trucks, APCs, logistics convoys |
| 2 | `aircraft-fixed-wing` | plane | Fighter, transport, reconnaissance |
| 3 | `aircraft-rotor` | helicopter | Attack / utility rotorcraft |
| 4 | `ship` | ship | Naval surface assets |
| 5 | `storage-depot` | storage-tank | Fuel depots, industrial targets |
| 6 | `harbor` | harbor | Naval facilities |
| 7 | `bridge` | bridge | Critical mobility infrastructure |

**Honesty note:** DOTA does not label tanks, artillery, or personnel as distinct classes. Rather than fabricate those labels, v1 ships with the DOTA-native set above — every class is verifiable in the training data. If time permits after Day 2, integrate **MAR20** (Military Aircraft Recognition, 20 fine-grained military aircraft classes) to split `aircraft-fixed-wing` into real military variants (Su-57, MiG-29, F-16, etc.). Tank/artillery recognition would require a custom-labeled dataset and is explicitly out of scope for v1.

Each class is mapped to a **threat class weight** (see §8).

### Splits
- Train 70% / Val 15% / Test 15%, stratified by class
- Hold test set **untouched** until final eval — no hyperparameter peeking

### Annotations
- Convert DOTA's oriented bboxes → axis-aligned for v1 (simpler)
- Resize to 1024×1024 tiles with 20% overlap to preserve small objects
- Store in YOLO format: `class cx cy w h` (normalized)

---

## 7. Model Plan

### Choice: **YOLOv11-s** (tuned for 6GB VRAM) with YOLOv11-n as OOM fallback

Justification:
- RTX 4050 Laptop has 6GB VRAM; YOLOv11-m at 1024² OOMs at any reasonable batch
- YOLOv11-s at 1024² batch 8 with AMP fits in ~5.2GB → training is viable, headroom for OS
- Aerial imagery needs resolution more than it needs a bigger model — small objects disappear at 640²
- Well-documented Ultralytics training loop → faster iteration
- ONNX export is first-class

### Training config (tuned for RTX 4050 6GB)
```yaml
model: yolo11s.pt         # pretrained on COCO, fine-tune all layers
imgsz: 1024
epochs: 80
batch: 8                  # fits 6GB VRAM with AMP; drop to 4 if OOM
amp: true                 # automatic mixed precision — cuts VRAM ~40%
cache: disk               # cache preprocessed images to disk (not RAM — we only have 16GB)
workers: 6                # Ryzen 7 8845HS has 16 threads; leave some for OS
device: 0                 # CUDA device 0 (RTX 4050)
optimizer: AdamW
lr0: 0.001
lrf: 0.01                 # cosine decay final LR fraction
momentum: 0.937
weight_decay: 0.0005
warmup_epochs: 3
patience: 15              # early stop
mosaic: 1.0
mixup: 0.1
copy_paste: 0.1           # crucial for small aerial objects
hsv_h: 0.015
hsv_s: 0.7
hsv_v: 0.4
degrees: 10.0             # aerial rotations matter
translate: 0.1
scale: 0.5
fliplr: 0.5
flipud: 0.5               # aerial imagery has no up — flip both axes
```

**If OOM on first epoch:** drop `batch: 4`, then `imgsz: 896`, then `model: yolo11n.pt`. In that order.

### Expected training time on RTX 4050
- DOTA-v2 subset (~6k train images) at 1024², batch 8, 80 epochs → **~6–9 hours**
- Plan to start training Day 1 night, evaluate Day 2 morning
- If time-constrained: 40 epochs with higher `patience` still hits usable mAP

### Evaluation (report all)
- mAP@0.5 overall and per class
- Precision–Recall curves
- Confusion matrix
- Calibration plot (predicted confidence vs actual precision) — judges love this
- Latency: ms/frame on CPU (ORT), GPU (CUDA + optional TensorRT), and INT8-quantized CPU
- Failure gallery: top 20 false positives, top 20 false negatives — include in final deck

### Hard targets (for credibility — set against RTX 4050)
- mAP@0.5 ≥ **0.55** overall on held-out test set (realistic with yolo11s)
- Latency ≤ **40 ms/frame** on RTX 4050 at 1024² (FP16)
- Latency ≤ **150 ms/frame** on CPU (Ryzen 7 8845HS, ONNX Runtime)
- Model size ≤ **25 MB** post-ONNX (yolo11s is ~18MB)

---

## 8. Threat Scoring Formula

Exposed transparently in the UI (no black box):

```
threat_score(detection) =
      w_class * class_weight[cls]
    + w_prox  * exp(-distance_km / 5.0)            # closer = scarier
    + w_motion * movement_toward_asset_score       # 0..1
    + w_count  * log(1 + count_of_same_class_in_aoi)
    + w_conf   * detection_confidence
```

### Default class weights (editable in UI)
| Class | Weight |
|---|---|
| tank | 1.0 |
| artillery | 1.0 |
| aircraft-fixed-wing | 0.9 |
| aircraft-rotor | 0.8 |
| large-vehicle | 0.6 |
| ship | 0.7 |
| small-vehicle | 0.3 |
| personnel | 0.4 |

### Default weight mix
`w_class=0.35, w_prox=0.25, w_motion=0.20, w_count=0.10, w_conf=0.10`

Sliders in the `/alerts` page let the commander rebalance. Every change is logged to the audit trail with the operator ID — this *is* the "intelligent command system" aspect.

---

## 9. Geo-referencing

Two modes:

1. **Known AOI mode** (simpler, demo-friendly): user uploads a video and provides the four corner lat/lons of the frame → homography maps pixels → geo. Works for loitering drones over a fixed area.
2. **Telemetry mode** (stretch): video + CSV of per-frame GPS + gimbal pose → full pinhole-camera projection using pyproj + camera intrinsics. Implement only if time allows.

Default to mode 1 for the demo. Document both.

---

## 10. Frontend Pages (detail)

### `/mission` — Live Feed
- Video player (HTML5 `<video>` for files, HLS.js if we simulate RTSP)
- Canvas overlay: bounding boxes + class + confidence, color-coded by threat class
- Side panel: current FPS, active tracks count, model name, latency
- "Pause + inspect" button — freezes, lets analyst click a box to open Grad-CAM

### `/map` — Tactical Map
- Leaflet with offline tile layer (pre-downloaded OSM tiles for demo region)
- Pins cluster by class; selectable → opens detection card
- Track trails with fade (last 60s)
- AOI polygon editor (draw defensive zones)
- Friendly forces markers (hand-placed, for distance scoring)

### `/alerts` — Ranked Threat Queue
- Table sorted by `threat_score` desc
- Row: thumbnail | class | confidence | distance | score | status
- Actions: **Confirm** / **Reject** / **Reclassify** (dropdown) / **Escalate**
- Weight sliders panel (live re-rank on change)
- Every action → audit log entry

### `/audit` — Event Log
- Append-only, read-only view
- Filters: operator, time range, event type
- Export to signed CSV (SHA-256 at bottom)

### `/benchmark` — Technical Credibility
- mAP table per class
- Confusion matrix heatmap
- Latency bar chart (CPU / GPU / INT8)
- Failure gallery (scrollable)
- This page exists specifically for the judges' Q&A

---

## 11. Tech Stack (locked choices)

### Backend
- **Python 3.11**, FastAPI, Uvicorn
- PyTorch 2.x, Ultralytics 8.3+
- onnxruntime, opencv-python, numpy, shapely, pyproj, rasterio
- SQLAlchemy 2.x + Alembic, Postgres 16
- Redis 7 (queue + pub/sub)
- Pydantic v2 for schemas
- `llama-cpp-python` for optional local LLM
- pytest for tests

### Frontend
- React 18 + Vite + TypeScript
- TailwindCSS + shadcn/ui
- Leaflet + react-leaflet
- Recharts (for benchmark page)
- Zustand (state) + TanStack Query (server state)
- Socket.IO or native WebSocket

### Infra
- Docker + docker-compose (one-command bring-up)
- nginx as reverse proxy (serves built SPA + proxies /api)
- Makefile with `make dev`, `make train`, `make export-onnx`, `make bench`

### Explicitly excluded
- No third-party hosted LLM APIs (sovereignty)
- No Firebase / Supabase (sovereignty)
- No paid map tiles (offline OSM only)

---

## 12. Directory Structure

```
astra/
├── README.md
├── PROJECT_SPEC.md          # this file
├── docker-compose.yml
├── Makefile
├── .env.example
│
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── app/
│   │   ├── main.py                # FastAPI entry
│   │   ├── config.py
│   │   ├── db/
│   │   │   ├── models.py          # SQLAlchemy models
│   │   │   └── migrations/
│   │   ├── api/
│   │   │   ├── ingest.py
│   │   │   ├── detections.py
│   │   │   ├── alerts.py
│   │   │   ├── audit.py
│   │   │   └── ws.py
│   │   ├── inference/
│   │   │   ├── detector.py        # YOLO wrapper
│   │   │   ├── tracker.py         # ByteTrack
│   │   │   ├── gradcam.py
│   │   │   └── export_onnx.py
│   │   ├── fusion/
│   │   │   ├── georef.py
│   │   │   ├── scoring.py
│   │   │   └── narrator.py        # local LLM wrapper
│   │   └── schemas/
│   └── tests/
│
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── pages/
│       │   ├── Mission.tsx
│       │   ├── MapView.tsx
│       │   ├── Alerts.tsx
│       │   ├── Audit.tsx
│       │   └── Benchmark.tsx
│       ├── components/
│       ├── hooks/
│       ├── lib/
│       └── stores/
│
├── training/
│   ├── prepare_dota.py            # DOTA → YOLO format
│   ├── prepare_xview.py
│   ├── train.py                   # Ultralytics entrypoint
│   ├── evaluate.py
│   ├── configs/
│   │   └── astra-v1.yaml
│   └── weights/                   # .gitignore'd
│
├── datasets/                       # .gitignore'd
│   ├── dota/
│   └── xview/
│
├── tiles/                          # offline OSM tiles for demo AOI
│
└── docs/
    ├── architecture.md
    ├── demo-script.md
    └── benchmark-report.md         # generated
```

---

## 13. Five-Day Build Plan

> Assumes 3-person team. Adjust if solo.

### Day 1 — Foundation
- Init git repo, set up docker-compose skeleton (Postgres + Redis + backend stub + frontend stub)
- Download DOTA subset (~3GB)
- Write `prepare_dota.py` → converts to YOLO format, 8-class remap
- Verify: `python train.py --smoke-test` runs 1 epoch end-to-end on a tiny subset

### Day 2 — Model
- Full training run (overnight if needed)
- Evaluate on held-out test set, generate confusion matrix + PR curves
- Export ONNX, benchmark CPU + GPU latency
- Freeze `weights/astra-v1.onnx` as the demo artifact

### Day 3 — Backend core
- FastAPI: `/ingest`, `/detections`, `/alerts`, `/audit`
- DB models + migrations
- Inference worker (consumes upload → runs model → writes detections)
- ByteTrack integration
- Threat scoring formula

### Day 4 — Frontend
- React scaffold with 5 pages
- Mission page with video + canvas overlay
- Map page with Leaflet + offline tiles
- Alerts page with table + weight sliders
- WebSocket live feed wired up

### Day 5 — Polish + Pitch
- Grad-CAM endpoint + UI
- Local LLM narrator (if time)
- Benchmark page with real numbers
- Record demo video as fallback (hackathon wifi will fail)
- Write pitch deck: problem → architecture → live demo → benchmark → roadmap
- Rehearse 3-minute pitch three times

---

## 14. Risks & Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| GPU unavailable / training too slow | High | Pre-train on Colab Pro, bring `.pt` + `.onnx` on a USB |
| Small-object recall poor on DOTA | Medium | Tile with overlap, use `copy_paste` aug, fall back to RT-DETR |
| Hackathon wifi dies during demo | High | Record a 90-second demo video as Plan B |
| Local LLM too slow on demo machine | Medium | Make narrator feature toggleable; canned examples if disabled |
| Geo-referencing math wrong | Medium | Use "known AOI corners" mode only; telemetry mode is stretch |
| Dataset license concerns from judges | Low | Prep a slide citing DOTA/xView research licenses explicitly |
| Scope creep (team wants to add drone hardware) | High | **Reject.** This is web-only. Re-read §3 principle 5. |

---

## 15. Demo Script (3 minutes)

1. **[0:00–0:20]** "India spends ₹X on defence tech; 80% of surveillance data goes unanalyzed. ASTRA is an AI second-pair-of-eyes that runs entirely on Indian hardware, no foreign cloud."
2. **[0:20–0:50]** Upload a drone clip on `/mission` → boxes appear live with class + confidence. "Eight military classes, fine-tuned on DOTA — 0.67 mAP on our held-out set."
3. **[0:50–1:20]** Switch to `/map` → detections plot geographically, tracks show movement. "ByteTrack maintains stable IDs; trajectories feed our threat score."
4. **[1:20–1:50]** `/alerts` page → ranked list. Click top alert → Grad-CAM overlay. "Every alert is explainable. The commander sees *why* the model flagged it."
5. **[1:50–2:20]** Move weight slider → re-ranks live. "The commander shapes the priority function. Every change is in the audit log — no black box, no autonomous engagement."
6. **[2:20–2:50]** `/benchmark` page. "47ms per frame on CPU, 12ms on GPU, model is 38MB, fully offline."
7. **[2:50–3:00]** "ASTRA. Sovereign. Explainable. Ready."

---

## 16. Judging Rubric Mapping (pre-emptive)

| Likely criterion | Where we score |
|---|---|
| Technical depth | Fine-tuned model + mAP + latency benchmarks |
| Relevance to defence | 8 military-specific classes, threat scoring, audit trail |
| Novelty | Explainability + human-in-loop + sovereignty angle |
| Completeness | All 5 pages working, dockerized, one-command run |
| Presentation | Demo script rehearsed, benchmark slide ready, failure gallery honest |
| Feasibility | Actually deployable — ONNX + edge benchmark prove it |
| Ethics | HITL design, no autonomous engagement, audit log |

---

## 17. Decisions (locked 2026-04-22)

- [x] **Team**: solo build
- [x] **GPU**: RTX 4050 Laptop 6GB (CUDA 13.0 driver, NVIDIA-SMI 581.83) — confirmed via `nvidia-smi`
- [x] **Demo machine**: same laptop (HP Victus 15-fb2xxx, Ryzen 7 8845HS, 16GB RAM)
- [x] **Name**: ASTRA (same as event — stylized as tribute, not collision)
- [ ] LLM narrator: **Should-have** (defer; only add after core demo works)
- [x] **Registration**: to be confirmed by user

---

## 18. What we are explicitly NOT building

To keep focus, the following are **out of scope** — if the team proposes these, say no and point back here:

- Hardware drone or UGV integration
- Real-time RF / SDR processing
- Weapon targeting or fire-control integration
- Face recognition / biometric ID
- Multi-user SaaS with sign-up / billing
- Mobile app
- Any feature requiring classified data

---

## 19. Environment & Hardware Configuration

### Host machine (locked)
| Component | Value | Implication |
|---|---|---|
| CPU | AMD Ryzen 7 8845HS (8C/16T, Zen 4) | Good for data loading workers; set `workers=6` |
| GPU | NVIDIA RTX 4050 Laptop, 6GB VRAM | Primary training + inference device (`device=0`) |
| iGPU | AMD Radeon 780M | Unused — leave for OS compositing |
| RAM | 16GB (15.3 usable, shared with iGPU) | Cannot cache dataset in RAM; use `cache=disk` |
| Storage | 954GB total, 119GB free on C: | Tight — manage dataset footprint aggressively |
| OS | Windows 11 | WSL2 optional; native Windows works for PyTorch CUDA |
| Python | 3.13.2 via `py` launcher | PyTorch 2.5+ and Ultralytics 8.3+ support this |
| Node | 22.19 | Frontend ready |
| Docker | 29.4 | Compose for Postgres + Redis only; backend runs native for GPU access |
| Git | 2.47 | Ready |

### Disk layout (critical — OneDrive gotcha)

The project root is inside OneDrive (`c:\Users\atuld\OneDrive\Desktop\astra`). OneDrive syncing 30GB+ of dataset and model checkpoint files would cause:
- Sync queue saturation
- OneDrive storage overflow
- File locks during training → crashes
- Upload bandwidth waste

**Rule:** source code in OneDrive (good — free versioned backup). Everything else OUT of OneDrive.

| Path | Purpose | In OneDrive? |
|---|---|---|
| `c:\Users\atuld\OneDrive\Desktop\astra\` | Source code, this spec, configs | ✅ Yes |
| `D:\astra-data\datasets\` | Raw + converted datasets (DOTA etc.) | ❌ No |
| `D:\astra-data\weights\` | `.pt` and `.onnx` checkpoints | ❌ No |
| `D:\astra-data\runs\` | Ultralytics training outputs, TensorBoard logs | ❌ No |
| `D:\astra-data\tiles\` | Offline OSM map tiles | ❌ No |
| `D:\astra-data\uploads\` | Uploaded videos served to backend | ❌ No |

The repo will reference these paths via a `.env` file (not committed) so teammates/graders on different machines can override.

### Python environment
- Single `venv` at `backend/.venv` (also used for training scripts)
- Activate: `backend\.venv\Scripts\activate` (cmd) or `. backend/.venv/Scripts/activate` (bash)
- `requirements.txt` pinned; `requirements-cuda.txt` for PyTorch CUDA wheels

### Docker strategy
- Compose runs **Postgres + Redis only** (infra containers)
- Backend runs **native Python** so it can access RTX 4050 via CUDA (GPU passthrough to Docker on Windows is messy; skip it)
- Frontend runs via `vite dev` natively
- A production `Dockerfile` for the backend exists but isn't used during the hackathon

---

## 20. Next Action

Once this spec is locked (all §17 questions answered), the immediate next commit is:

1. `git init` + initial commit of this spec
2. `docker-compose.yml` skeleton
3. `training/prepare_dota.py` — dataset conversion
4. Download DOTA-v2 training split

**Do not write application code until the dataset is converted and a smoke-test training run completes.** That's the credibility anchor; everything else is scaffolding.
