"""Self-contained HTML report for a run directory (no external assets; works offline).

    astra html RUN_DIR  ->  RUN_DIR/report.html

Per flight: a trajectory thumbnail of TRUE path (simulator) vs BELIEVED path (autopilot EKF), the
goal, and the attack onset. If report.json exists, its signature status and input hashes are shown.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

import numpy as np

from astra import logs
from astra.geo import latlon_to_ne

CSS = """
:root{--bg:#fbfbf9;--fg:#1d2125;--muted:#5d646c;--line:#d9dcdf;--card:#ffffff;--truth:#1f6fd1;--belief:#c2410c;--ok:#1a7f45;--bad:#b42318}
@media (prefers-color-scheme:dark){:root{--bg:#121416;--fg:#e7e9eb;--muted:#9aa1a8;--line:#2b3035;--card:#1a1d20;--truth:#6aa8ff;--belief:#ff8a4c;--ok:#4cc38a;--bad:#ff6b5e}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:1180px;margin:0 auto;padding:24px 16px 64px}h1{font-size:24px;margin:0 0 4px}h2{font-size:17px;margin:32px 0 10px}
.muted{color:var(--muted)}table{border-collapse:collapse;width:100%;font-size:13px}th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
th{color:var(--muted);font-weight:600}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px}.card h3{font-size:12.5px;margin:0 0 6px;word-break:break-all}
.pill{display:inline-block;padding:1px 8px;border-radius:999px;font-size:12px;border:1px solid var(--line)}.ok{color:var(--ok)}.bad{color:var(--bad)}
svg{width:100%;height:auto;display:block}.legend span{margin-right:14px;font-size:12.5px}.wrap{overflow-x:auto}
code{font-size:12px;word-break:break-all}
"""


def _track(fl: logs.FlightLog):
    sim, pos = fl["SIM"], fl["POS"]
    lat0, lon0 = float(sim["Lat"][0]), float(sim["Lng"][0])
    tn, te = latlon_to_ne(lat0, lon0, sim["Lat"], sim["Lng"])
    bn, be = latlon_to_ne(lat0, lon0, pos["Lat"], pos["Lng"])
    return (sim["t"], tn, te), (pos["t"], bn, be)


def _svg(fl: logs.FlightLog, goal: tuple[float, float] | None, w: int = 240, h: int = 200) -> str:
    (tt, tn, te), (bt, bn, be) = _track(fl)
    step_t, step_b = max(1, len(tt) // 400), max(1, len(bt) // 400)
    xs = np.concatenate([te, be] + ([np.array([goal[1]])] if goal else []))
    ys = np.concatenate([tn, bn] + ([np.array([goal[0]])] if goal else []))
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    span = max(x1 - x0, y1 - y0, 50.0) * 1.1
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2

    def P(e, n):
        return (w / 2 + (e - cx) / span * w, h / 2 - (n - cy) / span * h)

    def poly(n, e, step):
        return " ".join(f"{x:.1f},{y:.1f}" for x, y in (P(e[i], n[i]) for i in range(0, len(n), step)))

    parts = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="true vs believed path">',
             f'<rect x="0" y="0" width="{w}" height="{h}" fill="none" stroke="var(--line)"/>',
             f'<polyline points="{poly(bn, be, step_b)}" fill="none" stroke="var(--belief)" stroke-width="1.6" stroke-dasharray="4 3"/>',
             f'<polyline points="{poly(tn, te, step_t)}" fill="none" stroke="var(--truth)" stroke-width="1.8"/>']
    if goal:
        gx, gy = P(goal[1], goal[0])
        parts.append(f'<circle cx="{gx:.1f}" cy="{gy:.1f}" r="4" fill="none" stroke="var(--fg)" stroke-width="1.4"/>')
    wins = fl.attack_windows()
    if wins:
        k = int(np.searchsorted(tt, wins[0][0]))
        if k < len(tt):
            ax, ay = P(te[k], tn[k])
            parts.append(f'<path d="M{ax-5:.1f},{ay-5:.1f} L{ax+5:.1f},{ay+5:.1f} M{ax-5:.1f},{ay+5:.1f} L{ax+5:.1f},{ay-5:.1f}" stroke="var(--bad)" stroke-width="1.8"/>')
    bar = 100 if span > 300 else 50
    bx = bar / span * w
    parts.append(f'<line x1="8" y1="{h-10}" x2="{8+bx:.1f}" y2="{h-10}" stroke="var(--muted)" stroke-width="2"/>'
                 f'<text x="8" y="{h-14}" font-size="10" fill="var(--muted)">{bar} m</text></svg>')
    return "".join(parts)


def render(run_dir: Path, max_cards: int = 120) -> Path:
    run_dir = Path(run_dir)
    rows = [json.loads(x) for x in (run_dir / "results.jsonl").read_text().splitlines()]
    env = json.loads((run_dir / "report.json").read_text()) if (run_dir / "report.json").exists() else None
    esc = html.escape
    out = ["<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>",
           "<title>ASTRA run report</title><style>", CSS, "</style></head><body><main>",
           f"<h1>ASTRA Proving Ground: run report</h1><p class=muted>{esc(str(run_dir))} · {len(rows)} flights</p>"]
    if env:
        b = env["body"]
        out.append("<h2>Attestation</h2><div class=wrap><table>")
        for k, v in [("Pack", b["pack"]["name"]), ("Pack sha256", b["pack"]["pack_sha256"]),
                     ("Simulator", b["inputs"]["simulator"]["image"]),
                     ("ArduPilot commit", b["inputs"]["simulator"]["ardupilot_commit"]),
                     ("Simulator patch sha256", b["inputs"]["simulator_patch_sha256"]),
                     ("Vendor params", f'{b["inputs"]["vendor_params_file"]} ({b["inputs"]["vendor_params_sha256"] or "-"})'),
                     ("Signer fingerprint", env["signer"]["fingerprint"])]:
            out.append(f"<tr><th>{esc(k)}</th><td><code>{esc(str(v))}</code></td></tr>")
        out.append("</table></div><p class=muted>Verify offline: <code>astra verify report.json --trust &lt;fingerprint&gt;</code>. "
                   "This page is a view; the signed artefact is report.json.</p>")
    out.append("<h2>Results</h2><div class=wrap><table><tr><th>scenario</th><th>seed</th><th>outcome</th><th>why</th>"
               "<th>max nav error (m)</th><th>stock autopilot noticed during attack</th></tr>")
    for r in sorted(rows, key=lambda r: (r["scenario_id"], r["seed"])):
        w = r["windows"][0] if r.get("windows") else {}
        cls = "ok" if r["passed"] else "bad"
        noticed = "-" if not w else ("yes" if w.get("l0_detected_during") else "no")
        out.append(f"<tr><td>{esc(r['scenario_id'])}</td><td>{r['seed']}</td><td><span class='pill {cls}'>{esc(r['outcome'])}</span></td>"
                   f"<td>{esc(r['reason'])}</td><td>{r['metrics'].get('max_nav_error_m', '-')}</td><td>{noticed}</td></tr>")
    out.append("</table></div><h2>True vs believed paths</h2><p class='legend muted'>"
               "<span style='color:var(--truth)'>━ true path (simulator)</span>"
               "<span style='color:var(--belief)'>╍ what the autopilot believed</span>"
               "<span>○ goal</span><span style='color:var(--bad)'>✕ attack onset</span></p><div class=grid>")
    n = 0
    for r in sorted(rows, key=lambda r: (r["scenario_id"], r["seed"])):
        npz = run_dir / f"{r['scenario_id']}__s{r['seed']}" / "flight.npz"
        if not npz.exists() or n >= max_cards:
            continue
        try:
            fl = logs.load_npz(npz)
            m = r["metrics"]
            goal = (m["goal_n_m"], m["goal_e_m"]) if "goal_n_m" in m else None
            svg = _svg(fl, goal)
        except Exception:  # noqa: BLE001 - a bad log shouldn't break the page
            continue
        cls = "ok" if r["passed"] else "bad"
        out.append(f"<div class=card><h3>{esc(r['scenario_id'])} · s{r['seed']}</h3>{svg}"
                   f"<div class=muted style='font-size:12px;margin-top:4px'><span class='{cls}'>{esc(r['outcome'])}</span> · "
                   f"max error {m.get('max_nav_error_m', '-')} m · final {m.get('final_true_dist_to_goal_m', '-')} m from goal</div></div>")
        n += 1
    out.append("</div></main></body></html>")
    path = run_dir / "report.html"
    path.write_text("".join(out), encoding="utf-8")
    return path
