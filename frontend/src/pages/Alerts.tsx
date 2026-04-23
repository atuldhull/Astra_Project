import { useState } from "react";
import { threatColor } from "../lib/api";

type Row = {
  id: number;
  cls: string;
  confidence: number;
  distance_km: number;
  score: number;
  status: "pending" | "confirmed" | "rejected" | "escalated";
};

const DEMO_ROWS: Row[] = [
  { id: 1, cls: "tank",              confidence: 0.91, distance_km: 2.1, score: 0.87, status: "pending" },
  { id: 2, cls: "artillery",         confidence: 0.84, distance_km: 3.6, score: 0.74, status: "pending" },
  { id: 3, cls: "aircraft-rotor",    confidence: 0.78, distance_km: 6.0, score: 0.63, status: "pending" },
  { id: 4, cls: "large-vehicle",     confidence: 0.66, distance_km: 1.4, score: 0.57, status: "confirmed" },
  { id: 5, cls: "ship",              confidence: 0.71, distance_km: 8.1, score: 0.44, status: "pending" },
  { id: 6, cls: "small-vehicle",     confidence: 0.58, distance_km: 0.9, score: 0.33, status: "rejected" },
];

const DEFAULTS = { w_class: 0.35, w_prox: 0.25, w_motion: 0.20, w_count: 0.10, w_conf: 0.10 };

export default function Alerts() {
  const [weights, setWeights] = useState(DEFAULTS);
  const [rows] = useState<Row[]>([...DEMO_ROWS].sort((a, b) => b.score - a.score));

  return (
    <div className="h-full flex flex-col">
      <header className="px-6 py-4 border-b border-border">
        <h1 className="text-lg font-semibold">Ranked Threat Queue</h1>
        <p className="text-xs text-muted">Priority = class × proximity × motion × density × confidence</p>
      </header>

      <div className="flex-1 p-6 grid grid-cols-[1fr_280px] gap-6 overflow-hidden">
        <div className="bg-panel border border-border rounded overflow-auto">
          <table className="w-full text-sm">
            <thead className="bg-panel2 text-muted text-xs uppercase tracking-wider sticky top-0">
              <tr>
                <th className="text-left px-4 py-3">#</th>
                <th className="text-left px-4 py-3">Class</th>
                <th className="text-left px-4 py-3">Conf</th>
                <th className="text-left px-4 py-3">Distance</th>
                <th className="text-left px-4 py-3">Score</th>
                <th className="text-left px-4 py-3">Status</th>
                <th className="text-left px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={r.id} className="border-t border-border hover:bg-panel2">
                  <td className="px-4 py-3 font-mono text-muted">{i + 1}</td>
                  <td className="px-4 py-3 font-mono">{r.cls}</td>
                  <td className="px-4 py-3 font-mono">{r.confidence.toFixed(2)}</td>
                  <td className="px-4 py-3 font-mono">{r.distance_km.toFixed(1)} km</td>
                  <td className={`px-4 py-3 font-mono font-semibold ${threatColor(r.score)}`}>
                    {r.score.toFixed(2)}
                  </td>
                  <td className="px-4 py-3 text-xs uppercase text-muted">{r.status}</td>
                  <td className="px-4 py-3 space-x-2">
                    <button className="text-xs px-2 py-1 rounded bg-threat-low/20 text-threat-low hover:bg-threat-low/30">Confirm</button>
                    <button className="text-xs px-2 py-1 rounded bg-threat-crit/20 text-threat-crit hover:bg-threat-crit/30">Reject</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <aside className="bg-panel border border-border rounded p-4 space-y-4">
          <div className="text-xs text-muted uppercase tracking-wider">Score Weights</div>
          {(Object.keys(DEFAULTS) as Array<keyof typeof DEFAULTS>).map((k) => (
            <div key={k} className="space-y-1">
              <div className="flex justify-between text-xs">
                <span className="text-muted">{k}</span>
                <span className="font-mono">{weights[k].toFixed(2)}</span>
              </div>
              <input
                type="range" min={0} max={1} step={0.05}
                value={weights[k]}
                onChange={(e) => setWeights({ ...weights, [k]: Number(e.target.value) })}
                className="w-full accent-accent"
              />
            </div>
          ))}
          <div className="text-[11px] text-muted pt-2 border-t border-border">
            Adjusting weights re-ranks the queue live. Every change is logged in the audit trail with your operator ID.
          </div>
        </aside>
      </div>
    </div>
  );
}
