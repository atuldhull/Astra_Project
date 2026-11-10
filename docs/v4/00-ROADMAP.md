# ASTRA v4 — Roadmap: the order we build in, and the gates between phases

> Start here. Reading order: **00 Roadmap → [01 Research](01-RESEARCH.md) →
> [02 Tech verification](02-TECH-VERIFICATION.md) → [03 Product spec](03-PRODUCT-SPEC.md) →
> [04 Algorithms](04-ALGORITHMS.md)**.

## Principles: how we avoid building things that fail later

1. **No phase starts until the previous gate passes.** Each gate has numbers. If a gate fails, we
   re-plan; we don't push on.
2. **Prove the risky thing first.** Attack injection and baseline measurement come before any UI,
   because everything depends on them.
3. **Every feature needs a user from 03 §2.** No user, no feature. (v3's failure.)
4. **Every algorithm needs a baseline, held-out data and a kill criterion before code** (04).
5. **Pin everything:** ArduPilot/PX4 release tags, Docker image digests, Python lockfile, seeds.
   Same inputs give the same result, forever.
6. **Interfaces before implementations:** scenario schema, run-result schema and attack-model API
   are versioned JSON schemas from day one, so later parts plug in without rewrites.
7. **Never depend on undocumented behaviour** (e.g. PX4 EKF2 spoof flags): use it if present,
   never require it.
8. **No lock-in:** everything runs fully offline on one laptop. Free cloud tiers are optional
   accelerators and can disappear (Oracle already halved its free tier in 2026).
9. **Licence check before adding any dependency** (OSI-approved only). Datasets used under their
   terms and never redistributed without permission.
10. **Tests in the same commit as the code.** CI must stay green. The v3 lesson: a test must fail
    when the thing it guards is broken (mutation-check critical tests).
11. **Honest numbers:** every claimed metric is produced by a script in `benchmarks/` and published,
    including misses.

## Phases and gates

```
P0 Foundation ─► G0 ─► P1 Feasibility spike ─► G1 ─► P2 Core engine ─► G2 ─► P3 Algorithms ─► G3 ─► P4 Product ─► G4 ─► P5 Pilot
```

| Phase | Work | Gate (must all pass) | If the gate fails |
|---|---|---|---|
| **P0 Foundation** (wk 0) | `v4` branch. Tag `v3.0-final`. Remove dead v3 modules (03 §6). Apache-2.0 LICENSE. Repo layout. Pinned toolchain. CI skeleton. JSON schemas v0 (scenario, run result, attack model). Lit-review pass on A1–A5 novelty | **G0:** CI green on the stripped repo. Schemas committed. Kept v3 tests (provenance/audit) still pass | Fix before anything else |
| **P1 Feasibility spike** (wk 1–2) | V1–V7 from 02 §4: SITL in Docker, 8× parallel, attack proxy injects drag-off, baseline gating curve, parse IEEE logs, PX4 SIH, FBM spike | **G1:** proxy reproduces all 7 attack models in logs. ≥ 40× aggregate real-time. Baseline S1/S2 curves recorded. IEEE live-RF logs parse | Proxy can't reach the EKF realistically → re-design injection (e.g. a simulated GPS driver in SITL) before continuing. Too slow → reduce fidelity tier |
| **P2 Core engine** (wk 3–5) | Attack proxy (7 models). Scenario packs. Parallel runner. STL scoring. Results API. Signed report v0 | **G2:** "EW Pre-Qual v1" (30 scenarios × 10 seeds) runs unattended overnight. Results reproducible bit-for-bit on re-run. Report verifies offline | Fix reproducibility first (determinism is non-negotiable for a test lab) |
| **P3 Algorithms** (wk 6–9) | A2 monitor → A3 classifier → A1 FBM → A2 co-evolution → A4 → A5 (dependency order) | **G3:** each algorithm meets its target *or* hits its kill criterion and is dropped/simplified, with the result published | Kill criteria in 04 apply. There's no "almost" |
| **P4 Product** (wk 9–10) | UI: profiles → run → atlas/replay → forensics → report → verify. Regression diff. OpenTimestamps. Auth hardening | **G4:** Playwright e2e of W1–W3. Red-team: a tampered report fails verify (S7). Docs and README with real numbers | — |
| **P5 Pilot** (wk 10+) | 2–3 OEMs run their own params offline. Measure S4 (diagnosis time) and S8 (sim-to-real) | ≥ 1 OEM would use it before their next trial | Learn why, adjust scope |

## Dependency order inside P3

```
A2 (monitor)  ──►  A3 (classifier, uses A2 features)
     │
     └──►  A1 (FBM, uses A2 as the stealth score)  ──►  A2 co-evolution (uses A1 counterexamples)
                                                    └──►  A5 (reuses A1 surrogate/search)
A4 (reconstruction, uses A2 onset)  — independent after A2
```

## Target repo layout (after P0)

```
astra/
├── backend/app/
│   ├── api/            profiles, packs, runs, results, forensics, reports, audit, health, ws
│   ├── runner/         job queue, SITL container orchestration
│   ├── attack/         GPS attack proxy + 7 attack models
│   ├── scoring/        STL specs, robustness, metrics
│   ├── forensics/      parsers, monitor (A2), classifier (A3), reconstruction (A4), inversion (A5)
│   ├── search/         failure-boundary mapping (A1)
│   ├── integrity/      provenance (signing), audit chain, timestamp anchoring
│   ├── reports/        JSON + PDF
│   └── db/
├── schemas/            scenario.schema.json, run_result.schema.json, attack_model.schema.json
├── packs/              ew-prequal-v1/*.yaml (versioned, hashed)
├── sim/                Dockerfiles: ardupilot-sitl, px4-sih (pinned tags)
├── benchmarks/         scripts producing every published number + results
├── cli/                astra run | verify | diagnose
├── frontend/           React shell (kept) + new pages
├── docs/v4/            these docs
└── LICENSE             Apache-2.0
```

## Decisions log

| Date | Decision | Why |
|---|---|---|
| 2026-11-10 | Pivot v3 → ASTRA Proving Ground | 01-RESEARCH |
| 2026-11-10 | Fully software; open-source deps only; free tiers only, never required | User constraint + principle 8 |
| 2026-11-10 | Project licence Apache-2.0 (proposed) | Free CI for public repos. Auditability for a neutral test lab |
| 2026-11-10 | Attacks run in simulation only, against the user's own profile | Safety boundary, 04 |
| 2026-11-10 | ArduPilot first, PX4 second (proposed) | Richer SITL GPS simulation |
