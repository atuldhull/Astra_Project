# ASTRA v4 — Algorithm backlog (ordered) for the next build session

> Written at the end of the first build session (2026-11-11) for the next model/session (Fable 5.2).
> Everything here is grounded in what was **measured** (see `benchmarks/RESULTS.md`). Each item has: why,
> approach, what it needs, how it will be judged (acceptance), when to stop (kill criterion), and order
> dependencies. Rules from HANDOFF.md apply: real-benign-flight gate, fresh held-out sets, no tuning on
> test data, harness failures are `error`.

## State of the art inside ASTRA (what already exists)

| ID | Algorithm | Status | Best measured result |
|---|---|---|---|
| A1 | Failure-boundary mapping (GP level-set) | done | 4-D: 6.5× more stealthy failures than random, 5/5 seeds |
| A2 | Block-median CUSUM monitor (C2 flow, C3 pos-vs-vel) | done v7 | 84/95 slow drag-offs (stock 9/95), 0 FA in 7.2 h |
| A2-onboard | Shield (Lua, C3) / Shield-Companion / Flow-Shield | done | Flow-Shield 42/47 consistent drags live; Shield 35/35 naive |
| A3 | Rule-based verdict (jam/spoof/mixed/none) | done v2 | 209/223 held-out, benign never accused |
| A5 | Incident → scenario inversion | done v2 | type 84/84, rate 9%, bearing 2°; re-fly within 8% for 3/4 |
| A6 | EKF parameter advisor (sweep) | done v1 | naive 0/12 → 12/12 with tuning; small benign sample |

## Ordered backlog

### 1. Real-attack validation (data, not a new algorithm) — **highest priority**
- **Why:** every detection number is simulation. S8 (sim-to-real) is only measured on the benign side.
- **Approach:** download the IEEE DataPort *UAV Attack Dataset* and *HITL UAV DoS/GPS spoofing* sets
  (PX4 ULog, includes live-RF spoofing/jamming). The user must create the free account and download.
  Run `astra diagnose` (the ULog adapter exists) and the Shield-Companion mirror on them.
- **Needs:** the datasets. Possibly extend `ulog.py` for older PX4 topic names (`vehicle_gps_position`).
- **Acceptance:** report per-file verdict vs dataset label. Target: ≥ 80% correct type on live-RF attacks
  and 0 false accusations on their benign flights.
- **Kill:** none. Whatever the result is, it gets published.

### 2. Fixed-wing witness channel (C4: airspeed/wind consistency)
- **Why:** on ArduPlane, consistent drag-offs are 0/24 detected. Fixed-wing matters for defence (loitering
  munitions, ISR).
- **Physics:** a consistent GNSS velocity bias b makes the inferred wind w_est = v_gps − v_air jump by b at
  onset. A constant b is indistinguishable from a real wind change, so detection must come from the
  **change-point** and from wind-physics priors (mean-wind change rates at low altitude, consistency
  across a loiter circle's headings, and agreement with a second independent wind estimate, e.g. from
  bank-angle/turn-rate dynamics).
- **Needs:** realistic wind variability in SITL first (`SIM_WIND_T`, `SIM_WIND_TC`, gust models), or the
  result will be inflated (constant SITL wind makes any wind change look anomalous). Corpus: ≥ 80 plane benign
  flights with variable wind.
- **Acceptance:** consistent drag ≥ 1 m/s detected ≥ 50% at ≤ 1 FA per 10 h on held-out plane flights
  *with variable wind*.
- **Kill:** if with realistic wind the benign false-alarm budget forces detection below 25%, publish the
  negative result and stop.

### 3. Low-rate naive spoof (0.25 m/s) improvement
- **Why:** weakest remaining naive case (offline 4/12; Shield 6/12).
- **Approach:** longer-horizon statistic. Integrate position-minus-velocity-integral over 60–120 s
  (displacement test) instead of 4 s blocks. Combine with the block CUSUM via a GLR over multiple window lengths.
- **Needs:** existing corpora (attack-dev for design, a **fresh** attack-test3 + benign-v4 for scoring).
- **Acceptance:** 0.25 m/s naive ≥ 8/12 with unchanged FA (0 in ≥ 7 h held-out) **and** passing the real-flight
  gate (≤ 0/39 on the PX4 public set).
- **Kill:** the real-flight gate fails (as raw-fix C3 did, 1/39).

### 4. Flow-Shield robustness to degraded flow
- **Why:** with a degraded flow sensor, consistent drags ≥ 1 m/s are caught only at 178–365 m.
- **Approach:** (a) adaptive per-flight noise estimation (scale Σ by a running robust variance of the
  flow residual, frozen during alarms); (b) a quality-weighted median (use OPTICAL_FLOW.quality); (c) fuse
  C2 with C3 evidence in one GLR.
- **Acceptance:** degraded-flow consistent drag ≥ 1 m/s alarm at ≤ 120 m median error, FA unchanged.
- **Kill:** no improvement over v7 on a fresh degraded set.

### 5. A1 extensions (multi-objective, multi-fidelity)
- **Why:** A1 wins in 4-D. Vendors care about the *cheapest* attack that breaks them.
- **Approach:** add attack-cost objective (e.g. drag rate × duration, or RF power proxy), Pareto front of
  (stealth, failure, cost). Multi-fidelity: screen at 20× / short missions, confirm boundary points at
  full mission length.
- **Acceptance:** same or better F1 than single-fidelity A1 at ≤ 60% of the simulator time.

### 6. A6 v2: closed-loop parameter optimisation
- **Why:** v1 is a fixed sweep on a tiny benign sample.
- **Approach:** Bayesian optimisation over EK3 gates/noises/glitch radius with constraint FA ≤ budget
  (measured on ≥ 80 benign flights), objective = A1 robustness margin. Report a Pareto table, never a single
  "best".
- **Acceptance:** a setting that beats defaults on naive detection with 0 extra benign alerts on ≥ 80 flights.

### 7. A5 v3: inversion for jamming and jumps; uncertainty
- **Approach:** fit duty cycle/period for intermittent jamming from fix-loss intervals; jump offset from
  the step residual. Add bootstrap confidence intervals on rate/bearing/onset.
- **Acceptance:** re-fly reproduction within 20% on ≥ 8/10 fresh incidents of each type.

### 8. PX4 parity items
- `astra advise` for EKF2 (`EKF2_GPS_P_NOISE`, `EKF2_GPS_V_NOISE`, `EKF2_GPS_P_GATE`, `EKF2_GPS_V_GATE`).
- PX4 optical flow in SIH (if supported) so Flow-Shield can be validated on PX4.

### 9. Power-on spoofing (absolute reference)
- **Why:** consistency monitors can't see a spoof that is present from boot (05-DETECTION-PHYSICS §1).
- **Approach:** known take-off point check (operator-entered or map-matched) and, longer term, a visual
  absolute-position fix. This is the crowded visual-navigation market; only pursue as a *check*, not
  a navigator.

## How to judge any new algorithm (copy this checklist)

1. Design only on dev corpora (`attack-dev`, `benign-v1`, `mixed-dev`).
2. Freeze the code and constants. Commit.
3. Generate **fresh** corpora (new RNG tags) and score once. Publish all misses and errors.
4. Pass the real-benign-flight gate (`benchmarks/real_far.py`, 39 public PX4 flights).
5. Update `benchmarks/RESULTS.md`, `PROGRESS.md`, and the README only with the published numbers.
