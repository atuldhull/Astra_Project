"""A6 v2: EKF-tuning advice for ArduPilot and PX4, with benign cost measured on typical AND harsh GNSS.

harsh = noisier real receivers (60 s wander at the real 90th-95th percentile; gnss-realism-v1.md).
"""
import sys
from pathlib import Path
from astra.advise import advise, render

runs = [("px4", None), ("px4", "harsh"), ("ardupilot", "harsh")]
if len(sys.argv) > 1:
    runs = [tuple(a.split(":")) if ":" in a else (a, None) for a in sys.argv[1:]]
for ap, prof in runs:
    out = Path(f"runs/advise-{ap}-{prof or 'typical'}")
    rows = advise(None, out, nbenign=20, parallel=4, autopilot=ap, gps_profile=prof)
    text = f"# A6 v2: {ap}, benign GNSS = {prof or 'typical'}\n\n" + render(rows, 20)
    Path(f"benchmarks/a6-{ap}-{prof or 'typical'}.md").write_text(text + "\n", encoding="utf-8")
    print(text.encode("ascii", "replace").decode(), flush=True)
