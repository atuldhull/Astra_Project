/**
 * Counter-Drone Sentinel (D3.3) — synthetic swarm + IFF + signed c2.
 *
 * Self-contained simulation. Honest framing visible at the top: no real
 * RF emission, no real kinetics. The Ed25519 IFF + the latency-stamped
 * c2 ack channel ARE real and reusable in production.
 *
 * Layout:
 *   PageHeader + 4 hero stats
 *   honest-disclosure banner
 *   left  flex-2 : Leaflet map with drones + trails
 *   right w-96   : decision matrix table (TTT-sorted)
 *   bottom bar   : scenario picker + start/stop + signed-c2 strip
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Polyline, Popup, Marker, Tooltip } from "react-leaflet";
import L from "leaflet";
import {
  Crosshair, Play, Square, ShieldCheck, ShieldAlert, Loader2,
  AlertTriangle, Zap, X, Plane,
} from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { HeroStat } from "../components/HeroStat";
import { Bezel } from "../components/Bezel";
import { StatusPill } from "../components/StatusPill";
import { EmptyState } from "../components/EmptyState";
import { toast } from "../components/Toast";
import {
  api, openC2Socket,
  type SentinelDrone, type SentinelTick, type SentinelAck,
} from "../lib/api";

// ── Constants ────────────────────────────────────────────────────────

const ANCHOR: [number, number] = [12.9716, 77.5946];
const OPERATOR_ID = "sentinel-op";  // would come from auth in production

const COLOR_FRIENDLY = "#4ade80";   // threat-low
const COLOR_FOE = "#ef4444";        // threat-crit
const COLOR_UNVERIFIED = "#94a3b8"; // muted
const COLOR_GHOST = "#475569";

// Latency tone for HeroStat (low/med/high/crit/neutral palette).
function latencyHeroTone(ms: number | null | undefined): "low" | "med" | "high" | "crit" | "neutral" {
  if (ms == null) return "neutral";
  if (ms < 50) return "low";
  if (ms < 200) return "high";
  return "crit";
}

// Toast severity matching the latency bucket.
function latencySeverity(ms: number): "success" | "warn" | "crit" {
  if (ms < 50) return "success";
  if (ms < 200) return "warn";
  return "crit";
}

// Tailwind text-class for inline latency badges in the acks tail.
function latencyTextClass(ms: number): string {
  if (ms < 50) return "text-threat-low";
  if (ms < 200) return "text-threat-high";
  return "text-threat-crit";
}

// ── Component ────────────────────────────────────────────────────────

type EngageTarget = { drone: SentinelDrone; action: "soft_kill" | "hard_kill" } | null;
type VerifyState = { state: "idle" | "loading" | "ok" | "fail"; reason?: string };

export default function CounterDrone() {
  const [scenarios, setScenarios] = useState<Array<{ id: string; label: string; description: string; n_drones: number; n_friendlies: number }>>([]);
  const [selectedScenario, setSelectedScenario] = useState<string>("swarm-loiter");
  const [running, setRunning] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);
  const [drones, setDrones] = useState<Map<string, SentinelDrone>>(new Map());
  const [verifyMap, setVerifyMap] = useState<Record<string, VerifyState>>({});
  const [engageTarget, setEngageTarget] = useState<EngageTarget>(null);
  const [busyEngage, setBusyEngage] = useState(false);
  const [acks, setAcks] = useState<SentinelAck[]>([]);
  const [nSigned, setNSigned] = useState(0);
  const [latencyP50, setLatencyP50] = useState<number | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // Initial fetch — scenarios + status
  useEffect(() => {
    api.sentinelScenarios().then((r) => setScenarios(r.scenarios)).catch(() => {});
    api.sentinelStatus().then((s) => {
      setRunning(s.running);
      if (s.running && s.run_id) setRunId(s.run_id);
      if (s.scenario) setSelectedScenario(s.scenario);
      if (s.n_commands_signed) setNSigned(s.n_commands_signed);
      if (s.latency_p50_ms != null) setLatencyP50(s.latency_p50_ms);
    }).catch(() => {});
  }, []);

  // WS connection — auto-reconnect on close
  useEffect(() => {
    let stopped = false;
    let backoff = 800;
    const connect = () => {
      const ws = openC2Socket((msg) => {
        const m = msg as SentinelTick | SentinelAck;
        if (m.type === "sentinel_tick") {
          const next = new Map<string, SentinelDrone>();
          for (const d of m.drones) next.set(d.id, d);
          setDrones(next);
          setRunId(m.run_id);
          setRunning(true);
        } else if (m.type === "sentinel_ack") {
          setAcks((a) => [m, ...a].slice(0, 12));
        }
      });
      wsRef.current = ws;
      ws.onopen = () => { backoff = 800; };
      ws.onclose = () => {
        if (stopped) return;
        window.setTimeout(connect, backoff);
        backoff = Math.min(backoff * 1.5, 5000);
      };
      ws.onerror = () => { /* close handler reconnects */ };
    };
    connect();
    return () => {
      stopped = true;
      try { wsRef.current?.close(); } catch { /* noop */ }
    };
  }, []);

  // Periodically poll status for the signed-c2 strip + p50 latency.
  useEffect(() => {
    const tick = async () => {
      try {
        const s = await api.sentinelStatus();
        setRunning(s.running);
        if (s.n_commands_signed != null) setNSigned(s.n_commands_signed);
        if (s.latency_p50_ms != null) setLatencyP50(s.latency_p50_ms);
        else setLatencyP50(null);
      } catch { /* noop */ }
    };
    tick();
    const handle = window.setInterval(tick, 4000);
    return () => window.clearInterval(handle);
  }, []);

  // Derived
  const droneList = useMemo(() => Array.from(drones.values()), [drones]);
  const foes = useMemo(() => droneList.filter((d) => d.role === "foe" && d.state === "active"), [droneList]);
  const friendlies = useMemo(() => droneList.filter((d) => d.role === "friendly"), [droneList]);
  const killed = useMemo(() => droneList.filter((d) => d.state === "destroyed").length, [droneList]);
  const sortedFoes = useMemo(() => {
    return [...foes].sort((a, b) => (a.ttt_s ?? 1e9) - (b.ttt_s ?? 1e9));
  }, [foes]);

  // ── Actions ──────────────────────────────────────────────────────
  async function startScenario(id?: string) {
    const sc = id ?? selectedScenario;
    try {
      const r = await api.sentinelStart({ scenario: sc });
      setRunning(true);
      setRunId(r.run_id);
      toast.success("Scenario started", `${r.scenario} · ${r.n_drones} drones · ${r.n_friendlies} friendly`);
    } catch (e) {
      toast.crit("Start failed", (e as Error).message);
    }
  }

  async function stopScenario() {
    try {
      await api.sentinelStop();
      setRunning(false);
      setRunId(null);
      setDrones(new Map());
      toast.info("Scenario stopped", "");
    } catch (e) {
      toast.crit("Stop failed", (e as Error).message);
    }
  }

  async function verifyDrone(drone_id: string) {
    setVerifyMap((m) => ({ ...m, [drone_id]: { state: "loading" } }));
    try {
      const r = await api.sentinelVerify(drone_id);
      if (r.ok) {
        setVerifyMap((m) => ({ ...m, [drone_id]: { state: "ok" } }));
      } else {
        setVerifyMap((m) => ({ ...m, [drone_id]: { state: "fail", reason: r.reason } }));
      }
    } catch (e) {
      setVerifyMap((m) => ({ ...m, [drone_id]: { state: "fail", reason: (e as Error).message } }));
    }
  }

  async function confirmEngage() {
    if (!engageTarget) return;
    setBusyEngage(true);
    try {
      const r = await api.sentinelEngage({
        drone_id: engageTarget.drone.id,
        action: engageTarget.action,
        operator_id: OPERATOR_ID,
      });
      const sev = latencySeverity(r.latency_ms);
      toast[sev](
        `${r.action.toUpperCase()} · ${r.drone_id}`,
        `latency ${r.latency_ms}ms · state → ${r.new_state}`,
      );
      setEngageTarget(null);
    } catch (e) {
      toast.crit("Engage failed", (e as Error).message);
    } finally {
      setBusyEngage(false);
    }
  }

  // ── Render ───────────────────────────────────────────────────────
  return (
    <div className="h-full flex flex-col">
      <PageHeader
        icon={Crosshair}
        title="Counter-Drone Sentinel"
        badge={
          running
            ? <StatusPill variant="live" size="sm">RUN {runId ?? "—"}</StatusPill>
            : <StatusPill variant="neutral" size="sm">idle</StatusPill>
        }
        subtitle="Simulation environment · production integration via TAK-server / RF link is on the R4 roadmap"
      />

      {/* Honest-disclosure banner */}
      <div className="mx-6 mt-3 px-4 py-2.5 rounded-lg border border-amber-400/40 bg-amber-400/10 text-amber-300 font-mono text-xs flex items-center gap-3">
        <AlertTriangle size={14} />
        <span className="font-semibold uppercase-wide tracking-wider text-[11px]">SIMULATION ENVIRONMENT</span>
        <span className="opacity-80">No real RF emission. No real kinetics. <span className="text-amber-200">Cryptographic IFF and signed c2 channel are real and reusable.</span></span>
      </div>

      {/* Hero strip */}
      <div className="px-6 pt-3 grid grid-cols-4 gap-3">
        <HeroStat label="active drones" value={droneList.filter((d) => d.state === "active").length} icon={Plane} tone="cyan" sub={`${friendlies.length} friendly · ${foes.length} foe`} />
        <HeroStat label="foes detected" value={foes.length} icon={AlertTriangle} tone={foes.length > 0 ? "high" : "neutral"} sub="active threats" />
        <HeroStat label="kills authorized" value={killed} icon={Crosshair} tone={killed > 0 ? "low" : "neutral"} sub={`${nSigned} signed cmds`} />
        <HeroStat label="c2 latency p50" value={latencyP50 ?? 0} unit="ms" decimals={1} icon={Zap} tone={latencyHeroTone(latencyP50)} sub="cmd → ack" ticker={latencyP50 != null} />
      </div>

      {/* Main grid: map + decision matrix */}
      <div className="flex-1 px-6 pt-3 pb-3 grid grid-cols-[1fr_24rem] gap-4 overflow-hidden">
        <Bezel
          className="relative"
          topBar={
            <>
              <span className="text-accent">SENTINEL</span>
              <span className="text-muted2">SCENARIO</span>
              <span className="tabular-nums text-text">{running ? selectedScenario : "—"}</span>
              <span className="text-muted2">RUN</span>
              <span className="tabular-nums text-text">{runId ?? "—"}</span>
              <span className="ml-auto text-muted2 tabular-nums">{droneList.length} contacts</span>
            </>
          }
          bottomBar={
            <>
              <span className="text-muted2">FOES</span>
              <span className="tabular-nums text-text">{foes.length}</span>
              <span className="text-muted2">KILLED</span>
              <span className="tabular-nums text-text">{killed}</span>
              <span className="ml-auto text-muted2">5 Hz · ws://c2</span>
            </>
          }
        >
          <div className="w-full h-full">
            {droneList.length === 0 ? (
              <div className="absolute inset-0 flex items-center justify-center">
                <EmptyState
                  icon={Crosshair}
                  title="No active scenario"
                  body="Pick a scenario at the bottom of the page and click Start. The c2 channel is already signing every command — verifiable on the right rail."
                />
              </div>
            ) : (
              <MapContainer
                center={ANCHOR}
                zoom={14}
                style={{ height: "100%", width: "100%" }}
                preferCanvas
              >
                <TileLayer
                  attribution="&copy; OpenStreetMap"
                  url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
                />
                {droneList.map((d) => {
                  const verify = verifyMap[d.id];
                  const baseColor = d.role === "friendly" ? COLOR_FRIENDLY :
                    verify?.state === "fail" ? COLOR_FOE :
                    d.role === "foe" ? COLOR_FOE : COLOR_UNVERIFIED;
                  const isLost = d.state === "signal_lost";
                  const isDestroyed = d.state === "destroyed";
                  const fillOpacity = isDestroyed ? 0.0 : isLost ? 0.15 : 0.65;
                  const radius = d.role === "friendly" ? 7 : 8;
                  const dashArray = (d.role === "foe" && verify?.state !== "fail") ? "3,3" : undefined;
                  return (
                    <div key={d.id}>
                      {d.trail.length > 1 && !isDestroyed && (
                        <Polyline
                          positions={d.trail.map((p) => [p[0], p[1]] as [number, number])}
                          pathOptions={{
                            color: baseColor,
                            weight: 1.5,
                            opacity: 0.25,
                          }}
                        />
                      )}
                      {!isDestroyed ? (
                        <CircleMarker
                          center={[d.lat, d.lon]}
                          radius={radius}
                          pathOptions={{
                            color: isLost ? COLOR_GHOST : baseColor,
                            weight: 2,
                            fillColor: isLost ? COLOR_GHOST : baseColor,
                            fillOpacity,
                            dashArray,
                          }}
                          eventHandlers={{ click: () => { /* selection handled via popup */ } }}
                        >
                          <Tooltip direction="top" offset={[0, -8]} opacity={0.9}>
                            <span style={{ fontFamily: "ui-monospace, monospace" }}>
                              {d.id} · {d.role}{d.ttt_s != null ? ` · TTT ${d.ttt_s.toFixed(1)}s` : ""}
                            </span>
                          </Tooltip>
                          <Popup>
                            <div className="text-xs font-mono">
                              <div><b>{d.id}</b> · {d.role}</div>
                              <div>state: {d.state}</div>
                              <div>speed: {d.speed_mps.toFixed(1)} m/s</div>
                              {d.range_km != null && <div>range: {d.range_km.toFixed(2)} km → {d.nearest_asset}</div>}
                              {d.ttt_s != null && <div>TTT: {d.ttt_s.toFixed(1)} s</div>}
                              {d.category && <div>category: <b>{d.category}</b></div>}
                            </div>
                          </Popup>
                        </CircleMarker>
                      ) : (
                        <Marker
                          position={[d.lat, d.lon]}
                          icon={L.divIcon({
                            className: "",
                            html: `<div style="color:${COLOR_FOE};font-size:18px;font-weight:bold;line-height:1;text-shadow:0 0 4px rgba(0,0,0,0.6);">×</div>`,
                            iconSize: [18, 18],
                            iconAnchor: [9, 9],
                          })}
                        >
                          <Tooltip direction="top" offset={[0, -8]}>{d.id} · destroyed</Tooltip>
                        </Marker>
                      )}
                    </div>
                  );
                })}
              </MapContainer>
            )}
          </div>
        </Bezel>

        {/* Decision matrix */}
        <aside className="glass rounded-lg shadow-panel flex flex-col overflow-hidden">
          <div className="px-3 py-2 border-b border-border flex items-center justify-between">
            <div>
              <div className="text-2xs uppercase-wide tracking-wider text-muted2 font-mono">DECISION MATRIX</div>
              <div className="text-[10px] text-muted font-mono mt-0.5">sorted by time-to-target</div>
            </div>
            <span className="text-2xs font-mono tabular-nums text-accent">{sortedFoes.length}</span>
          </div>
          <div className="flex-1 overflow-auto">
            {!running ? (
              <div className="px-3 py-4 text-2xs text-muted2">No active scenario.</div>
            ) : sortedFoes.length === 0 ? (
              <div className="px-3 py-4 text-2xs text-muted2">No foes within range.</div>
            ) : (
              <table className="w-full text-2xs font-mono">
                <thead className="text-muted2 uppercase-wide tracking-wider">
                  <tr className="border-b border-border">
                    <th className="text-left px-2 py-1.5">id</th>
                    <th className="text-right px-2 py-1.5">range</th>
                    <th className="text-right px-2 py-1.5">ttt</th>
                    <th className="text-left px-2 py-1.5">cat</th>
                    <th className="text-right px-2 py-1.5">sig</th>
                    <th className="text-right px-2 py-1.5">action</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedFoes.map((d) => {
                    const v = verifyMap[d.id] ?? { state: "idle" as const };
                    const catTone = d.category === "hard_kill" ? "text-threat-crit" :
                      d.category === "soft_kill" ? "text-threat-high" :
                      "text-muted";
                    return (
                      <tr key={d.id} className="border-b border-border/60 hover:bg-panel2/60">
                        <td className="px-2 py-1.5 text-text">{d.id}</td>
                        <td className="px-2 py-1.5 text-right tabular-nums">{d.range_km?.toFixed(2) ?? "—"}</td>
                        <td className="px-2 py-1.5 text-right tabular-nums">{d.ttt_s?.toFixed(1) ?? "—"}</td>
                        <td className={`px-2 py-1.5 ${catTone}`}>{d.category ?? "—"}</td>
                        <td className="px-2 py-1.5 text-right tabular-nums text-muted">{(d.signal * 100).toFixed(0)}</td>
                        <td className="px-2 py-1.5">
                          <div className="flex items-center justify-end gap-1">
                            <button
                              onClick={() => verifyDrone(d.id)}
                              disabled={v.state === "loading"}
                              className={`px-1.5 py-0.5 rounded border text-[10px] uppercase-wide tracking-wider transition-fast ${
                                v.state === "ok" ? "border-threat-low/40 bg-threat-low/10 text-threat-low" :
                                v.state === "fail" ? "border-threat-crit/40 bg-threat-crit/10 text-threat-crit" :
                                "border-border text-muted hover:text-text hover:bg-panel2"
                              }`}
                              title={v.state === "fail" ? `IFF fail: ${v.reason}` : v.state === "ok" ? "IFF ok" : "Run Ed25519 verify"}
                            >
                              {v.state === "loading" ? <Loader2 size={9} className="animate-spin" /> :
                                v.state === "ok" ? <ShieldCheck size={9} /> :
                                v.state === "fail" ? <ShieldAlert size={9} /> :
                                "vrfy"}
                            </button>
                            <button
                              onClick={() => setEngageTarget({ drone: d, action: "soft_kill" })}
                              className="px-1.5 py-0.5 rounded border border-threat-high/40 bg-threat-high/10 text-threat-high text-[10px] uppercase-wide tracking-wider hover:bg-threat-high/20 transition-fast"
                              title="Soft-kill (signal jam)"
                            >
                              soft
                            </button>
                            <button
                              onClick={() => setEngageTarget({ drone: d, action: "hard_kill" })}
                              className="px-1.5 py-0.5 rounded border border-threat-crit/40 bg-threat-crit/10 text-threat-crit text-[10px] uppercase-wide tracking-wider hover:bg-threat-crit/20 transition-fast"
                              title="Hard-kill (kinetic)"
                            >
                              hard
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
          {/* Recent acks tail */}
          <div className="border-t border-border px-3 py-2 max-h-32 overflow-auto">
            <div className="text-2xs uppercase-wide tracking-wider text-muted2 font-mono mb-1">RECENT ACKS</div>
            {acks.length === 0 ? (
              <div className="text-2xs text-muted2">none</div>
            ) : acks.slice(0, 5).map((a, i) => (
              <div key={i} className="flex justify-between text-2xs font-mono">
                <span className="text-muted truncate">{a.drone_id} · {a.action}</span>
                <span className={latencyTextClass(a.latency_ms)}>
                  {a.latency_ms.toFixed(1)}ms
                </span>
              </div>
            ))}
          </div>
        </aside>
      </div>

      {/* Bottom bar: scenario picker + start/stop + signed-c2 strip */}
      <div className="px-6 pb-4 flex items-end gap-4">
        <div className="flex-1 min-w-0">
          <Bezel
            topBar={<>
              <span className="text-accent">C2</span>
              <span className="text-muted2">CHANNEL</span>
              <span className="text-text">Ed25519-signed</span>
              <span className="ml-auto text-muted2">commands sent</span>
              <span className="tabular-nums text-text">{nSigned}</span>
              <span className="text-muted2">all verified ✓</span>
            </>}
          >
            <div className="px-4 py-3 text-xs text-muted">
              Every <code className="text-text">/sentinel/engage</code> request is signed with the same Ed25519
              key that signs detections (T1.1) and stamps server-side latency_ms on the
              <code className="text-text"> sentinel_ack</code> WebSocket event. The audit chain captures
              chain-of-custody as <code className="text-text">weights_changed</code> rows tagged
              <code className="text-text"> sentinel.engage</code>.
            </div>
          </Bezel>
        </div>
        <div className="flex flex-col gap-2 shrink-0">
          <select
            value={selectedScenario}
            onChange={(e) => setSelectedScenario(e.target.value)}
            className="bg-panel border border-border rounded px-2 py-1.5 text-xs font-mono min-w-[180px]"
          >
            {scenarios.map((s) => (
              <option key={s.id} value={s.id}>{s.label}</option>
            ))}
          </select>
          <div className="flex gap-2">
            <button
              onClick={() => startScenario()}
              className="flex-1 flex items-center justify-center gap-1 bg-accent text-bg px-3 py-1.5 rounded text-xs font-medium hover:brightness-110 transition-fast"
            >
              <Play size={12} /> start
            </button>
            <button
              onClick={stopScenario}
              disabled={!running}
              className="flex-1 flex items-center justify-center gap-1 glass border border-amber-400/40 text-amber-300 px-3 py-1.5 rounded text-xs font-medium hover:bg-amber-400/10 disabled:opacity-40 disabled:cursor-not-allowed transition-fast"
            >
              <Square size={12} /> stop
            </button>
          </div>
        </div>
      </div>

      {/* Engage confirmation modal */}
      {engageTarget && (
        <div
          className="fixed inset-0 z-[10001] bg-bg/70 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => !busyEngage && setEngageTarget(null)}
        >
          <div
            className="glass-strong border border-border rounded-lg max-w-md w-full p-5 space-y-4 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="font-mono text-2xs uppercase-wide tracking-wider text-muted2">
                  CONFIRM {engageTarget.action.toUpperCase().replace("_", " ")}
                </div>
                <div className="text-base font-semibold text-text mt-0.5">
                  {engageTarget.drone.id}
                </div>
              </div>
              <button
                onClick={() => !busyEngage && setEngageTarget(null)}
                className="text-muted hover:text-text -m-1 p-1.5 rounded"
                aria-label="Cancel"
              >
                <X size={16} />
              </button>
            </div>
            <div className="bg-bg/60 border border-border rounded p-3 font-mono text-2xs space-y-1">
              <div className="flex justify-between"><span className="text-muted2">role</span><span>{engageTarget.drone.role}</span></div>
              <div className="flex justify-between"><span className="text-muted2">range</span><span>{engageTarget.drone.range_km?.toFixed(2)} km</span></div>
              <div className="flex justify-between"><span className="text-muted2">ttt</span><span>{engageTarget.drone.ttt_s?.toFixed(1)} s</span></div>
              <div className="flex justify-between"><span className="text-muted2">nearest asset</span><span>{engageTarget.drone.nearest_asset ?? "—"}</span></div>
              <div className="flex justify-between"><span className="text-muted2">expected latency</span><span className="text-threat-low">&lt; 50 ms</span></div>
            </div>
            <div className="text-xs text-muted leading-snug">
              Command will be Ed25519-signed and broadcast on the c2 channel. The simulation responds within milliseconds; in production this would emit
              {engageTarget.action === "soft_kill" ? " an RF jamming pulse" : " a kinetic interception command"}.
            </div>
            <div className="flex items-center justify-end gap-2">
              <button
                onClick={() => setEngageTarget(null)}
                disabled={busyEngage}
                className="px-3 py-1.5 rounded text-sm text-muted hover:text-text disabled:opacity-50"
              >
                cancel
              </button>
              <button
                onClick={confirmEngage}
                disabled={busyEngage}
                className={`flex items-center gap-2 px-3 py-1.5 rounded text-sm font-medium transition-fast ${
                  engageTarget.action === "hard_kill"
                    ? "bg-threat-crit/20 border border-threat-crit/40 text-threat-crit hover:bg-threat-crit/30"
                    : "bg-threat-high/20 border border-threat-high/40 text-threat-high hover:bg-threat-high/30"
                } disabled:opacity-50`}
              >
                {busyEngage ? <Loader2 size={13} className="animate-spin" /> : <Crosshair size={13} />}
                confirm {engageTarget.action.replace("_", " ")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
