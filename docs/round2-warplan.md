# ASTRA — Round 2 War Plan

> **Read this first if context was compacted.** Everything you need to resume is here.
>
> **Status:** Round 1 PASSED. Round 2 prep, 96-hour sprint.
> **Event:** ASTRA Defence-Tech Expo 2026, BMSIT&M Bengaluru.
> **Project root:** `c:\Users\atuld\OneDrive\Desktop\astra` · **Data:** `D:\astra-data\` · **Venv:** `D:/astra-data/venvs/astra/`

---

## 🧠 Round 1 — what we already shipped

**Trained model:** YOLOv11-nano on DOTA-v1.5 (40 epochs, 1h 53min, RTX 4050 6GB)
- mAP@0.5 overall = **0.515**
- aircraft-fixed-wing = **0.915**, ship = 0.770, harbor = 0.733, large-vehicle = 0.660
- Inference: 22 ms GPU / 36 ms CPU · 5.5 MB ONNX
- Weights: `D:/astra-data/runs/astra-v1-2/weights/best.pt`

**Backend** (FastAPI, Postgres, Redis): 13 endpoints
`/health · /ingest · /ingest/url · /predict · /explain · /adversarial · /detections · /tracks · /alerts (GET+PATCH) · /audit · /reports/.../{id}.pdf · /ws/live (stub)`

**Frontend** (React + Vite + Tailwind + Leaflet + Recharts): 6 pages
`Mission · Map · Alerts · Audit · Benchmark · Adversarial`

**7 novel features shipped:**
1. Grad-CAM / EigenCAM pixel-level explainability (click box → heatmap)
2. ByteTrack multi-frame tracking with map polylines
3. FGSM adversarial attack page (measured ε=0.05 → 54% drop)
4. Alert narrator (deterministic templates, 4 urgency tiers)
5. SHA-256 signed PDF mission reports
6. RTSP / HTTP / file:// URL stream ingest
7. EXIF-GPS auto-extraction → real-world AOI

**Docs in repo:**
- `PROJECT_SPEC.md` — original spec
- `README.md` — full project overview
- `docs/architecture.md` — technical architecture
- `docs/pitch-deck.md` — original pitch
- `docs/pitch-content.md` — copy-paste content bank
- `docs/demo-video-script.md` — recording script
- `docs/rehearsal-guide.md` — day-of guide
- `docs/runbook.md` — startup runbook
- `docs/v2-roadmap.md` — earlier post-v1 backlog
- `docs/slide-build-guide.md` — Google Slides tutorial
- `docs/demo-samples.md` — 5 hand-picked demo images at `D:\astra-data\demo-samples\`

**Last git commit:** `0f98051` (pitch-content.md). All work is in git on `main` branch.

---

## 🎯 Round 2 strategy — what wins from here

Three winning narratives we layer in:

1. **Specificity** — *"Not just 'aircraft.' Su-57 vs MiG-29 vs F-16."* (MAR20)
2. **Collective intelligence without data sharing** — federated learning across 3 simulated bases (FoolsGold)
3. **Adversarial-aware** — measured weakness AND mitigation curve (adversarial training)

Three research-paper-grade contributions to highlight:

- **Contribution 1:** Adversarial-aware sovereign ISR pipeline (FGSM in UI + adversarial-trained variant with measured curve)
- **Contribution 2:** Federated aerial detection with FoolsGold Sybil resistance
- **Contribution 3:** SAM-gated cascade detection-classification with OOD rejection

In pitch: *"Three contributions we believe are publishable."*

---

## 📅 96-HOUR SCHEDULE — hour by hour

### DAY 1 (hours 0-24) — Foundation upgrades

| Hour | Block | Deliverable |
|---|---|---|
| 00-04 | **MAR20 dataset acquisition + prep** | dataset downloaded, converted to YOLO format, train/val split |
| 04-10 | **MAR20 model training** (overnight if needed) | trained `astra-aircraft-v1.pt` with per-class mAP report |
| 10-14 | **Cascade integration** (YOLO → MAR20 on aircraft crops) | `aircraft_classifier.py`, pipeline updated |
| 14-18 | **Frontend: aircraft sub-class display** | Mission + Alerts show "Su-57 0.84" labels |
| 18-22 | **WebSocket real-time push** | backend broadcasts on every Detection write |
| 22-24 | **Frontend: Map live subscription** | pins POP onto map as pipeline runs |

**Day 1 result:** fine-grained military aircraft classification + true real-time push.

### DAY 2 (hours 24-48) — Federated + Adversarial Hardening

| Hour | Block | Deliverable |
|---|---|---|
| 24-28 | **Flower FL framework setup** (3 simulated nodes + 1 aggregator) | local orchestration |
| 28-34 | **DOTA 3-way geographic split** | per-node datasets ready |
| 34-40 | **Federated training run** (3-5 rounds with FedAvg) | global model > any single node |
| 40-44 | **FoolsGold poison detection** | sybil quarantine demo |
| 44-48 | **Federated dashboard page** (4 panels: node1, node2, node3, aggregator with mAP curves) | new sidebar page |
| 44-52 | **Adversarial training** (parallel track — retrain on FGSM-perturbed examples) | `astra-v1-hardened.pt` |
| 52-56 | **A/B comparison panel on Adversarial page** (v1 vs v1-hardened curves) | dramatic before/after |

**Day 2 result:** federated learning multi-base + adversarial hardening with measured mitigation.

### DAY 3 (hours 48-72) — Operational Realism

| Hour | Block | Deliverable |
|---|---|---|
| 48-52 | **SAM out-of-distribution gatekeeper** | unknown-class flagging |
| 52-56 | **Mission diff / change-detection** | "3 new vehicles since yesterday" |
| 56-62 | **Two-operator dual-control workflow** | escalated alerts need 2 confirmations |
| 62-66 | **Telegram bot integration** | high-threat → DM commander's phone |
| 66-70 | **RAG commander Q&A** (Phi-3.5 local + DB retrieval) | conversational interface |
| 70-72 | **Audio drone-detection sidecar** (optional) | dual-modality alert if time |
| 70-74 | **Replay scrub timeline UI** (video missions) | scrubbable playhead |
| 74-78 | **TensorRT INT8 export + benchmark** | 3rd performance number for slides |
| 78-80 | **Tamper-evident commit-chain audit** (hash-linked rows) | upgrade audit story |

**Day 3 result:** dual-control · mobile alerts · conversational interface · edge benchmark.

### DAY 4 (hours 72-96) — Polish + Pitch + Rehearsal

| Hour | Block | Deliverable |
|---|---|---|
| 72-76 | **End-to-end regression** of every feature | all 12+ features verified together |
| 76-82 | **New benchmark report** (per-class mAP both models, federated curve, adversarial v1 vs v1.2 curve, ensemble uncertainty histogram, Jetson INT8 numbers) | 1 stat-dense PDF |
| 82-86 | **Pitch deck v2 rebuild** (12 slides) | new deck |
| 86-90 | **Demo video re-record** (4 min cinematic) | fresh video |
| 90-94 | **Rehearsal × 5** with timer + Q&A drilling | smooth delivery |
| 94-96 | **Backup videos** for every demo | offline fallbacks |

---

## 📋 Feature specs (per major item)

### F-MAR20 — Fine-grained military aircraft

- **Dataset:** MAR20 from https://gcheng-nwpu.github.io/#Datasets (free, registration-light)
- **Classes:** 20 military aircraft variants (Su-57, MiG-29, F-16, F-22, B-2, A-10, C-130, C-17, P-3C, B-52, etc.)
- **Files:**
  - `training/prepare_mar20.py` (new) — convert MAR20 VOC-XML → YOLO format
  - `training/configs/astra-aircraft-v1.yaml` (new) — training config
  - `backend/app/inference/aircraft_classifier.py` (new) — classify aircraft crops
  - `backend/app/services/pipeline.py` — integrate cascade
  - `frontend/src/pages/Mission.tsx` — show sub-class label
  - `frontend/src/pages/Alerts.tsx` — show specific aircraft type
- **Acceptance:**
  - Trained model with per-class mAP report
  - Pipeline detects aircraft → crops → classifies → returns specific type with confidence
  - Frontend shows "Su-57 0.84" instead of just "aircraft-fixed-wing 0.92"

### F-WEBSOCKET — Real-time live push

- **Files:**
  - `backend/app/api/ws.py` — already has `pool.broadcast()` stub, wire up
  - `backend/app/services/pipeline.py` — call `pool.broadcast()` on each detection write
  - `frontend/src/pages/MapView.tsx` — subscribe to WS, append pins live
  - `frontend/src/pages/Mission.tsx` — optional: progress bar for video missions
- **Acceptance:** upload video → pins POP onto Map page in real time as pipeline progresses

### F-FEDERATED — Federated learning across 3 bases

- **Library:** `flwr` (Flower) — `pip install flwr`
- **Files:**
  - `federated/server.py` (new) — Flower aggregation server with SentinelStrategy(FedAvg + FoolsGold)
  - `federated/client.py` (new) — Flower client wrapping a YOLO model
  - `federated/foolsgold.py` (new) — cosine-similarity-based poison detection
  - `federated/run_demo.py` (new) — orchestrates 3 clients + 1 server
  - `frontend/src/pages/Federated.tsx` (new) — 4 panels with live mAP curves
  - `backend/app/api/federated.py` (new) — endpoint exposing federated state to UI
- **Acceptance:**
  - 3 nodes train on disjoint DOTA subsets, aggregator runs FedAvg + FoolsGold
  - Global model after 5 rounds beats any single node's local model
  - Inject sybil → FoolsGold flags + quarantines
  - UI shows live training curves per node

### F-ADV-TRAIN — Adversarial training mitigation

- **Files:**
  - `training/configs/astra-v1-hardened.yaml` (new) — same as v1 but with FGSM augmentation
  - `training/adversarial_augment.py` (new) — generate FGSM-perturbed batches during training
  - Re-run `train.py` to produce `astra-v1-hardened.pt`
  - `backend/app/api/adversarial.py` — accept `model_variant` param (v1 vs v1-hardened)
  - `frontend/src/pages/Adversarial.tsx` — A/B toggle between models, side-by-side curves
- **Acceptance:** v1 at ε=0.05 = 46% retention; v1-hardened at ε=0.05 = ≥75% retention

### F-SAM — SAM-based out-of-distribution gatekeeper

- **Library:** `segment-anything` (Meta SAM) — `pip install segment-anything`
- **Model:** `sam_vit_b_01ec64.pth` (~360 MB) to `D:/astra-data/models/`
- **Files:**
  - `backend/app/inference/sam_gate.py` (new) — segment image, count distinct objects
  - `backend/app/services/pipeline.py` — if SAM finds N objects but YOLO classifies K<N with high conf, flag (N-K) as "unknown / OOD"
  - `frontend/src/pages/Mission.tsx` — render OOD boxes in grey with "?"
- **Acceptance:** upload random non-DOTA image (e.g. building rooftops) → boxes show as "unknown" rather than misclassifying as ship/vehicle

### F-DIFF — Mission change detection

- **Files:**
  - `backend/app/api/diff.py` (new) — POST takes 2 mission IDs, returns added/removed/moved tracks
  - `frontend/src/pages/Map.tsx` or new `MissionDiff.tsx` — diff visualization
- **Acceptance:** upload same scene at 2 different times → diff shows new vs gone vs moved

### F-DUAL — Two-operator dual-control

- **Files:**
  - `backend/app/db/models.py` — Alert gains `confirmations` JSON field (list of {operator_id, timestamp})
  - `backend/app/api/alerts.py` — escalated alert needs 2 distinct operator_ids before "engaged" status
  - `frontend/src/pages/Alerts.tsx` — show "1/2 confirmations" badge
- **Acceptance:** escalate alert → confirm with cmdr-01 → button greyed for cmdr-01 → confirm with cmdr-02 → status → engaged

### F-TELEGRAM — Mobile alert bot

- **Setup:** create Telegram bot via @BotFather, save token to `.env` (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`)
- **Library:** `python-telegram-bot` or just `httpx` to Telegram Bot API
- **Files:**
  - `backend/app/services/notifier.py` (new) — `notify_telegram(message, image_path=None)`
  - `backend/app/services/pipeline.py` — call notifier on threat_score > 0.85
- **Acceptance:** upload high-threat image → phone buzzes with alert + thumbnail

### F-RAG — Conversational commander Q&A

- **Library:** `llama-cpp-python` + Phi-3.5-mini-instruct GGUF (~2.4 GB) at `D:/astra-data/models/`
- **Fallback:** rule-based Q&A on common queries (no LLM)
- **Files:**
  - `backend/app/services/rag.py` (new) — retrieve from DB + format prompt + call LLM
  - `backend/app/api/chat.py` (new) — POST /api/v1/chat with question
  - `frontend/src/pages/Chat.tsx` (new) — chat interface
- **Acceptance:** type *"What ships were detected near FOB Delta yesterday?"* → answer with counts and IDs

### F-TENSORRT — Edge benchmark

- **Tool:** Ultralytics' built-in TensorRT export
- **Files:**
  - `training/export_tensorrt.py` (new) — `model.export(format='engine', int8=True, dynamic=False)`
  - `training/benchmark.py` — add TensorRT INT8 lane
  - `frontend/src/pages/Benchmark.tsx` — add TensorRT row
- **Acceptance:** docs/benchmark-report.md gains TensorRT INT8 row · displayed on Benchmark page

---

## 🎤 Pitch deck v2 (12 slides)

| # | Title | Focus |
|---|---|---|
| 1 | The ISR avalanche, revisited | round-2 reminder + "we made it operational" |
| 2 | What's new since round 1 | 7 named features as a map |
| 3 | Live demo — fine-grained ID | upload image → "Su-57 Felon, 0.84" |
| 4 | Live demo — real-time + map | upload video → pins APPEAR live |
| 5 | Live demo — federated learning | 3-node split-screen, attack on node 1, all 3 improve |
| 6 | Live demo — adversarial mitigated | side-by-side v1 vs v1.2 curves |
| 7 | Live demo — Telegram alert | phone buzzes on stage |
| 8 | Architecture | 5-layer stack (added "edge alert" + "federated trust") |
| 9 | Numbers | 3 latency targets · 2 mAP targets · adversarial mitigation curve · federated convergence curve |
| 10 | Comparative edge | vs round 1, commercial, other Indian defence AI |
| 11 | Roadmap to deployment | DRDO integration · MIL-STD-882 · field trials |
| 12 | Close | "Sovereign. Explainable. Measured. Federated. Mitigated. Operational. Ready." |

---

## ⚙ Operator handoff protocol (4-shift rotation)

### Standing rules
1. **Every commit message = handoff doc.** Format: what shipped, what tested, what's next.
2. **Branch per feature** (`feat/mar20`, `feat/websocket`, `feat/federated`, `feat/sam`, etc.). Merge to main after E2E test passes.
3. **`docs/STANDUP.md`** updated at each shift change with: current task, blockers, next 4 hours.
4. **Never commit dirty.** `git status` must be clean before handoff.
5. **Daily 15-min sync at 24h boundaries.**
6. **Sleep is non-negotiable.** Max 12-hour shift.

### Tooling
- TodoWrite list = single source of truth for "what's left"
- All passwords / API keys (Telegram token, etc.) in `.env`
- Backend stays running on shared dev machine
- VS Code Live Share if 2 operators overlap

---

## 🚦 Risk matrix

| Risk | P | Mitigation |
|---|---|---|
| MAR20 dataset hard to download | M | Plan B: synthesize fine-grained labels via clustering DOTA `plane` crops |
| Federated training fails to converge | LM | Plan B: stage convergence with multiple training runs at different seeds |
| `llama-cpp-python` install breaks | M | Plan B: rule-based Q&A on canned questions, same UX |
| Telegram needs internet on demo day | L | Plan B: WhatsApp Web Click-to-Send + screen recording of phone notification |
| Adversarial training overruns | M | Plan B: ship adversarial DATA AUGMENTATION (cheaper) instead of full FGSM training |
| SAM model is 360 MB · slow CPU | LM | Plan B: only run SAM on user request, not every detection |
| TensorRT INT8 calibration fails | M | Plan B: TensorRT FP16 — still a 3rd benchmark number |

---

## 📝 On "start" — agent does these in order

1. **Health check** — Docker · backend `/health` · frontend :5173 · git status clean
2. **TodoWrite** — populate full Day-1 sub-tasks
3. **Begin Day 1, hour 0:** start MAR20 dataset acquisition
   - Direct user/operator to MAR20 download page
   - Write `training/prepare_mar20.py` while download proceeds
   - Verify image counts after extraction
4. **Hand off to MAR20 training** (background, ~6 hours)
5. **While training runs:** write WebSocket push integration (Day 1 hour 18-24 work brought forward)
6. **Commit per phase, gate before each major feature, no scope creep**

---

## 🏆 End-state target

**8-page dashboard** · **2 ML models** (general + aircraft fine-grained) · **federated multi-node** · **adversarial-mitigated** · **3 inference targets** (GPU FP32, CPU ONNX, Edge INT8) · **3 publishable contributions** · **12-slide pitch deck v2** · **5 live demo moments** (fine-grained, real-time, federated, adversarial-mitigated, telegram) · **mobile alerts** · **conversational interface** · **mission diff** · **dual-control workflow** · **SAM-gated OOD rejection** · **fresh 4-min demo video** · **rehearsal × 5**

That's 3-4× the surface area of round 1. Every item is judge-defensible. Trophy material.
