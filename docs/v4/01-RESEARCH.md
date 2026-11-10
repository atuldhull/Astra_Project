# ASTRA v4 — Research: problem, workflows, existing solutions

> Status: research complete, 2026-11-10. Product: **ASTRA Proving Ground**, a software-only test,
> scoring and forensics lab for drone navigation under GPS jamming and spoofing.
> Next: [02-TECH-VERIFICATION.md](02-TECH-VERIFICATION.md) → [03-PRODUCT-SPEC.md](03-PRODUCT-SPEC.md).

## 1. Directions considered and rejected

| Direction | Why rejected |
|---|---|
| v3 as-is (aerial detection + signed audit) | Recall 0.49 can't triage. Threat-score motion term hardcoded to 0. Provenance signs whatever is uploaded with a key on the same disk. Federated/mesh/Sentinel are simulations. No user |
| Imagery-claim verification for fact-checkers | Weak demand: people who share fakes don't seek verification, and the user base is a few dozen unpaid desks |
| Better detector / visual navigation module | Crowded (Endee Labs, PhoQtek, VECROS, SurveyX, Paar, Zuppa, Vermeer, Twist). Needs hardware and flight testing. The user asked for software-only |

## 2. The problem

**Drones lose navigation under GPS jamming and spoofing, and makers have no cheap, repeatable way
to test for it before the one trial that decides their contract.**

- **India, post-Sindoor.** Reported Army GPS-denied trials (Sept 2025, near Dehradun): none of 46
  indigenous makers passed. Drones drifted or crashed within minutes of EW activation. The Army
  reportedly wants GPS-alternative navigation in the next iDEX cycle, and ₹10,000 crore was
  announced for EW-hardened prototypes. *(Secondary source: idrw citing India Today; not officially
  confirmed.)*
- The Army's later EW trials "focused aggressively on the terminal phase, where most drones fail
  under real-world jamming", using multi-spectrum GNSS jammers, at altitudes up to 17,500 ft.
- Armed forces publicly list "GPS-free operations" and beating jamming as top drone requirements
  (Tribune).
- Border airspace: DGCA logged 465 GPS interference/spoofing events in Punjab and Jammu between
  Nov 2023 and Feb 2025. There were 863 drone incursions from Pakistan in a year.
- **Ukraine:** about 75% of small tactical UAV losses are caused by EW (Technology Forces of Ukraine).

### Who is forced to care

| User | Why they can't ignore it | What they need |
|---|---|---|
| **Indian drone OEMs** (46+ who faced Army trials) | No pass, no contract. A trial is one shot | Find failures *before* the range. Re-test every firmware change |
| **Trial evaluators** (Army, DGQA, DRDO labs, IAF Dronathon) | Must compare vendors fairly and record results | Standard scenarios, comparable scores, tamper-proof records |
| **Navigation-module startups** (Endee, PhoQtek, …) | Must prove their module helps on a customer's airframe | Neutral benchmark against GPS-only baselines |
| **Operating units** | After a loss: was it jamming, spoofing, or a fault? | Flight-log forensics |

## 3. Current workflows (where we fit)

### 3.1 Procurement and trial pipeline (India)

```
RFI ──► TEC clearance ──► Field Evaluation Trials ──► Staff evaluation ──► DGQA cert ──► Order
                          ("No Cost No Commitment",    (SHQ shortlists)     (MIL-STD-810H etc.)
                           EW / GNSS-denied phases)
        + MoD 20-point security evaluation for military drones
```

The vendor pays for trial participation in time, travel and lost airframes, and gets one shot. **Between
RFI and Field Evaluation Trials, vendors have no standard EW test.** That gap is where ASTRA fits.
Field trial certificates are signed on paper by a DGQA-designated officer.

### 3.2 OEM engineering loop today

1. Build on ArduPilot (GPLv3) or PX4 (BSD-3). Most Indian small drones are Pixhawk-class, and an
   ex-Army general noted that most Sindoor drones were "assembled, core systems not made in India".
2. Tune parameters in SITL or on the bench. GPS-loss testing is ad hoc: `SIM_GPS_DISABLE`,
   `SIM_GPS_GLITCH_*` (ArduPilot) or `SIM_GPS_BLOCK` / failure injection (PX4).
3. Field-test where possible. Real jamming is illegal outside authorised ranges, so most vendors
   **can't test real jamming at all**.
4. Go to trial. Fail. Read logs in PX4 Flight Review / UAV LogViewer / QGC by hand. Guess the cause.

### 3.3 Existing tools at each step

| Step | Tool | What it does | Gap |
|---|---|---|---|
| RF-level testing | **Safran Skydel GSG-8**, Spirent | Software-defined GNSS RF simulators with jamming and spoofing scenarios | Price on request (lakhs–crores), RF hardware, tests the **receiver**, not whether the whole drone completes the mission |
| Autopilot fuzzing | **PGFuzz** (NDSS'21), **RVFuzzer** (USENIX Sec'19), RVAT | Policy-guided fuzzing of ArduPilot/PX4. PGFuzz found 156 bugs, including a PX4 GPS-loss failsafe that didn't trigger in ORBIT mode | Academic, general-purpose bug hunting. No EW scenario library, no mission scoring, no reports |
| GNSS-denied sim research | Stochastic fixed-wing sim (arXiv 2102.00883), Pegasus (Isaac Sim) | Monte Carlo testing of nav algorithms | Research code. One airframe type. Not the vendor's own firmware and params |
| Built-in protection | PX4 EKF2 innovation gating, multi-EKF, `EKF2_GPS_CHECK` spoof/jam flags | Rejects inconsistent GPS | Spoof/jam flags are driver-dependent and undocumented. **Carefully shaped injection can keep the innovation ratio under threshold** (IEEE Access 2024). ArduPilot: no built-in spoof detector found |
| Log analysis | **PX4 Flight Review** ("GPS Noise & Jamming" plot), UAV LogViewer, QGC Log Viewer, Mission Planner | Plots | **No spoofing detection, no jamming-vs-spoofing classification, no reconstructed true path**. Expert reads plots by hand |
| Spoof detection research | QUADFormer (transformer on EKF residuals), MSSTP-OAD (0.984 acc), XGBoost on 30 features, C/N0 + AGC discrimination (PoliTo) | Papers | Each tested on its own data. No tool. No cross-dataset results |
| Datasets | IEEE DataPort: UAV Attack Dataset (PX4 ULog, sim and **live RF** spoofing/jamming), HITL GPS-spoofing set (PX4 1.11, Pixhawk 4), Drone Sensor Fusion set | Labelled attacked flights | Raw data only |
| Field trials | Army, IAF Dronathon (Pokhran) | Ground truth | One shot, months apart, paper results |

### 3.4 The gap

We found no product that runs the **vendor's own firmware and parameters** through a **standard
library of jamming and spoofing scenarios**, scores **mission outcomes**, diagnoses **real flight
logs**, and issues **tamper-proof results** an evaluator can trust. Today an OEM combines SITL
parameters, manual log reading and hope.

## 4. Why this direction is optimal

| Criterion | ASTRA Proving Ground |
|---|---|
| Real, current, forced demand | ✅ Army trials, iDEX cycle, EW requirement after Sindoor |
| Fully software | ✅ SITL, logs, reports |
| Reachable users | ✅ OEMs are public companies and iDEX participants. Pilot at the next iDEX/Dronathon |
| Crowdedness | ✅ Navigation modules are crowded; *testing and forensics* are not (none found) |
| Free building blocks | ✅ ArduPilot, PX4, pymavlink, pyulog, public attack datasets |
| Laptop-feasible | ✅ SITL runs multi-instance, faster than real time |
| Uses existing ASTRA code | ✅ backend, DB, React shell, Ed25519 signing, hash-chain audit, PDF reports |
| Neutral position | ✅ Benchmarks every nav-module startup instead of competing with them |

**Risks to validate early:** OEM willingness to pay (talk to 3–5 OEMs), and sim-to-real fidelity
(validate against the IEEE DataPort *live* RF logs).

## Sources

**Problem / India:** [idrw: 46 makers fail GPS-denied trials](https://idrw.org/indian-armys-drone-wake-up-call-46-indigenous-makers-fail-gps-denied-trials-post-op-sindoor-exposing-electronic-warfare-gaps/) · [idrw: Army EW trials, terminal phase](https://idrw.org/indian-armys-latest-drone-trials-become-a-combat-grade-audition-only-a-few-indian-firms-survive-the-ew-gauntlet/) · [Tribune: forces want GPS-free ops](https://www.tribuneindia.com/news/india/post-operation-sindoor-armed-forces-look-at-next-gen-tech-on-drones) · [The Week: Army EW/drone trials](https://www.theweek.in/news/defence/2025/05/31/indian-army-tests-killer-drones-electronic-warfare-tools-in-combat-trials-across-country.amp.html) · [The Week: 225 FPV, 17,500 ft trials](https://www.theweek.in/news/defence/2026/10/07/indian-armys-high-altitude-warfare-capabilities-set-for-a-major-boost-as-force-adds-225-fpv-drones.html) · [20-point security testing](https://newsable.asianetnews.com/india/india-new-drone-security-rules-aim-to-stop-hidden-foreign-control-risks-20-point-security-testing-for-military-drones-articleshow-k8flitp) · [idrw: GPS interference on the border](https://idrw.org/indian-aviation-experts-demand-jamming-resistant-overhaul-as-gps-interference-from-pakistan-border-endangers-skies/) · [863 incursions](https://www.newsbytesapp.com/news/india/india-logged-863-drone-incursions-from-pakistan-last-year/tldr) · [Assembled, not made in India](https://www.businesstoday.in/india/story/ex-army-general-warns-most-drones-in-op-sindoor-were-assembled-core-systems-are-not-made-in-india-482646-2025-07-01) · [Pravda: Twist Robotics / 75% EW losses](https://www.pravda.com.ua/eng/news/2026/01/28/8018266)

**Procurement:** [DRDO/DPSU trial procedure draft](https://www.scribd.com/document/630963367/DraftChIIIADRDOOFBDPSU) · [Coast Guard RPA RFI](https://indiancoastguard.gov.in/sites/default/files/10%20male%20rpa%20rfi.pdf) · [DDP field-trial template](https://www.ddpmod.gov.in/sites/default/files/adffe484b91c7f9d4da622ce1761eef657db6013cb70d13ad5eccd54802faa94/d2c6b5fe5ec7e7ca99be59a24b4514ba0cf4e4885a23bae6bbeb2f53f2958340.pdf)

**Competitors / tools:** [Safran Skydel GSG-8 Gen2](https://safran-navigation-timing.com/product/skydel-gsg-8-gen2) · [GSG-8 Gen2 datasheet](https://safran-navigation-timing.com/wp-content/uploads/2025/10/SAFRAN-GSG-8-Gen2-Datasheet-10-27-2025-US.pdf) · [PGFuzz](https://www.ndss-symposium.org/ndss-paper/pgfuzz-policy-guided-fuzzing-for-robotic-vehicles) · [RVFuzzer](https://friends.cs.purdue.edu/pubs/USENIXSec19.pdf) · [RVAT](https://github.com/Lqs66/RVAT) · [Fixed-wing GNSS-denied sim](https://arxiv.org/abs/2102.00883) · [PX4 Flight Review](https://docs.px4.io/v1.11/en/log/flight_review.html) · [UAV LogViewer](https://ardupilot.org/dev/docs/common-uavlogviewer.html) · [QGC Log Viewer](https://docs.qgroundcontrol.com/master/en/qgc-user-guide/analyze_view/log_viewer.html) · [PX4 forum: EKF2 spoof/jam flags](https://discuss.px4.io/t/gps-jamming-and-spoofing/48265) · [ArduPilot forum: pre-flight spoof detection](https://discuss.ardupilot.org/t/how-to-detect-gps-spoofing-during-pre-flight-before-takeoff/141346) · [Endee Labs](https://unmannedairspace.info/uncategorized/endee-labs-introduces-ai-enabled-visual-navigation-system-for-drones) · [Vermeer](https://optics.org/news/vermeer-raises-10m-for-optical-drone-navigation)

**Datasets / research:** [UAV Attack Dataset](https://ieee-dataport.org/open-access/uav-attack-dataset) · [HITL GPS spoofing dataset](https://ieee-dataport.org/open-access/hitl-uav-dos-gps-spoofing-attacks-mavlink) · [Drone Sensor Fusion Dataset](https://ieee-dataport.org/node/15046) · [IEEE Access 2024: PX4 spoofing](https://doaj.org/article/3ba38236b8594ca9a212e55aebe56784) · [QUADFormer](https://arxiv.org/abs/2501.07597) · [Rigid-covert swarm spoofing](https://arxiv.org/abs/2608.06885) · [ML spoofing detection 2025](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12251763/) · [PoliTo AGC + C/N0](https://iris.polito.it/retrieve/handle/11583/2839032/383268) · [GNSS-SDR anti-spoofing](https://pubs.gnuradio.org/index.php/grcon/article/download/73/55)
