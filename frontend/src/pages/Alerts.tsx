import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { Check, X, ArrowUpCircle, Loader2, RefreshCw, Crosshair, ShieldCheck, AlertTriangle, Flame, Inbox } from "lucide-react";
import { api, threatColor, type Alert, type Mission } from "../lib/api";
import { PageHeader } from "../components/PageHeader";
import { HeroStat } from "../components/HeroStat";
import { StatusPill } from "../components/StatusPill";
import { EmptyState } from "../components/EmptyState";
import { toast } from "../components/Toast";
import { ThreatWaveform } from "../components/ThreatWaveform";
import { ExportMenu } from "../components/ExportMenu";

// Must match backend DEFAULT_WEIGHTS in scoring.py
const DEFAULT_W = { w_class: 0.35, w_prox: 0.25, w_motion: 0.20, w_count: 0.10, w_conf: 0.10 };

// Class colors (kept in sync with Mission/MapView)
const CLASS_COLORS: Record<string, string> = {
  "small-vehicle":       "#4ade80",
  "large-vehicle":       "#facc15",
  "aircraft-fixed-wing": "#60a5fa",
  "aircraft-rotor":      "#a78bfa",
  "ship":                "#22d3ee",
  "storage-depot":       "#fb923c",
  "harbor":              "#f472b6",
  "bridge":              "#94a3b8",
};

type Weights = typeof DEFAULT_W;

// Recompute a threat score from its breakdown with new weights.
// The backend produced each term as (raw_term * default_weight). We recover
// the raw term by dividing out the default, then multiply by the user's.
function rerankScore(a: Alert, w: Weights): number {
  const b = a.score_breakdown;
  const raw = {
    c:   DEFAULT_W.w_class  ? b.class_term      / DEFAULT_W.w_class  : 0,
    p:   DEFAULT_W.w_prox   ? b.proximity_term  / DEFAULT_W.w_prox   : 0,
    m:   DEFAULT_W.w_motion ? b.motion_term     / DEFAULT_W.w_motion : 0,
    n:   DEFAULT_W.w_count  ? b.count_term      / DEFAULT_W.w_count  : 0,
    cf:  DEFAULT_W.w_conf   ? b.confidence_term / DEFAULT_W.w_conf   : 0,
  };
  const sum =
    w.w_class  * raw.c  +
    w.w_prox   * raw.p  +
    w.w_motion * raw.m  +
    w.w_count  * raw.n  +
    w.w_conf   * raw.cf;
  return Math.max(0, Math.min(1, sum));
}

// Resolve a detection's class via detection_id — we hold a map indexed by id
type DetClass = { class_id: number; class_name: string; confidence: number };

export default function Alerts() {
  const [missions, setMissions] = useState<Mission[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [detMap, setDetMap] = useState<Map<number, DetClass>>(new Map());
  const [weights, setWeights] = useState<Weights>(DEFAULT_W);
  const [operatorId, setOperatorId] = useState("cmdr-01");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  // Load missions and default-select newest
  useEffect(() => {
    api.listMissions(50)
      .then((m) => {
        setMissions(m);
        if (m.length > 0) {
          const stored = Number(localStorage.getItem("astra:lastMissionId") ?? "");
          const preferred = m.find((x) => x.id === stored) ?? m[0];
          setSelectedId(preferred.id);
        }
      })
      .catch((e) => setError(`missions: ${(e as Error).message}`));
  }, []);

  // Poll alerts + detections for the selected mission
  useEffect(() => {
    if (selectedId == null) return;
    let cancelled = false;
    const fetchAll = async () => {
      try {
        setLoading(true);
        const [a, dets] = await Promise.all([
          api.listAlerts({ mission_id: selectedId }),
          api.listDetections({ mission_id: selectedId, limit: 500 }),
        ]);
        if (cancelled) return;
        setAlerts(a);
        const m = new Map<number, DetClass>();
        for (const d of dets) m.set(d.id, { class_id: d.class_id, class_name: d.class_name, confidence: d.confidence });
        setDetMap(m);
      } catch (e) {
        if (!cancelled) setError(`alerts: ${(e as Error).message}`);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchAll();
    pollRef.current = window.setInterval(fetchAll, 5000);
    return () => {
      cancelled = true;
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, [selectedId]);

  // Client-side reranking
  const ranked = useMemo(() => {
    return alerts
      .map((a) => ({ alert: a, live: rerankScore(a, weights) }))
      .sort((x, y) => y.live - x.live);
  }, [alerts, weights]);

  async function act(alertId: number, action: "confirm" | "reject" | "escalate" | "engage") {
    setBusyId(alertId);
    setError(null);
    try {
      const updated = await api.actOnAlert(alertId, { action, operator_id: operatorId });
      // optimistic update
      setAlerts((prev) => prev.map((a) => (a.id === alertId ? updated : a)));
      const sev = updated.status === "engaged" ? "crit" : updated.status === "escalated" ? "warn" : "success";
      toast[sev](`Alert #${alertId} ${updated.status}`, `by ${operatorId}${action === "engage" && updated.status === "escalated" ? ` · ${updated.confirmations?.length ?? 0}/2 confirms` : ""}`);
    } catch (e) {
      const msg = (e as Error).message;
      setError(`${action} failed: ${msg}`);
      toast.crit(`${action} failed`, msg);
    } finally {
      setBusyId(null);
    }
  }

  function resetWeights() {
    setWeights(DEFAULT_W);
  }

  const counts = {
    pending: alerts.filter((a) => a.status === "pending").length,
    confirmed: alerts.filter((a) => a.status === "confirmed").length,
    rejected: alerts.filter((a) => a.status === "rejected").length,
    escalated: alerts.filter((a) => a.status === "escalated").length,
  };

  // Top-1 critical-threat alert for the hero panel
  const topCrit = ranked.find(({ live }) => live >= 0.75)?.alert;
  const engagedCount = alerts.filter((a) => a.status === "engaged").length;

  return (
    <div className="h-full flex flex-col">
      <PageHeader
        icon={AlertTriangle}
        title="Ranked Threat Queue"
        subtitle={
          <>
            {alerts.length} alerts · {counts.pending} pending · {counts.confirmed} confirmed · {counts.rejected} rejected · {counts.escalated} escalated
            {engagedCount > 0 && (<>{" · "}<span className="text-threat-crit">{engagedCount} engaged</span></>)}
            {loading && " · refreshing..."}
          </>
        }
        badge={topCrit ? <StatusPill variant="err" size="sm">CRITICAL · {(topCrit.threat_score * 100).toFixed(0)}%</StatusPill> : null}
        actions={
          <>
            <label className="text-xs text-muted">Mission:</label>
            <select
              className="bg-panel border border-border rounded px-3 py-1.5 text-sm font-mono min-w-[200px]"
              value={selectedId ?? ""}
              onChange={(e) => setSelectedId(Number(e.target.value))}
            >
              {missions.length === 0 && <option>(no missions)</option>}
              {missions.map((m) => (
                <option key={m.id} value={m.id}>
                  #{m.id} · {m.name}
                </option>
              ))}
            </select>
            <label className="text-xs text-muted">Operator:</label>
            <input
              className="bg-panel border border-border rounded px-3 py-1.5 text-sm font-mono w-28"
              value={operatorId}
              onChange={(e) => setOperatorId(e.target.value)}
            />
            <ExportMenu filename={`astra-alerts-mission-${selectedId ?? "all"}`} rows={alerts} />
          </>
        }
      />

      {/* Hero KPI strip */}
      <div className="px-6 pt-4 grid grid-cols-4 gap-3">
        <HeroStat
          label="total alerts"
          value={alerts.length}
          icon={AlertTriangle}
          tone={alerts.length > 0 ? "cyan" : "neutral"}
          sub={`${counts.pending} pending`}
        />
        <HeroStat
          label="critical (≥0.75)"
          value={ranked.filter(({live}) => live >= 0.75).length}
          icon={Flame}
          tone="crit"
          sub="needs attention"
        />
        <HeroStat
          label="escalated"
          value={counts.escalated}
          icon={ArrowUpCircle}
          tone={counts.escalated > 0 ? "high" : "neutral"}
          sub="awaiting 2nd op"
        />
        <HeroStat
          label="engaged"
          value={engagedCount}
          icon={Crosshair}
          tone={engagedCount > 0 ? "crit" : "neutral"}
          sub="dual-confirmed"
        />
      </div>

      {error && (
        <div className="mx-6 mt-3 bg-threat-crit/20 border border-threat-crit/40 text-threat-crit p-2 rounded text-xs">
          {error}
        </div>
      )}

      {/* Threat waveform strip — drama-bar showing the queue as audio-style bars */}
      <div className="px-6 pt-3">
        <div
          className="glass-strong rounded-md px-3 py-2 flex items-center gap-3"
          title="Threat-frequency waveform — one bar per alert, height ∝ threat score (0-1), color by severity. Newest alerts on the right. Lets the operator spot rising threat trends at a glance."
        >
          <span className="text-2xs uppercase-wide text-muted2 font-mono tracking-wider shrink-0">
            THREAT&nbsp;FREQ
          </span>
          <div className="flex-1 min-w-0">
            <ThreatWaveform scores={ranked.map((r) => r.live).slice(0, 80)} height={42} />
          </div>
          <span className="text-2xs uppercase-wide text-muted2 font-mono tracking-wider shrink-0 tabular-nums">
            {ranked.length} pts · max {ranked[0] ? (ranked[0].live * 100).toFixed(0) : "—"}%
          </span>
        </div>
      </div>

      <div className="flex-1 p-6 pt-3 grid grid-cols-[1fr_300px] gap-6 overflow-hidden">
        <div className="glass rounded-lg overflow-auto shadow-panel">
          <table className="w-full text-sm">
            <thead className="bg-panel2 text-muted text-xs uppercase tracking-wider sticky top-0 z-10">
              <tr>
                <th className="text-left px-3 py-3 w-8">#</th>
                <th className="text-left px-3 py-3">Class</th>
                <th className="text-left px-3 py-3">Conf</th>
                <th className="text-left px-3 py-3">Distance</th>
                <th className="text-left px-3 py-3">Nearest</th>
                <th className="text-left px-3 py-3">Live Score</th>
                <th className="text-left px-3 py-3">Orig</th>
                <th className="text-left px-3 py-3">Status</th>
                <th className="text-left px-3 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {ranked.length === 0 && (
                <tr>
                  <td colSpan={9}>
                    <EmptyState
                      icon={Inbox}
                      title="No alerts in queue"
                      body="The threat narrator hasn't flagged anything yet. Upload an image or video on the Mission page to generate detections + threat-scored alerts."
                      cta={{ label: "Go to Mission page", href: "/mission" }}
                    />
                  </td>
                </tr>
              )}
              {ranked.map(({ alert: a, live }, i) => {
                const det = detMap.get(a.detection_id);
                const clsName = det?.class_name ?? "?";
                const clsColor = CLASS_COLORS[clsName] ?? "#ff7a1a";
                const dist = a.score_breakdown.distance_km;
                const nearest = a.score_breakdown.nearest_asset;
                const isBusy = busyId === a.id;
                return (
                  <Fragment key={a.id}>
                  <tr
                    className="border-t border-border hover:bg-panel2 transition-colors"
                  >
                    <td className="px-3 py-2 font-mono text-muted" rowSpan={a.narrative ? 2 : 1}>{i + 1}</td>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-2 font-mono text-xs">
                        <span
                          className="w-2 h-2 rounded-full flex-shrink-0"
                          style={{ background: clsColor }}
                        />
                        {clsName}
                      </div>
                    </td>
                    <td className="px-3 py-2 font-mono text-xs">
                      {det ? det.confidence.toFixed(2) : "—"}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs">
                      {dist != null ? `${dist.toFixed(2)} km` : "—"}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-muted">{nearest ?? "—"}</td>
                    <td
                      className={`px-3 py-2 font-mono font-semibold text-base ${threatColor(live)}`}
                    >
                      {live.toFixed(3)}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-muted">
                      {a.threat_score.toFixed(3)}
                    </td>
                    <td className="px-3 py-2 text-[11px] uppercase font-mono">
                      {a.status === "pending" && <span className="text-muted">pending</span>}
                      {a.status === "confirmed" && <span className="text-threat-low">confirmed</span>}
                      {a.status === "rejected" && <span className="text-threat-crit">rejected</span>}
                      {a.status === "escalated" && (
                        <div className="flex flex-col">
                          <span className="text-threat-high">escalated</span>
                          {a.confirmations && a.confirmations.length > 0 && (
                            <span className="text-[9px] text-threat-high/70 normal-case mt-0.5">
                              {a.confirmations.length}/2 confirms
                            </span>
                          )}
                        </div>
                      )}
                      {a.status === "engaged" && (
                        <div className="flex items-center gap-1 text-threat-crit">
                          <Crosshair size={11} /> engaged
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      {a.status === "pending" && (
                        <div className="flex items-center gap-1">
                          <button
                            disabled={isBusy}
                            onClick={() => act(a.id, "confirm")}
                            className="p-1 rounded bg-threat-low/20 text-threat-low hover:bg-threat-low/30 disabled:opacity-30"
                            title="Confirm"
                          >
                            {isBusy ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />}
                          </button>
                          <button
                            disabled={isBusy}
                            onClick={() => act(a.id, "reject")}
                            className="p-1 rounded bg-threat-crit/20 text-threat-crit hover:bg-threat-crit/30 disabled:opacity-30"
                            title="Reject"
                          >
                            <X size={12} />
                          </button>
                          <button
                            disabled={isBusy}
                            onClick={() => act(a.id, "escalate")}
                            className="p-1 rounded bg-threat-high/20 text-threat-high hover:bg-threat-high/30 disabled:opacity-30"
                            title="Escalate"
                          >
                            <ArrowUpCircle size={12} />
                          </button>
                        </div>
                      )}
                      {a.status === "escalated" && (() => {
                        const alreadyConfirmed = (a.confirmations ?? []).some(
                          (c) => c.operator_id === operatorId,
                        );
                        return (
                          <div className="flex items-center gap-1">
                            <button
                              disabled={isBusy || alreadyConfirmed}
                              onClick={() => act(a.id, "engage")}
                              className={`flex items-center gap-1 px-2 py-1 rounded text-[10px] font-mono uppercase tracking-wider ${
                                alreadyConfirmed
                                  ? "bg-panel2 text-muted cursor-not-allowed"
                                  : "bg-threat-crit/20 text-threat-crit hover:bg-threat-crit/30"
                              }`}
                              title={alreadyConfirmed ? `${operatorId} has already confirmed` : "Confirm engagement (needs 2 distinct operators)"}
                            >
                              {isBusy ? <Loader2 size={10} className="animate-spin" /> : <ShieldCheck size={10} />}
                              {alreadyConfirmed ? "you ✓" : "confirm engage"}
                            </button>
                          </div>
                        );
                      })()}
                      {(a.status === "confirmed" || a.status === "rejected" || a.status === "engaged") && (
                        <span className="text-[11px] text-muted font-mono">
                          {a.operator_id ?? "system"}
                        </span>
                      )}
                    </td>
                  </tr>
                  {a.narrative && (
                    <tr className="hover:bg-panel2 transition-colors">
                      <td colSpan={8} className="px-3 pb-2 pt-0 text-[11px] italic text-accent/80 leading-snug">
                        <span className="text-muted mr-2">⟶</span>
                        {a.narrative}
                      </td>
                    </tr>
                  )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>

        <aside className="glass rounded-lg p-4 space-y-4 overflow-auto shadow-panel">
          <div className="flex items-center justify-between">
            <div className="text-xs text-muted uppercase tracking-wider">Score Weights</div>
            <button
              onClick={resetWeights}
              className="text-xs text-muted hover:text-accent flex items-center gap-1"
            >
              <RefreshCw size={10} /> reset
            </button>
          </div>
          {(Object.keys(DEFAULT_W) as Array<keyof Weights>).map((k) => (
            <div key={k} className="space-y-1">
              <div className="flex justify-between text-xs">
                <span className="text-muted font-mono">{k}</span>
                <span className="font-mono">
                  {weights[k].toFixed(2)}
                  {weights[k] !== DEFAULT_W[k] && (
                    <span className="text-muted ml-1">(def {DEFAULT_W[k].toFixed(2)})</span>
                  )}
                </span>
              </div>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={weights[k]}
                onChange={(e) => setWeights({ ...weights, [k]: Number(e.target.value) })}
                className="w-full accent-accent"
              />
            </div>
          ))}
          <div className="text-[11px] text-muted pt-2 border-t border-border leading-snug">
            Sliders re-rank the queue client-side. The original server-computed score stays
            in the "Orig" column — drag a slider and watch rows reorder live. Weights reset
            on page reload; the backend default is the starting position.
          </div>
        </aside>
      </div>
    </div>
  );
}
