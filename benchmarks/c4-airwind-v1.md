# C4 fixed-wing air-data witness: measured on real flights (negative result)

**Question.** A consistent GNSS spoof (position and velocity agree) is invisible to GPS-only checks. On a
fixed-wing aircraft, the wind triangle gives a witness: w = v_gps − v_air. A velocity spoof of b m/s shifts
the estimated wind by exactly b. Can that be told apart from real wind change?

**Data.** 120 real PX4 fixed-wing mission flights. They are public Flight Review logs, seed "astra-fw-design",
each with ≥ 5 min in mission mode (`runs/fwdesign`). Code: `src/astra/detect/airwind.py`.

## Findings

1. **Most real fixed-wings have no usable airspeed sensor.** Only 25 of 105 readable logs (24%) had a
   valid true airspeed. C4 cannot apply to the rest.
2. **Real wind estimates move a lot.** The table shows the largest shift of the mean wind estimate per flight,
   recent window vs a reference window. The airspeed scale is fitted per flight from heading diversity.

| variant (recent / gap / reference, s) | flights | median of max | 90th pct | worst |
|---|---|---|---|---|
| all flight, 30/30/60 | 25 | 2.25 m/s | 3.99 | 4.84 |
| straight flight only (bank < 15°), 30/30/60 | 19 | 1.70 | 2.98 | 4.88 |
| straight flight only, 60/60/120 | 11 | 1.28 | 2.00 | 2.53 |
| straight flight only, 120/60/240 | 7 | 1.30 | 1.56 | 1.56 |
| PX4's own EKF wind, 30/30/60 (reference) | 13 | 1.52 | 3.10 | 9.15 |

3. **Consequence.** A false-alarm-safe threshold (1.25 × worst benign) is about 3–6 m/s depending on the
   window. A consistent spoof is detectable only above that rate, and only after 2–4 minutes of mostly
   straight flight. Consistent drags of 1–2 m/s, the stealthy case that matters, give **0% detection**.

## Verdict: not shipped (backlog kill criterion met)

The backlog's acceptance was ≥ 50% of consistent drags ≥ 1 m/s at ≤ 1 FA/10 h. Real wind variability
alone exceeds 1 m/s within minutes on most flights. This matches the physics note in 05-DETECTION-PHYSICS:
a constant bias equals a wind change. No windowing beats real wind variability at 1–2 m/s.

What might still work (not attempted):
- A *gross* consistent-spoof alarm (≥ 5 m/s) for the 24% of airframes with airspeed sensors.
- Checking whether stock PX4's airspeed validator already reacts to such spoofs. It would probably declare
  the *airspeed sensor* failed, which is the wrong attribution and worth a test in PX4 SIH fixed-wing.
- Independent wind sources (ground weather station, multiple aircraft in the same area).
