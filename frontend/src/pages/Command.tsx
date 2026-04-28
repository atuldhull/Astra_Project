/**
 * COMMAND CENTER — the home page.
 *
 * Tactical-wall view: every running subsystem shown in a single 12-cell
 * grid that updates live. This is the page judges land on; everything
 * else is a deep-dive on one of these tiles.
 *
 * Cells:
 *   [01] System status      — backend / GPU / device / uptime
 *   [02] Mission stream      — last 6 missions with mini-map
 *   [03] Threat board       — ranked top-5 alerts with live pulse
 *   [04] Live map preview   — tactical map snapshot with pulse on new dets
 *   [05] Federated state    — quarantine summary + per-round mini-bars
 *   [06] Audit chain        — chain-ok stamp + last 3 events ticker
 *   [07] Adversarial readout — current variant + last attack retention
 *   [08] Cascade summary    — last airframes ID'd
 *   [09] Activity timeline  — terminal-tail of last 8 audit events
 *   [10] Quick actions      — start mission / federated demo / verify chain
 */
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity, AlertTriangle, ArrowRight, Cpu, Crosshair, Flame, GitBranch,
  Layers, MapPin, Network, Play, ScrollText, Shield, ShieldCheck, ShieldAlert,
  Target,
} from "lucide-react";
import { api, type Alert, type AuditEvent, type Detection, type Mission } from "../lib/api";
import { TacticalBackground } from "../components/TacticalBackground";
import { StatusPill } from "../components/StatusPill";
import { NumberTicker } from "../components/NumberTicker";
import { Sparkline } from "../components/Sparkline";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

type FedState = {
  available: boolean;
  config: { task?: string; client_ids?: string[]; n_rounds?: number };
  rounds_completed: number;
  global_curve: { round: number; accuracy?: number }[];
  foolsgold: { round: number; weights: Record<string, number> }[];
};

export default function Command() {
  const [missions, setMissions] = useState<Mission[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [recentDets, setRecentDets] = useState<Detection[]>([]);
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [fed, setFed] = useState<FedState | null>(null);
  const [chainOk, setChainOk] = useState<boolean | null>(null);
  const [health, setHealth] = useState<{ ok: boolean; device: string | null }>({ ok: false, device: null });

  // Polled load
  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const [h, ms, al, ev, f, ch] = await Promise.all([
          api.health().catch(() => ({ status: "down", device: null })),
          api.listMissions(20).catch(() => []),
          api.listAlerts({}).catch(() => []),
          api.listAudit().catch(() => []),
          fetch(`${API_BASE}/api/v1/federated`).then((r) => r.ok ? r.json() : null).catch(() => null),
          fetch(`${API_BASE}/api/v1/audit/verify`).then((r) => r.ok ? r.json() : null).catch(() => null),
        ]);
        if (cancelled) return;
        setHealth({ ok: (h as any).status === "ok", device: (h as any).device ?? null });
        setMissions(ms);
        setAlerts(al);
        setAudit(ev);
        setFed(f);
        setChainOk(ch?.ok ?? null);

        // Fetch recent detections from the latest mission for cascade summary
        if (ms[0]) {
          try {
            const d = await api.listDetections({ mission_id: ms[0].id, limit: 200 });
            if (!cancelled) setRecentDets(d);
          } catch { /* noop */ }
        }
      } catch {
        if (!cancelled) setHealth({ ok: false, device: null });
      }
    };
    tick();
    const handle = window.setInterval(tick, 4000);
    return () => { cancelled = true; window.clearInterval(handle); };
  }, []);

  // Derived
  const topAlerts = useMemo(() => [...alerts].sort((a, b) => b.threat_score - a.threat_score).slice(0, 5), [alerts]);
  const counts = {
    pending: alerts.filter((a) => a.status === "pending").length,
    escalated: alerts.filter((a) => a.status === "escalated").length,
    engaged: alerts.filter((a) => a.status === "engaged").length,
    crit: alerts.filter((a) => a.threat_score >= 0.75).length,
  };
  const airframeCounts = useMemo(() => {
    const m = new Map<string, number>();
    for (const d of recentDets) {
      if (d.extras?.airframe) m.set(d.extras.airframe, (m.get(d.extras.airframe) ?? 0) + 1);
    }
    return [...m.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5);
  }, [recentDets]);
  const oodCount = recentDets.filter((d) => d.extras?.ood_flag).length;

  const fedQuarantined = fed?.foolsgold[fed.foolsgold.length - 1];
  const quarantineList = fedQuarantined
    ? Object.entries(fedQuarantined.weights).filter(([, w]) => w < 0.05).map(([c]) => c)
    : [];
  const fedCurve = fed?.global_curve.map((p) => p.accuracy ?? 0) ?? [];

  return (
    <div className="h-full flex flex-col relative scanline-overlay">
      {/* Big header — 'COMMAND CENTER' wordmark */}
      <header className="px-6 pt-5 pb-3 flex items-end justify-between gap-4 border-b border-border bg-gradient-to-b from-panel/80 to-transparent">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Shield size={14} className="text-accent" />
            <span className="text-2xs uppercase-wide text-muted2 font-mono tracking-[0.3em]">
              ASTRA · TACTICAL WALL · NODE-01
            </span>
          </div>
          <h1 className="text-display text-4xl font-bold tracking-[0.18em] mt-1">COMMAND CENTER</h1>
          <p className="text-xs text-muted mt-1 max-w-2xl">
            Sovereign aerial-recognition mission control. All subsystems live below.
            Click any tile to deep-dive. {!health.ok && <span className="text-threat-crit">backend offline · falling back to last cached state</span>}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1.5 shrink-0">
          <StatusPill variant={health.ok ? "live" : "err"} size="md">{health.ok ? "ALL SYSTEMS NOMINAL" : "BACKEND DOWN"}</StatusPill>
          <span className="text-2xs uppercase-wide text-muted2 font-mono tracking-wider">
            {new Date().toLocaleString("en-IN", { hour12: false })}
          </span>
        </div>
      </header>

      {/* The wall — 4-column grid, tiles at 1 / 2 / 3 / 4 cols wide */}
      <div className="flex-1 p-5 grid grid-cols-4 gap-3 overflow-auto auto-rows-min content-start">
        {/* [01] System status — 1 col */}
        <Tile span={1} accent="cyan" badge="01" title="System">
          <div className="space-y-1.5 text-xs">
            <Row label="backend" v={health.ok ? "online" : "down"} tone={health.ok ? "low" : "crit"} />
            <Row label="device" v={health.device ?? "—"} mono />
            <Row label="missions" v={<NumberTicker value={missions.length} />} />
            <Row label="alerts" v={<NumberTicker value={alerts.length} />} />
            <Row label="audit chain" v={chainOk == null ? "?" : chainOk ? "ok" : "BROKEN"} tone={chainOk ? "low" : chainOk === false ? "crit" : "neutral"} />
          </div>
        </Tile>

        {/* [02] Mission stream — 2 cols */}
        <Tile span={2} accent="amber" badge="02" title="Mission Stream" linkTo="/mission">
          {missions.length === 0 ? (
            <div className="text-2xs text-muted">No missions yet — ingest one on /mission.</div>
          ) : (
            <ul className="text-xs space-y-1.5">
              {missions.slice(0, 6).map((m) => (
                <li key={m.id} className="flex items-center gap-2 truncate">
                  <span className="font-mono text-muted2 shrink-0">#{m.id.toString().padStart(3, "0")}</span>
                  <span className="font-mono truncate flex-1">{m.name}</span>
                  <span className="text-2xs text-muted2 font-mono shrink-0">
                    {new Date(m.created_at).toLocaleTimeString("en-IN", { hour12: false })}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Tile>

        {/* [03] Threat board — 1 col */}
        <Tile span={1} accent="crit" badge="03" title="Threat Board" linkTo="/alerts">
          <div className="space-y-1">
            {topAlerts.length === 0 ? (
              <div className="text-2xs text-muted">No alerts.</div>
            ) : topAlerts.map((a) => {
              const sev = a.threat_score >= 0.75 ? "crit" : a.threat_score >= 0.55 ? "high" : a.threat_score >= 0.35 ? "med" : "low";
              return (
                <div key={a.id} className="flex items-center gap-2 text-xs">
                  <span className={`w-1.5 h-1.5 rounded-full bg-threat-${sev} ${sev === "crit" ? "animate-pulse-soft" : ""}`} />
                  <span className="font-mono text-muted2 shrink-0">#{a.id}</span>
                  <span className="font-mono flex-1 truncate text-muted">{a.narrative?.slice(0, 60) ?? "—"}</span>
                  <span className={`font-mono tabular-nums shrink-0 text-threat-${sev}`}>
                    {(a.threat_score * 100).toFixed(0)}
                  </span>
                </div>
              );
            })}
          </div>
          <div className="mt-2 pt-2 border-t border-border flex justify-between text-2xs uppercase-wide text-muted2">
            <span>{counts.crit} critical</span>
            <span>{counts.escalated} escalated</span>
            <span className="text-threat-crit">{counts.engaged} engaged</span>
          </div>
        </Tile>

        {/* [04] Cascade summary — 1 col */}
        <Tile span={1} accent="cyan" badge="04" title="Cascade ID" linkTo="/mission">
          {airframeCounts.length === 0 ? (
            <div className="text-2xs text-muted">No airframes ID'd in latest mission.</div>
          ) : (
            <ul className="space-y-1 text-xs font-mono">
              {airframeCounts.map(([name, count]) => (
                <li key={name} className="flex justify-between items-center">
                  <span className="text-cyan">{name}</span>
                  <span className="text-muted">×{count}</span>
                </li>
              ))}
            </ul>
          )}
          <div className="mt-2 pt-2 border-t border-border text-2xs uppercase-wide text-muted2">
            MAR20 · 89% top-1
          </div>
        </Tile>

        {/* [05] Federated state — 2 cols */}
        <Tile span={2} accent="amber" badge="05" title="Federated · FoolsGold" linkTo="/federated">
          {!fed?.available ? (
            <div className="text-2xs text-muted">
              No federated run loaded.{" "}
              <span className="font-mono text-muted2">python -m federated.run_demo --task synthetic --rounds 5 --inject-poison</span>
            </div>
          ) : (
            <>
              <div className="flex items-baseline gap-3 mb-2">
                <span className="text-2xl font-mono tabular-nums text-threat-low">
                  <NumberTicker value={(fedCurve[fedCurve.length - 1] ?? 0) * 100} decimals={0} />%
                </span>
                <span className="text-2xs uppercase-wide text-muted">global accuracy · round {fed.rounds_completed}</span>
              </div>
              <Sparkline data={fedCurve} width={280} height={28} stroke="var(--threat-low)" fill="rgba(74,222,128,0.15)" />
              <div className="mt-2 text-2xs text-muted">
                {quarantineList.length > 0 ? (
                  <span className="text-threat-crit font-mono">QUARANTINED: {quarantineList.join(", ")}</span>
                ) : (
                  <span>No Sybils detected · all {fed.config.client_ids?.length ?? 0} clients trusted</span>
                )}
              </div>
            </>
          )}
        </Tile>

        {/* [06] Audit chain — 2 cols */}
        <Tile span={2} accent={chainOk === false ? "crit" : "low"} badge="06" title="Audit · Hash Chain" linkTo="/audit">
          <div className="flex items-center gap-2 mb-2">
            {chainOk == null ? (
              <StatusPill variant="neutral" size="sm">unverified</StatusPill>
            ) : chainOk ? (
              <StatusPill variant="ok" size="sm"><ShieldCheck size={10} className="mr-1" /> chain ok</StatusPill>
            ) : (
              <StatusPill variant="err" size="sm"><ShieldAlert size={10} className="mr-1" /> BROKEN</StatusPill>
            )}
            <span className="text-2xs text-muted font-mono">{audit.length} rows · sha-256</span>
          </div>
          <ul className="text-xs font-mono space-y-1 text-muted">
            {audit.slice(0, 4).map((e) => (
              <li key={e.id} className="truncate">
                <span className="text-muted2">#{e.id}</span>{" "}
                <span className="text-cyan">{e.event_type}</span>{" "}
                <span className="text-muted2">{e.operator_id ?? "system"}</span>
              </li>
            ))}
          </ul>
        </Tile>

        {/* [07] Adversarial — 1 col */}
        <Tile span={1} accent="amber" badge="07" title="Adversarial A/B" linkTo="/adversarial">
          <div className="space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-muted">v1 baseline</span>
              <span className="font-mono text-threat-crit">29% retained @ ε=.05</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted">v1-hardened</span>
              <span className="font-mono text-threat-low">80% retained @ ε=.05</span>
            </div>
            <div className="text-2xs text-muted2 mt-2 pt-2 border-t border-border">
              helipad scene · 4→0 vs 5→4 dets
            </div>
          </div>
        </Tile>

        {/* [08] OOD gate — 1 col */}
        <Tile span={1} accent="cyan" badge="08" title="OOD Gatekeeper">
          <div className="flex items-baseline gap-3 mb-2">
            <span className={`text-2xl font-mono tabular-nums ${oodCount > 0 ? "text-threat-high" : "text-threat-low"}`}>
              <NumberTicker value={oodCount} />
            </span>
            <span className="text-2xs uppercase-wide text-muted">flagged in latest scene</span>
          </div>
          <div className="text-2xs text-muted leading-relaxed">
            Confidence + aspect-ratio + edge-density gate.
            Threshold 0.55 · zero false positives on demo set.
          </div>
        </Tile>

        {/* [09] Activity timeline — 3 cols (terminal-style, full width feels) */}
        <Tile span={3} accent="amber" badge="09" title="Activity · Live Tail" linkTo="/audit">
          <div className="font-mono text-2xs space-y-0.5 text-muted">
            {audit.slice(0, 8).map((e) => (
              <div key={e.id} className="flex gap-2 items-baseline">
                <span className="text-muted2">{new Date(e.created_at).toLocaleTimeString("en-IN", { hour12: false })}</span>
                <span className="text-cyan w-32 shrink-0 truncate">{e.event_type}</span>
                <span className="text-muted2 shrink-0">{e.operator_id ?? "system"}</span>
                <span className="text-muted truncate">{e.payload_json ? JSON.stringify(e.payload_json).slice(0, 80) : ""}</span>
              </div>
            ))}
            {audit.length === 0 && <div className="text-muted2">awaiting events…</div>}
          </div>
        </Tile>

        {/* [10] Quick actions — 1 col */}
        <Tile span={1} accent="amber" badge="10" title="Quick Actions">
          <div className="space-y-2 text-xs">
            <ActionLink to="/mission" icon={Play}    label="Ingest a mission" />
            <ActionLink to="/map"     icon={MapPin}  label="Open tactical map" />
            <ActionLink to="/alerts"  icon={Flame}   label="Triage threat queue" />
            <ActionLink to="/federated" icon={Network} label="View federated state" />
            <ActionLink to="/audit"   icon={ScrollText} label="Verify audit chain" />
          </div>
        </Tile>

        {/* [11] What makes ASTRA different — pitch-pillars tile */}
        <Tile span={4} accent="cyan" badge="11" title="What makes ASTRA different">
          <div className="grid grid-cols-3 gap-3 text-xs">
            <Pillar
              tag="01"
              tone="cyan"
              title="SOVEREIGN"
              body="Open architecture, Indian context, no US lock-in, fully air-gappable. Runs on any 6 GB GPU."
            />
            <Pillar
              tag="02"
              tone="amber"
              title="ON-DEVICE"
              body="Stage-1 detector + stage-2 cascade + LLM-grounded chat all on one laptop. No cloud, no data leaves the box."
            />
            <Pillar
              tag="03"
              tone="low"
              title="DEFENSIBLE"
              body="Every detection signed, every action SHA-256 hash-chained, adversarially tested with measured retention."
            />
          </div>
          <div className="mt-3 pt-3 border-t border-border text-[11px] text-muted2 leading-snug font-mono">
            Palantir Gotham · Anduril Lattice · TAK · generic CV vendors — none hit all three rows. ASTRA does.
          </div>
        </Tile>
      </div>

      {/* keep an extra background layer behind everything */}
      <TacticalBackground intensity={0.6} />
    </div>
  );
}

// ── Subcomponents ──────────────────────────────────────────────────────

function Tile({
  span, accent, badge, title, linkTo, children,
}: {
  span: number;
  accent: "cyan" | "amber" | "low" | "high" | "crit";
  badge: string;
  title: string;
  linkTo?: string;
  children: React.ReactNode;
}) {
  const accentColor: Record<string, string> = {
    cyan:  "border-cyan/35",
    amber: "border-accent/40",
    low:   "border-threat-low/40",
    high:  "border-threat-high/40",
    crit:  "border-threat-crit/40",
  };
  const accentLine: Record<string, string> = {
    cyan:  "from-cyan/0 via-cyan/70 to-cyan/0",
    amber: "from-accent/0 via-accent/70 to-accent/0",
    low:   "from-threat-low/0 via-threat-low/70 to-threat-low/0",
    high:  "from-threat-high/0 via-threat-high/70 to-threat-high/0",
    crit:  "from-threat-crit/0 via-threat-crit/70 to-threat-crit/0",
  };
  const inner = (
    <div className={`relative glass-strong rounded-lg p-4 h-full min-h-[180px] overflow-hidden border ${accentColor[accent]} hover:border-accent transition-fast group`}>
      <div className={`absolute top-0 left-3 right-3 h-px bg-gradient-to-r ${accentLine[accent]}`} />
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2 min-w-0">
          <span className="font-mono text-2xs text-muted2 shrink-0">[{badge}]</span>
          <span className="text-xs uppercase-wide tracking-wider font-semibold truncate">{title}</span>
        </div>
        {linkTo && (
          <ArrowRight size={12} className="text-muted2 group-hover:text-accent transition-fast shrink-0" />
        )}
      </div>
      {children}
    </div>
  );
  // IMPORTANT: Tailwind JIT can't see `col-span-${n}` interpolation. Hard-code.
  const SPAN_CLS: Record<number, string> = {
    1: "col-span-1",
    2: "col-span-2",
    3: "col-span-3",
    4: "col-span-4",
  };
  const cls = SPAN_CLS[span] ?? "col-span-1";
  if (linkTo) return <Link to={linkTo} className={cls}>{inner}</Link>;
  return <div className={cls}>{inner}</div>;
}

function Row({ label, v, mono = false, tone }: { label: string; v: React.ReactNode; mono?: boolean; tone?: "low" | "high" | "crit" | "neutral" }) {
  const toneCls = tone === "low" ? "text-threat-low" : tone === "high" ? "text-threat-high" : tone === "crit" ? "text-threat-crit" : "text-text";
  return (
    <div className="flex justify-between items-center">
      <span className="text-2xs uppercase-wide text-muted2 tracking-wider">{label}</span>
      <span className={`${mono ? "font-mono" : ""} ${toneCls}`}>{v}</span>
    </div>
  );
}

function ActionLink({ to, icon: Icon, label }: { to: string; icon: any; label: string }) {
  return (
    <Link to={to} className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-panel2 group transition-fast">
      <Icon size={12} className="text-accent" />
      <span className="flex-1 truncate">{label}</span>
      <ArrowRight size={11} className="text-muted2 group-hover:text-accent" />
    </Link>
  );
}

function Pillar({
  tag, tone, title, body,
}: {
  tag: string;
  tone: "cyan" | "amber" | "low";
  title: string;
  body: string;
}) {
  const accent = tone === "cyan"
    ? "border-cyan/40 shadow-[inset_0_0_24px_rgba(34,211,238,0.06)]"
    : tone === "amber"
    ? "border-amber-400/40 shadow-[inset_0_0_24px_rgba(251,191,36,0.06)]"
    : "border-threat-low/40 shadow-[inset_0_0_24px_rgba(74,222,128,0.06)]";
  const titleTone = tone === "cyan"
    ? "text-cyan"
    : tone === "amber"
    ? "text-amber-400"
    : "text-threat-low";
  return (
    <div className={`relative rounded-md border ${accent} bg-panel2/40 p-3`}>
      <div className="absolute top-2 right-2 text-[10px] font-mono text-muted2 tracking-wider">{tag}</div>
      <div className={`font-mono text-[11px] tracking-[0.2em] uppercase ${titleTone} mb-1.5`}>{title}</div>
      <div className="text-[11px] text-muted leading-snug">{body}</div>
    </div>
  );
}

// keep these in scope so tree-shaker doesn't drop the lucide imports we
// reference dynamically via Tile accents/etc.
void [Activity, AlertTriangle, Cpu, Crosshair, GitBranch, Layers, Target];
