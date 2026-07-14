# Demo Sample Images

> Physical location: `$ASTRA_DATA_DIR\demo-samples\`
> Not committed to git (images live outside the repo — see `.gitignore`).

These 5 images were hand-picked by auto-ranking 100 random DOTA val tiles through the actual `/predict` endpoint and choosing the ones with the most visually impressive + class-diverse detections. The model has **never seen them during training** (val split).

## The 5 picks

| # | File | Detections | Class breakdown | Demo use |
|---|---|---|---|---|
| 1 | `01-vehicle-convoy.jpg` | **300** | 238 small-veh, 62 large-veh | 🔥 WOW — wall of boxes |
| 2 | `02-airfield-hero.jpg` | 26 | **17 aircraft**, 9 vehicles | 🏆 HERO — showcases 91.5% aircraft mAP |
| 3 | `03-naval-port.jpg` | 75 | 72 ships, 3 harbors | Maritime story |
| 4 | `04-mixed-scene.jpg` | 46 | 28 ships, 15 vehicles, 3 harbors | 3-class diversity |
| 5 | `05-helipad.jpg` | 10 | 6 rotor, 2 fixed-wing, 2 vehicles | 4-class diversity |

## Demo pick order

**Lead** with `01-vehicle-convoy.jpg` — 300 boxes on a parking scene is the most instantly cinematic. If a judge says "try a different one" (they will), go to `02-airfield-hero.jpg` and highlight the **91.5% mAP aircraft class — real number, real image**.

Keep #3-5 as reserve.

## Honest origin for Q&A

All 5 are from **DOTA-v1.5**, the public academic aerial dataset from Wuhan University. It aggregates Google Earth + WorldView satellite + drone imagery, all published for research. Zero classified content, zero proprietary data. The specific tiles here are from the VAL split — the model only ever saw them at inference, never training. Live detections = genuine generalization, not memorization.

## If you need to add more
Point your browser at http://localhost:5173, upload any image from `$ASTRA_DATA_DIR\datasets\astra-v1\images\val\`, and if it looks good — copy it to `$ASTRA_DATA_DIR\demo-samples\` with a descriptive name.
