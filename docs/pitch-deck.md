# ASTRA — Pitch Deck Draft

> **Audience:** ASTRA Defence-Tech event, BMSIT&M Bengaluru
> **Duration:** 3 minutes pitch + 2 minutes Q&A
> **Stage layout:** 5 slides, each 20-40 seconds, demo is the centerpiece

One-liner to open and close with:
> **"Sovereign, explainable, edge-deployable AI for aerial target recognition — trained on a student laptop in under 2 hours, ready for Jetson tomorrow."**

---

## SLIDE 1 — The Problem *(20 seconds)*

### Visual
- Full-bleed background: a satellite/drone image
- Overlay stat: **"Only 1 in 5 ISR frames gets analyzed"**
- ASTRA logo top-left

### On-slide text
> **India's ISR data avalanche**
>
> - India's drone + satellite imagery grows ~40% annually
> - Human analysts can't keep up — most frames go unreviewed
> - Commercial AI (AWS Rekognition, Google Vision) — **foreign cloud, non-sovereign, unacceptable**
> - Deployed edge AI for Indian defence: **fragmented, closed, non-explainable**

### Speaker notes *(what to say)*
> **"Every Indian drone and satellite generates terabytes of surveillance imagery every day. Human analysts review less than 20 percent of it — threats slip through. Existing commercial AI solutions live on foreign cloud infrastructure, which isn't acceptable for defence applications. And domestic alternatives are either closed-source or non-explainable black boxes. This is the gap ASTRA fills."**

**Pacing tip:** land "less than 20 percent" hard. Pause after "foreign cloud". Move briskly.

---

## SLIDE 2 — ASTRA Architecture *(35 seconds)*

### Visual
- Four-layer stack diagram (top to bottom):
  1. 🖥️  **Command & Control UI** — React dashboard, 5 views
  2. 🔀 **Fusion & Reasoning** — tracker, geo-ref, threat scoring
  3. 🧠 **Inference** — yolo11n + ONNX, 22ms on consumer GPU
  4. 📥 **Ingest** — drone RTSP, satellite tiles, uploads
- To the right: 3 principle badges:
  - **SOVEREIGN** (no external calls)
  - **EXPLAINABLE** (every alert shows its score breakdown)
  - **HUMAN-IN-THE-LOOP** (no autonomous engagement)

### On-slide text
> **Four-layer sovereign stack**
>
> - Fully offline — zero foreign API dependencies
> - 8 defence-relevant classes from DOTA-v1.5
> - Audit-trail every commander action, tamper-evident log
> - Edge-portable: 5.5 MB ONNX, runs on Jetson-class hardware

### Speaker notes *(what to say)*
> **"ASTRA is a four-layer stack. Layer 1 ingests drone or satellite imagery. Layer 2 runs YOLOv11 detection. Layer 3 fuses detections — geolocates them, tracks them across frames, scores threat priority. Layer 4 is the commander dashboard. Three principles: it's fully sovereign — zero foreign API calls, everything runs on local infrastructure. It's explainable — every alert exposes its score breakdown. And it's human-in-the-loop — the model is assistive, never autonomous. Every commander action is logged in a tamper-evident audit trail."**

**Pacing tip:** don't read the bullets. Gesture at the diagram.

---

## SLIDE 3 — Live Demo *(90 seconds — the money shot)*

### Visual
- Full-screen share of the ASTRA browser app at http://localhost:5173
- Have a drone-view image ready to upload (use `D:\astra-data\datasets\astra-v1\images\val\P0003__t000.jpg` or similar dense tile)

### Demo script — beat by beat

**[0-10s] Open Mission page**
> *"This is the live system. I'll upload an image the model has never seen — a held-out validation tile from DOTA."*
> — click Ingest, pick image

**[10-25s] Boxes appear**
> *"In 40 milliseconds on our RTX 4050 laptop, we see 54 objects — class, confidence, color-coded. Right panel shows breakdown: 41 large vehicles, 11 small vehicles, all with high confidence."*
> — let them see the boxes for 3 seconds

**[25-45s] Switch to Map**
> *"Those same detections, geo-referenced onto the AOI. Cyan pins are friendly force positions. Every colored dot is a real detection with its real lat-long computed from the AOI corners."*
> — click a pin, popup shows class + conf

**[45-70s] Switch to Alerts**
> *"The threat queue, ranked by a transparent score. Watch this — "*
> — drag `w_class` slider up
> *"The commander tunes the priority function live. Every change is logged."*
> — click green checkmark on top alert
> *"Alert confirmed, operator attributed, status flipped."*

**[70-90s] Flash Audit page**
> *"Every action is there — ingest, confirm, rejections, weight changes. Immutable. Signed. This is how defence AI should look — transparent, not a black box."*

### Fallback
If wifi dies or the demo stalls: **play `docs/astra-demo.mp4`** (recorded backup, 90 sec, same sequence).

### Pacing tip
Rehearse this 3 times before going on stage. The slider-drag moment is your highlight — linger on it for 3 seconds.

---

## SLIDE 4 — The Numbers *(25 seconds)*

### Visual
- 2×2 grid of big stat cards (same style as Benchmark page):
  - **mAP@0.5 = 0.515** across 8 classes
  - **22.3 ms / 44.9 FPS** on RTX 4050
  - **35.7 ms** CPU ONNX (edge deploy)
  - **5.5 MB** model size
- Below: per-class bar chart (screenshot from `/benchmark` page)
- Footer: *"Trained in 1.888 hours on consumer 6GB laptop"*

### On-slide text
> **Real numbers on held-out DOTA-v1.5 val (1,561 images, 67k objects)**
>
> | Class | mAP@0.5 |
> |---|---|
> | aircraft-fixed-wing | **0.915** |
> | ship | 0.770 |
> | harbor | 0.733 |
> | large-vehicle | 0.660 |
> | aircraft-rotor | 0.242 |
> | storage-depot | 0.393 |
> | small-vehicle | 0.408 |
> | bridge | 0.000 (known issue) |

### Speaker notes *(what to say)*
> **"Real numbers on a held-out validation set, not training data. 0.515 mean average precision across eight classes — aircraft detection clears 91 percent. We hit that on a RTX 4050 laptop with 6 gigs of VRAM in under two hours of training. Inference is 22 milliseconds on GPU, 35 on CPU via ONNX. The model is 5.5 megabytes — fits on a Jetson Nano. This isn't a cloud-scale system; it's designed for the actual edge hardware Indian defence uses."**

**Pacing tip:** stress "this isn't a cloud-scale system". Pause before "actual edge hardware".

### Honest framing for 0.000 bridge
If a judge asks — and they might — **own it**:
> *"DOTA's bridges are annotated as narrow diagonal rectangles. Our OBB-to-AABB conversion produced loose axis-aligned boxes that covered everything around the bridge, not just the bridge. It's a known preprocessing limitation. The fix is rotated-bounding-box support, on the roadmap."*

Never hide. Own.

---

## SLIDE 5 — Roadmap *(20 seconds)*

### Visual
- 4 milestone cards horizontally:
  - **v1.1** (2 weeks)
  - **v1.2** (1 month)
  - **v2** (3 months)
  - **v3** (6 months, flagship)

### On-slide text
> **v1.1** — MAR20 integration → fine-grained military aircraft classification (Su-57, MiG-29, F-16, etc.)
>
> **v1.2** — Real drone telemetry → pinhole-camera georeferencing replaces bilinear AOI
>
> **v2.0** — Multi-camera fusion, ByteTrack across frames with movement-intent scoring
>
> **v3.0** — Jetson Orin Nano edge deployment, power-budget-aware inference, air-gapped ops

### Speaker notes *(what to say)*
> **"Two weeks: swap the bridge data preprocessing and integrate MAR20 for military aircraft variants. One month: pinhole-camera georef replacing the bilinear approximation. Three months: multi-camera fusion and movement-intent scoring. Six months: production Jetson deployment, air-gapped. ASTRA is shipping today as a proof point — the platform is ready to grow."**

### Close
> **"ASTRA. Sovereign. Explainable. Ready."**
> — step back, make eye contact, wait for applause or the first question.

---

## Q&A PREP

### Most likely questions + tight answers

**Q: "Why 0.515 mAP? That's below state of the art."**
> *"This is yolo11-nano — 2.6 million parameters — trained for two hours on a 6GB laptop. The same architecture on an RTX 4090 with full DOTA and 80 epochs hits roughly 0.65. The point of our config is edge-deployable. We chose nano because real drones run on Jetson, not 4090s."*

**Q: "What's the difference between yours and commercial solutions?"**
> *"Three things. One: sovereignty — we run fully offline, no external API calls. Two: explainability — click any alert and you see the exact score breakdown. Three: human-in-the-loop by design, not as a feature flag. We do not have an autonomous engagement path because we do not want one."*

**Q: "How does it handle adversarial inputs / spoofing / camouflage?"**
> *"Not a v1 capability. The roadmap includes adversarial training and a SAM-based foundation layer for anomaly detection. Today's strength is nominal ISR imagery, not adversarial ops."*

**Q: "What about classified datasets?"**
> *"The platform is designed sovereign — air-gapped deployment is already supported. We trained on DOTA because it's public. Operational training data would be the deploying agency's own labeled imagery."*

**Q: "Why YOLO and not something else?"**
> *"YOLO is the best speed/accuracy trade for real-time detection on edge hardware. Transformer detectors like RT-DETR have marginal accuracy gains but cost 3-5x more compute. For drones circling at low power, YOLO wins."*

**Q: "How do you know the threat score is right?"**
> *"We don't claim it's perfect — we claim it's tunable and transparent. Every term is exposed in the UI. The commander shapes the function to their situation. That's the opposite of black-box AI — it's commander-directed AI."*

**Q: "This looks like an undergraduate project. How would you productionize it?"**
> *"Agreed, this is the hackathon cut. Productionization means: 1) expand to rotated-bbox support, 2) validate on operational data, 3) MIL-STD-882 safety case, 4) integration testing against actual drone platforms, 5) Jetson deployment benchmarks, 6) hardening against network partitions. The architecture we demonstrated today supports every step."*

**Q: "What's the cost to deploy?"**
> *"Zero cloud bill. A single Jetson Orin Nano runs the inference — ~$400 in hardware per unit. Compare to any commercial AI-as-a-service where you pay per inference forever."*

**Q: "Can it run on a regular laptop without a GPU?"**
> *"Yes. CPU inference via ONNX Runtime is 35 ms per frame on a Ryzen 7 — 28 frames per second. Good enough for sub-real-time analyst workflows without any GPU."*

---

## DELIVERY CHECKLIST

### Morning of the pitch
- [ ] Laptop charged to 100% + plugged in
- [ ] Backup demo video (`astra-demo.mp4`) on USB + laptop desktop
- [ ] Browser tab on http://localhost:5173 open, Mission page
- [ ] A 2nd tab on /benchmark
- [ ] Test image pre-loaded in Downloads folder (e.g., `P0003__t000.jpg`)
- [ ] Docker containers running (`docker ps` shows astra-postgres + astra-redis)
- [ ] Backend `/health` returns `model_loaded: true`
- [ ] Close Slack, Discord, email, any desktop notification apps
- [ ] DND mode on
- [ ] Water bottle

### During the pitch
- Face the judges, not the screen
- Speak slower than you think you need to
- If something breaks: 2-second pause, switch to backup video, move on
- End with the one-liner, step back, maintain eye contact

### Expected Q&A length
- Most panels give 2-3 questions (~90 seconds)
- Worst case: 1 hostile question. Don't argue — acknowledge, pivot to a strength

---

## BUILD INSTRUCTIONS — turning this into actual slides

### Fastest path: Google Slides (30 min)
1. New Google Slides doc, black background theme
2. Use these 5 sections as 5 slides — paste the "On-slide text" into each
3. For Slide 3 (Demo): embed the demo video *or* replace with a giant screenshot
4. For Slide 4 (Numbers): screenshot the `/benchmark` page directly — it's already a good slide
5. Add transitions: simple fade-in
6. Share link viewable-to-all (in case your laptop dies and you need to present from phone)

### Alternative: PowerPoint
Same as above but offline. Save as .pptx and .pdf (pdf = laptop-agnostic backup).

### Alternative: go ultra-minimal — Reveal.js
If you want web-native slides that live next to the code, convert this markdown to slides with:
```bash
npm install -g @slidev/cli
slidev docs/pitch-deck.md
```
Gives you a localhost:3030 slide deck with code highlighting. Overkill for a 3-min pitch though.

### Screenshots you need (save to `docs/screenshots/`)
1. Mission page with boxes drawn on an image → slide 3 preview
2. Map page with pins + AOI polygon → slide 3 preview OR slide 2 architecture
3. Alerts page showing the ranked queue → slide 3 preview
4. Benchmark page → slide 4
5. Audit page with events → slide 3 preview or slide 2 architecture evidence

---

## FINAL RECOMMENDATION

**Time to build slides:** 60-90 minutes.
**Time to rehearse:** 45 minutes (3 runs at 3 minutes each + discussion time).
**Do not try to redesign the deck.** Use what's here. It's tuned for the pitch flow and the judges will track it.
