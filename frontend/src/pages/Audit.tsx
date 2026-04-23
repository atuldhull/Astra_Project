const DEMO_EVENTS = [
  { t: "2026-04-22T20:31:14Z", op: "cmdr-01", type: "alert_confirmed", body: "Alert #14 confirmed (tank, score 0.82)" },
  { t: "2026-04-22T20:30:51Z", op: "cmdr-01", type: "weights_changed", body: "w_prox 0.25 → 0.35" },
  { t: "2026-04-22T20:30:02Z", op: "cmdr-01", type: "alert_rejected", body: "Alert #12 rejected (small-vehicle, civilian)" },
  { t: "2026-04-22T20:28:33Z", op: "system",  type: "ingest_completed", body: "Mission MISSION-001 processed, 84 detections" },
  { t: "2026-04-22T20:27:00Z", op: "cmdr-01", type: "ingest_started", body: "Mission MISSION-001 from drone-a.mp4" },
];

export default function Audit() {
  return (
    <div className="h-full flex flex-col">
      <header className="px-6 py-4 border-b border-border">
        <h1 className="text-lg font-semibold">Audit Log</h1>
        <p className="text-xs text-muted">Append-only · every command and system action is logged</p>
      </header>
      <div className="flex-1 p-6 overflow-auto">
        <div className="bg-panel border border-border rounded font-mono text-xs">
          {DEMO_EVENTS.map((e, i) => (
            <div key={i} className="border-b border-border last:border-0 px-4 py-3 grid grid-cols-[160px_80px_160px_1fr] gap-4">
              <span className="text-muted">{e.t}</span>
              <span className="text-accent">{e.op}</span>
              <span className="text-muted">{e.type}</span>
              <span>{e.body}</span>
            </div>
          ))}
        </div>
        <div className="text-[11px] text-muted mt-3">
          SHA-256 checkpoint: <span className="font-mono">(computed on export)</span>
        </div>
      </div>
    </div>
  );
}
