# ASTRA Round 3 — Workflow & Sequencing

> **Mission:** Ship 22 features + a complete frontend overhaul on top of the
> shipped Round-2 codebase. ~100 hours of operator time, executed at 2x. No
> training runs without explicit "done" handoff. No demo-day surprises.
>
> **Single source of truth** for the next sprint. Read this first if context
> compacts.

---

## 0. Ground rules (read first, follow always)

1. **Every code change ships in its own commit.** No batch commits across features.
2. **Every commit ends with `python scripts/e2e_regression.py` clean.** If it doesn't, that commit doesn't ship.
3. **Local-execution checkpoints (training / model export / data download) PAUSE THE AGENT.**
   The agent writes the script, prints the exact command for the operator, then waits for "done" before continuing.
   If the agent hits an error during a checkpoint that should have been operator-run, it backs out and asks.
4. **Backwards compatibility:** every R3 feature must coexist with R2's `v0.2.0-round2` tag — operator can roll back at any time.
5. **No silent fallbacks.** If a feature can't load (missing model, missing env var, missing data), surface the reason in the UI — don't pretend success.
6. **Demoability test:** every feature gets a 1-line entry in the demo failure recovery cheatsheet (`docs/pitch-content-r2.md`) before its commit lands.
7. **Frontend is the chassis everything else hangs from.** Phase 1 (frontend overhaul) lands first — every feature after that is built into the new design system, not retrofitted.

---

## 1. Phase ordering

```
Phase 1   Frontend overhaul + design system               (~6h)
Phase 2   Quick wins (operator-assist + lightweight)      (~5h)
Phase 3   Shipping-grade features (PDF, scrub, exports)   (~10h)
Phase 4   ML upgrades (PGD, federated MAR20, RAG)         (~25h)
Phase 5   Production engineering (auth, CI, compose)      (~6h)
Phase 6   Research-grade (DP, continual, MHT, multi-modal)(~30h)
Phase 7   Final integration sweep + RELEASE-R3 + v0.3.0   (~3h)
                                                          ~85h target
```

Phase 1 first because every later feature lands inside the new design system,
not on top of it. Last because integration risk compounds — never let two
phases run unmerged.

---

## 2. Phase 1 — Frontend overhaul (priority #1)

### 2.1 Why this is first
You said it bluntly: *"front end is not proper, looks very simple, judges won't like it."* Half right (sparse-but-functional is the genre), half right (we *can* polish a lot). Phase 1 lifts visual quality without sacrificing the dense-data-credibility aesthetic that defence judges expect.

**Reference aesthetics:** Palantir Gotham, Anduril Lattice, Bloomberg Terminal, NORAD Space-Track. *Not* SaaS landing-pages, *not* Stripe Dashboard, *not* iOS settings.

### 2.2 Design system tokens
Single source of CSS variables, applied via Tailwind config, used by every component:
- Color palette: 5-step neutral, 3 accent (orange-burn, mil-cyan, threat-red), 4 status (low/med/high/crit)
- Typography scale: 10/11/12/14/16/18/24/32 px, monospace stack first, system sans fallback
- Elevation tokens: 0/1/2/3 with backdrop-blur values
- Motion tokens: 150/200/350 ms with cubic-bezier(0.4, 0, 0.2, 1)
- Glow effect tokens: per-status color with rgba alpha for box-shadow

### 2.3 Specific components to ship
- **Splash boot screen** — first visit, ~2s: logo glyph fade + "ASTRA online" terminal-style boot lines + version + node-ID. Skippable on click.
- **Sidebar v2** — top: brand mark with subtle pulse. Below: nav items with active-state glow accent bar. Bottom: real-time status pills (backend OK · GPU 72°C · 14 missions · 78 alerts · last sync 3s ago)
- **Glass-morph panels** — replace flat `bg-panel` with `bg-panel/70 backdrop-blur-md border-border/50` everywhere
- **Page header pattern** — standardise: title + status pill + sparkline (where relevant) + action cluster
- **Hero stats row per page** — 4 KPI cards at top of every page (Mission, Map, Alerts, etc.) with count-up animation
- **Toast notifier** — bottom-right stack, success/info/warn/crit, swipe-to-dismiss, 5s auto-fade
- **Loading skeletons** — replace `<Loader2 className="animate-spin" />` everywhere with shaped pulsing skeletons that match the final layout
- **Empty states** — every "no data" view gets an SVG illustration + 1 line + 1 CTA button
- **Number tickers** — KPI numbers count up from 0 on first paint and on update (250ms easing)
- **New-detection pulse** — Map: when a pin POPs from WS, scale-up 1.0 → 1.4 → 1.0 over 600ms with glow
- **Threat-level micro-animation** — alert rows pulse subtle red gradient when score ≥ 0.85
- **Theme toggle** — keep dark default; light + "commander green-on-black" themes optional
- **Cursor + selection accent** — accent-colored selection background, not browser default

### 2.4 Not changing
- Page layouts (the dense grid/sidebar pattern is correct for the genre)
- Recharts choices (line/bar) — they read as "real data" not "marketing chart"
- Mono font for numbers (mandatory for the credibility signal)
- Density (judges scan — don't add whitespace)

### 2.5 Phase-1 commit plan (each its own commit)
1. `frontend/src/styles/tokens.css` + Tailwind config — design tokens
2. Sidebar v2 + brand mark + status pills
3. Splash boot screen
4. Toast notifier + skeletons + empty states (shared components)
5. Per-page hero stats rows (one commit per page: Mission, Map, Alerts, Audit, Federated, Diff, Adversarial, Benchmark)
6. Map pin POP animation + threat-level pulse + count-up tickers

Each ends with `npm run build` clean and one screenshot in `docs/screenshots/`.

---

## 3. Phase 2 — Quick wins

| # | Feature | Time | Operator? | Notes |
|---|---|---|---|---|
| F2 | Telegram bot setup + verify | 30 min | YES (BotFather + token) | Agent waits for `done`. Then tests with high-threat ingest. |
| F5 | TensorRT INT8 export | 30 min | YES (script runs on operator hardware) | Agent stops; operator runs script; agent records numbers in benchmark report. |
| F11 | Onboarding tour (Shepherd.js) | 1.5h | no | New-visitor spotlight tour. Skippable. localStorage flag. |
| F12 | Theme toggle | 1h | no | Built on Phase-1 tokens. Persisted in localStorage. |
| F13 | CSV / JSON exports | 1h | no | Export buttons on Detections / Alerts / Audit. Pure client-side. |
| F20 | GitHub Actions CI | 1h | YES (push to enable) | `.github/workflows/e2e.yml` runs regression on push. |

---

## 4. Phase 3 — Shipping-grade features

| # | Feature | Time | Operator? | Notes |
|---|---|---|---|---|
| F3 | Pitch PDF v2 (12 slides) | 2h | no | New `scripts/make_pitch_pdf_r2.py`. Reads `docs/pitch-content-r2.md`. |
| F4 | Playwright demo automation | 2h | YES (npm install + headed run) | `e2e/demo.spec.ts` walks 4-min demo. Backup video. |
| F9 | Mission report PDF v2 | 2h | no | Adds airframe table, OOD section, federated participation log, chain validation cert. |
| F10 | Map heatmap + clustering | 2h | no | leaflet.heat + leaflet.markercluster. Toggle in legend. |
| F14 | Mission comparison view | 2h | no | Side-by-side image + canvas overlay. Reuse Diff endpoint. |
| F15 | Replay scrub timeline | 3h | no | Custom HTML5 video controls + box-update on `seek` event. |

---

## 5. Phase 4 — ML upgrades

These are the heavy ones. Every one has a checkpoint that pauses the agent.

| # | Feature | Time | Operator checkpoint? | Plan B |
|---|---|---|---|---|
| F1 | PGD adversarial training | 3h agent + 3h training | YES — agent writes `training/pgd_train.py`, prints command, waits for "done" | If PGD doesn't beat the helipad-only baseline, ship the script + numbers anyway as "the proper defence shows partial improvement; full convergence requires longer training" |
| F8 | MAR20 cls federated training | 2h agent + 1h training | YES — same pattern: prepare partition, write config, wait for operator | If federated MAR20 underperforms standalone MAR20, ship the convergence curve as proof-of-orchestration |
| F6 | RAG commander Q&A | 6h | YES (download Phi-3.5 GGUF ~2.4GB) | Plan B: rule-based templates over a known query list — same UX, no LLM. Already in the war plan as Plan B. |
| F7 | Real Flower federated | 4h agent + verify | YES (network test on operator machine) | If gRPC binding fails on Windows, fall back to documenting in-process as "Flower-style" with a note |
| F16 | Multi-modal audio (YAMNet) | 8h | YES (model download + audio test) | If accuracy is poor on aerial drone audio, ship as "experimental" tab with disclaimer |
| F17 | Differential privacy federated | 4h | no (extension to F8) | Add gradient noise to FoolsGold loop. Charts: utility-vs-privacy curve. |
| F18 | Continual learning | 6h | YES (overnight retrain) | Operator-confirmed/rejected alerts → fine-tune queue → nightly retrain script. |
| F19 | Multi-hypothesis tracking | 6h | no | Replace `model.track(tracker="bytetrack.yaml")` with custom MHT loop. |

---

## 6. Phase 5 — Production engineering

| # | Feature | Time | Operator? | Notes |
|---|---|---|---|---|
| F22 | JWT authentication | 3h | YES (set ASTRA_JWT_SECRET) | Login page + bearer tokens + role-based engage permission. |
| F20 | (already in Phase 2) GitHub Actions CI | 1h | — | If you have a public repo. |
| F21 | Docker-compose for full stack | 2h | YES (Dockerfile-frontend test) | `docker compose up` brings backend + frontend + postgres + redis. |

---

## 7. Phase 6 — Research-grade (overflow / nice-to-have)

These are the "if there's time after the main batch" items. ~30h total, easy to defer if Phase 1-5 take longer than budgeted.

| # | Feature | Risk |
|---|---|---|
| F16 | Multi-modal audio | Domain mismatch (YAMNet on drone audio) |
| F17 | DP federated | Math has to be right or the noise wrecks accuracy |
| F18 | Continual learning | Pipeline complexity; operator UX for "confirm to teach" |
| F19 | MHT | Replacing a working tracker has regression risk |

---

## 8. Phase 7 — Final integration

1. **Re-run `python scripts/e2e_regression.py`** — ALL GREEN, no exceptions
2. **Update `docs/benchmark-report.md`** with new numbers (PGD, federated MAR20, audio)
3. **Update `docs/pitch-content-r2.md`** with new demo cues for each new feature
4. **Write `docs/RELEASE-R3.md`** — same template as R2
5. **Update README.md** — R3 banner + new feature list
6. **Tag `v0.3.0-round3`**
7. **Final demo recording with Playwright** (F4)

---

## 9. Dependency graph

```
                ┌─────────────────────────────┐
                │  Phase 1: Frontend overhaul │
                └──────────────┬──────────────┘
                               │
             ┌─────────────────┼──────────────────┐
             │                 │                  │
        ┌────▼────┐       ┌────▼────┐        ┌────▼────┐
        │ Phase 2 │       │ Phase 3 │        │ Phase 5 │
        │ Quick   │       │ Ship    │        │ Prod    │
        └────┬────┘       └────┬────┘        └────┬────┘
             │                 │                  │
             └────────┬────────┴────────┬─────────┘
                      │                 │
                 ┌────▼────┐       ┌────▼────┐
                 │ Phase 4 │       │ Phase 6 │
                 │ ML      │       │ Research│
                 └────┬────┘       └────┬────┘
                      │                 │
                      └────────┬────────┘
                               │
                       ┌───────▼───────┐
                       │ Phase 7: Ship │
                       └───────────────┘
```

Phase 4 and 5 in parallel where checkpoints allow. Phase 6 is the overflow
bucket — defer if Phase 1-5 take longer than budgeted.

---

## 10. Operator checkpoint protocol

When the agent reaches a checkpoint that requires the operator to run something
locally (training, model download, env var setup), it does this:

1. **Write the script and any config** to disk.
2. **Print the EXACT command** the operator should run, including paths.
3. **Print expected output / ETA / success criteria.**
4. **STOP** — do not proceed to the next task.
5. **Wait for "done"** in the chat.
6. On "done", verify the artifact exists, then continue.
7. On error from operator, debug remotely (agent can read logs/files via tools), fix script, ask operator to re-run.

Checkpoints in this sprint:
- F1 PGD training (~3h on operator GPU)
- F2 Telegram bot setup (~10 min on phone)
- F5 TensorRT export (~30 min on operator GPU)
- F6 Phi-3.5 GGUF download (~2.4 GB)
- F7 Real Flower local network test
- F8 MAR20 cls federated training (~1h on operator GPU)
- F16 YAMNet audio test
- F18 Continual-learning nightly retrain (~30 min)
- F20 GitHub Actions push (operator pushes to remote)
- F22 JWT secret in .env

---

## 11. Risk register

| Risk | Probability | Mitigation |
|---|---|---|
| Frontend overhaul breaks existing demos | M | Run e2e_regression after each Phase-1 commit. Keep R2 tag for rollback. |
| PGD doesn't measurably beat baseline on 6GB GPU | M | Document the methodology as the contribution; ship the script either way. |
| RAG / Phi-3.5 install breaks on operator machine | M | Plan B (rule-based) already in war plan; UX identical. |
| Real Flower gRPC fails on Windows | H | In-process orchestrator already shipped; document as "Flower-compatible API." |
| Multi-modal audio accuracy poor on aerial domain | H | Ship as "experimental" tab; don't gate any pitch line on it. |
| 22 features bloat dashboard, hurt navigability | M | Group nav by category in sidebar v2; collapsible sections. |
| Auth gates the demo and operator forgets the password | L | Default dev creds in .env; auth-OFF flag for hackathon mode. |

---

## 12. Tracking & cadence

- Real-time work tracker: TodoWrite list (32 items)
- Per-feature commits with format `R3 F{N}: {title} — {1-line summary}`
- Daily roll-up at the end of each phase: agent posts `Phase {N} done — X commits, Y E2E green, Z files changed`
- Operator can interrupt at any time with a fresh prompt; agent persists state via this doc + TodoWrite

---

**Start signal:** Phase 1 commit #1 (design tokens + Tailwind config) begins immediately after this doc lands. No more planning.
