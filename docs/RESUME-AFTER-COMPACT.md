# ASTRA — Resume After Compact

> **Read this first** if context was compacted. This doc + the linked
> companion docs are the single source of truth for the project state.

---

## TL;DR — what is this?

**ASTRA** = Aerial Surveillance & Threat Recognition Assistant.
Sovereign, explainable, edge-deployable AI for aerial target recognition.
Built for **BMSIT&M Defence-Tech Expo 2026, Bengaluru** (target Apr 30).

- **Round 1** PASSED → 8-class DOTA detector, dashboard, signed PDFs.
- **Round 2** SHIPPED → fine-grained MAR20 cascade, federated FoolsGold, adversarial A/B, dual-control, hash-chain audit. Tag `v0.2.0-round2`.
- **Round 3** SHIPPED → command-center frontend overhaul + 22 features. Tag `v0.3.0-round3`. **HEAD: `73483b9`**.

The user is satisfied with the visual layer after R3 ship.

---

## Where to find every piece

| Role | File |
|---|---|
| **Round-2 war plan** | `docs/round2-warplan.md` |
| **Round-3 sprint plan** | `docs/round3-workflow.md` |
| **Round-2 release notes** | `docs/RELEASE-R2.md` |
| **Round-3 release notes (canonical)** | `docs/RELEASE-R3.md` |
| **Operator runbook** (5 manual tasks) | `docs/OPERATOR-R3.md` |
| **Pitch content** (12 slides + script + recovery cheatsheet) | `docs/pitch-content-r2.md` |
| **Pitch PDF (R3)** | `docs/astra-pitch-r3.pdf` |
| **Benchmark numbers** | `docs/benchmark-report.md` |
| **Demo failure recovery** | `docs/pitch-content-r2.md` (cheatsheet section) |
| **Pre-demo checklist** | `docs/pitch-content-r2.md` (T-30 min section) |

---

## Tech stack (do NOT redeploy if user asks "set up X")

- **Frontend:** React 18 + Vite + TypeScript + Tailwind + Leaflet + Recharts
- **Backend:** FastAPI + Pydantic + SQLAlchemy 2 + Postgres 16 + Redis 7 (Docker)
- **ML:** Ultralytics YOLOv11n (DOTA stage-1) + YOLOv11n-cls (MAR20 stage-2). 5.5 MB + 3.2 MB models.
- **Federated:** in-process FedAvg + FoolsGold + optional DP-SGD (no Flower gRPC; deferred deliberately)
- **Auth:** custom HMAC-SHA256 JWT (no python-jose/pyjwt dep). OFF by default; flip `ASTRA_AUTH_ENABLED=1`.
- **OS:** Windows 11 + Python 3.11/3.13. Venv at `D:/astra-data/venvs/astra/`. Data root at `D:/astra-data/`.

---

## Critical paths to remember

```
Repo root          /c/Users/atuld/OneDrive/Desktop/astra
Data root          D:/astra-data
Venv python        D:/astra-data/venvs/astra/Scripts/python.exe
Stage-1 weights    D:/astra-data/weights/astra-v1.pt           (5.5 MB)
Stage-1 ONNX       D:/astra-data/weights/astra-v1.onnx
Stage-1 hardened   D:/astra-data/weights/astra-v1-hardened.pt  (R2 augmented; R3 ships PGD script for proper redo)
Stage-2 cascade    D:/astra-data/runs/astra-aircraft-v1/weights/best.pt (3.2 MB, picked up by aircraft_classifier.py lazily)
MAR20 dataset      D:/astra-data/datasets/MAR20/         (3,842 imgs, 20 airframes)
MAR20 cls dataset  D:/astra-data/datasets/mar20-cls/     (cropped, train/val per-class folders)
DOTA dataset       D:/astra-data/datasets/astra-v1/      (9,832 tiles 1024² @ 20% overlap, 8 classes)
Federated log      D:/astra-data/federated/run.jsonl
Demo samples       D:/astra-data/demo-samples/01-vehicle-convoy.jpg ... 05-helipad.jpg
```

---

## Run commands (reference)

### Daily 3-terminal startup
```bash
# T1 — Docker
docker compose -f /c/Users/atuld/OneDrive/Desktop/astra/docker-compose.yml up -d

# T2 — Backend
cd /c/Users/atuld/OneDrive/Desktop/astra/backend
D:/astra-data/venvs/astra/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# T3 — Frontend
cd /c/Users/atuld/OneDrive/Desktop/astra/frontend
npm run dev
```
Open `http://localhost:5173`.

### When port 8000 is taken (zombie backend)
```bash
netstat -ano | grep ":8000.*LISTENING"   # note the PID
taskkill //PID <PID> //F
```

### Pre-demo go/no-go
```bash
D:/astra-data/venvs/astra/Scripts/python.exe scripts/e2e_regression.py
# expect "ALL GREEN — Round 2 features verified."
```

### Operator-only commands (all in `docs/OPERATOR-R3.md`)
- F2 Telegram: edit `.env`, restart backend.
- F5 TensorRT: `python training/export_tensorrt.py --int8`
- F1 PGD: `python training/pgd_finetune.py --epochs 5`
- F8 Federated MAR20: `python -m federated.run_demo --task mar20 ...`
- F6 LLM upgrade: drop Phi-3.5 GGUF + `pip install llama-cpp-python`
- F18 Continual: `python training/continual_finetune.py`

---

## Feature matrix (every R2 + R3 capability)

### Sidebar pages (10 total)
1. **Command** (R3, home `/command`) — 10-tile tactical wall, live-polling, accent-coded cells
2. **Mission** — Bezel + HUD viewer with REC/GPS/TRK/ID corner chips, telemetry strips
3. **Map** — TAC·MAP bezel, heatmap toggle, LIVE pulse, pin POP from WS
4. **Alerts** — threat-frequency waveform, dual-control engage workflow, ranked queue
5. **Audit** — animated SHA-256 chain ribbon, verify button, terminal-tail log
6. **Benchmark** — race-the-targets bars + per-class radar + cascade mini-board
7. **Adversarial** — v1 / v1-hardened picker, A/B retention gauges
8. **Federated** — radial topology + flow dots + 4 panels (acc/per-client/weights/quarantine)
9. **Diff** — Leaflet color-coded diff + Δ-by-class histogram
10. **Chat** — RAG/rule-based commander Q&A
11. (`/login` — operator console; not in sidebar)

### Behind the scenes
- WebSocket `/ws/live` real-time push (pipeline → Map LIVE pulse)
- SHA-256 hash-chained audit (`audit_events.prev_hash + row_hash`)
- Two-stage cascade: `aircraft_classifier.py` runs MAR20 cls on every aircraft det
- OOD gatekeeper (`backend/app/inference/ood_gate.py`) — conf + aspect + edge-density
- FoolsGold cosine-similarity Sybil quarantine (`federated/foolsgold.py`)
- Optional DP-SGD (`--dp-sigma N` on run_demo)
- JWT auth (HMAC-SHA256, default OFF)
- Telegram fan-out (env-controlled, threshold-gated)
- 3 themes: dark / commander green-on-black / light
- Splash boot screen + onboarding tour (Shepherd-free, custom)
- TacticalBackground atmospheric layer behind every page

### Numbers to know (for any question)
- DOTA stage-1 mAP@0.5: **0.515** (aircraft 0.92, ship 0.77)
- MAR20 stage-2 top-1: **89.03%**, top-5: **99.32%**
- GPU latency: 22 ms · CPU ONNX: 36 ms · cascade overhead: +0.5 ms
- Adversarial helipad: v1 **0%** retention, v1-hardened **80%** at ε=0.05
- Federated under attack: WITHOUT FoolsGold **0%**, WITH FoolsGold **76%** accuracy
- Audit chain: 100+ rows verified ok
- Total model size: **8.7 MB** (5.5 + 3.2)

---

## Live state at compact time

- Backend was **RUNNING** when user announced compact (started in bg as task `bgriq6dv9`).
- It listens on `127.0.0.1:8000`, model_loaded=true, device=cuda:0.
- Frontend was last running on `localhost:5173` (vite dev server in user's terminal).
- Latest fix: commit `73483b9` — fixed `chat` not in `app/api/__init__.py` import line. Backend was crashing with `NameError: name 'chat' is not defined` until that landed.
- Port 8000 currently held by uvicorn process. If user reports backend down, check zombie PID + restart.

---

## Bugs encountered + how they were fixed

1. **R2 Postgres enum migration:** `Base.metadata.create_all` doesn't add new enum values. Fixed in `init_db.py` with explicit `ALTER TYPE auditeventtype ADD VALUE IF NOT EXISTS`.
2. **R2 audit chain backfill:** repair logic only handled NULL hashes; rows written with bad chain remained broken. Fixed by re-walking and rewriting any mismatched row from genesis.
3. **R2 FGSM falling back to noise:** newer Ultralytics wraps `_inference` in `torch.inference_mode()` which broke gradient backprop. Fixed by switching inner model to `train()` mode + handling new dict-shaped output `{boxes, scores, feats}`.
4. **R3 Tailwind JIT col-span bug:** `col-span-${n}` template literal classes don't get emitted. Fixed by hard-coding `SPAN_CLS` lookup in Command Center Tile.
5. **R3 chat import bug** (just now, `73483b9`): `chat.router` registered but `chat` not in import line → NameError on backend startup. Fixed by adding `chat` to the alphabetised import.
6. **R3 backend zombie** (just now): old backend instance crashed mid-request, held port 8000 with 1 MB RAM. Fix: `taskkill //PID <id> //F` then restart.

---

## Operator deferred / won't-do

- **F7 Real Flower gRPC** — in-process orchestrator covers algorithmic story; gRPC adds Windows port-binding fragility for zero pitch gain.
- **F14 Mission compare standalone** — Diff page Δ-histogram + Leaflet diff already covers the demo signal.
- **F15 Replay scrub** — HTML5 video controls already provide scrubbing + Mission.tsx syncs boxes to `videoCurrentTime`.
- **F16 Multi-modal audio (YAMNet)** — domain mismatch (YAMNet on aerial drone audio is research, not hackathon).
- **F19 MHT (Multi-Hypothesis Tracking)** — replacing ByteTrack is regression risk for zero pitch gain on demo footage.

---

## What's left for the user (operator-only)

| Task | Time | Doc |
|---|---|---|
| Telegram bot setup | 10 min | `docs/OPERATOR-R3.md` §F2 |
| TensorRT INT8 export | 30 min | `docs/OPERATOR-R3.md` §F5 |
| PGD adversarial training | 2-4h GPU | `docs/OPERATOR-R3.md` §F1 |
| MAR20 federated training | 1h GPU | `docs/OPERATOR-R3.md` §F8 |
| Phi-3.5 GGUF for LLM Q&A | 10 min | `docs/OPERATOR-R3.md` §F6 |
| Demo video re-record | 30 min | use Playwright `e2e/demo.spec.ts` |
| Rehearsal × 5 | varies | `docs/pitch-content-r2.md` slot timing |

None of these block the demo — codebase ships without them. Each adds a specific demo moment.

---

## When the user says "start" or "continue" after compact

1. **Don't re-do work.** Round 1 + 2 + 3 are SHIPPED. Don't rebuild.
2. **Read this doc first.** Then `docs/RELEASE-R3.md` for the feature matrix.
3. **Check git state** with `git log --oneline -10` and confirm tag `v0.3.0-round3` exists.
4. **If user says "run X" or "demo Y"** → look up the command in this doc's "Run commands" section.
5. **If user reports broken thing** → check `docs/pitch-content-r2.md` failure recovery cheatsheet first; many issues have a known fix.
6. **If user wants new feature** → it goes in a Round 4 sprint plan; do not bolt onto R3.

---

## Single-line resume

> ASTRA shipped at `v0.3.0-round3` (commit `73483b9`). 22 R3 features
> stacked on R2's 10. Frontend cinematic. Backend zombie occasionally
> needs `taskkill //PID <id> //F` on port 8000. Operator runbook in
> `docs/OPERATOR-R3.md`. Pitch in `docs/pitch-content-r2.md`. Numbers in
> `docs/benchmark-report.md`. Don't rebuild — extend.
