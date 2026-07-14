# ASTRA — Runbook (how to start everything)

> Day-of-demo reference. Follow top to bottom.

## 1. Demo content locations

### Images
Already on your drive at `$ASTRA_DATA_DIR\demo-samples\`:
- `01-vehicle-convoy.jpg` — 300 vehicles (lead demo)
- `02-airfield-hero.jpg` — 17 aircraft (adversarial + hero)
- `03-naval-port.jpg` · `04-mixed-scene.jpg` · `05-helipad.jpg` (reserves)

### Videos (download ~5 min before demo)
**Pexels (easiest):**
1. https://www.pexels.com/search/videos/aerial%20drone/
2. Pick a 5-15s clip, click **Free Download** (640×360 or 720p)
3. Save to `C:\Users\atuld\Desktop\drone-clip.mp4`

**OR — use the verified test URL (no download):** paste this in the **Stream** button on Mission page:
```
https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/360/Big_Buck_Bunny_360_10s_1MB.mp4
```

## 2. Pre-flight

```bash
nvidia-smi | head -5            # should list RTX 4050
docker ps                        # Docker Desktop must be running
```

If Docker not up → open Docker Desktop from Start menu, wait 30s.

## 3. Startup — 3 terminals

### Terminal 1 — Infra
```bash
cd "/c/Users/atuld/OneDrive/Desktop/astra"
docker compose up -d
docker ps --format "{{.Names}}: {{.Status}}" | grep astra
# Expected: astra-postgres (healthy) + astra-redis (healthy)
```

### Terminal 2 — Backend
```bash
. $ASTRA_DATA_DIR/venvs/astra/Scripts/activate
cd "/c/Users/atuld/OneDrive/Desktop/astra/backend"
uvicorn app.main:app --reload
```

Wait for: `Application startup complete.`

Verify in browser: http://127.0.0.1:8000/health → `model_loaded: true`

If model_loaded is false:
```bash
cp "$ASTRA_DATA_DIR/runs/astra-v1-2/weights/best.pt" "$ASTRA_DATA_DIR/weights/astra-v1.pt"
# then Ctrl+C uvicorn, re-run it
```

### Terminal 3 — Frontend
```bash
cd "/c/Users/atuld/OneDrive/Desktop/astra/frontend"
npm run dev
```

Open **http://localhost:5173**.

## 4. Warm the model

Before any demo, do ONE dry upload:
1. Mission page → Ingest → pick `01-vehicle-convoy.jpg`
2. Wait ~20s for CUDA warm-up on the first run
3. Subsequent uploads = ~40ms

**Never skip this before going on stage.**

## 5. Shutdown

```bash
# Ctrl+C in Terminal 2 (backend) and Terminal 3 (frontend)
# Docker containers survive reboot-less:
docker compose stop       # to stop
docker compose down       # to remove (DATA PERSISTS in named volumes)
```

## 6. Common issues

| Symptom | Fix |
|---|---|
| `/health` → model_loaded: false | `cp best.pt` to expected path, restart backend |
| Frontend 500s | Backend not running |
| Port 5173 in use | `taskkill /F /IM node.exe` |
| 20-second first inference | Normal CUDA warm-up. Pre-warm. |
| Stream URL hangs | 8s timeout built in — try a different URL or use file upload |

## 7. Page-by-page demo cues

| Page | Show |
|---|---|
| Mission | Upload image → boxes → click a box → Grad-CAM |
| Map | Geo-pins + AOI polygon (+ polylines if video) |
| Alerts | Italic narratives · slider drag → reorder · green ✓ |
| Audit | Event log · PDF button |
| Benchmark | Real numbers |
| Adversarial | Upload `02-airfield-hero.jpg` · FGSM · drag ε → watch detections drop |

## 8. Demo day packing

- Laptop + charger (100% charged)
- USB stick with: `astra-demo.mp4`, `astra-pitch.pdf`, `astra-pitch.pptx`
- HDMI + HDMI-to-USB-C adapter
- Google Slides share link saved in phone notes
- Water bottle
