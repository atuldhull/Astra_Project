# ASTRA Round 2 — Release Notes

**Version:** v0.2.0
**Tag:** `v0.2.0-round2`
**Status:** Shipped — all 10 R2 features verified end-to-end via `python scripts/e2e_regression.py` → ALL GREEN.
**Sprint:** 96-hour build (4 days) per [docs/round2-warplan.md](round2-warplan.md).

---

## What shipped

### 1. Stage-2 fine-grained airframe classifier (cascade)
- **Model:** YOLOv11n-cls trained on MAR20 (3,842 images, 22,341 crops, 20 military airframes — F-22, Su-35, B-52, P-3C, KC-135, …)
- **Numbers:** **89.03% top-1**, **99.32% top-5**, 0.5 ms/crop, 3.2 MB on disk
- **How it works:** stage-1 detector emits `aircraft-fixed-wing` boxes; pipeline crops each, feeds to stage-2; result stored in `detections.extras_json` as `{airframe, airframe_confidence, airframe_top3}`
- **Visible:** Mission video overlay shows `E-8 0.90` instead of `aircraft-fixed-wing 0.92`; "Airframes ID'd · MAR20 cascade" sidebar panel; Map popup shows `⤷ E-8 (90%)`
- **Files:** [training/prepare_mar20.py](../training/prepare_mar20.py), [training/configs/astra-aircraft-v1.yaml](../training/configs/astra-aircraft-v1.yaml), [backend/app/inference/aircraft_classifier.py](../backend/app/inference/aircraft_classifier.py)

### 2. Federated learning + FoolsGold Sybil resistance
- **Library:** in-process FedAvg orchestrator (no Flower/gRPC — one process, no network failure modes)
- **Algorithm:** faithful re-implementation of Fung et al., RAID 2020 — per-pair pardon, post-pardon row-max → 1-wv → logit amplification → quarantine
- **Numbers:**
  - Baseline (3 honest non-IID): 17% → **60%** over 5 rounds, all clients trusted
  - Attack (3 honest + 2 colluding Sybils, label-flipped): attackers get aggregation weight **0.000**, honest 3 still aggregate, **76% accuracy**
  - **Δ from defense: +76 percentage points** (without FoolsGold, model collapses to 0%)
- **Visible:** new `Federated` page with 4 panels (global accuracy curve, per-client local accuracy, FoolsGold weight bars, quarantine status), 3-second polling
- **Files:** [federated/](../federated/), [backend/app/api/federated.py](../backend/app/api/federated.py), [frontend/src/pages/Federated.tsx](../frontend/src/pages/Federated.tsx)

### 3. Adversarial-aware A/B
- **v1:** Round-1 baseline DOTA detector
- **v1-hardened:** 10-epoch fine-tune from `astra-v1.pt` on FGSM-augmented training tiles (2,950 perturbed copies) + cranked HSV/rotation augmentation
- **Numbers (FGSM ε=0.05 retention):**
  | Image | v1 | v1-hardened | Δ |
  |---|---:|---:|---:|
  | 01-vehicle-convoy | 13% | 11% | -2 pp |
  | 02-airfield-hero | 29% | 23% | -6 pp |
  | 03-naval-port | 68% | 10% | -58 pp |
  | 04-mixed-scene | 56% | 65% | **+9 pp** |
  | **05-helipad** | **0%** | **80%** | **+80 pp** |
- **Honest disclosure:** FGSM-augmentation defense is **partial** — dramatic on some attack surfaces, neutral on others. Full PGD adversarial training is the v3 roadmap item. The pitch leads with the helipad win.
- **Visible:** Adversarial page gains v1 / v1-hardened picker (greys out missing variants); A/B retention strip shows both retention pcts + delta
- **Files:** [training/adversarial_augment.py](../training/adversarial_augment.py), [training/configs/astra-v1-hardened.yaml](../training/configs/astra-v1-hardened.yaml), [backend/app/inference/adversarial.py](../backend/app/inference/adversarial.py), [backend/app/api/adversarial.py](../backend/app/api/adversarial.py), [frontend/src/pages/Adversarial.tsx](../frontend/src/pages/Adversarial.tsx)
- **FGSM repair:** newer Ultralytics wraps the Detect head's `_inference` in `torch.inference_mode()`, breaking gradient backprop. Round-1 silently fell back to noise (reporting fake 93% retention). Fixed by switching the inner model to `train()` mode for the forward pass — train-mode head returns dict `{boxes, scores, feats}` with un-tainted tensors.

### 4. Out-of-distribution gatekeeper
- **Approach:** lightweight per-detection 0..1 score from three signals — low confidence (vs per-class floor), anomalous aspect ratio (vs per-class typical range), low edge density (Canny inside bbox). Threshold = 0.55.
- **No SAM weights required** (360 MB download avoided). SAM hook stub kept in `ood_gate.sam_available()` for v3 upgrade.
- **Visible:** OOD-flagged detections render dashed-grey with `?` prefix on Mission video overlay and as smaller transparent pins on Map. Popup tooltip shows the trigger reasons.
- **Files:** [backend/app/inference/ood_gate.py](../backend/app/inference/ood_gate.py)

### 5. Operational realism layer
- **WebSocket live push:** pipeline broadcasts on every Detection+Alert write; Map page subscribes via `/ws/live`, refetches on each event, LIVE indicator pulses with auto-reconnect
- **Mission diff:** POST `/api/v1/diff` with `(earlier, later)` mission ids; greedy nearest-neighbour same-class matching with configurable radius + move threshold; new `Diff` page with 3-color Leaflet view
- **Dual-operator engage workflow:** new `engaged` AlertStatus; `engage` action requires alert in `escalated` state and rejects duplicate operator IDs (HTTP 409); transitions only when 2 distinct operator IDs have confirmed; new audit event types `alert_confirmation` (partial) + `alert_engaged` (final)
- **Telegram bot:** httpx-based notifier in [backend/app/services/notifier.py](../backend/app/services/notifier.py); fires when `threat_score >= TELEGRAM_ALERT_THRESHOLD` (default 0.85); silently no-ops if env vars absent
- **Tamper-evident audit chain:** `audit_events.prev_hash + row_hash` (SHA-256 hex) — each row chains to its predecessor's hash; `GET /api/v1/audit/verify` walks the chain and returns first broken row id; Audit page header gains green/red `chain ok` / `chain broken @ #N` badge

### 6. Edge benchmark export
- **TensorRT INT8 export script:** [training/export_tensorrt.py](../training/export_tensorrt.py) — Ultralytics built-in exporter with INT8 attempt and FP16 fallback; built-in latency benchmark (50 runs on dummy image)
- **Operator-run on the deployment device** (engines aren't portable across GPUs)

---

## Migration notes (since R1)

The R1 → R2 migration is a single command:
```bash
python backend/scripts/init_db.py
```
Idempotent. Adds 4 columns (`detections.extras_json`, `alerts.confirmations_json`, `audit_events.prev_hash`, `audit_events.row_hash`), 3 Postgres enum values (`alertstatus.engaged`, `auditeventtype.alert_confirmation`, `auditeventtype.alert_engaged`), and backfills the audit hash chain from genesis (re-walks every row and rewrites mismatched hashes).

---

## E2E regression — go/no-go for the demo

```bash
python scripts/e2e_regression.py
```
Hits 10 feature checkpoints. Latest run on the live backend: **ALL GREEN — 83 audit rows verified, 14 detections produced, 13/14 cascade fired, dual-control engage E2E correct, federated curve has 6 points, FoolsGold quarantined 2 Sybils.**

Exit code 0 = ship-ready. Non-zero = fix before stage.

---

## What we deferred (honest list)

| Item | Why | Status |
|---|---|---|
| Real PGD adversarial training | ~2-4 hour additional training run on a custom loop; FGSM-augmentation hits the time/value sweet spot for a hackathon | v3 roadmap |
| RAG commander Q&A (Phi-3.5 + retrieval) | Scope creep risk inside 96 hours; deterministic narrator covers the same conversational use case | v3 roadmap |
| Video scrub timeline UI | Optional; current playback already syncs boxes to `videoCurrentTime` | v3 roadmap |
| Full SAM 360 MB OOD model | Lightweight Canny+aspect heuristic delivers same demo signal at zero download cost | v3 roadmap (hook stub present) |
| Live multi-machine federated (real Flower/gRPC) | In-process orchestrator is more reliable on Windows for a single-machine demo; algorithmic content (FoolsGold) is identical | v3 roadmap |

---

## Codebase changes — by the numbers

```
git log --oneline 5a8bbd8..HEAD | wc -l    # commits since Day 2 mid
git diff 0f98051 HEAD --shortstat          # since Round-1 final
```
- **6 Round-2 commits** + 1 follow-up patch
- **~3,800 lines added** across backend, frontend, training, federated, scripts, docs
- **10 new files** (3 backend api + 1 backend inference + 1 backend service + 2 frontend pages + 6 federated package files + 3 training files + 2 docs + 1 scripts)
- **2 new sidebar nav entries** (Federated, Diff)
- **1 new model variant** (`astra-v1-hardened.pt`)
- **1 new model task** (cls — `astra-aircraft-v1.pt`)

---

## Pitch handoff

For the actual presentation:
- **Pitch content & talking script:** [docs/pitch-content-r2.md](pitch-content-r2.md) (12 slides, 30s/60s/4min variants, demo failure recovery cheatsheet)
- **Numbers reference:** [docs/benchmark-report.md](benchmark-report.md) (every claim sourced)
- **Pre-demo checklist:** end of `pitch-content-r2.md` (T-30 minute commands)

Run the E2E regression at T-30. If it returns red, **don't go on stage** — fix it.

---

**Three publishable contributions, one project, five days. Trophy material.**
