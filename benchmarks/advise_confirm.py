"""A6 v2 confirmation: the shortlisted 'safe' settings vs stock on 80 benign flights with harsh GNSS.

Attack flights are reused from the earlier runs (identical attacks). Run once; not tuned afterwards.
usage: python benchmarks/advise_confirm.py AUTOPILOT ATTACK_FROM_DIR SETTING[,SETTING...]
"""
import sys
from pathlib import Path
from astra.advise import advise, render

ap, src, sets = sys.argv[1], sys.argv[2], sys.argv[3].split(",")
out = Path(f"runs/advise80-{ap}-harsh")
rows = advise(None, out, nbenign=80, parallel=4, autopilot=ap, gps_profile="harsh",
              attack_from=Path(src), settings=sets)
text = (f"# A6 v2 confirmation: {ap}, 80 benign flights, harsh GNSS\n\n" + render(rows, 80)
        + f"\n\nAttack flights reused from `{src}`.")
Path(f"benchmarks/a6-confirm-{ap}.md").write_text(text + "\n", encoding="utf-8")
print(text.encode("ascii", "replace").decode(), flush=True)
