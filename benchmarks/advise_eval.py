"""A6 v2: EKF-tuning advice for ArduPilot and PX4, with benign cost measured on typical AND harsh GNSS.

harsh = noisier real receivers (60 s wander near the real 90th-95th percentile; gnss-realism-v1.md).
Harsh runs fly benign flights only and reuse the attack flights of the typical run (identical attacks).
usage: python benchmarks/advise_eval.py AUTOPILOT:PROFILE[:ATTACK_FROM_DIR] ...
"""
import sys
from pathlib import Path
from astra.advise import advise, render

for arg in sys.argv[1:]:
    ap, prof, *src = arg.split(":", 2)
    prof = None if prof == "typical" else prof
    out = Path(f"runs/advise-{ap}-{prof or 'typical'}")
    rows = advise(None, out, nbenign=20, parallel=4, autopilot=ap, gps_profile=prof,
                  attack_from=Path(src[0]) if src else None)
    note = f"\n\nAttack flights reused from `{src[0]}`." if src else ""
    text = f"# A6 v2: {ap}, benign GNSS = {prof or 'typical'}\n\n" + render(rows, 20) + note
    Path(f"benchmarks/a6-{ap}-{prof or 'typical'}.md").write_text(text + "\n", encoding="utf-8")
    print(text.encode("ascii", "replace").decode(), flush=True)
