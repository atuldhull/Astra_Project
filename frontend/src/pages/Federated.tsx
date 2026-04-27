import { useEffect, useMemo, useState } from "react";
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid, Legend, ReferenceLine,
} from "recharts";
import { Loader2, RefreshCw, ShieldAlert, ShieldCheck, Network } from "lucide-react";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

// ── Types matching backend/app/api/federated.py response ────────────────
type GlobalPoint = {
  round: number;
  loss?: number;
  accuracy?: number;
  note?: string | null;
};

type ClientPoint = {
  round: number;
  loss?: number;
  accuracy?: number;
  n_examples?: number;
  is_poison?: boolean;
};

type FoolsGoldRow = {
  round: number;
  weights: Record<string, number>;
  diag: Record<string, { max_sim?: number; raw_pardon?: number; weight?: number; flagged?: boolean }>;
};

type FederatedState = {
  available: boolean;
  config: {
    task?: string;
    n_rounds?: number;
    local_epochs?: number;
    lr?: number;
    client_ids?: string[];
    poison_client_id?: string | null;
    n_classes?: number;
    device?: string;
  };
  rounds_completed: number;
  global_curve: GlobalPoint[];
  client_curves: Record<string, ClientPoint[]>;
  foolsgold: FoolsGoldRow[];
  raw_count: number;
};

// Distinct, accessible palette for up to 8 clients. Honest clients get
// cool colours, attackers get red regardless of position.
const HONEST_PALETTE = ["#22d3ee", "#4ade80", "#facc15", "#a78bfa", "#fb923c", "#60a5fa", "#f472b6", "#94a3b8"];
const POISON_COLOR = "#ef4444";

function clientColor(_cid: string, idx: number, isPoison: boolean): string {
  return isPoison ? POISON_COLOR : HONEST_PALETTE[idx % HONEST_PALETTE.length];
}

function Panel({ title, children, sub }: { title: string; sub?: string; children: React.ReactNode }) {
  return (
    <div className="glass rounded-lg p-4 flex flex-col shadow-panel">
      <div className="flex items-baseline justify-between mb-3">
        <div className="text-sm font-semibold">{title}</div>
        {sub && <div className="text-[11px] text-muted">{sub}</div>}
      </div>
      {children}
    </div>
  );
}

export default function Federated() {
  const [state, setState] = useState<FederatedState | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function fetchState() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/federated`);
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      setState(await res.json());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  // Initial fetch + 3s polling so live runs animate as rounds land.
  useEffect(() => {
    fetchState();
    const t = window.setInterval(fetchState, 3000);
    return () => window.clearInterval(t);
  }, []);

  const cfg = state?.config ?? {};
  const allClientIds = useMemo(() => {
    if (!state) return [] as string[];
    const fromCfg = cfg.client_ids ?? [];
    const fromCurves = Object.keys(state.client_curves);
    // Stable order: config order first, then any extras seen in curves
    const out = [...fromCfg];
    for (const c of fromCurves) if (!out.includes(c)) out.push(c);
    return out;
  }, [state, cfg]);

  const isPoisonId = (cid: string) => {
    if (cfg.poison_client_id && cid === cfg.poison_client_id) return true;
    // Also flag any ID starting with "attacker" (run_demo.py convention with
    // multiple Sybils — only the first is captured in poison_client_id).
    return cid.toLowerCase().startsWith("attacker");
  };

  // Reshape per-client curves into one row per round for grouped charts.
  const perRoundClientAcc = useMemo(() => {
    if (!state) return [] as any[];
    const rounds = new Set<number>();
    for (const arr of Object.values(state.client_curves)) {
      for (const p of arr) if (p.round != null) rounds.add(p.round);
    }
    return [...rounds].sort((a, b) => a - b).map((r) => {
      const row: any = { round: r };
      for (const cid of allClientIds) {
        const p = state.client_curves[cid]?.find((x) => x.round === r);
        if (p) row[cid] = p.accuracy;
      }
      return row;
    });
  }, [state, allClientIds]);

  // Reshape FoolsGold weights into per-round rows for the stacked bar.
  const perRoundWeights = useMemo(() => {
    if (!state) return [] as any[];
    return state.foolsgold.map((fg) => ({ round: fg.round, ...fg.weights }));
  }, [state]);

  const lastFg = state?.foolsgold?.[state.foolsgold.length - 1];
  const flaggedClients = useMemo(() => {
    if (!lastFg) return [] as string[];
    return Object.entries(lastFg.diag)
      .filter(([, d]) => d.flagged)
      .map(([c]) => c);
  }, [lastFg]);

  const bestGlobal = useMemo(() => {
    if (!state || state.global_curve.length === 0) return null;
    return state.global_curve.reduce(
      (best, p) => (p.accuracy != null && p.accuracy > (best?.accuracy ?? -1) ? p : best),
      null as GlobalPoint | null,
    );
  }, [state]);

  return (
    <div className="h-full flex flex-col">
      <header className="px-6 py-4 border-b border-border flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold flex items-center gap-2">
            <Network size={18} className="text-accent" />
            Federated Learning
            {state?.available && cfg.task && (
              <span className="text-[10px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded bg-panel2 text-muted border border-border">
                {cfg.task}
              </span>
            )}
          </h1>
          <p className="text-xs text-muted">
            {state?.available
              ? `${state.rounds_completed} of ${cfg.n_rounds ?? "?"} rounds · ${allClientIds.length} clients · device: ${cfg.device ?? "?"}`
              : "No federated run found. Start one with `python -m federated.run_demo --task synthetic --rounds 5 --inject-poison`"}
            {loading && " · refreshing..."}
          </p>
        </div>
        <button
          onClick={fetchState}
          className="p-1.5 rounded hover:bg-panel2 text-muted"
          title="Refresh"
        >
          {loading ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
        </button>
      </header>

      {error && (
        <div className="mx-6 mt-3 bg-threat-crit/20 border border-threat-crit/40 text-threat-crit p-2 rounded text-xs">
          {error}
        </div>
      )}

      {state?.available ? (
        <div className="flex-1 p-6 grid grid-cols-2 gap-6 overflow-auto">
          {/* PANEL 1: Global accuracy curve */}
          <Panel
            title="Global model accuracy"
            sub={bestGlobal ? `peak ${(bestGlobal.accuracy! * 100).toFixed(1)}% @ round ${bestGlobal.round}` : undefined}
          >
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={state.global_curve}>
                <CartesianGrid strokeDasharray="3 3" stroke="#23303d" />
                <XAxis dataKey="round" stroke="#8b9aad" fontSize={11} />
                <YAxis stroke="#8b9aad" fontSize={11} domain={[0, 1]} />
                <Tooltip
                  contentStyle={{ background: "#121821", border: "1px solid #23303d", fontSize: 11 }}
                  formatter={(v: any) => (typeof v === "number" ? v.toFixed(3) : v)}
                />
                <Line
                  type="monotone"
                  dataKey="accuracy"
                  stroke="#ff7a1a"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  isAnimationActive={false}
                />
                {flaggedClients.length > 0 && (
                  <ReferenceLine y={0.5} stroke="#23303d" strokeDasharray="2 4" label={{ value: "50%", fill: "#8b9aad", fontSize: 10, position: "right" }} />
                )}
              </LineChart>
            </ResponsiveContainer>
            <div className="mt-2 text-[11px] text-muted leading-snug">
              Loss / accuracy on the held-out val set after each round of FedAvg aggregation.
            </div>
          </Panel>

          {/* PANEL 2: Per-client local-train accuracy */}
          <Panel
            title="Per-client local accuracy"
            sub={`${allClientIds.length} clients`}
          >
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={perRoundClientAcc}>
                <CartesianGrid strokeDasharray="3 3" stroke="#23303d" />
                <XAxis dataKey="round" stroke="#8b9aad" fontSize={11} />
                <YAxis stroke="#8b9aad" fontSize={11} domain={[0, 1]} />
                <Tooltip
                  contentStyle={{ background: "#121821", border: "1px solid #23303d", fontSize: 11 }}
                  formatter={(v: any) => (typeof v === "number" ? v.toFixed(3) : v)}
                />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                {allClientIds.map((cid, i) => (
                  <Line
                    key={cid}
                    type="monotone"
                    dataKey={cid}
                    stroke={clientColor(cid, i, isPoisonId(cid))}
                    strokeWidth={isPoisonId(cid) ? 2.5 : 1.5}
                    strokeDasharray={isPoisonId(cid) ? "4 2" : undefined}
                    dot={{ r: 2 }}
                    isAnimationActive={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
            <div className="mt-2 text-[11px] text-muted leading-snug">
              Each client's local-train accuracy. Sybil/attacker clients are dashed red.
            </div>
          </Panel>

          {/* PANEL 3: FoolsGold weights per round */}
          <Panel
            title="FoolsGold aggregation weights"
            sub="cosine-sim Sybil reweighting"
          >
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={perRoundWeights}>
                <CartesianGrid strokeDasharray="3 3" stroke="#23303d" />
                <XAxis dataKey="round" stroke="#8b9aad" fontSize={11} />
                <YAxis stroke="#8b9aad" fontSize={11} domain={[0, 1]} />
                <Tooltip
                  contentStyle={{ background: "#121821", border: "1px solid #23303d", fontSize: 11 }}
                  formatter={(v: any) => (typeof v === "number" ? v.toFixed(3) : v)}
                />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                {allClientIds.map((cid, i) => (
                  <Bar
                    key={cid}
                    dataKey={cid}
                    stackId="w"
                    fill={clientColor(cid, i, isPoisonId(cid))}
                    isAnimationActive={false}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
            <div className="mt-2 text-[11px] text-muted leading-snug">
              Stacked weight per round. Sybils fall to ~0 once history accumulates enough cosine signal.
            </div>
          </Panel>

          {/* PANEL 4: Quarantine status + run config */}
          <Panel
            title="Quarantine status"
            sub={lastFg ? `round ${lastFg.round}` : undefined}
          >
            <div className="space-y-2">
              {allClientIds.length === 0 && (
                <div className="text-xs text-muted">No clients reported yet.</div>
              )}
              {allClientIds.map((cid, i) => {
                const d = lastFg?.diag?.[cid];
                const w = lastFg?.weights?.[cid];
                const flagged = !!d?.flagged;
                const colour = clientColor(cid, i, isPoisonId(cid));
                return (
                  <div
                    key={cid}
                    className={`flex items-center justify-between bg-panel2 rounded px-3 py-2 border ${flagged ? "border-threat-crit/50" : "border-border"}`}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span
                        className="w-2.5 h-2.5 rounded-full shrink-0"
                        style={{ background: colour }}
                      />
                      <span className="font-mono text-sm truncate">{cid}</span>
                      {isPoisonId(cid) && (
                        <span className="text-[10px] uppercase tracking-wider bg-threat-crit/20 text-threat-crit px-1.5 py-0.5 rounded border border-threat-crit/40">
                          attacker
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-3 text-xs font-mono">
                      <span className="text-muted">w={w != null ? w.toFixed(3) : "—"}</span>
                      <span className="text-muted">sim={d?.max_sim != null ? d.max_sim.toFixed(2) : "—"}</span>
                      {flagged ? (
                        <span className="flex items-center gap-1 text-threat-crit">
                          <ShieldAlert size={12} /> quarantined
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-threat-low">
                          <ShieldCheck size={12} /> trusted
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="mt-4 pt-3 border-t border-border text-[11px] text-muted leading-relaxed">
              <div className="uppercase tracking-wider mb-1">Run config</div>
              <div className="font-mono">
                task: <span className="text-text">{cfg.task ?? "—"}</span> ·
                rounds: <span className="text-text">{cfg.n_rounds ?? "—"}</span> ·
                local epochs: <span className="text-text">{cfg.local_epochs ?? "—"}</span> ·
                lr: <span className="text-text">{cfg.lr ?? "—"}</span>
              </div>
              <div className="font-mono mt-1">
                classes: <span className="text-text">{cfg.n_classes ?? "—"}</span> ·
                device: <span className="text-text">{cfg.device ?? "—"}</span>
              </div>
            </div>
          </Panel>
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center text-center">
          <div>
            <Network size={56} className="mx-auto mb-4 text-muted opacity-30" />
            <p className="text-sm text-muted mb-2">No federated run on disk yet.</p>
            <p className="text-xs text-muted">
              Start one with:
            </p>
            <pre className="bg-panel border border-border rounded px-3 py-2 mt-2 inline-block font-mono text-xs text-accent text-left">
              python -m federated.run_demo --task synthetic --rounds 5 --inject-poison
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
