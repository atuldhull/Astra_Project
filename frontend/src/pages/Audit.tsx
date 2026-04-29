import { useEffect, useMemo, useRef, useState } from "react";
import { Loader2, RefreshCw, Search, FileDown, ShieldCheck, ShieldAlert, Link2, ScrollText, Database, Hash, Users } from "lucide-react";
import { api, type AuditEvent, type Mission } from "../lib/api";
import { PageHeader } from "../components/PageHeader";
import { HeroStat } from "../components/HeroStat";
import { StatusPill } from "../components/StatusPill";
import { EmptyState } from "../components/EmptyState";
import { toast } from "../components/Toast";
import { ChainVisual } from "../components/ChainVisual";
import { ExportMenu } from "../components/ExportMenu";
import { absoluteIst, relativeTime } from "../lib/time";
import { useStallTimeout } from "../lib/useStallTimeout";
import { SkeletonRow } from "../components/Skeleton";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

const EVENT_COLORS: Record<string, string> = {
  ingest_started:     "#60a5fa",
  ingest_completed:   "#4ade80",
  alert_confirmed:    "#4ade80",
  alert_rejected:     "#ef4444",
  alert_reclassified: "#facc15",
  alert_escalated:    "#fb923c",
  weights_changed:    "#a78bfa",
};

// Audit rows show relative time so the operator can scan recency
// without parsing UTC offsets. Hovering reveals the exact IST timestamp.

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
  const [missions, setMissions] = useState<Mission[]>([]);
  const [exportMissionId, setExportMissionId] = useState<number | null>(null);
  const [exporting, setExporting] = useState(false);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const stalled = useStallTimeout(loading, 15_000);
  const [error, setError] = useState<string | null>(null);
  const [chainStatus, setChainStatus] = useState<{ ok: boolean; checked: number; broken_at_id: number | null; reason?: string; genesis?: string; tip?: string } | null>(null);
  const [verifying, setVerifying] = useState(false);
  const [verifyFlash, setVerifyFlash] = useState(false);
  const [provFp, setProvFp] = useState<string | null>(null);
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
    api.listMissions(50)
      .then((m) => {
        setMissions(m);
        if (m.length > 0) {
          const stored = Number(localStorage.getItem("astra:lastMissionId") ?? "");
          const pref = m.find((x) => x.id === stored) ?? m[0];
          setExportMissionId(pref.id);
        }
      })
      .catch(() => {});
    pollRef.current = window.setInterval(load, 4000);
    // v3.0/T1.1 — fetch provenance public-key fingerprint for the footer
    api.provenanceKey().then((s) => setProvFp(s.fingerprint ?? null)).catch(() => {});
    return () => { if (pollRef.current) window.clearInterval(pollRef.current); };
  }, []);

  async function verifyChain() {
    setVerifying(true);
    setVerifyFlash(false);
    const t0 = performance.now();
    try {
      const res = await fetch(`${API_BASE}/api/v1/audit/verify`);
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const v = await res.json();
      // Floor at 700ms so the SHA-walk animation lands.
      const elapsed = performance.now() - t0;
      if (elapsed < 700) await new Promise((r) => setTimeout(r, 700 - elapsed));
      setChainStatus(v);
      setVerifyFlash(true);
      window.setTimeout(() => setVerifyFlash(false), 2500);
      if (v.ok) {
        toast.success("Chain verified", `${v.checked} rows · genesis ${(v.genesis ?? "").slice(0, 8)}… → tip ${(v.tip ?? "").slice(-8)}`);
      } else {
        toast.crit("Chain integrity broken", `Row #${v.broken_at_id} fails: ${v.reason}`);
      }
    } catch (e) {
      const msg = (e as Error).message;
      setError(`verify: ${msg}`);
      toast.crit("Verify failed", msg);
    } finally {
      setVerifying(false);
    }
  }

  async function exportReport() {
    if (exportMissionId == null) return;
    setExporting(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/reports/mission/${exportMissionId}.pdf`);
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `astra-mission-${exportMissionId}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      setError(`export: ${(e as Error).message}`);
    } finally {
      setExporting(false);
    }
  }

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

  // Hero KPI inputs
  const distinctOps = new Set(events.map((e) => e.operator_id).filter(Boolean)).size;

  return (
    <div className="h-full flex flex-col">
      <PageHeader
        icon={ScrollText}
        title="Audit Log"
        badge={
          chainStatus != null ? (
            chainStatus.ok ? (
              <StatusPill variant="ok" size="sm" title={`${chainStatus.checked} rows hash-verified`}>
                <ShieldCheck size={10} className="mr-1" /> chain ok
              </StatusPill>
            ) : (
              <StatusPill variant="err" size="sm" title={`Broken at id ${chainStatus.broken_at_id}: ${chainStatus.reason}`}>
                <ShieldAlert size={10} className="mr-1" /> chain broken @ #{chainStatus.broken_at_id}
              </StatusPill>
            )
          ) : null
        }
        subtitle={
          <>
            Append-only · SHA-256 hash-chained · {events.length} events{loading && " · refreshing..."}
            {provFp && (
              <>
                {" · "}
                <span className="text-muted2 font-mono" title={`Server pubkey fingerprint (Ed25519): ${provFp}`}>
                  pubkey {provFp.slice(0, 10)}…{provFp.slice(-6)}
                </span>
              </>
            )}
          </>
        }
        actions={
          <>
            <div className="relative">
              <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted pointer-events-none" />
              <input
                placeholder="filter events..."
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                className="bg-panel border border-border rounded pl-8 pr-3 py-1.5 text-sm w-52"
              />
            </div>
            <div className="flex items-center gap-2 border-l border-border pl-3">
              <label className="text-xs text-muted">Export:</label>
              <select
                className="bg-panel border border-border rounded px-2 py-1.5 text-xs font-mono min-w-[180px]"
                value={exportMissionId ?? ""}
                onChange={(e) => setExportMissionId(Number(e.target.value))}
              >
                {missions.length === 0 && <option>(no missions)</option>}
                {missions.map((m) => (
                  <option key={m.id} value={m.id}>#{m.id} · {m.name}</option>
                ))}
              </select>
              <button
                onClick={exportReport}
                disabled={exporting || exportMissionId == null}
                className="flex items-center gap-1 bg-accent text-bg px-3 py-1.5 rounded text-xs font-medium hover:brightness-110 disabled:opacity-50 transition-fast"
                title="Generate signed PDF mission report"
              >
                {exporting ? <Loader2 size={12} className="animate-spin" /> : <FileDown size={12} />}
                PDF
              </button>
            </div>
            <button
              onClick={verifyChain}
              disabled={verifying}
              className="flex items-center gap-1 glass border border-border px-3 py-1.5 rounded text-xs hover:bg-panel2 disabled:opacity-50 transition-fast"
              title="Walk the entire audit log and verify every SHA-256 link"
            >
              {verifying ? <Loader2 size={12} className="animate-spin" /> : <Link2 size={12} />}
              verify chain
            </button>
            <ExportMenu filename="astra-audit-log" rows={events} />
            <button
              onClick={load}
              className="p-1.5 rounded hover:bg-panel2 text-muted transition-fast"
              title="Refresh"
            >
              {loading ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
            </button>
          </>
        }
      />

      {/* Verify-chain flash banner — landing zone for demo theatre */}
      {(verifying || verifyFlash) && chainStatus !== null && (
        <div
          className={`mx-6 mt-4 px-4 py-3 rounded-lg border font-mono text-xs flex items-center gap-3 transition-all ${
            chainStatus.ok
              ? "border-threat-low/60 bg-threat-low/10 text-threat-low shadow-[0_0_24px_rgba(74,222,128,0.18)]"
              : "border-threat-crit/60 bg-threat-crit/10 text-threat-crit"
          } ${verifyFlash ? "animate-pulse" : ""}`}
        >
          {chainStatus.ok ? <ShieldCheck size={16} /> : <ShieldAlert size={16} />}
          <span className="font-semibold uppercase-wide tracking-wider text-[11px]">
            {chainStatus.ok ? "CHAIN VERIFIED" : "CHAIN BROKEN"}
          </span>
          <span className="opacity-90">
            {chainStatus.checked} rows · SHA-256 walk
          </span>
          {chainStatus.genesis && chainStatus.tip && (
            <span className="ml-auto text-muted2">
              genesis <span className="text-text">{chainStatus.genesis.slice(0, 10)}…</span>
              {" → tip "}
              <span className="text-text">{chainStatus.tip.slice(0, 10)}…{chainStatus.tip.slice(-6)}</span>
            </span>
          )}
          {!chainStatus.ok && (
            <span className="ml-auto">
              broken @ #{chainStatus.broken_at_id} · {chainStatus.reason}
            </span>
          )}
        </div>
      )}
      {verifying && chainStatus === null && (
        <div className="mx-6 mt-4 px-4 py-3 rounded-lg border border-accent/40 bg-accent/5 text-accent font-mono text-xs flex items-center gap-3">
          <Loader2 size={14} className="animate-spin" />
          <span className="uppercase-wide tracking-wider text-[11px] font-semibold">WALKING SHA-256 CHAIN FROM GENESIS</span>
          <span className="ml-auto text-muted2">recomputing every row hash...</span>
        </div>
      )}

      {/* Hero KPI strip */}
      <div className="px-6 pt-4 grid grid-cols-4 gap-3">
        <HeroStat
          label="audit events"
          value={events.length}
          icon={ScrollText}
          tone="cyan"
          sub="append-only"
        />
        <HeroStat
          label="chain rows"
          value={chainStatus?.checked ?? 0}
          icon={Hash}
          tone={chainStatus?.ok ? "low" : chainStatus ? "crit" : "neutral"}
          sub={chainStatus ? (chainStatus.ok ? "verified" : "BROKEN") : "click verify"}
        />
        <HeroStat
          label="distinct ops"
          value={distinctOps}
          icon={Users}
          tone="neutral"
          sub="recorded"
        />
        <HeroStat
          label="missions logged"
          value={new Set(events.map((e)=>e.mission_id).filter(Boolean)).size}
          icon={Database}
          tone="neutral"
          sub="end-to-end"
        />
      </div>

      {error && (
        <div className="mx-6 mt-3 bg-threat-crit/20 border border-threat-crit/40 text-threat-crit p-2 rounded text-xs">
          {error}
        </div>
      )}

      {/* Chain ribbon — animated SHA-256 link visualization above the log */}
      <div className="px-6 pt-3">
        <div
          className="glass-strong rounded-md px-3 py-2"
          title="Hash-chain ribbon — each link shows row id + truncated SHA-256 hash + event type. Tampering with any historical row breaks the chain at that point. Same primitive Bitcoin uses for block headers."
        >
          <div className="text-2xs uppercase-wide text-muted2 font-mono tracking-wider mb-0.5 flex items-center justify-between">
            <span>SHA-256 · CHAIN VISUAL · LAST 8 ROWS</span>
            <span className={chainStatus?.ok ? "text-threat-low" : chainStatus?.ok === false ? "text-threat-crit" : "text-muted"}>
              {chainStatus?.ok ? "VERIFIED ✓" : chainStatus?.ok === false ? "BROKEN ✗" : "—"}
            </span>
          </div>
          <ChainVisual rows={events.slice(0, 8)} ok={chainStatus?.ok ?? null} />
        </div>
      </div>

      <div className="flex-1 p-6 pt-3 flex gap-6 overflow-hidden">
        <div className="flex-1 glass rounded-lg overflow-auto font-mono text-xs shadow-panel">
          {events.length === 0 && loading ? (
            <div className="p-4 space-y-2">
              {Array.from({ length: 8 }).map((_, i) => (
                <SkeletonRow key={i} cols={4} />
              ))}
              {stalled && (
                <div className="text-xs text-threat-high pt-2 px-1">
                  Still loading after 15s — backend may be slow or unreachable. Try the verify-chain button or refresh.
                </div>
              )}
            </div>
          ) : filtered.length === 0 ? (
            <EmptyState
              icon={ScrollText}
              title={events.length === 0 ? "No audit events yet" : "No matches"}
              body={events.length === 0 ? "Every ingest/confirm/reject/escalate/engage writes an immutable hash-chained row here. Run a mission to populate." : "Adjust your filter to see events."}
              cta={events.length === 0 ? { label: "Run a mission", href: "/mission" } : undefined}
            />
          ) : (
            filtered.map((e) => (
              <div
                key={e.id}
                className="border-b border-border last:border-0 px-4 py-3 grid grid-cols-[170px_90px_170px_1fr] gap-4 hover:bg-panel2"
              >
                <span className="text-muted" title={absoluteIst(e.created_at)}>{relativeTime(e.created_at)}</span>
                <span className="text-accent">{e.operator_id ?? "system"}</span>
                <span style={{ color: EVENT_COLORS[e.event_type] ?? "#8b9aad" }}>
                  {e.event_type}
                </span>
                <span className="text-text">{describe(e)}</span>
              </div>
            ))
          )}
        </div>

        <aside className="w-60 glass rounded-lg p-4 space-y-3 text-xs shadow-panel">
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
