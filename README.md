# ASTRA — Aerial Surveillance & Threat Recognition Assistant

> **Sovereign · on-device · defensible.** Defence-grade aerial recognition that runs end-to-end on a 6 GB laptop GPU. Three pillars no other product hits all of: open architecture, no cloud, every claim cryptographically signed.

Built for the **ASTRA Defence-Tech Expo 2026, BMSIT&M Bengaluru**.
Track: *AI & Machine Learning in Defence Technology*.

**Current release: `v3.0.0-` (Day 2 of v3.0 sprint).**
Round 1, Round 2, Round 3 all shipped (`v0.3.0-round3`); v3.0 "sovereign" branch adds detection-level signatures, chain anchoring, calibrated OOD, command palette, and grounded LLM Q&A.

See [docs/V3.0-DAYLOG.md](docs/V3.0-DAYLOG.md) for the day-by-day shipping log,
[docs/V3.0-DECISIONS.md](docs/V3.0-DECISIONS.md) for binding architecture decisions,
[docs/RELEASE-R3.md](docs/RELEASE-R3.md) for the prior R3 feature matrix.

---

## What's new in v3.0

### Defensibility layer (every claim cryptographically attested)

* **T1.1 · Detection provenance signatures (Ed25519)** — every Detection signed at ingest over `model_hash · image_sha256 · mission_id · class_id · confidence · bbox · timestamp`. Tamper any field in the DB → next verify fails. Click any detection's signed badge → modal walks the canonical payload + runs verify live.
* **T1.2 · Chain anchor** — every audit-chain tip is captured to an append-only `anchors/log.jsonl`. The Audit page's `Verify anchors` button re-walks every historical anchor against the live chain and surfaces any tip mismatch. Path to OpenTimestamps / coalition-partner anchoring is built in.
* **T1.3 · Calibrated Mahalanobis OOD** — replaces the R2 heuristic. 9-D feature vector → per-class Gaussian → Mahalanobis distance → flag if > 99th percentile of in-distribution distances. Calibrated against 823 real detections (6 classes); same architecture upgrades to YOLO penultimate-layer features in R4 by swapping one extractor function. The R2 heuristic is kept as fallback.

### Operator UX

* **T1.7 · Command palette** — `⌘K` / `Ctrl+K` from anywhere. Indexes 10 sidebar pages, the 50 most-recent missions, 25 most-recent alerts, and quick actions (verify chain, anchor now, demo mode). Fuzzy match. Keyboard-driven.
* **T1.8 · Contextual help** — press `?` anywhere; per-route cheat sheet for all 10 pages. Skips inputs so chat composer stays usable.
* **T0.4 · Cinematic Verify-Chain** — `Verify chain` on Audit page floors at 700ms so the SHA-walk feels intentional; banner shows row count + genesis + tip hash.
* **T0.7 · Top-3 airframe alternates** — when the cascade says "F-22 91%", the 2nd & 3rd guesses appear as small chips. Communicates uncertainty per detection.
* **T0.8 · Operational tooltips** — every specialty viz (ThreatWaveform, ChainVisual, FederatedTopology, RetentionGauge, HeatmapOverlay) explains itself on hover.
* **T0.11 · IST + relative timestamps** — `2m ago` with full IST tooltip on hover. No more UTC arithmetic in your head.
* **T0.12 · Toast hardening** — visible cap (5), identical-toast dedupe with `×N` badge, sticky criticals.
* **T0.14 · Per-route ErrorBoundary** — a render fault in one page never white-screens the whole console. Reset, reload, copy-stack actions.
* **T0.15 · Demo mode** — sidebar toggle hides operator chrome, skips splash + onboarding, pulses "DEMO MODE" pill at top.
* **T1.10 · One-pager auto-PDF** — `GET /api/v1/benchmarks/onepager.pdf`: 4.3 KB single-page A4 with three pillars + live metrics + competitive delta strip. Built for procurement officers to take away.
* **T1.12 · Pillars tile on Command** — full-width SOVEREIGN / ON-DEVICE / DEFENSIBLE tile.

### Real numbers, captured live

The Benchmark page reads directly from JSON files under `benchmarks/` produced by:

| Number | Value (latest capture) | Script |
|---|---|---|
| Detector mAP@0.5 | **0.523** | `scripts/capture_detector_map.py` |
| Detector mAP@0.5:0.95 | **0.290** | (above) |
| Detector precision / recall | 0.722 / 0.490 | (above) |
| Cascade top-1 | **89.03%** | training run, MAR20 |
| Ingest→alert p50 | **499 ms** | `scripts/capture_latency.py` |
| Ingest→alert p99 | **626 ms** | (above) |
| Audit chain rows verified | live count, genesis-anchored | `Verify chain` button |

### Backend platform

* **T0.6 · Warmup hook + LLM cache** — YOLO + cascade + Phi-3.5 preload at boot (~6s). First request after boot drops from ~1500ms cold start to ~500ms steady-state.
* **T0.16 · `scripts/preflight.sh`** — pre-demo readiness gate. ALL GREEN required.
* **T0.17 · `scripts/dev-restart.sh`** — single-command zombie-kill + uvicorn restart for the recurring WinError 10013.
* **T0.13 · Soft-delete missions** — DELETE `/api/v1/ingest/{id}` sets `deleted_at`; detections + audit preserved (chain stays append-only by contract).
* **T0.10 · Skeletons + 15s stall hint** — no white-screen waits; long-running loads surface a "still loading" hint.

### LLM-grounded Q&A (Phi-3.5)

The Chat page now talks to a real LLM when `D:/astra-data/models/phi-3.5-mini-instruct.Q4_K_M.gguf` is present and `llama-cpp-python` is installed. Two-tier with graceful fallback:

* **Tier 1 (LLM):** Phi-3.5-mini retrieves recent missions + top alerts as context; phrases natural-English answers; honest about what it doesn't know.
* **Tier 2 (rule-based):** regex intent matcher over the DB. Always works.
* **Mission-scoped threads** persisted in Postgres (`chat_messages` table). Refresh-survives.
* **`details of mission #N`** intent → multi-section briefing (overview, detections by class, airframes ID'd, alerts, operator notes, audit summary).
* **`note: <text>`** intent → save free-form note attached to the active mission.

---

## What's still in the box from R1–R3

### Two-stage detection model
* **YOLOv11-nano** fine-tuned on DOTA-v1.5 — 8 defence-relevant classes (small/large vehicle, fixed/rotor aircraft, ship, storage-depot, harbor, bridge).
* **MAR20 cascade classifier** — fine-grained military airframe ID (F-22, Su-35, B-52, P-3C, …). 89.03% top-1 / 99.32% top-5 on MAR20.
* **5.5 MB + 3.2 MB** total on disk. Fits on a Jetson Nano.

### Pipeline
* `/predict` — single-shot image inference (~30ms warm).
* `/ingest` — full pipeline: detect → cascade → OOD assess → threat score → audit log → WS broadcast.
* `/ingest/url` — RTSP/HTTP/HTTPS URL ingestion via FFmpeg.
* `/explain` — Grad-CAM (EigenCAM) heatmap on click.
* Video tracking via Ultralytics ByteTrack — stable `track_id` with movement trails.
* FGSM adversarial attack with measured retention curve.
* Threat scoring with transparent 5-term breakdown + template-based narrator.

### Federated learning
* **In-process FedAvg orchestrator** — N nodes trained, weights averaged, broadcast.
* **FoolsGold (Fung 2020)** — cosine-similarity Sybil quarantine. 2 colluding attackers → weight ≈ 0.000.
* **DP-SGD** — per-client gradient L2-clip + Gaussian noise.

### Tamper-evident audit
* SHA-256 hash chain from a genesis row.
* `verify_chain()` re-walks every row; mismatch identifies the tampered row.
* Chain anchors extend protection beyond the chain itself.

### Dual-control engagement
* `ESCALATED → ENGAGED` requires 2 distinct operator IDs to confirm.
* `confirmations_json` audit-logged per step.

### Frontend (10 pages)

| Page | Purpose |
|---|---|
| **Command** | Live tactical wall — every subsystem one tile + the SOVEREIGN/ON-DEVICE/DEFENSIBLE pillars strip. |
| **Mission** | Drag in image/video; canvas overlay; click-to-Grad-CAM; auto-loaded detections survive tab navigation. |
| **Map** | Geo-pinned detections + heatmap toggle + per-marker airframe + Verify-signed badge. |
| **Alerts** | Threat queue with weight sliders + waveform + dual-control engage workflow. |
| **Audit** | Hash-chained log; `verify chain` cinematic banner; chain-anchor strip; PDF export. |
| **Benchmark** | mAP, latency, cascade — all read live from `benchmarks/*.json`. |
| **Adversarial** | FGSM A/B with epsilon slider; v1 vs v1-hardened retention. |
| **Federated** | FedAvg + FoolsGold dashboard with topology, accuracy, weights, quarantine. |
| **Diff** | Side-by-side mission comparison. |
| **Chat** | Mission-scoped Phi-3.5 Q&A with persistence + briefing intent. |

---

## Quick start

Prereqs: Windows 11, Python 3.13, Node 22+, Docker Desktop, CUDA-capable GPU (tested on RTX 4050 Laptop 6GB).

```bash
# 1. Data dir (deliberately on D: to escape OneDrive sync)
mkdir D:\astra-data\{datasets,weights,runs,uploads,secrets,anchors,models}

# 2. Python venv
py -3.13 -m venv D:/astra-data/venvs/astra
. D:/astra-data/venvs/astra/Scripts/activate
pip install --upgrade pip
pip install -r backend/requirements-cuda.txt   # torch 2.6.0+cu124 (~2 GB)
pip install -r backend/requirements.txt        # ultralytics, fastapi, reportlab, etc.
pip install cryptography llama-cpp-python      # v3.0 add-ons

# 3. Frontend
cd frontend && npm install && cd ..

# 4. Infra
docker compose up -d

# 5. (Optional) Download Phi-3.5 GGUF for live LLM in /chat
curl -L --fail -o D:/astra-data/models/phi-3.5-mini-instruct.Q4_K_M.gguf \
  "https://huggingface.co/bartowski/Phi-3.5-mini-instruct-GGUF/resolve/main/Phi-3.5-mini-instruct-Q4_K_M.gguf?download=true"

# 6. Train your own detector OR drop a trained .pt at D:/astra-data/weights/astra-v1.pt
python training/train.py --config training/configs/astra-v1.yaml

# 7. (Optional) Calibrate the Mahalanobis OOD gate against your detections
python scripts/calibrate_ood.py --per-class 200 --percentile 99

# 8. Run
./scripts/dev-restart.sh             # backend, watches logs
cd frontend && npm run dev           # in another terminal

# 9. Verify before any demo
./scripts/preflight.sh               # expect ALL GREEN
```

Open **http://localhost:5173/**. First-run users see a 90-second onboarding tour. Press `⌘K` from anywhere to jump; press `?` for contextual help.

---

## Demo flow (5 minutes)

1. **Splash** → Command Center loads with live numbers + the three pillars tile.
2. **Mission** → drag `D:/astra-data/demo-samples/02-airfield-hero.jpg`. Within 1.5s: 13 fixed-wing aircraft detected, top-3 cascade chips appear (P-3C / F-22 / E-3 alternates).
3. Click any detection's **`signed`** badge → modal opens, click *Verify now* → ✓ "Signature valid".
4. **Audit** → click *verify chain* → SHA-256 walks 200+ rows from genesis to tip with green banner. Then click *Anchor now* → external tip captured. Then *Verify anchors* → ✓ all anchors valid.
5. **Chat** → header pill shows `Phi-3.5 LLM`. Type `details of mission #N` → professional briefing.
6. **Federated** → topology graph showing 3 clients + central aggregator; FoolsGold quarantines `attacker-1`.
7. **Adversarial** → FGSM attack with retention gauge; baseline vs hardened side-by-side.
8. Switch on **demo mode** → operator chrome hides; "DEMO MODE" pulse top-center.

---

## API surface (selected)

| Endpoint | Purpose |
|---|---|
| `GET /health` | model + device + version |
| `POST /api/v1/ingest` | multipart file → fires the full pipeline |
| `POST /api/v1/predict` | one-shot detection JSON |
| `GET /api/v1/detections` | filterable list incl. `signature_b64` + `image_sha256` |
| `GET /api/v1/audit/verify` | walk SHA-256 chain → `{ok, checked, genesis, tip}` |
| `GET /api/v1/provenance/key` | server pubkey + fingerprint + model_hash |
| `GET /api/v1/provenance/verify/{id}` | re-verify a detection's signature |
| `GET /api/v1/anchor/status` | last anchor + total |
| `POST /api/v1/anchor/now` | force-capture current tip |
| `GET /api/v1/anchor/verify` | every anchor vs live chain |
| `GET /api/v1/ood/calibration` | Mahalanobis backend + per-class thresholds |
| `POST /api/v1/chat` | mission-scoped Q&A; LLM if available, rules otherwise |
| `GET /api/v1/chat/thread?mission_id=N` | persisted conversation |
| `POST /api/v1/chat/note` | attach note to a mission |
| `GET /api/v1/benchmarks/detector` | live mAP capture |
| `GET /api/v1/benchmarks/latency` | live p50/p95/p99 |
| `GET /api/v1/benchmarks/onepager.pdf` | judge take-away PDF |
| `WS /ws/live` | real-time event stream |

Open **http://localhost:8000/docs** for full Swagger UI.

---

## Repo layout

```
astra/
├── backend/                 FastAPI · SQLAlchemy 2 · Postgres · Ultralytics
│   └── app/
│       ├── api/             route modules — ingest, predict, audit, provenance,
│       │                    anchor, ood, chat, benchmarks, federated, …
│       ├── db/              SQLAlchemy 2 ORM models + idempotent migrations
│       ├── inference/       detector, classifier, ood_gate, ood_calib, gradcam,
│       │                    adversarial
│       ├── services/        pipeline, audit, anchor, provenance, rag, reports,
│       │                    onepager, notifier
│       └── schemas/         Pydantic DTOs
│
├── frontend/                React 18 + Vite 6 + Tailwind + Leaflet + Recharts
│   └── src/
│       ├── pages/           Command, Mission, MapView, Alerts, Audit, Benchmark,
│       │                    Adversarial, Federated, Diff, Chat, Login
│       ├── components/      Bezel, HudOverlay, ChainVisual, FederatedTopology,
│       │                    ThreatWaveform, RetentionGauge, HeatmapOverlay,
│       │                    VerifyBadge, AnchorStrip, CommandPalette, HelpOverlay,
│       │                    ErrorBoundary, OnboardingTour, …
│       └── lib/             api, time, demoMode, useStallTimeout, auth
│
├── federated/               in-process FedAvg + FoolsGold + DP-SGD orchestrator
├── training/                YOLO config, prepare_dota, train, prepare_mar20,
│                            pgd_finetune, continual_finetune, export_onnx
├── scripts/                 capture_detector_map · capture_latency · calibrate_ood ·
│                            preflight.sh · dev-restart.sh · e2e_regression
├── benchmarks/              detector_val.json · latency.json · adversarial_ab.json
├── docs/                    V3.0-DECISIONS · V3.0-DAYLOG · RELEASE-R3 · OPERATOR-R3
│                            · pitch-content-r2 · benchmark-report · architecture
├── e2e/                     Playwright spec + config
├── docker-compose.yml       Postgres 16 + Redis 7
└── PROJECT_SPEC.md          original locked spec
```

---

## Architecture

**Four layers:**
1. **Ingest** — file upload · RTSP stream · satellite tiles
2. **Inference** — stage-1 YOLOv11n · stage-2 MAR20 cascade · OOD gate (Mahalanobis or heuristic) · Grad-CAM
3. **Fusion & reasoning** — ByteTrack · geo-ref · threat scoring · audit chain · chain anchoring · Ed25519 signing · narrator · RAG
4. **Command & control** — 10-page React dashboard · PDF reports · WebSocket live push · LLM Q&A

**Five principles (v3.0):** sovereign · on-device · defensible · explainable · human-in-the-loop.

---

## Credits + honest disclosures

- Detection: **YOLOv11** (Ultralytics, AGPLv3) · **DOTA-v1.5** (Xia et al., Wuhan)
- Cascade: trained on **MAR20** (20 military airframes, public)
- Tracker: **ByteTrack** (Zhang et al., 2022)
- Federated: **FedAvg** (McMahan 2017) + **FoolsGold** (Fung 2020) + **DP-SGD** (Abadi 2016)
- Adversarial: **FGSM** (Goodfellow 2015), **PGD** (Madry 2018, finetune script ready)
- OOD: **Mahalanobis distance** with pooled covariance (Lee 2018 family)
- Provenance: **Ed25519** signatures via `cryptography`
- LLM: **Phi-3.5-mini-instruct** (Microsoft) via **llama-cpp-python**
- PDF: **reportlab** · Maps: **Leaflet + OpenStreetMap**

**This is a hackathon project, not a cleared product.** Training used public academic data only; no classified imagery touched this system. Productionization requires operational data validation, MIL-STD-882 safety case, integration testing against deployed drone platforms, and FIPS-140-3 crypto module review.

---

## License

AGPLv3 (inherited from Ultralytics YOLO). Contact the author for alternative licensing.
