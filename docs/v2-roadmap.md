# ASTRA v2 Roadmap — What We Can Still Add (pre-Apr 30)

> **Built-today baseline:** v1.0 complete — trained yolo11n, live inference, Grad-CAM explainability, geo-ref map, ranked alerts, audit log, benchmark page, pitch deck, demo video script, rehearsal guide.
>
> **Remaining runway:** 6 days (Apr 24 → Apr 30 event).
>
> **Hard constraints:**
> - Don't break the working v1 demo — all additions are additive, reversible
> - Every feature must work on the RTX 4050 6GB laptop
> - Every feature must run 100% offline (sovereign)
> - No feature is worth risking demo-day stability

---

## SECTION A — Strategic priorities

### Your pitch's weakest flanks (where judges will attack)

| Risk | Judge objection | Current defence | Potential fix |
|---|---|---|---|
| **1** | *"YOLO is a known-technology — what's novel?"* | "Grad-CAM + sovereign architecture" (decent) | Add adversarial robustness demo + novel augmentation (stronger) |
| **2** | *"You detect, but do you track?"* | "Single-frame only — roadmap" (weak) | Add ByteTrack on video (fixes it) |
| **3** | *"How is this 'military'? It's just object detection."* | "DOTA has planes, ships" (thin) | Fine-tune on MAR20 → actual Su-57 / MiG-29 variants (strong) |
| **4** | *"Your model is deterministic — what about explainability BEYOND heatmaps?"* | "Grad-CAM per box" (good) | Add LLM narrator generating natural-language justifications (stronger) |
| **5** | *"How does this scale — one laptop can't defend India."* | "Jetson roadmap" (acceptable) | Add federated-learning conceptual demo (SENTINEL-style) |

### Impact × effort matrix

| Feature | Pitch impact | Time | Risk | Priority |
|---|---|---|---|---|
| **F1 — Video + ByteTrack** | ★★★★★ | 6 hrs | Low | **DO FIRST** |
| **F2 — MAR20 fine-grained aircraft** | ★★★★☆ | 8-10 hrs | Medium (retraining) | **DO SECOND** |
| **F3 — LLM narrator (Phi-3.5)** | ★★★★☆ | 4-6 hrs | Medium (Windows install) | **Optional** |
| **F4 — Adversarial robustness demo** | ★★★☆☆ | 3-4 hrs | Low | Optional |
| **F5 — Federated learning concept demo** | ★★☆☆☆ | 5-6 hrs | Medium | Skip unless very ahead |
| F6 — RTSP live stream support | ★★★☆☆ | 2 hrs | Low | Nice-to-have |
| F7 — PDF mission report export | ★★☆☆☆ | 2 hrs | Low | Polish |
| F8 — Bridge class fix (OBB→rotated) | ★★☆☆☆ | 4 hrs (retrain) | Medium | Skip |

### Recommended 6-day schedule

| Day | Date | Plan |
|---|---|---|
| **0** | Apr 24 (today) | Slides + demo video (YOUR task) + commit Section D polish items |
| **1** | Apr 25 | **F1 — Video + ByteTrack** (biggest demo upgrade) |
| **2** | Apr 26 | **F2 — MAR20 fine-grained aircraft** (retraining takes the day) |
| **3** | Apr 27 | **F3 — LLM narrator** if ahead, OR F4 adversarial robustness |
| **4** | Apr 28 | Integration testing, polish, re-record demo video with new features |
| **5** | Apr 29 | Full rehearsal, backup video, Q&A prep, packing |
| **6** | Apr 30 | 🎯 Event — you ship |

If you don't want to add anything: **v1 as-is is demo-complete.** Everything below is optional firepower.

---

## SECTION B — Feature specifications (in priority order)

---

### F1 — Video + ByteTrack multi-frame tracking

**Why it matters:** Currently, Mission page analyzes single frames. Judges will ask *"what about video?"* — this fixes that. Stable track IDs across frames + movement trails is visually dramatic and technically non-trivial. Also unlocks the `motion_term` in the threat scoring formula that's currently always 0.

**What gets built:**
- Backend: extend `ingest.py` video handling + use Ultralytics built-in `model.track()` which bundles ByteTrack
- Pipeline changes: for videos, track stable IDs across all frames, compute per-track movement vectors (bearing + speed)
- Frontend: Mission page video mode → play video with boxes moving, persistent track IDs overlaid, colored trails
- Map page: track trails as polylines, fading older positions

**Technical steps:**
1. Install: nothing new — Ultralytics already ships ByteTrack built-in
2. `backend/app/services/pipeline.py`:
   - For video inputs, call `model.track(source, stream=True, tracker="bytetrack.yaml")` instead of `model.predict()`
   - Each detection now has a `track_id` — write it to the existing `Detection.track_id` column (already in schema!)
3. New endpoint: `GET /api/v1/tracks?mission_id=X` — returns detections grouped by track_id with timestamps
4. `frontend/src/pages/Mission.tsx`: if video, play + draw boxes from the tracked results, boxes labeled with track IDs
5. `frontend/src/pages/MapView.tsx`: render polylines for each track's lat/lon history with fade

**Demo moment:**
*"This is 30 frames from a drone. Watch box 17 — that's the same truck across 4 seconds of footage. And the red line on the map is its path. We can compute speed, heading, and intent."*

**Files touched:**
- `backend/app/services/pipeline.py` (video branch)
- `backend/app/api/detections.py` (tracks endpoint)
- `frontend/src/pages/Mission.tsx` (video playback with track overlay)
- `frontend/src/pages/MapView.tsx` (track polylines)

**Acceptance criteria:**
- Upload a video → `track_id` populated in DB
- Map shows 3+ distinct track trails
- Stable IDs: same object gets same ID across frames

**Time estimate:** 6 hours
**Risk:** low — Ultralytics API is mature, we already have DB schema for track_id

---

### F2 — MAR20 fine-grained military aircraft

**Why it matters:** Kills the "this is just DOTA" objection. DOTA has 1 class `plane` — MAR20 has **20 military aircraft types**: Su-57, MiG-29, F-16, F-22, B-2, etc. Directly strengthens defence credibility. Your aircraft mAP goes from one number to twenty class-specific numbers.

**What gets built:**
- Download MAR20 dataset (~7GB, free, academic)
- Fine-tune a SECOND yolo11n model (or head-only) specifically on aircraft
- Routing: when main model detects `aircraft-fixed-wing`, a second pass runs the MAR20 model on just that crop → returns specific type
- Frontend: aircraft detections show the specific type (e.g. "Su-57 (0.84)")

**Technical steps:**
1. Download MAR20: https://gcheng-nwpu.github.io/#Datasets — free, registration optional
2. Prepare MAR20 as YOLO format (it ships in VOC-XML → convert with a script)
3. Fine-tune yolo11n for 40 epochs on MAR20 crops (256×256 input — aircraft crops are small)
4. Export as `astra-aircraft-v1.pt` / `.onnx`
5. `backend/app/inference/aircraft_classifier.py` — new module that classifies aircraft crops
6. Pipeline integration: when detector finds `aircraft-fixed-wing` box, crop → classify → store the specific type as `narrative` field or new column
7. Frontend: show specific aircraft type in tooltips + detection cards

**Demo moment:**
*"Our primary model detects 'aircraft'. Our MAR20 sub-model classifies it — **Su-57 fighter, 84% confidence**. This is what defence fine-grained recognition looks like. And it's a second model running on the same 6GB laptop, zero additional hardware."*

**Files touched:**
- `training/prepare_mar20.py` (new)
- `training/configs/astra-aircraft-v1.yaml` (new)
- `backend/app/inference/aircraft_classifier.py` (new)
- `backend/app/services/pipeline.py` (classifier hook)
- `frontend/src/pages/Mission.tsx` (show sub-class)

**Acceptance criteria:**
- MAR20 dataset downloaded + converted
- Second model trained with per-class mAP reported
- Pipeline shows specific aircraft type for aircraft detections

**Time estimate:** 8-10 hours
- Dataset download + prep: 2 hours
- Training: 3 hours (small dataset, 256² input is fast)
- Integration: 3 hours
- Testing + polish: 1 hour

**Risk:** medium — training has to work on first try (no time for failed runs). Mitigation: start with 20 epochs, not 40; fine-tune only the detection head (freeze backbone); use the same config we know works.

---

### F3 — Local LLM narrator (Phi-3.5-mini)

**Why it matters:** Adds a memorable "AI explaining AI" moment. Every alert gets a commander-friendly natural-language summary like:
> *"Three large vehicles detected in convoy formation, 89m NE of FOB Delta. Confidence 0.87. Threat level: elevated. No prior sightings in audit trail."*

This creates a "wow" moment in the demo and answers the "how does a commander use raw detections?" objection.

**What gets built:**
- Install `llama-cpp-python` (Python bindings for llama.cpp)
- Download Phi-3.5-mini-instruct GGUF quantized (~2.4 GB, free, Microsoft-released)
- Backend: narrator service that takes alert + context → generates 1-sentence summary
- Endpoint: `POST /api/v1/narrate?alert_id=X`
- Frontend: narrative shown under each alert, auto-generated on alert creation OR on-demand click

**Technical steps:**
1. `/d/astra-data/venvs/astra/Scripts/pip install llama-cpp-python` — this is the risky part on Windows
2. Download: `Phi-3.5-mini-instruct-Q4_K_M.gguf` from HuggingFace (~2.4 GB) to `D:\astra-data\models\`
3. `backend/app/fusion/narrator.py`:
   - Load model once (lazy, cached)
   - Function `narrate(alert, detections_in_aoi) -> str` with a carefully structured prompt
4. Integration into `pipeline.py`: after creating an Alert, call `narrate()` → store result in `Alert.narrative` column (already exists!)
5. Endpoint `POST /api/v1/narrate/{alert_id}` for on-demand regeneration
6. Frontend `Alerts.tsx`: show narrative as small italic text under each row

**Demo moment:**
Click top alert → narrative appears:
> *"Convoy of 12 large vehicles forming up near FOB Delta, 87m distance. Matches historical reconnaissance patterns from sector 4-B. Recommend confirmation by C2 before engagement."*

Then click ✓ — *"Alert confirmed. Audit log updated."*

**Fallback (if llama-cpp fails on Windows):** Use canned templates as a simpler narrator:
```python
def narrate(alert, context):
    if alert.threat_score > 0.8:
        urgency = "Immediate attention required"
    elif alert.threat_score > 0.5:
        urgency = "Elevated threat"
    else:
        urgency = "Routine observation"
    return f"{urgency}. {context.class_count} {context.class_name}(s) detected {context.distance_km:.1f}km from {context.nearest_asset}. Confidence {alert.confidence:.0%}."
```

**Files touched:**
- `backend/app/fusion/narrator.py` (new)
- `backend/app/services/pipeline.py` (call narrator after alert creation)
- `backend/app/api/alerts.py` (on-demand narrate endpoint)
- `frontend/src/pages/Alerts.tsx` (show narrative)

**Acceptance criteria:**
- LLM installed + model loaded
- Each alert gets a narrative (either LLM or template)
- Narrative shown in Alerts page

**Time estimate:** 4-6 hours (can balloon if llama-cpp install rabbit-holes)
**Risk:** medium — Windows + llama-cpp-python install sometimes needs MSVC. Template fallback guarantees it ships.

---

### F4 — Adversarial robustness demo (FGSM)

**Why it matters:** Preempts the "what about camouflage / adversarial attacks?" Q&A. Lets you show that you understand model fragility AND have a mitigation plan. You don't need to actually fix adversarial robustness — you need to **demonstrate awareness** and show what happens.

**What gets built:**
- A small "Adversarial" page in the UI: upload an image, slide a noise-intensity slider, watch detections degrade
- Backend: `/api/v1/adversarial` endpoint that applies FGSM (Fast Gradient Sign Method) perturbation with a given ε
- Shows: original (54 detections) → ε=0.01 perturbed (20 detections) → ε=0.05 (4 detections)

**Technical steps:**
1. `backend/app/inference/adversarial.py` — implement FGSM:
   ```python
   def fgsm_attack(image, model, epsilon):
       # compute gradient of loss w.r.t. input
       # perturb input in direction of gradient sign
       # return adversarially-perturbed image
   ```
2. New endpoint `POST /api/v1/adversarial` (file + epsilon param) → returns perturbed image + new detection count
3. New frontend page `/adversarial` with upload + slider + side-by-side comparison

**Demo moment:**
*"Watch what happens when we add imperceptible noise — the image looks identical to the human eye, but the model's detections collapse from 54 to 4. This is the adversarial attack surface. Our roadmap includes adversarial training — for v2 we'll harden this with randomized smoothing."*

**Files touched:**
- `backend/app/inference/adversarial.py` (new)
- `backend/app/api/adversarial.py` (new endpoint)
- `frontend/src/pages/Adversarial.tsx` (new page)
- `frontend/src/App.tsx` (add route)

**Acceptance criteria:**
- Upload image + set epsilon → perturbed image rendered + new detection count shown
- Visibly-similar images, drastically-different detections

**Time estimate:** 3-4 hours
**Risk:** low — FGSM is a textbook implementation

---

### F5 — Federated learning conceptual demo (SENTINEL-style)

**Why it matters:** Shows scalability story. If a judge (maybe the same judge who sees SENTINEL!) asks *"how does this scale across 100 military bases?"*, you have a concrete answer. Also appropriates the SENTINEL-style framing without competing with them.

**What gets built:**
- Mock federated-training page: simulate 3 "bases" running ASTRA, show their local mAPs improving via weight averaging
- No actual federated training — just a visualization of weight deltas being averaged
- Uses Flower framework if available, or just numpy mock

**Why this is LOW priority:** it's a fake demo — the actual federated training would take days to implement properly. Judges might see through it. Only do if very ahead of schedule.

**Time estimate:** 5-6 hours
**Risk:** medium — can look fake

---

### F6 — RTSP live stream support

**Why it matters:** One-line answer to *"can this work on real drone feeds?"*

**What gets built:**
- `backend/app/api/stream.py` — accept an RTSP URL, run inference on frames in real time, broadcast to WebSocket
- Frontend: option to enter RTSP URL instead of file upload
- Test with: a publicly-broadcast RTSP camera (there are free testing URLs)

**Time estimate:** 2 hours
**Risk:** low
**Priority:** nice-to-have addition to Mission page — low lift, shows production-readiness

---

### F7 — PDF mission report export

**Why it matters:** Adds a "commander workflow" touch. Clicking "Export" on a Mission generates a PDF with:
- Mission metadata (name, date, AOI)
- All detections with thumbnails
- Threat-ranked alerts
- Audit trail snippet
- Signed SHA-256 hash of the report

**Files touched:**
- `backend/app/api/reports.py` (new — use `reportlab` or `weasyprint`)
- `frontend/src/pages/Audit.tsx` (export button)

**Time estimate:** 2 hours
**Priority:** polish, not critical

---

### F8 — Bridge class fix

**Why it matters:** Your current `bridge` class has mAP=0.000 because OBB→AABB converts narrow diagonal bridges into huge useless boxes. Fixing this requires either (a) using YOLO's OBB (oriented bounding box) variant OR (b) filtering out bridge annotations entirely from training.

**Time estimate:** 4 hours (mostly retraining)
**Impact:** mAP goes from 0.515 overall to maybe 0.55. Incremental. The honest-framing in Q&A is already a strong enough response.

**Recommendation:** **skip** unless F1-F3 all done + ahead of schedule.

---

## SECTION C — Pitch deck updates (whichever features you add)

### If F1 (video + tracking) shipped:
**Slide 3 (Live Demo)** — add a beat:
> *"Now watch this video clip. Boxes don't just detect — they TRACK. See track #17 moving across the frame? That's the same convoy, 4 seconds of footage. On the map, there's its trail."*

**Slide 5 (Roadmap)** — remove "Multi-camera fusion + ByteTrack" from v2.0 (it's done).

### If F2 (MAR20) shipped:
**Slide 4 (Numbers)** — add row:
> *"Aircraft fine-grained: 20 military variants, 0.74 top-1 accuracy on MAR20 test set."*

**Slide 5 (Roadmap)** — remove "MAR20 aircraft variants" from v1.1 (it's done).

### If F3 (LLM narrator) shipped:
**Slide 2 (Architecture)** — add bullet: *"Local Phi-3.5 LLM generates commander-friendly alert narratives."*
**Slide 3 (Live Demo)** — add beat showing a narrative appearing under an alert.

---

## SECTION D — Small polish items (take 15-30 min each, do them while slides/video are being built)

These are minor quality-of-life improvements that don't need a full "feature phase":

1. **`/health` endpoint enhancement** — return current GPU utilization + model stats
2. **Empty states in UI** — currently "No missions — upload via Mission" messages look bare. Style them with icons.
3. **Loading states** — spinners for slow pages
4. **Dark mode refinement** — check all pages have consistent colors (already pretty good)
5. **Sidebar highlight for active page** — already done but verify
6. **Favicon** — add `astra-icon.ico` to frontend (current is Vite default)
7. **README update** — reflect final state, add screenshots, add install instructions for someone else
8. **`docs/architecture.md`** — single-page technical architecture doc (good for linking in pitch)
9. **Copy training `results.png` + `confusion_matrix.png`** from `D:/astra-data/runs/astra-v1-2/` to `docs/screenshots/training-*.png` — use in pitch deck Slide 4

---

## SECTION E — Decision framework

For each feature, ask yourself these 3 questions:

1. **"Will a judge see this in the 3-minute pitch?"** — if no, skip.
2. **"Does this break v1 if it fails?"** — if yes, build it on a git branch only.
3. **"Can I rehearse the demo in < 30 min after building it?"** — if no, too complex.

---

## SECTION F — Final concrete recommendation

**If you ask me what to pick right now:**

### Today (Apr 24):
- ✅ Build slides (YOUR task, 60-90 min)
- ✅ Record demo video using [demo-video-script.md](demo-video-script.md) (20-45 min)
- ✅ Apply Section D polish items 1, 5, 6, 7, 9 (30-60 min, optional)

### Tomorrow (Apr 25):
- 🔥 **F1 — Video + ByteTrack**. Biggest single upgrade. 6 hours.

### Apr 26:
- 🔥 **F2 — MAR20 fine-grained aircraft**. 8-10 hours.

### Apr 27-28:
- Polish integration
- Re-record demo video with new features
- Full rehearsal

### Apr 29:
- Backup demo video
- Q&A drills
- Hardware pack

### Apr 30:
- 🎤 **Ship.**

---

## SECTION G — How to invoke me to execute any feature

When you're ready to build any feature, just say:

> **"Build F1"** (or F2, F3, etc.)

I'll:
1. Confirm the spec matches
2. Execute step-by-step like Phases 1-7
3. Test end-to-end
4. Commit to git
5. Ask before moving to next feature

All features are independent — if F1 fails or you change your mind, v1 stays intact. Every feature is on its own git commit, easily reverted.

---

**Ready when you are.** Pick a feature, or tell me to stand down and focus on your slides/video.
