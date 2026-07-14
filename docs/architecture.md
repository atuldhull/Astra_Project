# ASTRA — Technical Architecture

> Single-page technical overview. If you're reviewing the repo after the pitch and want to understand how it hangs together, start here.

## Design principles

1. **Sovereign** — Zero external API calls. Everything — model weights, map tiles (with a cached OSM layer in production), PDF generation, LLM narrator — runs on the local machine. The system is compatible with fully air-gapped deployment.
2. **Explainable** — Every detection can be explained at two levels: *pixel-level* via Grad-CAM heatmap, and *decision-level* via the transparent threat-score breakdown surfaced in the UI and in every PDF report.
3. **Human-in-the-loop** — The system is *assistive*. There is no autonomous-engagement path, by design. Every commander action (confirm / reject / escalate / weight change) writes a timestamped, operator-attributed row to an append-only audit log.
4. **Robustness-tested** — We measure the model's adversarial weakness rather than claiming robustness. An FGSM-based attack page exposes the ε → detection-drop curve.

## Four-layer stack

```
┌─────────────────────────────────────────────────────────────────────────┐
│  LAYER 4 — Command & Control                                             │
│                                                                          │
│  React 18 + Vite + TypeScript + Tailwind + Leaflet + Recharts           │
│                                                                          │
│  ┌─────────┐  ┌───────┐  ┌────────┐  ┌───────┐  ┌──────────┐  ┌────────┐│
│  │ Mission │  │  Map  │  │ Alerts │  │ Audit │  │ Benchmark│  │ Advers.││
│  │ upload  │  │ geo-  │  │ ranked │  │ log + │  │   mAP +  │  │  FGSM  ││
│  │ + boxes │  │ pins  │  │ queue  │  │  PDF  │  │  charts  │  │ slider ││
│  └─────────┘  └───────┘  └────────┘  └───────┘  └──────────┘  └────────┘│
└────────────────────────────────┬────────────────────────────────────────┘
                                 │ REST + WebSocket
┌────────────────────────────────┴────────────────────────────────────────┐
│  LAYER 3 — Fusion & Reasoning                                            │
│                                                                          │
│  ┌───────────────┐  ┌──────────────┐  ┌───────────────┐  ┌─────────────┐│
│  │  ByteTrack    │  │   georef     │  │  scoring.py   │  │ narrator.py ││
│  │  persistent   │  │   AOI-corner │  │  5-term       │  │ 4 urgency   ││
│  │  track_ids    │  │   bilinear   │  │  threat score │  │ tiers + hint││
│  └───────────────┘  └──────────────┘  └───────────────┘  └─────────────┘│
│                                                                          │
│  ┌───────────────────┐  ┌──────────────────┐  ┌──────────────────┐      │
│  │   gradcam.py      │  │ adversarial.py   │  │   reports.py     │      │
│  │   EigenCAM SVD    │  │   FGSM + noise   │  │ reportlab PDF    │      │
│  │   on C2PSA layer  │  │   gradient-based │  │ SHA-256 signed   │      │
│  └───────────────────┘  └──────────────────┘  └──────────────────┘      │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
┌────────────────────────────────┴────────────────────────────────────────┐
│  LAYER 2 — Inference                                                     │
│                                                                          │
│  YOLOv11-nano · 2.6M params · 22.3 ms GPU / 36 ms CPU                   │
│  · trained on DOTA-v1.5 tiled to 1024² with 20% overlap                  │
│  · mAP@0.5 = 0.515 overall, 0.915 on aircraft-fixed-wing                 │
│  · 8 classes (small/large vehicle, fixed/rotor aircraft, ship,           │
│                storage-depot, harbor, bridge)                            │
│  · ONNX exportable · 5.5 MB post-optimization                            │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │ cv2.VideoCapture / UploadFile
┌────────────────────────────────┴────────────────────────────────────────┐
│  LAYER 1 — Ingest                                                        │
│                                                                          │
│  File upload (PNG/JPG/MP4/MOV) │ RTSP/HTTP/HTTPS stream │ file://        │
│  cv2 + FFmpeg backend · letterbox 640² · RGB normalize                   │
└──────────────────────────────────────────────────────────────────────────┘
```

## Data flow

### Image mission
```
Mission.tsx upload                                         Alerts.tsx
     │                                                          ▲
     │  POST /api/v1/predict   ──►  detector.detect()          │
     │  ◄── boxes (JSON)                                        │
     │  (instant canvas overlay)                                │
     │                                                          │
     │  POST /api/v1/ingest    ──►  BackgroundTask             │
     │  ◄── mission_id              process_mission()           │
     │                                 │                        │
     │                                 ├── detector.detect()    │
     │                                 ├── georef.pixel_to_latlon
     │                                 ├── scoring.compute_score│
     │                                 ├── narrator.narrate()   │
     │                                 └── write Detection +    │
     │                                          Alert + Audit   │
     │                                                          │
     └──────────── localStorage lastMissionId ──► Map/Alerts ───┘
                                                   poll /detections + /alerts
```

### Video mission
```
Mission.tsx upload                                         Map.tsx
     │                                                          ▲
     │  POST /api/v1/ingest    ──►  BackgroundTask             │
     │  ◄── mission_id              process_mission()           │
     │                                 │                        │
     │                                 └── detector.detect_and_track_video()
     │                                        │                 │
     │                                        ├── ultralytics model.track
     │                                        │   (persist=True, bytetrack)
     │                                        ├── per-frame record with
     │                                        │   stable track_id               │
     │                                        └── write Detection(track_id)     │
     │                                                          │
     │  Poll /detections ──► videoDets ──► canvas overlay       │
     │                       synced to video.currentTime        │
     │                                                          │
     │  GET /api/v1/tracks ─► track polylines on Leaflet ───────┘
```

### Adversarial page
```
Adversarial.tsx
     │
     │  POST /api/v1/adversarial
     │   file + epsilon + method
     │
     │        │
     │        ├── detector.detect(original)      ──► N detections
     │        │
     │        ├── adversarial.perturb_fgsm()
     │        │    - preprocess to 640² RGB tensor
     │        │    - x.requires_grad = True
     │        │    - forward pass through DetectionModel
     │        │    - loss = mean(top-32 max-class-sigmoid)
     │        │    - backward to get ∂loss/∂x
     │        │    - x_adv = x - ε·sign(∂loss/∂x)
     │        │
     │        ├── detector.detect(perturbed)     ──► M detections
     │        │
     │        └── return {original, perturbed, base64_image, latency}
     │
     │  ◄── JSON with both summaries + perturbed image inline
     │
     │  Render side-by-side with box overlays on each
```

## Threat scoring formula

From `backend/app/fusion/scoring.py`:

```
threat_score =  w_class  × class_weight[class_name]
             +  w_prox   × exp(-distance_km / 5.0)
             +  w_motion × movement_toward_asset      (0..1)
             +  w_count  × log(1 + N_same_class - 1)
             +  w_conf   × detection_confidence

Default weights: w_class=0.35, w_prox=0.25, w_motion=0.20, w_count=0.10, w_conf=0.10
Default class weights: aircraft=0.9, large-veh=0.6, ship=0.7, …
Clamped to [0, 1].
```

The **Alerts** page surfaces all five terms in the `score_breakdown_json` of every alert. Dragging weight sliders client-side recomputes the score from the per-term raw values (recovered by dividing the term by its default weight).

## Audit trail

`AuditEvent` rows are **append-only**:

| field | content |
|---|---|
| `id` | auto-increment PK |
| `event_type` | `ingest_started` · `ingest_completed` · `alert_confirmed` · `alert_rejected` · `alert_reclassified` · `alert_escalated` · `weights_changed` |
| `operator_id` | string (commander identity) |
| `mission_id` | nullable FK |
| `alert_id` | nullable FK |
| `payload_json` | JSON-B with event-specific detail (filename, bytes, reason, etc.) |
| `created_at` | `server_default=NOW()` |

The PDF mission-report generator computes a SHA-256 hash over the canonical JSON summary of the report body (mission name, detection counts, class counts, status counts, detection/alert IDs) and embeds it at the footer. Any post-generation tampering of the content fields invalidates the signature.

## Key numbers

### Model
| | Value |
|---|---|
| Backbone | YOLOv11n (Ultralytics 8.4.41) |
| Parameters | 2.6 M |
| Training resolution | 640² (tiled from 1024² DOTA imagery during prep) |
| Training hardware | RTX 4050 Laptop GPU, 6 GB VRAM |
| Training time | 1.888 hours (40 epochs, fraction=0.3) |
| GPU inference | 22.3 ms (FP32) / 44.9 FPS |
| CPU inference | 36 ms (ONNX FP32) / 28 FPS |
| Model file | 5.5 MB (`.pt` + `.onnx` both that size) |

### Accuracy (DOTA-v1.5 val, 1,561 images, 67k objects)
| Class | mAP@0.5 |
|---|---|
| aircraft-fixed-wing | **0.915** |
| ship | 0.770 |
| harbor | 0.733 |
| large-vehicle | 0.660 |
| small-vehicle | 0.408 |
| storage-depot | 0.393 |
| aircraft-rotor | 0.242 |
| bridge | 0.000 (OBB→AABB bug, roadmap v1.1) |
| **Overall** | **0.515** |

### Adversarial robustness (FGSM, measured live)
| ε | detections retained | signal |
|---|---|---|
| 0.00 | 100% | baseline |
| 0.02 | 77% | light degradation |
| **0.05** | **46%** | **vehicle classes collapse** |
| 0.08 | 54% | class confusion |
| 0.12 | catastrophic | false-positive bloom |

## Security properties

| Claim | Mechanism |
|---|---|
| No external calls | All models + datasets local · no third-party API clients in requirements.txt · map tiles cacheable for air-gap |
| Tamper-evident audit | Append-only rows + SHA-256 report signatures |
| Operator attribution | Every write-action carries `operator_id`; default `cmdr-01` |
| Explainable per-alert | Grad-CAM pixel heatmap · 5-term score breakdown · narrator sentence |
| Model integrity | `ASTRA_MODEL_PATH` in `.env` · checksum exposure in `/health` on roadmap |
| Sovereign deployment path | Runs on 6GB consumer GPU · Jetson Nano compatible · ONNX Runtime CPU fallback |

## What we don't claim

- **Production-ready**: This is a hackathon build. Operational deployment requires data validation, MIL-STD safety case, integration testing.
- **Adversarial-hardened**: Measured weakness exists. Mitigation (adversarial training + randomized smoothing) is roadmap v1.2.
- **Perfect detection**: bridge class is broken due to OBB→AABB preprocessing. Honest in pitch + roadmap.
- **Multi-base tested**: single-node today. Federated training across bases is v2.0.

## Dependency graph (high-level)

### Python runtime
- torch 2.6.0+cu124
- ultralytics 8.4.41 (YOLO, ByteTrack, ONNX export)
- fastapi 0.115 · uvicorn · starlette · pydantic 2
- sqlalchemy 2 · psycopg2-binary · redis
- opencv-python · numpy · scipy · shapely · pyproj · rasterio
- onnx · onnxruntime-gpu
- reportlab (PDF)
- grad-cam (EigenCAM class — though we implement direct SVD via hooks)

### Front-end
- react 18 · vite 6 · typescript 5.7
- tailwindcss 3 · autoprefixer
- leaflet 1.9 + react-leaflet 4 (maps)
- recharts 2 (benchmark charts)
- lucide-react (icons)
- zustand (state, reserved)
- react-router-dom 6

### Infra
- postgres 16-alpine (compose)
- redis 7-alpine (compose)

## Extension paths

| Upgrade | Files to touch | Effort |
|---|---|---|
| Real Phi-3.5 LLM narrator | `fusion/narrator.py` has a stubbed hook; install `llama-cpp-python`, drop GGUF in `$ASTRA_DATA_DIR/models/` | 4 hrs |
| MAR20 fine-grained aircraft | `training/prepare_mar20.py` + `inference/aircraft_classifier.py` | 8-10 hrs |
| Federated training | Flower FL server + per-node trainer wrapper | 1-2 days |
| Rotated bboxes (bridge fix) | YOLO-OBB variant + label format change | 1 day retraining |
| Multi-camera fusion | Multi-Mission alignment + cross-stream tracker | 1 week |

See [v2-roadmap.md](v2-roadmap.md) for the full backlog with per-feature specs.
