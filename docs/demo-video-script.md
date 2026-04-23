# ASTRA — Demo Video Recording Script

> **Purpose:** a 90-second recorded walkthrough of the live demo, played as a fallback if the live system crashes, wifi dies, or projector can't connect to your laptop.
> **Target file:** `docs/astra-demo.mp4`
> **Target length:** 85-100 seconds
> **Target resolution:** 1920×1080 minimum

## Two recording modes — pick one

| Mode | Effort | Polish |
|---|---|---|
| **A — Silent capture** | 15 min | Good enough — you narrate live while playing it |
| **B — With voiceover** | 45 min | Better for standalone distribution |

**Do Mode A first.** It's the insurance policy. If you have spare time later, add a voiceover.

---

## PRE-RECORDING SETUP *(do before hitting record)*

### 1. Clean browser / desktop
- Close every app that shows notifications (Slack, Discord, Outlook, WhatsApp web)
- Turn on **Windows Focus Assist / DND** → Start menu → type "focus" → Alarms only
- Close every browser tab except the ones you need
- Hide the taskbar: right-click taskbar → Taskbar settings → "Automatically hide" on

### 2. Position windows
- Browser at http://localhost:5173 — **maximized**
- Start on the **Mission** page, with no image loaded yet
- Browser zoom: Ctrl+0 (default 100%)
- Dev tools closed
- No browser extensions popping up (Grammarly, React DevTools, etc.)

### 3. Have the test image ready
- Copy `D:\astra-data\datasets\astra-v1\images\val\P0003__t000.jpg` to your Desktop as `drone-clip.jpg` (cleaner filename in the file picker)
- Confirm you can upload it and the backend still returns 54 detections (quick sanity check before recording)

### 4. Verify stack is up
- `docker ps` → astra-postgres + astra-redis both "healthy"
- http://127.0.0.1:8000/health → `model_loaded: true`
- http://localhost:5173 → loads

### 5. Warm the model
Record one dry-run upload **before** you hit record — this triggers CUDA JIT compilation so the recorded version runs at 40 ms, not 22 seconds.

---

## RECORDING TOOL — Windows Game Bar *(fastest, no install)*

### Setup
1. Press **Win + G** → Game Bar opens
2. First time: click "Yes, this is a game" if prompted (works on any app)
3. Settings gear → Capturing → turn OFF microphone for Mode A (silent), or ON for Mode B (voiceover)
4. Settings → Capturing → Video quality: **Standard or High** (1080p preferred), FPS **30**

### Start / stop
- **Win + Alt + R** → start/stop recording (works without Game Bar being open)
- Files save to: `C:\Users\atuld\Videos\Captures\`

### Tip
If Game Bar says "game not detected":
- Right-click your browser → "Open with Game Bar" — then Win+G works

### Alternative if Game Bar fails
OBS Studio (free, 5-min install). Download from https://obsproject.com. Create a "Display Capture" source, set output to MP4 1920x1080 30fps. Hit Start Recording.

---

## SHOT LIST — Mode A (silent, 90 seconds)

**Total: 92 seconds estimated. Trim tight — 90s max in the final cut.**

### Shot 1 — Title card / opening *(0:00-0:05)*
- Start on Mission page, empty state
- Move cursor slowly over the ASTRA logo in the sidebar for 2 seconds
- Hover over each sidebar item (Mission, Map, Alerts, Audit, Benchmark) — 0.5s each — to telegraph the app structure

### Shot 2 — Ingest the image *(0:05-0:15)*
- Click the **Ingest** button in the top-right
- File picker opens → pick `drone-clip.jpg` from Desktop
- Wait for the image to render (1 sec)
- **Pause 2 seconds on the unprocessed image** so the viewer sees it's a real drone-like aerial

### Shot 3 — Detections appear *(0:15-0:30)*
- The "Running inference" spinner shows briefly (~0.5s)
- **Boxes appear** with class labels + confidence colors
- Right panel populates: Latency, Detections count, By-class breakdown, Top detections
- **Mouse over a specific box** for 1-2 seconds to highlight it
- Then pan the cursor across the image showing multiple boxes
- **Dwell 3 seconds** on the full-screen detection result so the viewer can absorb it

### Shot 4 — Switch to Map *(0:30-0:45)*
- Click **Map** in sidebar
- Wait for tiles to load (~1s)
- Map zooms into the AOI polygon + pins
- **Pan cursor** across the pin cluster for 2s
- Click one CircleMarker (preferably an aircraft — blue pin) → popup opens
- Dwell 2 seconds showing the popup with lat/lon/conf
- Close popup

### Shot 5 — Switch to Alerts *(0:45-1:10)*
- Click **Alerts** in sidebar
- Wait for table to render
- **Slowly move cursor down the top 5 rows** (1 sec)
- **Drag the `w_class` slider from 0.35 up to 0.80** — rows reorder live. This is the wow moment, **dwell on it for 3 full seconds**.
- Drag `w_prox` down to 0.10 — rows reorder again
- **Click the green ✓ on the top pending alert** → status flips to "confirmed", operator "cmdr-01" shows up

### Shot 6 — Switch to Audit *(1:10-1:25)*
- Click **Audit** in sidebar
- Event log populates — your `alert_confirmed` event is at the top
- **Hover over the top row** for 2s (shows operator + event type + payload description)
- Right sidebar shows event counts by type — dwell 2 seconds

### Shot 7 — Benchmark page close *(1:25-1:32)*
- Click **Benchmark** in sidebar
- The 4 stat cards show mAP / GPU latency / CPU latency / Model size
- Per-class chart underneath
- **Hold final shot for 3 seconds**, then stop recording

### Final length target
- Aim for 85-90 seconds. If your first take is 110s, trim the dwell shots.
- If your first take is 70s, add an extra 3-second dwell on Shot 5 (the slider drag).

---

## SHOT LIST — Mode B (with voiceover, 90 seconds)

Same shots as Mode A, **plus these voiceover lines**. Record in a quiet room, with your laptop mic or a headset mic.

### Voiceover script — read slowly

**[Shot 2 — upload]** *(at 0:07)*
> "This is ASTRA running live. Uploading a drone tile the model has never seen."

**[Shot 3 — detections]** *(at 0:17)*
> "Forty-one milliseconds per frame on a 6-gig consumer GPU. Fifty-four objects detected across eight classes. Every box is color-coded, every class is real."

**[Shot 4 — map]** *(at 0:32)*
> "Those same detections plotted geographically. Cyan pins mark friendly force positions. The dashed outline is the area of interest."

**[Shot 5 — alerts / slider]** *(at 0:50)*
> "The commander tunes the threat score live. Watch the rows reorder. Every alert shows exactly how it got its score — no black box. Click to confirm — operator, timestamp, everything logged."

**[Shot 6 — audit]** *(at 1:12)*
> "Immutable audit trail. Every action. Tamper-evident."

**[Shot 7 — benchmark]** *(at 1:27)*
> "Sovereign. Explainable. Edge-deployable. Ready."

Total speaking time: ~60 seconds out of 90.

### Recording tip
- Record voiceover in a **separate audio file** (Voice Recorder app on Windows, free)
- Use a video editor (DaVinci Resolve — free, CapCut — free) to mux audio over the silent capture
- If that's too fiddly: just narrate live during the pitch over the silent video. Same effect, zero editing.

---

## POST-PROCESSING

### If Mode A (silent, no editing needed)
1. Locate the recorded file in `C:\Users\atuld\Videos\Captures\` — it'll be named like `Brave 2026-04-24 14-32-11.mp4`
2. Open in **Windows Clipchamp** (preinstalled) or **VLC**
3. Trim start and end if needed:
   - Clipchamp: drag handles on timeline
   - VLC: Media → Convert/Save, set start/end times
4. Save as `docs/astra-demo.mp4`

### If Mode B (with voiceover)
1. Open free **DaVinci Resolve** or **CapCut** (simpler)
2. Import the silent video + the voiceover audio
3. Align voiceover to the cue points listed above
4. Optional: fade in/out on audio
5. Export as 1080p MP4, H.264 codec, ~10 Mbps bitrate
6. Save as `docs/astra-demo.mp4`

### Final file target
- **Location:** `docs/astra-demo.mp4`
- **Size:** under 100 MB (90 sec at 1080p 10Mbps ≈ 90 MB)
- **Format:** MP4 (H.264), plays everywhere
- **Resolution:** 1920×1080
- **Framerate:** 30 FPS

### Sanity check after saving
- Open the file in VLC or Windows Media Player
- Scrub to 0:15 — detection boxes visible?
- Scrub to 0:55 — slider drag visible? Rows reordering?
- Scrub to 1:15 — audit log with alert_confirmed event?

If all three check out → **ship it**.

---

## BACKUP STRATEGY — redundancy matters

**Three copies, three places. Always.**

1. **Primary:** `docs/astra-demo.mp4` in the project (committed to git)
2. **USB backup:** copy to a USB drive, put it in your laptop bag the morning of the demo
3. **Cloud backup:** upload to Google Drive with a short shareable link — if your laptop itself dies, you can download on a loaner

### Git note
Normally .mp4 files shouldn't be in git (they bloat the repo). But for a hackathon submission, **committing the demo video is fine**. It's a useful artifact when judges review the repo afterward.

If the repo gets too big (>100MB on GitHub), move the video to Google Drive and link to it from the `README.md`:
```md
## Demo video
▶️ [docs/astra-demo.mp4 — Google Drive link](https://drive.google.com/...)
```

---

## FAST PATH — if you only have 20 minutes total

1. Close notifications + tabs (2 min)
2. Verify stack up (1 min)
3. Warm the model with one dry upload (1 min)
4. Hit Win+Alt+R, do the 7 shots from Mode A (3 min)
5. Stop recording (Win+Alt+R)
6. Open file in Captures folder, rename to `astra-demo.mp4`, move to `docs/` (2 min)
7. Commit it (1 min)
8. You're done. Total: ~10 min. Leave the voiceover as a stretch goal.

---

## WHAT TO DO IF THE RECORDING GOES BADLY

Common issues + quick fixes:

**"Game Bar won't start recording"**
→ Switch to OBS Studio (5-min install, also free)
→ Or use **Xbox Game Bar** app from Microsoft Store (sometimes the built-in one is bugged)

**"Recording is choppy / laggy"**
→ Close Docker Desktop during recording (it's CPU-heavy)
→ Browser at http://localhost:5173 but with fewer extensions
→ Lower Game Bar video quality to Standard (instead of High)

**"Detection takes 22 seconds (cold start) in the recording"**
→ You forgot to warm the model. Stop recording. Upload once off-camera, then restart recording.

**"Video file is too large"**
→ Re-export at Standard quality (5 Mbps instead of 10)
→ Or convert to H.265 with VLC (half the size, same quality)

**"Slider drag doesn't look smooth"**
→ It's your cursor movement — drag slowly, about 1 second per 0.1 unit of slider value

---

## RECORDING CHECKLIST *(actually execute this)*

- [ ] Browser maximized on http://localhost:5173, Mission page, empty
- [ ] `drone-clip.jpg` on Desktop
- [ ] `docker ps` shows 2 healthy ASTRA containers
- [ ] `/health` returns model_loaded: true
- [ ] Did one dry upload to warm model
- [ ] Focus Assist ON
- [ ] Notifications off
- [ ] Taskbar hidden
- [ ] Win+Alt+R starts recording → 🔴 indicator shows up
- [ ] Followed Shot 1-7 in order
- [ ] Win+Alt+R to stop
- [ ] File in `C:\Users\atuld\Videos\Captures\`
- [ ] Renamed + moved to `docs/astra-demo.mp4`
- [ ] Committed to git
- [ ] Copied to USB
- [ ] Uploaded to Google Drive

That's the demo video done.

---

## APPENDIX — screen order in case you forget

```
Mission → (upload) → Mission (with boxes) → Map → Alerts → (slider, confirm) → Audit → Benchmark
```

Memorize this sequence. If you're ever mid-recording and forget what's next, just follow the sidebar **top to bottom** — that's the order.
