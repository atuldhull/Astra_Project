# ASTRA Pitch Deck — Step-by-Step Build Guide (Zero Experience Required)

> **Tool:** Google Slides (free, browser-based, auto-saves). PowerPoint users: the menus are 95% identical — follow the same steps.
> **Time:** 60-90 minutes total
> **Output:** 5-slide deck, dark defence-industry aesthetic, ready for the pitch

---

## PART 0 — ONE-TIME SETUP (5 min)

### Open Google Slides
1. Open **Chrome** (or any browser)
2. Go to **https://slides.google.com**
3. Sign in with your Google account (the same one you use for Gmail)
4. Click the big **"+ Blank"** card at the top-left → a new empty deck opens

### Name the file
5. Top-left, click the text that says **"Untitled presentation"**
6. Type: **`ASTRA Pitch Deck`**
7. Press Enter → Google saves it automatically

### Set the dark theme (critical for defence aesthetic)
8. Top menu: click **Slide** → **Change background**
9. Click **Choose color** → click the custom color icon (little eyedropper)
10. Enter hex code: **`#0a0f14`** (same dark navy our app uses)
11. Click **"Add to all slides"** then **Done**

Your deck is now dark. 🔲

### Set text color to white (once, saves clicking 50 times later)
12. Click the slide title placeholder (it says "Click to add title")
13. Select the text → top toolbar, click **Text color** (A with color bar)
14. Custom color → hex: **`#e5edf4`** (almost white)
15. Do the same for the subtitle placeholder

### Pick a font (once)
16. With text selected → click **font dropdown** (it currently says "Arial")
17. Choose **"Inter"** (clean, modern) or **"Roboto"** (Google default, equally fine). If neither exists, use Arial.

---

## PART 1 — SLIDE 1: The Problem (10 min)

### Layout
Click **Layout** button (top toolbar) → pick **"Title"** (just a big title + subtitle area).

### Title (biggest text)
Click the title placeholder. Type:

```
The ISR Data Avalanche
```

Format it:
- Font size: **60pt**
- Color: white (`#e5edf4`)
- Bold: Yes (press Ctrl+B)

### Subtitle
Click the subtitle placeholder. Type:

```
India's surveillance imagery grows faster than analysts can review it.
```

Format:
- Font size: **22pt**
- Color: muted grey (`#8b9aad`)

### Add the 4 bullet points
Click **Insert** → **Text box**. Draw a text box below the subtitle (about 60% of slide width).

Type these 4 lines (hit Enter between each):

```
▸ Indian drones + satellites generate ~40% more imagery year-on-year
▸ Less than 20% of frames ever get human-analyzed — threats slip through
▸ Commercial AI depends on foreign cloud — unacceptable for defence
▸ Domestic alternatives exist but are closed-source, non-explainable black boxes
```

Format:
- Font size: **20pt**
- Color: white
- Line spacing: **1.5** (Format → Line & paragraph spacing → Custom spacing → 1.5)

### Add the punchline at the bottom
Insert another text box at the bottom of the slide. Type:

```
India needs AI that is sovereign, explainable, and edge-deployable.
```

Format:
- Font size: **26pt**
- Color: **orange accent** — hex `#ff7a1a`
- Bold
- Center-aligned (Ctrl+Shift+E)

### ASTRA logo / name in corner
Insert text box in top-left (small). Type:

```
ASTRA
```

Format:
- Font size: **16pt**
- Color: `#ff7a1a` (orange)
- Bold + letter-spacing wide (Format → Format options → Text → Character spacing → 2)

**Slide 1 done.** Preview: press **F5** to see full-screen. Escape to exit.

---

## PART 2 — SLIDE 2: Architecture (15 min)

### Add new slide
- Top-left: **+ New slide** dropdown → **Blank** layout

### Title at top
Insert text box at top. Type:

```
ASTRA — Four-Layer Sovereign Stack
```

- Font: **40pt**, bold, white

### Subtitle
Below title:

```
Fully offline · pixel-level explainable · human-in-the-loop by design
```

- Font: **16pt**, muted grey `#8b9aad`

### The 4-layer diagram (biggest chunk of work)

You'll build 4 stacked rectangles. Here's the trick: build one perfectly, then duplicate it 3 times.

**Step 2a — Draw the first rectangle (Layer 4: top)**
1. Insert → **Shape** → **Shapes** → pick **Rounded rectangle**
2. Drag to draw a wide, short rectangle in the middle of the slide
3. Make it roughly 600 pixels wide, 70 pixels tall
4. Click the shape → **Fill color** → hex `#121821` (dark panel)
5. **Border color** → hex `#23303d` (subtle border)
6. **Border weight** → 1px

**Step 2b — Add text inside**
7. Double-click the rectangle → type:

```
🖥️  Layer 4 — Commander Dashboard
5 pages: Mission · Map · Alerts · Audit · Benchmark
```

8. Format: 18pt on line 1, 13pt muted on line 2

**Step 2c — Duplicate 3 times**
9. Click the rectangle → **Ctrl+D** to duplicate → drag the copy below
10. Repeat two more times so you have 4 stacked rectangles

**Step 2d — Edit each one's text** (click in, edit)

| Rectangle (top to bottom) | Line 1 (big) | Line 2 (small) |
|---|---|---|
| 1 (top) | `🖥️  Layer 4 — Commander Dashboard` | `5 pages: Mission · Map · Alerts · Audit · Benchmark` |
| 2 | `🔀  Layer 3 — Fusion & Reasoning` | `Geo-ref · threat scoring · Grad-CAM explainability` |
| 3 | `🧠  Layer 2 — Inference` | `YOLOv11-nano · 2.6M params · 22ms on RTX 4050` |
| 4 (bottom) | `📥  Layer 1 — Ingest` | `Drone RTSP · satellite tiles · uploaded files` |

**Step 2e — Add the 3 principle badges (right side)**

Insert 3 small rectangles (rounded) on the right of the diagram. For each:
- Fill: `#ff7a1a` (orange) with **20% opacity** (Fill color → Custom → set alpha low)
- Border: `#ff7a1a`, 2px
- Inside text, centered, white, 14pt bold:

```
SOVEREIGN
```
```
EXPLAINABLE
```
```
HUMAN-IN-LOOP
```

Stack them vertically on the right. Each one ~150×50 pixels.

**Slide 2 done.**

---

## PART 3 — SLIDE 3: Live Demo (15 min)

This slide is almost entirely a **big screenshot** of your actual app.

### Take the screenshot first
1. Open your running app: **http://localhost:5173**
2. Go to **Mission** page
3. Upload `D:\astra-data\demo-samples\01-vehicle-convoy.jpg`
4. Wait for boxes to appear (all 300 of them)
5. Press **Win + Shift + S** → screen snip → select the entire app window including boxes and side panel
6. Paste into Paint (or keep in clipboard)
7. Save as `docs/screenshots/mission-demo.png`

Also take:
- Map page with pins visible → `docs/screenshots/map-demo.png`
- Alerts page with ranked table → `docs/screenshots/alerts-demo.png`
- Grad-CAM heatmap → `docs/screenshots/gradcam-demo.png`

### Build the slide
1. New slide → Blank layout

### Title bar (small)
Top strip, text box:

```
Live Demo
```

- 32pt, white, bold, top-left corner

Below title, subtitle:

```
Upload → Detect → Geo-locate → Rank threat → Explain — all in <50ms on a consumer GPU
```

- 14pt, muted

### Insert the main screenshot (Mission page with 300 boxes)
1. Insert → Image → Upload from computer → pick `mission-demo.png`
2. Position it to fill the middle/right of the slide (~70% width)
3. Drag corners to resize proportionally

### Add 3 callout text boxes around the screenshot
Insert small text boxes with:

**Callout 1 (top):**
```
300 detections
in 41ms
```
- 24pt bold, color `#4ade80` (green)
- Arrow pointing at the detection boxes

**Callout 2 (middle):**
```
Pixel-level
explainability
```
- 18pt, color `#60a5fa` (blue)
- Arrow pointing at a box

**Callout 3 (bottom):**
```
Click any box →
Grad-CAM heatmap
```
- 14pt, muted grey

### Footer
Bottom of slide:

```
Running live at http://localhost:5173 — switch back to browser to demo, or play docs/astra-demo.mp4 as backup
```

- 12pt, color muted `#8b9aad`, bottom-center

**Slide 3 done.**

---

## PART 4 — SLIDE 4: The Numbers (15 min)

The **credibility slide**. 4 big stat cards + a bar chart.

### Screenshot prep
1. Open http://localhost:5173 → **Benchmark** page
2. Screenshot the **4 stat cards + the per-class bar chart**
3. Save as `docs/screenshots/benchmark.png`

### Build slide
1. New slide → Blank

### Title
```
Performance — DOTA-v1.5 Val Set
```
- 40pt, bold, white, top

### Subtitle
```
1,561 images · 67,029 annotated objects · model trained in 1h53m on laptop
```
- 14pt, muted

### Option A — Just paste the benchmark screenshot
Insert → Image → upload `benchmark.png` → resize to fit 80% of slide.

### Option B — Build native cards (cleaner, 10 min extra)

Build 4 small rectangles across the middle of the slide:

For each card:
- Rounded rectangle, fill `#121821`, border `#23303d`
- Size: ~220 × 120 pixels
- Text inside, centered:
  - **Tiny grey label** (top, 10pt muted): `MAP@0.5 OVERALL`
  - **Huge number** (middle, 48pt bold white)
  - **Tiny caption** (bottom, 11pt muted)

Fill each card:

| Card | Label | Number | Caption |
|---|---|---|---|
| 1 | MAP@0.5 OVERALL | **0.515** | across 8 classes |
| 2 | GPU LATENCY | **22.3 ms** | RTX 4050 · 44.9 FPS |
| 3 | CPU LATENCY | **35.7 ms** | ONNX Runtime · 28 FPS |
| 4 | MODEL SIZE | **5.5 MB** | yolo11n · Jetson-ready |

### Below cards — per-class mAP table
Insert a small table (**Insert** → **Table** → 2×9):

| Class | mAP@0.5 |
|---|---|
| aircraft-fixed-wing | **0.915** |
| ship | 0.770 |
| harbor | 0.733 |
| large-vehicle | 0.660 |
| small-vehicle | 0.408 |
| storage-depot | 0.393 |
| aircraft-rotor | 0.242 |
| bridge | 0.000 (known issue — OBB→AABB) |

- Header row: bold, white, background `#ff7a1a` (orange)
- Data rows: white text, background `#121821`
- Your hero number (aircraft-fixed-wing **0.915**) in bright green `#4ade80`, bold

### Footer punchline
Bottom of slide, centered, bold:

```
Trained in 1h53m on a ₹90k laptop — not cloud.
```

- 22pt, color orange `#ff7a1a`

**Slide 4 done.**

---

## PART 5 — SLIDE 5: Roadmap & Close (10 min)

### Build slide
New slide → Blank layout

### Title
```
Roadmap
```
- 40pt, bold, white

### Timeline (horizontal) — 4 milestones
Insert **Shape** → **Arrow → rectangle** (just plain rectangles work fine if arrow shape is confusing). Draw 4 rectangles in a row:

| Rectangle | Label | Detail |
|---|---|---|
| v1.1 (2 wks) | **Military aircraft** | MAR20 dataset — Su-57, MiG-29, F-16 |
| v1.2 (1 mo) | **Real telemetry** | Pinhole-camera georef replaces AOI corners |
| v2.0 (3 mo) | **Multi-cam fusion** | ByteTrack + movement-intent scoring |
| v3.0 (6 mo) | **Jetson deployment** | Air-gapped edge ops |

Format each:
- Width ~180px, height ~120px
- Fill `#121821`, border `#23303d`
- Version label on top (orange, 16pt bold)
- Middle bold white text (18pt, the milestone name)
- Bottom italic muted detail (11pt)

Connect them with small arrow shapes between (Insert → Shape → Arrow).

### Giant closing tagline (bottom half of slide)

Insert a text box taking the whole bottom half. Type (exactly these three lines):

```
Sovereign.
Explainable.
Ready.
```

Format:
- Font: **80pt**, bold
- Color: `#ff7a1a` (orange)
- Center-aligned
- Line spacing: 1.4

This is your **mic-drop line.** When you say it, pause after each word.

### ASTRA logo at bottom
Small, bottom-right corner, 12pt, orange:

```
ASTRA  ·  BMSIT&M Bengaluru  ·  2026
```

**Slide 5 done. All 5 slides built.** 🎉

---

## PART 6 — POLISH (15 min)

### Add transitions (between slides)
1. Top menu → **Slide** → **Transition**
2. Pick **Fade** (subtle, professional — not Spin / Cube / Flip — those scream Powerpoint 2003)
3. Duration: **0.4 seconds**
4. Click **Apply to all slides**

### Check font consistency
Click through each slide. If any text uses a different font by accident, fix it. Consistency matters more than picking the "right" font.

### Check alignment
For each slide:
- Does the title start at roughly the same left/top position?
- Are elements visually aligned to a grid?

Google Slides has smart-guides — as you drag elements they'll snap. Use it.

### Test full-screen
Press **F5** to present from Slide 1. Walk through all 5 slides. Look for:
- Any text that's cut off the edge
- Anything that looks misaligned
- Any typo you missed

---

## PART 7 — EXPORT & BACKUP (5 min)

### Download as PowerPoint (backup format)
1. **File** → **Download** → **Microsoft PowerPoint (.pptx)**
2. Save into `docs/` as `astra-pitch.pptx`

### Download as PDF (universal format — can view on any device)
1. **File** → **Download** → **PDF Document (.pdf)**
2. Save as `docs/astra-pitch.pdf`

### Get the shareable link (for phone fallback)
1. **Share** button (top-right) → click
2. **General access** → change from "Restricted" to **"Anyone with the link"** → "Viewer"
3. **Copy link** → save it somewhere you can access from your phone (notes app, email to yourself)

**This gives you 3 formats:**
- Google Slides (laptop, browser)
- .pptx (PowerPoint file on USB stick as backup)
- .pdf (works on ANY device, ANY projector)

### Commit them to git (optional — good practice)
From Git Bash:
```bash
cd "/c/Users/atuld/OneDrive/Desktop/astra"
git add docs/astra-pitch.pptx docs/astra-pitch.pdf
git commit -m "Add final pitch deck"
```

---

## PART 8 — SCREENSHOT CHECKLIST

Save all screenshots under `docs/screenshots/`. Take these specific shots:

- [ ] `mission-demo.png` — Mission page with 300 boxes from `01-vehicle-convoy.jpg`
- [ ] `mission-aircraft.png` — Mission page showing aircraft detections from `02-airfield-hero.jpg`
- [ ] `gradcam-demo.png` — Click a detection → heatmap visible
- [ ] `map-demo.png` — Map page with pins scattered over AOI
- [ ] `alerts-demo.png` — Alerts page showing the ranked queue
- [ ] `audit-demo.png` — Audit page with events listed
- [ ] `benchmark.png` — Benchmark page with all 4 stat cards + bar chart

Use **Win + Shift + S** for each (built-in Windows screenshot tool).

---

## COMMON GOTCHAS

### "I can't find custom color entry"
In Google Slides → any fill/color picker → click **"Custom"** at the bottom → hex input field appears.

### "My text keeps defaulting to black when I start a new text box"
Select the text → Text color → set to white. Google Slides remembers your last-used color.

### "My elements don't align to a grid"
Google Slides shows red/blue guide lines as you drag elements — they indicate center alignment with other objects. Drag slowly.

### "The deck looks empty / boring"
That's actually good for defence. Dense, cluttered decks = bad. Keep whitespace. Let the numbers land.

### "I'm running out of time — what can I skip?"
Skip the native cards in Slide 4 — just paste the `benchmark.png` screenshot. Saves 10 minutes.

Skip the roadmap rectangles in Slide 5 — just use bullet text. Saves 5 minutes.

### "I accidentally deleted everything"
Google Slides → **File** → **Version history** → **See version history** → restore any prior version.

---

## FINAL 2-MINUTE GUT CHECK

Before you stop:
- [ ] All 5 slides present
- [ ] All text readable (no dark text on dark background, no tiny fonts)
- [ ] Transitions set to Fade
- [ ] Downloaded `.pptx` + `.pdf`
- [ ] Shareable link saved in phone
- [ ] USB copy of `.pptx` made

If all ticked — **you're done building.** Next step is the demo video script (`docs/demo-video-script.md`).

🫡
