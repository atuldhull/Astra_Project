import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Loader2, RefreshCw, Search, FileDown, ShieldCheck, ShieldAlert, Link2,
  ScrollText, Database, Hash, Users, FileText, ChevronsLeft, ChevronsRight, Network,
} from "lucide-react";
import { api, type AuditEvent, type Mission, type MeshWitness } from "../lib/api";
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
import { AnchorStrip } from "../components/AnchorStrip";
import { MeshFeedPanel } from "../components/MeshFeedPanel";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";
const RAIL_OPEN_KEY = "astra:auditRailOpen";

// All event types the backend AuditEventType enum can emit. Used to drive
// the multi-select chip bar above the log.
const ALL_EVENT_TYPES = [
  "ingest_started",
  "ingest_completed",
  "alert_confirmed",
  "alert_rejected",
  "alert_reclassified",
  "alert_escalated",
  "alert_confirmation",
  "alert_engaged",
  "weights_changed",
] as const;

const EVENT_COLORS: Record<string, string> = {
  ingest_started:      "#60a5fa",
  ingest_completed:    "#4ade80",
  alert_confirmed:     "#4ade80",
  alert_rejected:      "#ef4444",
  alert_reclassified:  "#facc15",
  alert_escalated:     "#fb923c",
  alert_confirmation:  "#fde68a",
  alert_engaged:       "#f97316",
  weights_changed:     "#a78bfa",
};

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
    case "alert_confirmation":
      return `Alert #${e.alert_id ?? "?"} confirmation by ${p.operator_id ?? e.operator_id ?? "?"} (${p.confirmations_so_far ?? "?"}/2)`;
    case "alert_engaged":
      return `Alert #${e.alert_id ?? "?"} ENGAGED — dual-control complete`;
    case "weights_changed":
      return `Threat scoring weights adjusted`;
    default:
      return JSON.stringify(p);
  }
}

// ── URL hash helpers ─────────────────────────────────────────────────

function readHashRange(): { since?: string; until?: string } {
  try {
    const h = window.location.hash.startsWith("#") ? window.location.hash.slice(1) : window.location.hash;
    const sp = new URLSearchParams(h);
    const since = sp.get("since") || undefined;
    const until = sp.get("until") || undefined;
    return { since, until };
  } catch {
    return {};
  }
}

function writeHashRange(since: string | null, until: string | null) {
  try {
    const sp = new URLSearchParams();
    if (since) sp.set("since", since);
    if (until) sp.set("until", until);
    const s = sp.toString();
    const h = s ? `#${s}` : "";
    if (window.location.hash !== h) {
      history.replaceState(null, "", `${window.location.pathname}${window.location.search}${h}`);
    }
  } catch { /* noop */ }
}

// ── Component ────────────────────────────────────────────────────────

type RowVerifyState =
  | { state: "idle" }
  | { state: "loading" }
  | { state: "ok"; row_hash: string }
  | { state: "fail"; reason: string };

export default function Audit() {
  const initial = readHashRange();
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
  // Filter state
  const [selectedTypes, setSelectedTypes] = useState<Set<string>>(new Set());
  const [since, setSince] = useState<string>(initial.since ?? "");
  const [until, setUntil] = useState<string>(initial.until ?? "");
  // Per-row verify
  const [rowVerify, setRowVerify] = useState<Record<number, RowVerifyState>>({});
  // Activity rail
  const [railOpen, setRailOpen] = useState<boolean>(() => {
    try { return localStorage.getItem(RAIL_OPEN_KEY) !== "0"; } catch { return true; }
  });
  const [activity, setActivity] = useState<{
    operators: Array<{ operator_id: string; total: number; by_event_type: Record<string, number> }>;
    system_events: number;
    total: number;
  } | null>(null);
  // mesh witness state
  const [witnessesByRow, setWitnessesByRow] = useState<Record<number, MeshWitness[]>>({});
  const [meshPeerCount, setMeshPeerCount] = useState<number>(0);
  const [syncingMesh, setSyncingMesh] = useState(false);
  const pollRef = useRef<number | null>(null);

  // Persist rail toggle
  useEffect(() => {
    try { localStorage.setItem(RAIL_OPEN_KEY, railOpen ? "1" : "0"); } catch { /* noop */ }
  }, [railOpen]);

  // URL hash <-> state sync
  useEffect(() => {
    writeHashRange(since || null, until || null);
  }, [since, until]);

  const buildParams = useCallback(() => {
    const params: { event_types?: string[]; since?: string; until?: string; limit?: number } = { limit: 1000 };
    if (selectedTypes.size > 0) params.event_types = Array.from(selectedTypes);
    if (since) params.since = since;
    if (until) params.until = until;
    return params;
  }, [selectedTypes, since, until]);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const e = await api.listAudit(buildParams());
      setEvents(e);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, [buildParams]);

  // pull witnesses for the events we just rendered.
  const loadWitnesses = useCallback(async (eventIds: number[]) => {
    if (eventIds.length === 0) {
      setWitnessesByRow({});
      return;
    }
    try {
      const r = await api.meshWitnesses(eventIds);
      const next: Record<number, MeshWitness[]> = {};
      for (const [k, v] of Object.entries(r.by_row)) next[Number(k)] = v;
      setWitnessesByRow(next);
      setMeshPeerCount(r.n_peers);
    } catch { /* silent — mesh is optional */ }
  }, []);

  async function syncMesh() {
    setSyncingMesh(true);
    try {
      const r = await api.meshSyncDemo(100);
      toast.success(
        "Mesh sync complete",
        `${r.witnesses_added} added · ${r.skipped} cached · ${r.refused_due_to_tampering} refused`,
      );
      try { localStorage.setItem("astra:meshLastSync", r.last_sync_ts); } catch { /* noop */ }
      await load();
      await loadWitnesses(events.map((e) => e.id).slice(0, 200));
    } catch (e) {
      toast.crit("Mesh sync failed", (e as Error).message);
    } finally {
      setSyncingMesh(false);
    }
  }

  const loadActivity = useCallback(async () => {
    try {
      const a = await api.operatorActivity({ since: since || undefined, until: until || undefined });
      setActivity(a);
    } catch { /* rail is optional — don't pollute the error banner */ }
  }, [since, until]);

  // Whenever the visible events list changes, refresh witness pills.
  useEffect(() => {
    loadWitnesses(events.map((e) => e.id).slice(0, 200));
  }, [events, loadWitnesses]);

  // Initial + poll. Filter changes reset the poll loop.
  useEffect(() => {
    load();
    loadActivity();
    api.listMissions(50).then((m) => {
      setMissions(m);
      if (m.length > 0) {
        const stored = Number(localStorage.getItem("astra:lastMissionId") ?? "");
        const pref = m.find((x) => x.id === stored) ?? m[0];
        setExportMissionId(pref.id);
      }
    }).catch(() => {});
    api.provenanceKey().then((s) => setProvFp(s.fingerprint ?? null)).catch(() => {});
    pollRef.current = window.setInterval(() => {
      load();
      loadActivity();
    }, 5000);
    return () => { if (pollRef.current) window.clearInterval(pollRef.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load, loadActivity]);

  // ── Verify chain ───────────────────────────────────────────────────
  async function verifyChain() {
    setVerifying(true);
    setVerifyFlash(false);
    const t0 = performance.now();
    try {
      const res = await fetch(`${API_BASE}/api/v1/audit/verify`);
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const v = await res.json();
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

  // ── Per-row verify ────────────────────────────────────────────────
  async function verifyRow(id: number) {
    setRowVerify((s) => ({ ...s, [id]: { state: "loading" } }));
    try {
      const r = await api.verifyAuditRow(id);
      if (r.ok && r.row_hash) {
        setRowVerify((s) => ({ ...s, [id]: { state: "ok", row_hash: r.row_hash! } }));
      } else {
        setRowVerify((s) => ({ ...s, [id]: { state: "fail", reason: r.reason || "unknown" } }));
      }
    } catch (e) {
      setRowVerify((s) => ({ ...s, [id]: { state: "fail", reason: (e as Error).message } }));
    }
  }

  // ── Cert PDF ──────────────────────────────────────────────────────
  function downloadCert() {
    if (!since && !until) {
      toast.warn("Pick a time range", "Cert PDF needs at least a 'since' or 'until' bound");
      return;
    }
    toast.info("Generating range certificate…", "Walking the chain in the selected window");
    const url = api.auditRangeCertUrl({
      since: since || undefined,
      until: until || undefined,
    });
    const a = document.createElement("a");
    a.href = url;
    a.download = `astra-audit-cert-${new Date().toISOString().slice(0, 19).replace(/[:-]/g, "")}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  // ── Mission report PDF (existing) ─────────────────────────────────
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

  // ── Filter chips ──────────────────────────────────────────────────
  function toggleType(t: string) {
    setSelectedTypes((s) => {
      const next = new Set(s);
      if (next.has(t)) next.delete(t);
      else next.add(t);
      return next;
    });
  }

  // ── Range presets ─────────────────────────────────────────────────
  function applyPreset(preset: "1h" | "24h" | "shift" | "all") {
    if (preset === "all") {
      setSince(""); setUntil("");
      return;
    }
    const now = new Date();
    const ms = preset === "1h" ? 3_600_000 : preset === "24h" ? 86_400_000 : 8 * 3_600_000;
    const from = new Date(now.getTime() - ms);
    setSince(toLocalInput(from));
    setUntil("");
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

  const distinctOps = new Set(events.map((e) => e.operator_id).filter(Boolean)).size;
  const rangeLabel = useMemo(() => {
    if (since && until) return `${since.slice(0, 16)} → ${until.slice(0, 16)}`;
    if (since) return `since ${since.slice(0, 16)}`;
    if (until) return `until ${until.slice(0, 16)}`;
    return "all time";
  }, [since, until]);

  return (
    <div className="h-full flex flex-col">
      <PageHeader
        icon={ScrollText}
        title="Audit Ledger"
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
            Append-only · SHA-256 hash-chained · {events.length} events · range: {rangeLabel}{loading && " · refreshing..."}
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
                className="bg-panel border border-border rounded pl-8 pr-3 py-1.5 text-sm w-44"
              />
            </div>
            <div className="flex items-center gap-2 border-l border-border pl-3">
              <label className="text-xs text-muted">Mission:</label>
              <select
                className="bg-panel border border-border rounded px-2 py-1.5 text-xs font-mono min-w-[160px]"
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
                Mission PDF
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
            <button
              onClick={syncMesh}
              disabled={syncingMesh}
              className="flex items-center gap-1 glass border border-border px-3 py-1.5 rounded text-xs hover:bg-panel2 disabled:opacity-50 transition-fast"
              title="Trigger demo peer agencies to pull, verify, and witness the chain"
            >
              {syncingMesh ? <Loader2 size={12} className="animate-spin" /> : <Network size={12} />}
              sync mesh
            </button>
            <button
              onClick={downloadCert}
              disabled={!since && !until}
              className="flex items-center gap-1 bg-cyan/20 border border-cyan/40 text-cyan px-3 py-1.5 rounded text-xs hover:bg-cyan/30 disabled:opacity-40 disabled:cursor-not-allowed transition-fast"
              title={(!since && !until) ? "Pick a time range first" : "Download cryptographic range certificate (PDF)"}
            >
              <FileText size={12} /> Cert PDF
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

      {/* Verify-chain flash banner */}
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
          <span className="opacity-90">{chainStatus.checked} rows · SHA-256 walk</span>
          {chainStatus.genesis && chainStatus.tip && (
            <span className="ml-auto text-muted2">
              genesis <span className="text-text">{chainStatus.genesis.slice(0, 10)}…</span>
              {" → tip "}
              <span className="text-text">{chainStatus.tip.slice(0, 10)}…{chainStatus.tip.slice(-6)}</span>
            </span>
          )}
          {!chainStatus.ok && (
            <span className="ml-auto">broken @ #{chainStatus.broken_at_id} · {chainStatus.reason}</span>
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

      <AnchorStrip />

      {/* Hero KPI strip */}
      <div className="px-6 pt-4 grid grid-cols-4 gap-3">
        <HeroStat label="audit events" value={events.length} icon={ScrollText} tone="cyan" sub="append-only" />
        <HeroStat
          label="chain rows"
          value={chainStatus?.checked ?? 0}
          icon={Hash}
          tone={chainStatus?.ok ? "low" : chainStatus ? "crit" : "neutral"}
          sub={chainStatus ? (chainStatus.ok ? "verified" : "BROKEN") : "click verify"}
        />
        <HeroStat label="distinct ops" value={distinctOps} icon={Users} tone="neutral" sub="recorded" />
        <HeroStat
          label="missions logged"
          value={new Set(events.map((e) => e.mission_id).filter(Boolean)).size}
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

      {/* Chain ribbon */}
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

      {/* Mesh witness feed (chronological, all peers) */}
      <div className="px-6 pt-3">
        <MeshFeedPanel />
      </div>

      {/* Filter chips + time-range scrubber */}
      <div className="px-6 pt-3 flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-1.5 flex-wrap">
          {ALL_EVENT_TYPES.map((t) => {
            const sel = selectedTypes.has(t);
            const color = EVENT_COLORS[t] ?? "#8b9aad";
            return (
              <button
                key={t}
                onClick={() => toggleType(t)}
                className={`text-2xs font-mono uppercase-wide tracking-wider px-2 py-1 rounded border transition-fast ${
                  sel
                    ? "border-accent bg-accent/15 text-accent"
                    : "border-border text-muted hover:text-text hover:border-border"
                }`}
                style={sel ? undefined : { borderLeft: `2px solid ${color}` }}
                title={`Toggle ${t} filter`}
              >
                {t}
                {typeCounts[t] != null && <span className="ml-1.5 opacity-60 tabular-nums">{typeCounts[t]}</span>}
              </button>
            );
          })}
          {selectedTypes.size > 0 && (
            <button
              onClick={() => setSelectedTypes(new Set())}
              className="text-2xs font-mono uppercase-wide tracking-wider px-2 py-1 rounded text-muted2 hover:text-text"
              title="Clear all filters"
            >
              clear
            </button>
          )}
        </div>
        <div className="flex items-center gap-2 ml-auto">
          <div className="flex items-center gap-1">
            <span className="text-2xs uppercase-wide text-muted2 font-mono">since</span>
            <input
              type="datetime-local"
              value={since}
              onChange={(e) => setSince(e.target.value)}
              className="bg-panel border border-border rounded px-2 py-1 text-2xs font-mono"
            />
          </div>
          <div className="flex items-center gap-1">
            <span className="text-2xs uppercase-wide text-muted2 font-mono">until</span>
            <input
              type="datetime-local"
              value={until}
              onChange={(e) => setUntil(e.target.value)}
              className="bg-panel border border-border rounded px-2 py-1 text-2xs font-mono"
            />
          </div>
          {(["1h", "24h", "shift", "all"] as const).map((p) => (
            <button
              key={p}
              onClick={() => applyPreset(p)}
              className="text-2xs font-mono uppercase-wide tracking-wider px-2 py-1 rounded border border-border text-muted hover:text-text hover:bg-panel2 transition-fast"
              title={
                p === "1h" ? "Last 1 hour" :
                p === "24h" ? "Last 24 hours" :
                p === "shift" ? "Last shift (8h)" :
                "All events (clear range)"
              }
            >
              {p === "shift" ? "last shift" : p === "all" ? "all" : `last ${p}`}
            </button>
          ))}
          <button
            onClick={() => setRailOpen((v) => !v)}
            className="ml-2 p-1 text-muted hover:text-text rounded"
            title={railOpen ? "Collapse activity rail" : "Expand activity rail"}
          >
            {railOpen ? <ChevronsRight size={14} /> : <ChevronsLeft size={14} />}
          </button>
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
              title={events.length === 0 ? "No audit events in this window" : "No matches"}
              body={events.length === 0 ? "Adjust filters or pick a wider time range. The chain is append-only — events are still on disk." : "Adjust your filter to see events."}
              cta={events.length === 0 ? { label: "Show all", onClick: () => { setSelectedTypes(new Set()); setSince(""); setUntil(""); } } : undefined}
            />
          ) : (
            filtered.map((e) => {
              const rv = rowVerify[e.id] ?? { state: "idle" as const };
              const w = witnessesByRow[e.id] ?? [];
              const wTotal = meshPeerCount || 2;
              const wTone = w.length === 0 ? "muted" : w.length < wTotal ? "warn" : "ok";
              const wTooltip = w.length === 0
                ? `No peers have witnessed this row yet. Click 'sync mesh' to trigger demo peers.`
                : w.map((x) => `${x.peer_id} · ${x.witnessed_at?.slice(0, 19) ?? "—"}`).join("\n");
              return (
                <div
                  key={e.id}
                  className="border-b border-border last:border-0 px-4 py-2.5 grid grid-cols-[160px_90px_180px_1fr_auto_auto] gap-3 hover:bg-panel2 items-center"
                >
                  <span className="text-muted" title={absoluteIst(e.created_at)}>{relativeTime(e.created_at)}</span>
                  <span className="text-accent">{e.operator_id ?? "system"}</span>
                  <span style={{ color: EVENT_COLORS[e.event_type] ?? "#8b9aad" }}>
                    {e.event_type}
                  </span>
                  <span className="text-text truncate">{describe(e)}</span>
                  <span
                    className={`text-2xs font-mono uppercase-wide tracking-wider px-2 py-0.5 rounded border shrink-0 ${
                      wTone === "ok"
                        ? "border-threat-low/40 bg-threat-low/10 text-threat-low"
                        : wTone === "warn"
                        ? "border-threat-high/40 bg-threat-high/10 text-threat-high"
                        : "border-border text-muted2 bg-panel2/40"
                    }`}
                    title={wTooltip}
                  >
                    <Network size={9} className="inline mr-1" />
                    {w.length}/{wTotal}
                  </span>
                  <button
                    onClick={() => verifyRow(e.id)}
                    disabled={rv.state === "loading"}
                    className={`flex items-center gap-1 text-2xs font-mono uppercase-wide tracking-wider px-2 py-0.5 rounded border transition-fast shrink-0 ${
                      rv.state === "ok"
                        ? "border-threat-low/40 bg-threat-low/10 text-threat-low"
                        : rv.state === "fail"
                        ? "border-threat-crit/40 bg-threat-crit/10 text-threat-crit"
                        : "border-border text-muted hover:text-text hover:bg-panel2/80"
                    }`}
                    title={
                      rv.state === "ok"
                        ? `verified · row_hash ${rv.row_hash.slice(0, 8)}…${rv.row_hash.slice(-6)}`
                        : rv.state === "fail"
                        ? `verify failed: ${rv.reason}`
                        : `re-walk SHA-256 from genesis to row #${e.id}`
                    }
                  >
                    {rv.state === "loading"
                      ? <Loader2 size={10} className="animate-spin" />
                      : rv.state === "ok"
                      ? <ShieldCheck size={10} />
                      : rv.state === "fail"
                      ? <ShieldAlert size={10} />
                      : <ShieldCheck size={10} />}
                    {rv.state === "ok" ? "ok" : rv.state === "fail" ? "fail" : "verify"}
                  </button>
                </div>
              );
            })
          )}
        </div>

        {/* Operator activity rail */}
        {railOpen && (
          <aside className="w-72 glass rounded-lg shadow-panel flex flex-col overflow-hidden shrink-0">
            <div className="px-4 py-2.5 border-b border-border flex items-center justify-between">
              <div>
                <div className="text-2xs uppercase-wide tracking-wider text-muted2 font-mono">OPERATOR ACTIVITY</div>
                <div className="text-[10px] text-muted font-mono mt-0.5">{rangeLabel}</div>
              </div>
              <button
                onClick={() => setRailOpen(false)}
                className="p-1 text-muted hover:text-text rounded"
                title="Collapse rail"
              >
                <ChevronsRight size={12} />
              </button>
            </div>
            <div className="flex-1 overflow-auto p-3 space-y-2.5">
              {!activity ? (
                <div className="text-2xs text-muted2">loading…</div>
              ) : activity.operators.length === 0 ? (
                <div className="text-2xs text-muted2">No operator activity in this window.</div>
              ) : (
                activity.operators.map((op) => {
                  const total = op.total || 1;
                  return (
                    <div key={op.operator_id}>
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-mono text-text truncate" title={op.operator_id}>{op.operator_id}</span>
                        <span className="font-mono tabular-nums text-accent">{op.total}</span>
                      </div>
                      <div className="flex h-2 mt-1 rounded overflow-hidden bg-panel2">
                        {Object.entries(op.by_event_type)
                          .sort(([, a], [, b]) => b - a)
                          .map(([et, n]) => {
                            const pct = (n / total) * 100;
                            const color = EVENT_COLORS[et] ?? "#8b9aad";
                            return (
                              <span
                                key={et}
                                className="h-full"
                                style={{ width: `${pct}%`, background: color }}
                                title={`${et} · ${n}`}
                              />
                            );
                          })}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
            <div className="px-3 py-2 border-t border-border text-[10px] text-muted2 font-mono">
              system events: <span className="text-muted tabular-nums">{activity?.system_events ?? "—"}</span>
              <span className="mx-1">·</span>
              total: <span className="text-muted tabular-nums">{activity?.total ?? "—"}</span>
            </div>
          </aside>
        )}
      </div>
    </div>
  );
}

// ── helpers ──────────────────────────────────────────────────────────

/** Format a Date as a value for <input type="datetime-local"> (local TZ). */
function toLocalInput(d: Date): string {
  const pad = (n: number) => n.toString().padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
