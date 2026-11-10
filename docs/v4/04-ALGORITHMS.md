# ASTRA v4 — Algorithms: prior art, what's new, how each is proven

> Rule: we only call something "new" when a prior-art search found nothing equivalent, and we
> re-check before publishing (Phase 0 lit review, [00-ROADMAP.md](00-ROADMAP.md)).
> Every algorithm has a **baseline, held-out data, and a kill criterion** before code is written.

## Safety boundary (applies to all algorithms)

ASTRA runs attacks **only inside simulation, against the user's own airframe profile**, to measure
and improve its robustness. There's no RF transmission code, no export of attack signals, and no
targeting of third-party systems. This is the same posture as fuzzing and CPS falsification tools.

## Prior-art status

| ID | Algorithm | Closest prior art found | Status |
|---|---|---|---|
| A1 | Failure-boundary mapping | PSY-TaLiRo / S-TaLiRo / Breach (temporal-logic falsification; a demo finds stealthy sensor attacks on a flight simulator). PGFuzz/RVFuzzer (autopilot fuzzing). Level-set estimation (active learning) | **New combination.** Maps the *whole* failure region, not one counterexample, on real ArduPilot/PX4 firmware + vendor params, under a stealth constraint |
| A2 | Co-evolved multi-channel monitor | Control-invariant detection (CCS'18), PID-Piper (DSN'21), EKF-residual ML (QUADFormer), adversarial training of IDS | **New combination.** Detector trained against the A1 adversary in a closed loop over five physical channels |
| A3 | Jam/spoof/fault classifier from ordinary logs | PoliTo AGC/C/N0 logic (receiver-level), ML papers (in-distribution) | **Incremental.** What's new is evaluating sim-trained → live-RF |
| A4 | Terrain-anchored forensic path reconstruction | TERCOM (missile navigation), RTS smoothing, LSTM log imputation, physics reconstruction (SAI 2025) | **Probably new in drone forensics** (barometer + DEM matching not found) |
| A5 | Incident → scenario inversion | GNSS threat simulators (arXiv 2405.17925), injection testbeds (arXiv 1906.03928) | **Probably new.** Estimating attack parameters from a real log and emitting a reproducible scenario wasn't found |

---

## A1. Failure-Boundary Mapping (FBM), the flagship

**Question it answers:** *"For this exact airframe and parameter set, which attacks make the
mission fail without being noticed, and how close is the vendor to that edge?"*

**Attack space** θ ∈ Θ: attack type, onset time (or mission phase), duration, drag rate
v (m/s), direction ψ, jam duty cycle, combinations, plus nuisance factors (wind, seed).

**Outcome** per sim run: robustness ρ(θ) from a Signal Temporal Logic (STL) mission spec, e.g.
`G(dist_to_geofence > 0) ∧ F[0,T](dist_to_goal < 10 m) ∨ (failsafe_triggered ∧ safe_land)`.
ρ < 0 means the mission failed. Stealth s(θ) = max detector score (built-in gating, or A2), and
s < τ means it went unnoticed.

**Algorithm:**
1. **Seed:** Sobol quasi-random design (~40 runs).
2. **Surrogate:** a Gaussian-process classifier/regressor on ρ, plus one on s.
3. **Acquire:** sample where the surrogate is most uncertain about the **boundary**
   {ρ = 0 ∧ s < τ} (straddle / level-set acquisition), not where failure is most likely.
   That gives a *map* instead of a single counterexample.
4. **Multi-fidelity:** screen with PX4 SIH / fast ArduPilot (high speed-up, coarse), and confirm
   boundary points at full fidelity.
5. **Stop** when boundary uncertainty is below ε or the budget runs out.

**Outputs:**
- **Robustness margin** M = min ‖θ − θ_nominal‖ over the stealthy-failure region (e.g. "smallest
  undetected drag that breaks it: 0.7 m/s").
- **Failure atlas:** 2-D slices (drag rate × onset phase, etc.) for the UI.
- Reproducible counterexample scenarios (YAML) for regression.

**Baseline:** a random sweep and a grid sweep with the same sim budget.
**Metric (S9):** unique stealthy-failure clusters found per 100 sim-hours, and boundary-estimate
accuracy against a dense ground-truth grid on 2 reference airframes.
**Target:** ≥ 1.5× random at equal budget.
**Kill criterion:** if it's < 1.2× random on both reference airframes after tuning, ship grid
sweeps and drop the claim.

**Tools:** BoTorch/GPyTorch (MIT) or scikit-learn GPs, SciPy Sobol, our own STL robustness
(simple; the `rtamt` library, BSD, is an option).

## A2. Co-evolved Multi-Channel Monitor (CMM)

**Channels** (all derivable from standard ArduPilot/PX4 logs):
1. EKF innovation test ratios (the baseline)
2. GPS vs IMU dead-reckoning position/velocity residual
3. **Control-response consistency:** predicted vs GPS-observed acceleration given attitude and
   thrust commands (a vehicle model identified per airframe from benign flights)
4. **Wind-estimate consistency:** sudden or unjustified wind-state change (fixed-wing needs an
   airspeed sensor or sideslip fusion; on copters use drag-model wind)
5. Baro vs GPS altitude residual

**Detector:** per-channel normalised residuals → a **multi-channel CUSUM/GLR** for persistent bias
plus a small gradient-boosted classifier on windowed features. Calibrated to a **false-alarm budget**
(≤ 1 per 10 flight-hours on benign data).

**Co-evolution loop:** A1 attacks the current CMM and finds stealthy failures. Those
counterexamples join the training set, and the monitor is re-calibrated. Repeat k rounds and report
the **margin after each round** (does the stealthy-failure region shrink?).

**Baseline:** built-in EKF gating (L0).
**Metrics:** S1 (drag-off detection at a fixed FAR), S2 (latency).
**Target:** S1 ≥ +40 pp, S2 ≥ 40% faster.
**Kill criterion:** if channels 3–4 add < 10 pp over channels 1–2 + 5, drop them (simpler monitor).
**Guard:** report the final-round A1 margin against CMM itself. Never claim "undetectable-proof".

## A3. Jam / spoof / fault classifier

Features: sat count, hAcc/vAcc/sAcc, noise/jamming indicators, fix type, C/N0/AGC when logged,
plus A2 residuals. Physics prior from PoliTo: AGC↓ C/N0↓ → jamming; AGC↓ C/N0 steady →
spoofing. Model: LightGBM.
**Protocol:** train on SITL + IEEE "HITL" logs, test on the **IEEE live-RF** logs (never seen).
**Metric:** S3 macro-F1 ≥ 0.85.
**Kill criterion:** if cross-dataset F1 < 0.7, ship rule-based physics logic only and state it.

## A4. Terrain-Anchored Forensic Reconstruction (TAFR)

1. Detect onset t₀ (A2).
2. From t₀: forward EKF on IMU + baro + compass (+ flow/VIO if present), **no GPS**.
3. **Terrain anchor:** height above ground (rangefinder, or baro minus takeoff elevation with
   drift modelling) gives a terrain-elevation profile along the dead-reckoned track. Correlate it
   against Copernicus GLO-30 DEM patches around candidate offsets (grid search + particle filter)
   to estimate the horizontal offset. This works only over varied terrain, and over flat terrain
   it reports "unanchored".
4. **RTS backward smoother** over the whole segment using both ends: last trusted GPS fix and,
   if any, a later trusted fix or the known crash/landing point.
5. Output: the reconstructed track with **1σ/2σ error ellipses**.

**Validation:** SITL flights with ground truth (spoof injected, true path known), over Ladakh-like
(varied) and Rajasthan-like (flat) DEM tiles.
**Metric:** median position error vs dead reckoning alone.
**Target:** ≥ 40% lower error over varied terrain, and honest "unanchored" output over flat terrain.
**Kill criterion:** no gain over the RTS smoother alone, so drop the terrain anchor.

## A5. Incident → Scenario Inversion (ISI)

Given a real log: a parametric attack model θ (from A1's space) + SITL replay of the same
mission/params → minimise ‖residuals_real − residuals_sim(θ)‖ over the A2 channels (Optuna/CMA-ES,
or BoTorch reusing A1's surrogate).
**Output:** a scenario YAML that reproduces the incident's signature, plus a fit score.
**Validation:** take SITL incidents with *known* θ and recover θ (parameter error).
**Metric:** drag-rate error ≤ 20%, onset error ≤ 5 s on synthetic incidents. Then try it on IEEE
live logs.
**Kill criterion:** an unidentifiable fit (flat objective), so report "can't reproduce" instead of
a wrong scenario.

## Sources

[PSY-TaLiRo stealthy attack demo](https://par.nsf.gov/servlets/purl/10433147) · [PSY-TaLiRo](https://ar5iv.arxiv.org/html/2106.02200) · [ARCH falsification report](https://www.sosy-lab.org/research/pub/2019-ARCH.Category_Report_Falsification.pdf) · [PGFuzz](https://www.ndss-symposium.org/ndss-paper/pgfuzz-policy-guided-fuzzing-for-robotic-vehicles) · [Control-invariant detection, CCS'18](https://par.nsf.gov/servlets/purl/10086394) · [Stealthy attacks vs control-based detection, ACSAC'19](https://blogs.ubc.ca/karthik/files/2019/09/acsac19.pdf) · [PID-Piper](https://people.ece.ubc.ca/zitaoc/files/Pid-Piper-DSN21.pdf) · [QUADFormer](https://arxiv.org/abs/2501.07597) · [Adversarial robustness of GPS-spoofing IDS](https://par.nsf.gov/servlets/purl/10535570) · [PoliTo AGC + C/N0](https://iris.polito.it/retrieve/handle/11583/2839032/383268) · [Drone forensics challenges](https://arxiv.org/pdf/2105.10917) · [Physics-based reconstruction, SAI 2025](https://thesai.org/Downloads/Volume17No2/Paper_2-A_Confidence_Aware_Multi_Layer_Framework.pdf) · [LSTM telemetry reconstruction](https://mdpi-res.com/d_attachment/jcp/jcp-06-00123/article_deploy/jcp-06-00123.pdf) · [GNSS threat simulator](https://arxiv.org/html/2405.17925v2) · [Spoofing injection testbed](https://arxiv.org/pdf/1906.03928) · [UAV Attack Dataset](https://ieee-dataport.org/node/2097)

---

## Status after the first build session (measured; details in PROGRESS.md)

| ID | Built | Measured result | Verdict vs kill criterion |
|---|---|---|---|
| A1 FBM | ✅ `astra.search`, `search_sitl` | Synthetic 2-D: 34–86% lower boundary error than random. **SITL 2-D: 97.6% vs random 100%**, no gain on a simple boundary | Kill criterion (< 1.2× random on both reference airframes) **not yet evaluated properly**: needs a 4-D SITL test. Keep, unproven |
| A2 monitor | ✅ v6 `astra.detect` | Held-out: 0 false alarms in 6.9 h. Slow drag-off detection 10/96 (stock) → 40/96 (GPS+IMU) → 65/96 (+flow) | S1 target met with a flow witness (+57 pp). C1 (Δv onset) contributes almost nothing (thresholds very high), candidate for removal |
| A2 onboard ("Shield", C3 in Lua) | ✅ `astra.onboard` | Evaluation in progress | – |
| A3 classifier | partial: rule-based verdict in `astra.forensics` | Not yet scored (needs jamming corpus + real logs) | – |
| A4 terrain anchor | ❌ | SITL ground is flat at the reference site, and terrain-following SITL is unverified | Deferred |
| A5 inversion | ❌ | – | Backlog (C2/C3 residuals already estimate the bias vector directly) |
| A6 param advisor | sweep script `benchmarks/a6_params.py` | Pending | – |

Design changes forced by measurement (keep these lessons):
- Per-sample CUSUM on autocorrelated residuals can't work. Use **block statistics**, with drift from the design shift.
- Flow model must be **geometric** (full body-frame velocity / slant range). The level-flight approximation breaks at cruise tilt.
- Use **block medians**: single bad flow frames are tens of m/s at 40 m range.
- "Robustness margin" must be the **upper** edge of the undetected region when failures start at the bottom of the range.
