# Real field attacks: Jammertest 2023 (Andøya, Norway) recordings through a software receiver (2026-11-13)

**Data.** FGI Jammer Test 2023 Repository (CC BY 4.0; Liaquat, Bhuiyan, Islam; FGI / National Land Survey of
Finland; https://etsin.fairdata.fi/dataset/2eee8cfd-db00-4e46-bd62-d7632c09c700). Raw L1/E1 I/Q from a LabSat 3
(30.69 MS/s, int8), recorded at the official Norwegian GNSS jamming/spoofing test event. Three tests:

| test | attack | recording | attack visible in the RF band |
|---|---|---|---|
| JT23_4.1.5 | high-power PRN-noise jamming | 400 s | 255 s → end (spectral flatness 0.89 → 0.43) |
| JT23_16.1.1 | incoherent spoofing (true ephemerides) | 896 s | ~120–700 s (power ×1.9) |
| JT23_17.1.6 | coherent spoofing (true ephemerides) | 1174 s | ~360–980 s (power ×2.3) |

**Pipeline** (`benchmarks/jammertest_fetch.py`, `jammertest/gnss-sdr.conf`, `jammertest_to_log.py`): each file streamed
(never stored whole; 152 GB in, 19 GB kept), low-passed and decimated ×8 to 3.84 MS/s; GNSS-SDR v0.0.22 (Docker
`carlesfernandez/docker-gnsssdr`, GPS L1 C/A, 12 channels) produces fixes every 200 ms; these become an ASTRA log in
"bench mode": static recorder (checked), stationary IMU (gravity only), airborne from 5 s after the first fix,
receiver noise = full-band power (fixed before scoring). No receiver self-report.

**What the receiver did (ground truth from its own output):** jamming: all satellites lost at 256 s, no fix until the
end. Incoherent spoof: after a 19–43 s outage the receiver re-acquired **~249 km away** with a healthy 9-satellite
fix for ~9 min, then jumped back after the spoofer stopped. Coherent spoof: captured after short outages, held ~31 m
off for ~4 min, then **dragged around a ~1 km loop at up to 25 m/s (altitude to 345 m)**, recorder actually static.

## Scores

**Blind (frozen 673b37d, harness v1, scored once):**

| test | verdict | right? |
|---|---|---|
| jamming | RF-attack-like (noise ×1.30 + fix loss at 317.6 s; outage detected from 256.4 s) | yes |
| incoherent spoof | RF-attack-like at 129.6 s (attack starts ~120 s) | attack yes; **spoof not identified, 249 km jump missed** |
| coherent spoof | RF-attack-like at 376.4 s (attack starts ~360 s) | attack yes; **spoof not identified, drag missed** |

**Real attacks detected blind: 3/3. Spoofing identified as spoofing: 0/2.**

**Why, and what changed (1298454; these recordings are now design data):**
1. Evidence near an outage was discarded as a "jamming artefact", including the 249 km re-acquisition jump.
   New physical check: re-acquired position farther than 100 m + 60 m/s × outage → spoofing evidence
   ("position jumped 248.6 km across a 43 s outage"). Not fitted to these data.
2. The GPS/IMU monitor and step check reported only their *first* alarm, so an early benign glitch hid a later
   attack. Now every alarm episode is evidence.
3. Harness v1 passed GNSS-SDR's single-epoch covariance (6–16 m) as the receiver accuracy, which made ASTRA treat
   the whole recording as "degraded"; v2 uses HDOP × 1.5 m (u-blox-like) and turns on GNSS-SDR's navigation filter.

**After the changes (design data, not validation):** incoherent spoof → position jump of 248.6 km found at 173 s and
241 km back at 749 s (no jumps in the jamming file or before any attack). Coherent spoof: still only RF-attack-like
from receiver evidence.

**What this harness cannot test:** the GPS-vs-IMU consistency checks (A2 monitor, position steps). The software
receiver's fixes wander 8–18 m in the clean minutes before each attack (a real receiver: ~1–2 m), so those checks
fire before any attack (A2 c3 saturates from ~80 s; steps from ~45 s). Their verdict text on these files
("spoofing-like: position step") is a harness artefact and is not counted. The coherent drag (slow acceleration,
consistent velocity) therefore remains **untested on real data**; it is also the case ASTRA's own limits list as
hardest.

**Takeaways (honest):** on real field attacks, ASTRA's receiver-side evidence (noise rise + satellite/fix loss)
caught all three within ~10–20 s of onset, blind. Telling spoofing from jamming failed blind; one fix (outage jump)
is physically motivated and now catches the incoherent case, and its false-alarm cost is measured on fresh real
flights in `real-gate-v9.md`. Sample: 3 attacks, 1 receiver, 1 site.
