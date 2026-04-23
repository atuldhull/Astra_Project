import { useEffect, useMemo, useRef, useState } from "react";
import { Loader2, RefreshCw, Search } from "lucide-react";
import { api, type AuditEvent } from "../lib/api";

const EVENT_COLORS: Record<string, string> = {
  ingest_started:     "#60a5fa",
  ingest_completed:   "#4ade80",
  alert_confirmed:    "#4ade80",
  alert_rejected:     "#ef4444",
  alert_reclassified: "#facc15",
  alert_escalated:    "#fb923c",
  weights_changed:    "#a78bfa",
};

function fmtTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toISOString().replace("T", " ").replace(/\.\d+Z$/, "Z");
  } catch { return iso; }
}

function describe(e: AuditEvent): string {
  const p = e.payload_json ?? {};
  switch (e.event_type) {
    case "ingest_started":
      return `Mission ${e.mission_id ?? "?"} from ${p.filename ?? "unknown"} (${p.size_bytes ?? 0} bytes)`;
    case "ingest_completed":
      return `Mission ${e.mission_id ?? "?"} processed — ${p.detection_count ?? 0} detections, ${p.alert_count ?? 0} alerts${p.aoi_present ? ", geo-referenced" : ""}`;
    case "alert_confirmed":
      return `Alert #${e.alert_id ?? "?"} confirmed` + (p.reason ? ` (${p.reason})` : "");
    case "alert_rejected":
      return `Alert #${e.alert_id ?? "?"} rejected` + (p.reason ? ` (${p.reason})` : "");
    case "alert_reclassified":
      return `Alert #${e.alert_id ?? "?"} reclassified to class id ${p.new_class_id ?? "?"}`;
    case "alert_escalated":
      return `Alert #${e.alert_id ?? "?"} escalated`;
    case "weights_changed":
      return `Threat scoring weights adjusted`;
    default:
      return JSON.stringify(p);
  }
}

export default function Audit() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  const load = async () => {
    try {
      setLoading(true);
      const e = await api.listAudit();
      setEvents(e);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    pollRef.current = window.setInterval(load, 4000);
    return () => { if (pollRef.current) window.clearInterval(pollRef.current); };
  }, []);

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return events;
    return events.filter((e) =>
      e.event_type.toLowerCase().includes(q) ||
      (e.operator_id ?? "").toLowerCase().includes(q) ||
      describe(e).toLowerCase().includes(q)
    );
  }, [events, filter]);

  const typeCounts: Record<string, number> = {};
  for (const e of events) typeCounts[e.event_type] = (typeCounts[e.event_type] ?? 0) + 1;

  return (
    <div className="h-full flex flex-col">
      <header className="px-6 py-4 border-b border-border flex items-center justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold">Audit Log</h1>
          <p className="text-xs text-muted">
            Append-only · {events.length} events{loading && " · refreshing..."}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted pointer-events-none" />
            <input
              placeholder="filter events..."
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="bg-panel border border-border rounded pl-8 pr-3 py-1.5 text-sm w-60"
            />
          </div>
          <button
            onClick={load}
            className="p-1.5 rounded hover:bg-panel2 text-muted"
            title="Refresh"
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
          </button>
        </div>
      </header>

      {error && (
        <div className="mx-6 mt-3 bg-threat-crit/20 border border-threat-crit/40 text-threat-crit p-2 rounded text-xs">
          {error}
        </div>
      )}

      <div className="flex-1 p-6 flex gap-6 overflow-hidden">
        <div className="flex-1 bg-panel border border-border rounded overflow-auto font-mono text-xs">
          {filtered.length === 0 ? (
            <div className="px-4 py-8 text-center text-muted">
              {events.length === 0 ? "No events yet. Upload via Mission to generate some." : "No events match filter."}
            </div>
          ) : (
            filtered.map((e) => (
              <div
                key={e.id}
                className="border-b border-border last:border-0 px-4 py-3 grid grid-cols-[170px_90px_170px_1fr] gap-4 hover:bg-panel2"
              >
                <span className="text-muted">{fmtTime(e.created_at)}</span>
                <span className="text-accent">{e.operator_id ?? "system"}</span>
                <span style={{ color: EVENT_COLORS[e.event_type] ?? "#8b9aad" }}>
                  {e.event_type}
                </span>
                <span className="text-text">{describe(e)}</span>
              </div>
            ))
          )}
        </div>

        <aside className="w-60 bg-panel border border-border rounded p-4 space-y-3 text-xs">
          <div className="text-muted uppercase tracking-wider">Event counts</div>
          {Object.entries(typeCounts).length === 0 ? (
            <div className="text-muted">—</div>
          ) : (
            Object.entries(typeCounts)
              .sort(([, a], [, b]) => b - a)
              .map(([type, n]) => (
                <div key={type} className="flex justify-between items-center font-mono">
                  <div className="flex items-center gap-2">
                    <span
                      className="w-2 h-2 rounded-full"
                      style={{ background: EVENT_COLORS[type] ?? "#8b9aad" }}
                    />
                    <span>{type}</span>
                  </div>
                  <span className="text-accent">{n}</span>
                </div>
              ))
          )}
          <div className="pt-3 mt-3 border-t border-border text-[11px] text-muted leading-snug">
            Polls every 4s. Each action (confirm / reject / escalate / ingest) appends an
            immutable row. SHA-256 checkpoint computed on export.
          </div>
        </aside>
      </div>
    </div>
  );
}
