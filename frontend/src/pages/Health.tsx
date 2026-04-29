/**
 * Health (D3.6) — single-pane System Metrics for the operator.
 *
 * Reads /api/v1/health/dashboard once on mount + every 10s. Each block
 * (models / chain / errors / calibration freshness) is independently
 * fault-tolerant — if a benchmark file is missing the rest still
 * renders, with a "Run capture" hint per stale slot.
 *
 * Lives in the OPERATOR group; hidden when Demo Mode is ON.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity, AlertTriangle, Anchor, Cpu, Database, HardDrive, HeartPulse,
  Layers, Loader2, RefreshCw, ScrollText, Server, ShieldCheck, Terminal, Zap,
} from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { HeroStat } from "../components/HeroStat";
import { Bezel } from "../components/Bezel";
import { StatusPill } from "../components/StatusPill";
import { toast } from "../components/Toast";
import { useStallTimeout } from "../lib/useStallTimeout";
import { absoluteIst, relativeTime } from "../lib/time";
import { api, type HealthDashboard } from "../lib/api";

const REFRESH_MS = 10_000;

function truncHash(h: string | null | undefined, head = 8, tail = 6): string {
  if (!h) return "—";
  if (h.length <= head + tail + 1) return h;
  return `${h.slice(0, head)}…${h.slice(-tail)}`;
}

function formatUptime(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ${s % 60}s`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ${m % 60}m`;
  const d = Math.floor(h / 24);
  return `${d}d ${h % 24}h`;
}

const SCRIPTS = {
  ood: "D:/astra-data/venvs/astra/Scripts/python.exe scripts/calibrate_ood.py",
  latency: "D:/astra-data/venvs/astra/Scripts/python.exe scripts/capture_latency.py --n 25",
  map: "D:/astra-data/venvs/astra/Scripts/python.exe scripts/capture_detector_map.py",
};

export default function Health() {
  const [data, setData] = useState<HealthDashboard | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const stalled = useStallTimeout(loading && data == null, 15_000);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const d = await api.healthDashboard();
      setData(d);
      setErr(null);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const handle = window.setInterval(load, REFRESH_MS);
    return () => window.clearInterval(handle);
  }, [load]);

  const subtitle = useMemo(() => {
    if (!data) return "loading…";
    const v = data.backend.version;
    const up = formatUptime(data.backend.uptime_s);
    return `backend ${v} · uptime ${up} · ${data.backend.device}`;
  }, [data]);

  return (
    <div className="h-full flex flex-col">
      <PageHeader
        icon={HeartPulse}
        title="Health · System Metrics"
        subtitle={subtitle}
        badge={
          err ? <StatusPill variant="err" size="sm">backend unreachable</StatusPill>
            : data ? <StatusPill variant="ok" size="sm">live</StatusPill>
            : <StatusPill variant="neutral" size="sm">…</StatusPill>
        }
        actions={
          <button
            onClick={load}
            className="p-1.5 rounded hover:bg-panel2 text-muted transition-fast"
            title="Refresh now"
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
          </button>
        }
      />

      {/* 4-stat hero */}
      <div className="px-6 pt-4 grid grid-cols-4 gap-3">
        <HeroStat
          label="missions"
          value={data?.db.mission_count ?? 0}
          icon={Layers}
          tone="cyan"
          sub={`${data?.db.deleted_mission_count ?? 0} soft-deleted`}
        />
        <HeroStat
          label="detections"
          value={data?.db.detection_count ?? 0}
          icon={Activity}
          tone="neutral"
          sub="lifetime"
        />
        <HeroStat
          label="audit rows"
          value={data?.db.audit_count ?? 0}
          icon={ScrollText}
          tone="neutral"
          sub="hash-chained"
        />
        <HeroStat
          label="anchors"
          value={data?.chain.anchor_total ?? 0}
          icon={Anchor}
          tone="low"
          sub={
            data?.chain.last_anchor
              ? `last ${relativeTime(data.chain.last_anchor.ts)}`
              : "none yet"
          }
        />
      </div>

      <div className="flex-1 px-6 pt-4 pb-6 space-y-4 overflow-auto">
        {/* Three-column row: Models / Chain / Errors */}
        <div className="grid grid-cols-3 gap-4">
          <Bezel
            topBar={
              <span className="flex items-center gap-2">
                <Cpu size={11} className="text-cyan" />
                MODELS
              </span>
            }
          >
            <div className="p-4 space-y-2.5">
              <ModelRow
                name="Detector"
                ready={data?.models.detector_ready ?? false}
                hint={data?.backend.model_path ?? "—"}
              />
              <ModelRow
                name="Cascade"
                ready={data?.models.cascade_ready ?? false}
                hint="MAR20 airframe"
              />
              <ModelRow
                name="Phi-3.5 LLM"
                ready={data?.models.llm_ready ?? false}
                hint={data?.models.llm_path ?? "—"}
              />
              <div className="pt-2 mt-2 border-t border-border">
                <div className="text-2xs uppercase-wide tracking-wider text-muted2 font-mono mb-1">model hash</div>
                <div className="font-mono text-2xs text-text break-all" title={data?.models.model_hash}>
                  {truncHash(data?.models.model_hash, 12, 12)}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2 pt-2 mt-2 border-t border-border text-2xs font-mono">
                <div>
                  <div className="text-muted2 uppercase-wide tracking-wider">device</div>
                  <div className="text-text">{data?.backend.device ?? "—"}</div>
                </div>
                <div>
                  <div className="text-muted2 uppercase-wide tracking-wider">cuda</div>
                  <div className={data?.backend.cuda_available ? "text-threat-low" : "text-muted"}>
                    {data?.backend.cuda_available ? "available" : "not available"}
                  </div>
                </div>
              </div>
            </div>
          </Bezel>

          <Bezel
            topBar={
              <span className="flex items-center gap-2">
                <ShieldCheck size={11} className="text-cyan" />
                CHAIN
              </span>
            }
          >
            <div className="p-4 space-y-2.5">
              <KvRow label="tip">
                <span className="font-mono text-2xs text-text break-all" title={data?.chain.tip ?? undefined}>
                  {truncHash(data?.chain.tip)}
                </span>
              </KvRow>
              <KvRow label="tip id">
                <span className="font-mono tabular-nums text-2xs text-text">
                  {data?.chain.tip_id ?? "—"}
                </span>
              </KvRow>
              <KvRow label="anchor total">
                <span className="font-mono tabular-nums text-2xs text-text">
                  {data?.chain.anchor_total ?? 0}
                </span>
              </KvRow>
              <div className="pt-2 mt-2 border-t border-border">
                <div className="text-2xs uppercase-wide tracking-wider text-muted2 font-mono mb-1">last anchor</div>
                {data?.chain.last_anchor ? (
                  <div className="space-y-1 font-mono text-2xs">
                    <div className="flex justify-between text-muted">
                      <span>at row</span>
                      <span className="text-text tabular-nums">{data.chain.last_anchor.count}</span>
                    </div>
                    <div className="flex justify-between text-muted">
                      <span>tip</span>
                      <span className="text-text" title={data.chain.last_anchor.tip}>
                        {truncHash(data.chain.last_anchor.tip)}
                      </span>
                    </div>
                    <div className="flex justify-between text-muted">
                      <span>when</span>
                      <span className="text-text" title={absoluteIst(data.chain.last_anchor.ts)}>
                        {relativeTime(data.chain.last_anchor.ts)}
                      </span>
                    </div>
                    <div className="flex justify-between text-muted">
                      <span>backend</span>
                      <span className="text-text">{data.chain.last_anchor.backend}</span>
                    </div>
                  </div>
                ) : (
                  <div className="text-2xs text-muted2 italic">never anchored</div>
                )}
              </div>
              <div className="pt-2 mt-2 border-t border-border">
                <div className="text-2xs uppercase-wide tracking-wider text-muted2 font-mono mb-1">peer witnesses</div>
                <div className="font-mono tabular-nums text-text">{data?.db.peer_witness_count ?? 0}</div>
              </div>
            </div>
          </Bezel>

          <Bezel
            topBar={
              <span className="flex items-center gap-2">
                <AlertTriangle size={11} className="text-cyan" />
                ERRORS
              </span>
            }
          >
            <div className="p-4 space-y-2.5">
              <KvRow label="count (24h)">
                <span
                  className={`font-mono tabular-nums text-sm ${
                    (data?.errors.count_24h ?? 0) > 0 ? "text-threat-med" : "text-threat-low"
                  }`}
                >
                  {data?.errors.count_24h ?? 0}
                </span>
              </KvRow>
              <KvRow label="last message">
                <span className="font-mono text-2xs text-text truncate max-w-[160px]" title={data?.errors.last_message ?? "none"}>
                  {data?.errors.last_message ?? "—"}
                </span>
              </KvRow>
              <KvRow label="last ts">
                <span className="font-mono text-2xs text-text" title={data?.errors.last_ts ? absoluteIst(data.errors.last_ts) : ""}>
                  {data?.errors.last_ts ? relativeTime(data.errors.last_ts) : "—"}
                </span>
              </KvRow>
              <div className="pt-2 mt-2 border-t border-border">
                <div className="text-2xs uppercase-wide tracking-wider text-muted2 font-mono mb-1">db rows</div>
                <div className="grid grid-cols-2 gap-1 text-2xs font-mono">
                  <Mini icon={Activity} label="alerts"   value={data?.db.alert_count ?? 0} />
                  <Mini icon={Database} label="chat"     value={data?.db.chat_message_count ?? 0} />
                  <Mini icon={Server}   label="audit"    value={data?.db.audit_count ?? 0} />
                  <Mini icon={HardDrive} label="missions" value={(data?.db.mission_count ?? 0) + (data?.db.deleted_mission_count ?? 0)} />
                </div>
              </div>
            </div>
          </Bezel>
        </div>

        {/* Calibration freshness — full width */}
        <Bezel
          topBar={
            <span className="flex items-center gap-2">
              <Zap size={11} className="text-cyan" />
              CALIBRATION FRESHNESS
            </span>
          }
        >
          <div className="p-4 grid grid-cols-3 gap-4">
            <FreshnessSlot
              label="OOD calibration"
              capturedAt={data?.ood?.captured_at ?? null}
              meta={
                data?.ood?.available
                  ? `${data?.ood?.classes?.length ?? 0} classes · Mahalanobis`
                  : (data?.ood?.hint ?? "not available")
              }
              command={SCRIPTS.ood}
            />
            <FreshnessSlot
              label="Ingest latency"
              capturedAt={data?.latency?.captured_at ?? null}
              meta={
                data?.latency
                  ? `p50 ${data.latency.data.p50_ms.toFixed(0)}ms · p99 ${data.latency.data.p99_ms.toFixed(0)}ms · n=${data.latency.data.n}`
                  : "no latency capture on disk"
              }
              command={SCRIPTS.latency}
            />
            <FreshnessSlot
              label="Detector mAP"
              capturedAt={data?.map?.captured_at ?? null}
              meta={
                data?.map
                  ? `mAP@.5 ${data.map.data.map_50.toFixed(3)} · mAP@.5:.95 ${data.map.data.map_50_95.toFixed(3)}`
                  : "no benchmark on disk"
              }
              command={SCRIPTS.map}
            />
          </div>
        </Bezel>

        {/* Footer status strip */}
        <div className="flex items-center justify-between text-2xs font-mono text-muted2 border-t border-border pt-3">
          <span>
            polling /health/dashboard every {REFRESH_MS / 1000}s
            {err && <span className="text-threat-crit"> · last error: {err}</span>}
            {stalled && !data && <span className="text-threat-high"> · backend slow or unreachable</span>}
          </span>
          {data && (
            <span title={absoluteIst(data.captured_at)}>
              snapshot {relativeTime(data.captured_at)}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

// ── small subviews ───────────────────────────────────────────────────

function KvRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-2xs uppercase-wide tracking-wider text-muted2 font-mono">{label}</span>
      {children}
    </div>
  );
}

function ModelRow({ name, ready, hint }: { name: string; ready: boolean; hint: string }) {
  return (
    <div className="flex items-start justify-between gap-2">
      <div className="min-w-0">
        <div className="text-xs text-text">{name}</div>
        <div className="text-2xs text-muted2 font-mono truncate" title={hint}>{hint}</div>
      </div>
      <StatusPill variant={ready ? "ok" : "warn"} size="sm">
        {ready ? "ready" : "absent"}
      </StatusPill>
    </div>
  );
}

function Mini({ icon: Icon, label, value }: { icon: typeof Activity; label: string; value: number }) {
  return (
    <div className="flex items-center gap-1.5 text-muted">
      <Icon size={10} className="text-muted2" />
      <span className="text-text tabular-nums">{value.toLocaleString()}</span>
      <span className="text-muted2 uppercase-wide tracking-wider">{label}</span>
    </div>
  );
}

function FreshnessSlot({
  label, capturedAt, meta, command,
}: {
  label: string;
  capturedAt: string | null;
  meta: string;
  command: string;
}) {
  // Stale = >7 days old, missing = no captured_at.
  const ageMs = capturedAt ? Date.now() - new Date(capturedAt).getTime() : null;
  const isStale = ageMs !== null && ageMs > 7 * 86_400_000;
  const variant = !capturedAt ? "warn" : isStale ? "warn" : "ok";

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="text-2xs uppercase-wide tracking-wider text-muted2 font-mono">{label}</span>
        <StatusPill variant={variant} size="sm">
          {!capturedAt ? "absent" : isStale ? "stale" : "fresh"}
        </StatusPill>
      </div>
      <div className="text-xs text-text font-mono">
        {capturedAt ? relativeTime(capturedAt) : "—"}
      </div>
      <div className="text-2xs text-muted2 font-mono leading-snug truncate" title={meta}>
        {meta}
      </div>
      <button
        onClick={() => {
          // No automation — capture scripts are operator-blocked. Toast
          // shows the exact command the operator should run.
          toast.info("Run capture", command);
          try {
            void navigator.clipboard?.writeText(command);
          } catch { /* noop */ }
        }}
        className="flex items-center gap-1.5 text-2xs font-mono text-cyan hover:text-cyan/80 mt-1"
        title="Copy command to clipboard"
      >
        <Terminal size={11} /> Run capture
      </button>
    </div>
  );
}
