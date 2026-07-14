# ASTRA — aerial detection with a tamper-evident audit trail

Detects aircraft in aerial imagery on a local GPU, and — the part I actually care about —
makes it hard to lie about what was detected afterwards. Every detection is Ed25519-signed at
ingest, and the audit log is a SHA-256 hash chain you can re-walk from genesis to prove no row
was edited or removed.

Built for the ASTRA Defence-Tech Expo 2026 at BMSIT&M. It is a prototype, not a product, and
the honest disclosures below are part of the README on purpose.

## What's real, and how well it works

**The provenance layer — this is the piece worth reviewing.**
Each detection is signed over a canonical payload (`model_hash · image_sha256 · mission_id ·
class_id · confidence · bbox · timestamp`), so altering any field in the database makes the next
verify fail. The audit log chains each row's hash into the next (`sha256(prev_hash ||
canonical_json(fields))`, genesis `0`×64), so you cannot quietly rewrite history — editing an
old row breaks every hash after it.

Real `cryptography` primitives, not a stub. It's covered by
[`backend/tests/test_provenance_and_audit.py`](backend/tests/test_provenance_and_audit.py):
sign/verify round-trips, key persistence across restart, eight tamper cases, wrong-key
rejection, and chain-tamper detection.

Worth knowing how that test file came about: my first version of it passed even when I
deliberately broke the chain — I sabotaged the row-hash function so it stopped folding in
`prev_hash`, turning the chain into a bag of unrelated hashes, and every test stayed green.
`verify_chain()` recomputes hashes with the same function that wrote them, so it happily
verifies against its own bug. The tests now pin the SHA-256 preimage independently.

**The detector — real, and not very good yet.**
Two-stage cascade: YOLOv11n locates objects, a second classifier identifies the airframe.
Measured on my validation split ([`benchmarks/detector_val.json`](benchmarks/detector_val.json)):

| metric | value |
|---|---|
| mAP@50 | 0.52 |
| **mAP@50:95** | **0.29** |
| precision | 0.72 |
| recall | 0.49 |
| `bridge` class AP | **0.00** |

That is a weak detector. Recall of 0.49 means it misses about half of what's there, and it
fails outright on one of eight classes. The bottleneck is training data, not architecture. I'd
rather publish the number than lead with the latency figure.

Latency p50 is ~500 ms, but that's 25 runs on a single image on one laptop (RTX 4050, 6 GB) —
treat it as a smoke test, not a benchmark.

**Out-of-distribution rejection.** Mahalanobis distance over a 9-dimensional colour/edge
feature vector, per-class Gaussian, flagged above the 99th percentile. Deliberately
model-agnostic: using YOLO's penultimate-layer features would be better and needs model
surgery I didn't do.

## What is *not* real

I'd rather you read this than discover it:

- **The Phi-3.5 LLM is not wired up.** In `fusion/narrator.py` the alert narrator is if/else
  string templates and the Phi-3.5 code is commented out entirely. `services/rag.py` does have
  a real `llama_cpp` path, but it needs a 2.4 GB GGUF you download yourself *and*
  `llama-cpp-python`, which isn't a declared dependency. Out of the box you get a regex intent
  matcher.
- **"Cross-agency mesh witnessing" is two synthetic peers in one process.** The signatures are
  genuine Ed25519 — but the server generates and holds *both* peer keypairs (`DEMO_PEERS =
  ("peer-IB", "peer-NIA")`). A party signing its own logs with keys it minted attests nothing.
  It demonstrates the protocol; it is not a trust boundary.
- **Chain anchoring is a local file** on the same disk as the thing it's anchoring, which is a
  weak guarantee. Anchoring to an external timestamp authority is the obvious next step and
  isn't done.
- **The counter-drone "Sentinel" module is fully synthetic.** Every drone track is
  `random.uniform()`. No RF, no kinetics. The IFF crypto around it is real; the world it
  operates on is invented.
- **The model weights are not in this repo.** Detection will raise `WeightsNotFoundError`
  telling you exactly what's missing until you train a detector or drop a `.pt` in place.

## Running it

The data directory (weights, secrets, anchors, models) lives outside the repo. Point
`ASTRA_DATA_DIR` at it; everything else derives from that one variable. It defaults to
`~/astra-data`.

## Capabilities

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
# 1. Data dir — anywhere you like; export ASTRA_DATA_DIR to point at it
export ASTRA_DATA_DIR=~/astra-data          # or wherever you want it
mkdir -p $ASTRA_DATA_DIR/{datasets,weights,runs,uploads,secrets,anchors,models}

# 2. Python venv
py -3.13 -m venv $ASTRA_DATA_DIR/venvs/astra
. $ASTRA_DATA_DIR/venvs/astra/Scripts/activate
pip install --upgrade pip
pip install -r backend/requirements-cuda.txt   # torch 2.6.0+cu124 (~2 GB)
pip install -r backend/requirements.txt        # ultralytics, fastapi, reportlab, etc.
pip install cryptography llama-cpp-python      # v3.0 add-ons

# 3. Frontend
cd frontend && npm install && cd ..

# 4. Infra
docker compose up -d

# 5. (Optional) Download Phi-3.5 GGUF for live LLM in /chat
curl -L --fail -o $ASTRA_DATA_DIR/models/phi-3.5-mini-instruct.Q4_K_M.gguf \
  "https://huggingface.co/bartowski/Phi-3.5-mini-instruct-GGUF/resolve/main/Phi-3.5-mini-instruct-Q4_K_M.gguf?download=true"

# 6. Train your own detector OR drop a trained .pt at $ASTRA_DATA_DIR/weights/astra-v1.pt
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
2. **Mission** → drag `$ASTRA_DATA_DIR/demo-samples/02-airfield-hero.jpg`. Within 1.5s: 13 fixed-wing aircraft detected, top-3 cascade chips appear (P-3C / F-22 / E-3 alternates).
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
