"""Readable, self-contained HTML page for one `astra diagnose` result (offline, no external assets).

    astra diagnose LOG --html report.html

The JSON stays the source of truth (embedded at the bottom); this page explains it for an operator.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

import numpy as np

from astra import logs
from astra.html_report import CSS

EXTRA_CSS = """
.verdict{border:1px solid var(--line);border-left:6px solid var(--muted);border-radius:10px;background:var(--card);padding:14px 16px;margin:16px 0}
.verdict.jam{border-left-color:#b7791f}.verdict.spoof,.verdict.mixed,.verdict.rf{border-left-color:var(--bad)}.verdict.none{border-left-color:var(--ok)}
.verdict b{font-size:18px;display:block;margin-bottom:4px}.kv{display:grid;grid-template-columns:max-content 1fr;gap:4px 14px;font-size:13.5px}
.kv div:nth-child(odd){color:var(--muted)}.chart text{font-size:10px;fill:var(--muted)}details{margin-top:24px}pre{font-size:11.5px;overflow:auto;max-height:420px}
"""

WHAT_NEXT = {
    "jam": "The receiver itself reported losing its fix or satellites. Check whether the times match a known "
           "interference source, flight near obstacles, or an antenna/cable fault before calling it an attack.",
    "spoof": "The GPS position moved in a way the drone's own motion does not explain while the receiver reported a "
             "healthy fix. Treat the GPS track after the first event as untrusted; compare with any independent "
             "record (video, ground observers, ATC/radar, a second receiver).",
    "rf": "The receiver's noise level rose sharply while it lost satellites or its fix: the signature of a nearby "
          "transmitter on the GPS band (jammer or spoofer). Seen in both live HackRF attacks we have and in none of "
          "927 real benign flights. Treat GPS after this time as untrusted and look for the source.",
    "mixed": "The receiver degraded, and separately the navigation became inconsistent. Review both timelines.",
    "inconclusive": "Weak evidence only: the same level is seen on a few percent of normal flights and in slow "
                    "simulated spoofs. Not an accusation. If this airframe often shows it, calibrate it "
                    "(`astra calibrate`) on its own normal flights.",
    "none": "No GNSS anomaly found by the available checks. This is not proof that no attack happened: a slow spoof "
            "that also fakes a matching velocity is invisible to GPS-only checks.",
}


def _kind(verdict: str) -> str:
    v = verdict.split(":")[0]
    return {"jamming-like": "jam", "spoofing-like": "spoof", "mixed": "mixed", "inconclusive": "inconclusive",
            "RF-attack-like": "rf", "not analysed": "inconclusive"}.get(v, "none")


def _lane(t, y, t0, t1, x0, w, top, h, color, label, ymax=None):
    ok = np.isfinite(y)
    if ok.sum() < 2:
        return ""
    t, y = t[ok], y[ok]
    step = max(1, len(t) // 800)
    t, y = t[::step], y[::step]
    hi = float(ymax if ymax is not None else max(np.nanmax(y), 1e-6)) * 1.05
    pts = " ".join(f"{x0 + (ti - t0) / (t1 - t0) * w:.1f},{top + h - min(yi, hi) / hi * h:.1f}" for ti, yi in zip(t, y))
    return (f'<text x="{x0}" y="{top - 3}">{html.escape(label)} (max shown {hi:.3g})</text>'
            f'<rect x="{x0}" y="{top}" width="{w}" height="{h}" fill="none" stroke="var(--line)"/>'
            f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="1.3"/>')


def _timeline(fl: logs.FlightLog, rep: dict) -> str:
    g, pos = fl["GPS"], fl["POS"]
    t0, t1 = float(min(g["t"][0], pos["t"][0])), float(max(g["t"][-1], pos["t"][-1]))
    if t1 <= t0:
        return ""
    W, x0, w, lh, gap = 900, 40, 850, 60, 26
    lanes = [(g["t"], g["NSats"].astype(float), "var(--truth)", "satellites used", None)]
    if fl.has("GPA"):
        a = fl["GPA"]
        lanes.append((a["t"], np.where((a["HAcc"] > 0) & (a["HAcc"] < 1e4), a["HAcc"], np.nan), "#b7791f",
                      "receiver-reported accuracy (m)", None))
    lanes.append((pos["t"], pos["RelHomeAlt"].astype(float), "var(--muted)", "height above take-off (m)", None))
    H = 20 + len(lanes) * (lh + gap) + 24
    X = lambda t: x0 + (t - t0) / (t1 - t0) * w  # noqa: E731
    parts = [f'<svg class=chart viewBox="0 0 {W} {H}" role="img" aria-label="flight timeline">']
    bottom = 20 + len(lanes) * (lh + gap) - gap
    for a, b in rep["evidence"]["jamming_intervals_s"]:
        parts.append(f'<rect x="{X(a):.1f}" y="14" width="{max(X(b) - X(a), 1.5):.1f}" height="{bottom - 14}" fill="#b7791f" opacity=".18"/>')
    for gt in rep.get("ground_truth", []):
        parts.append(f'<rect x="{X(gt["start_s"]):.1f}" y="10" width="{max(X(gt["end_s"]) - X(gt["start_s"]), 1.5):.1f}" '
                     f'height="4" fill="var(--fg)"/>')
    for i, (t, y, c, lab, ym) in enumerate(lanes):
        parts.append(_lane(np.asarray(t, float), np.asarray(y, float), t0, t1, x0, w, 20 + i * (lh + gap), lh, c, lab, ym))
    for t, _why in rep["evidence"]["spoofing_events"]:
        parts.append(f'<line x1="{X(t):.1f}" y1="14" x2="{X(t):.1f}" y2="{bottom}" stroke="var(--bad)" stroke-width="1.6"/>')
    for t, _why in rep["evidence"]["weak_events"]:
        parts.append(f'<line x1="{X(t):.1f}" y1="14" x2="{X(t):.1f}" y2="{bottom}" stroke="var(--bad)" stroke-width="1" stroke-dasharray="3 3"/>')
    for k in range(6):
        tt = t0 + (t1 - t0) * k / 5
        anchor = "start" if k == 0 else ("end" if k == 5 else "middle")
        parts.append(f'<text x="{X(tt):.1f}" y="{H - 6}" text-anchor="{anchor}">{tt:.0f} s</text>')
    parts.append("</svg>")
    return "".join(parts)


def render(rep: dict, out: Path) -> Path:
    esc = html.escape
    fl = None
    try:
        from astra.forensics import _load
        fl = _load(Path(rep["log"]))
    except Exception:  # noqa: BLE001 - the page still works without the chart
        pass
    kind = _kind(rep["verdict"])
    head, _, tail = rep["verdict"].partition(":")
    rc, a2 = rep["receiver"], rep["a2_monitor"]
    o = ["<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>",
         "<title>ASTRA flight forensics</title><style>", CSS, EXTRA_CSS, "</style></head><body><main>",
         f"<h1>Flight forensics</h1><p class=muted><code>{esc(rep['log'])}</code></p>",
         f"<div class='verdict {kind}'><b>{esc(head)}</b>{esc(tail.strip())}"
         f"<p style='margin:8px 0 0'>{esc(WHAT_NEXT['jam' if kind == 'jam' else kind])}</p></div>"]
    if fl is not None:
        o += ["<h2>Timeline</h2><p class='legend muted'><span style='color:#b7791f'>▮ receiver lost fix / satellites</span>"
              "<span style='color:var(--bad)'>│ spoofing evidence</span><span style='color:var(--bad)'>┆ weak evidence</span>"
              + ("<span>▬ simulated attack (ground truth)</span>" if rep.get("ground_truth") else "") + "</p>",
              f"<div class=wrap>{_timeline(fl, rep)}</div>"]
    ev = ([(t, w, "spoofing") for t, w in rep["evidence"]["spoofing_events"]]
          + [(t, w, "weak") for t, w in rep["evidence"]["weak_events"]]
          + [(a, f"receiver lost fix/satellites until {b} s", "jamming") for a, b in rep["evidence"]["jamming_intervals_s"]])
    o.append("<h2>Evidence</h2>")
    if ev:
        o.append("<div class=wrap><table><tr><th>time (s)</th><th>type</th><th>what</th></tr>")
        for t, w, k in sorted(ev):
            o.append(f"<tr><td>{t}</td><td>{k}</td><td>{esc(w)}</td></tr>")
        o.append("</table></div>")
    else:
        o.append("<p class=muted>None.</p>")
    o.append("<h2>Receiver and checks</h2><div class=kv>")
    rows = [("Lowest satellite count with a fix", rc.get("min_sats_in_fix")),
            ("Worst reported accuracy", f"{rc['max_reported_hacc_m']} m" if rc.get("max_reported_hacc_m") is not None else "-"),
            ("Receiver's own flags", json.dumps(rc["self_report"]) if rc.get("self_report") else "not logged"),
            ("Consistency monitor (A2)", ("alarm" if a2.get("alarm") else "no alarm") + f" · {a2.get('config', '')}"
             if a2.get("available") else f"unavailable: {a2.get('reason', '')}"),
            ("Skipped checks", "; ".join(f"{k}: {v}" for k, v in (a2.get("skipped_channels") or {}).items()) or "none"),
            ("Largest unexplained position step", f"{rep['position_steps']['max_m']} m" if rep.get("position_steps") else "-"),
            ("Stock autopilot GNSS alerts", len(rep.get("stock_alerts", [])))]
    if rep.get("takeoff_check"):
        tk = rep["takeoff_check"]
        rows.append(("Take-off point check", f"{tk.get('offset_m')} m from declared pad (limit {tk.get('limit_m')} m)"
                     if "offset_m" in tk else tk.get("reason")))
    for k, v in rows:
        o.append(f"<div>{esc(k)}</div><div>{esc(str(v))}</div>")
    o.append("</div><h2>Limits</h2><ul class=muted>"
             "<li>Checks use GPS, IMU and (if calibrated) optical flow from this log only. A slow spoof that also fakes a "
             "matching velocity cannot be seen without an independent sensor.</li>"
             "<li>Measured rates: false 'spoofing-like' on 4/1,041 fresh real benign PX4 flights (0.4%); 'RF-attack-like' on "
             "0/927; 'inconclusive' on about 3%. Attack detection rates are from simulation; only 3 real attacks have "
             "been tested so far.</li>"
             "<li>A spoof present from power-on is only checked if the real take-off point is given (<code>--takeoff</code>).</li></ul>"
             "<details><summary>Full JSON</summary><pre>" + esc(json.dumps(rep, indent=1, default=str)) + "</pre></details>"
             "</main></body></html>")
    out = Path(out)
    out.write_text("".join(o), encoding="utf-8")
    return out
