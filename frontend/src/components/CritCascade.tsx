/**
 * CritCascade — layered visual signal for ≥0.75 threat detections.
 *
 * Subscribes to /ws/live for the lifetime of the app. When a detection
 * with threat_score >= 0.75 arrives:
 *
 *   1. <CritSweep/> — a full-width red sweep bar pulses across the top
 *      of the screen for ~1.6s, then fades. Idempotent: each unique
 *      alert_id triggers the sweep at most once per session.
 *   2. <CritUnackBadge/> — surfaced next to the sidebar's "Threats"
 *      label, shows the count of unacknowledged crit alerts.
 *      Acknowledge by visiting /alerts (an "ack everything visible"
 *      side-effect baked into useCritAck).
 *   3. Toast "CRIT" with mission + threat score, sticky (Toast.tsx
 *      keeps crit until the user dismisses).
 *   4. (Optional, opt-in) ASTRA_CRIT_SOUND env flag enables a short
 *      synthetic beep via AudioContext — default OFF for expo halls.
 *
 * No DB, no backend changes. Pure subscriber pattern.
 */
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertOctagon } from "lucide-react";
import { openLiveSocket } from "../lib/api";
import { toast } from "./Toast";

type CritEvent = {
  alert_id: number | null;
  detection_id: number;
  mission_id: number;
  class_name: string;
  threat_score: number;
  at: number;        // unix ms
};

// alert action feed (op-2 sees op-1's confirm in real time).
export type AlertAction = {
  alert_id: number;
  mission_id: number;
  action: string;          // "engage" | "engage_partial" | "confirm" | "reject" | "reclassify" | "escalate"
  operator_id: string;
  status: string;          // alert.status after this action
  confirmations?: string[];
  needed?: number;
  at: number;              // unix ms (client-side stamp for freshness)
};

type State = {
  // Most recent event drives the sweep animation.
  recent: CritEvent | null;
  // Acknowledged ids are dropped from the unack count.
  unack: Map<number, CritEvent>;   // keyed by alert_id (or detection_id when alert_id null)
  seen: Set<number>;                // alert_ids that have already triggered a sweep
  // last action per (alert_id), 4-second freshness window enforced
  // by the readers (no central timer to keep this lock-free).
  actions: Map<number, AlertAction>;
};

const _state: State = {
  recent: null,
  unack: new Map(),
  seen: new Set(),
  actions: new Map(),
};

const ACTION_FRESHNESS_MS = 4000;

const listeners = new Set<(s: State) => void>();
function emit() {
  for (const fn of listeners) fn(_state);
}

const CRIT_THRESHOLD = 0.75;
const SWEEP_DURATION_MS = 1600;
// per-layer cooldown so a 15-crit burst in 3s doesn't seizure
// the UI. Each "recent" assignment honours the cooldown; subsequent
// crits within the window still update unack/seen but don't re-fire
// the cinematic stack.
const CINEMATIC_COOLDOWN_MS = 1200;
let _lastCinematicAt = 0;

function _key(e: { alert_id: number | null; detection_id: number }): number {
  return e.alert_id ?? -e.detection_id; // separate namespaces
}

function _enableSound(): boolean {
  try {
    return localStorage.getItem("astra:critSound") === "1";
  } catch { return false; }
}

function _beep(): void {
  if (!_enableSound()) return;
  try {
    const Ctx = (window as any).AudioContext ?? (window as any).webkitAudioContext;
    if (!Ctx) return;
    const ctx = new Ctx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.value = 880;
    gain.gain.value = 0.08;
    osc.connect(gain).connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.18);
    setTimeout(() => ctx.close(), 400);
  } catch { /* noop */ }
}

export const critCascade = {
  /** Push a fresh crit event into the cascade. */
  push(e: Omit<CritEvent, "at">) {
    const k = _key(e);
    if (_state.seen.has(k)) return;
    _state.seen.add(k);
    const entry: CritEvent = { ...e, at: Date.now() };
    // Always track unack (badge count must reflect every fresh crit) but
    // only re-fire the cinematic layer when out of cooldown.
    _state.unack.set(k, entry);
    const now = Date.now();
    if (now - _lastCinematicAt >= CINEMATIC_COOLDOWN_MS) {
      _state.recent = entry;
      _lastCinematicAt = now;
      emit();
      _beep();
      // Auto-clear the "recent" pointer after the sweep animation finishes
      // so the next out-of-cooldown crit can re-trigger immediately.
      window.setTimeout(() => {
        if (_state.recent && _state.recent.at === entry.at) {
          _state.recent = null;
          emit();
        }
      }, SWEEP_DURATION_MS + 50);
    } else {
      // Still re-emit so the badge re-renders with the new unack count.
      emit();
    }
  },
  /** Acknowledge all unack crits — called on /alerts page mount. */
  ackAll() {
    if (_state.unack.size === 0) return;
    _state.unack.clear();
    emit();
  },
  /** Acknowledge a single crit by alert_id or -detection_id. */
  ack(key: number) {
    if (_state.unack.delete(key)) emit();
  },
  subscribe(fn: (s: State) => void) {
    listeners.add(fn);
    fn(_state);
    return () => { listeners.delete(fn); };
  },
  /** push an alert_action event from the WS feed. */
  pushAction(a: Omit<AlertAction, "at">) {
    _state.actions.set(a.alert_id, { ...a, at: Date.now() });
    emit();
    // Auto-emit again after the freshness window so consumers re-render
    // and drop the pulse — keeps the API stateless on consumers.
    window.setTimeout(emit, ACTION_FRESHNESS_MS + 50);
  },
  /** Read the freshest alert_action for a given mission, if still within
   *  the freshness window. Returns null otherwise. */
  freshActionForMission(mission_id: number): AlertAction | null {
    const now = Date.now();
    let best: AlertAction | null = null;
    for (const a of _state.actions.values()) {
      if (a.mission_id !== mission_id) continue;
      if (now - a.at > ACTION_FRESHNESS_MS) continue;
      if (!best || a.at > best.at) best = a;
    }
    return best;
  },
  /** is `recent` a crit for this mission? Lasts SWEEP_DURATION_MS. */
  recentCritForMission(mission_id: number): CritEvent | null {
    if (!_state.recent) return null;
    if (_state.recent.mission_id !== mission_id) return null;
    if (Date.now() - _state.recent.at > 1600) return null;
    return _state.recent;
  },
  /** is there ANY recent crit (for sidebar flash)? */
  recentCritGlobal(): CritEvent | null {
    if (!_state.recent) return null;
    if (Date.now() - _state.recent.at > 1600) return null;
    return _state.recent;
  },
  /** fresh alert_action for a specific alert id, used by row pulse. */
  freshActionForAlert(alert_id: number): AlertAction | null {
    const a = _state.actions.get(alert_id);
    if (!a) return null;
    if (Date.now() - a.at > ACTION_FRESHNESS_MS) return null;
    return a;
  },
  /** Dev tool only — wipe seen so the demo can replay the same alert. */
  reset() {
    _state.recent = null;
    _state.unack.clear();
    _state.seen.clear();
    _state.actions.clear();
    emit();
  },
};

/** Mount once at App level — opens the WS, listens, keeps it open. */
export function CritCascadeListener() {
  useEffect(() => {
    let cancelled = false;
    let ws: WebSocket | null = null;
    let reopenHandle: number | null = null;

    const open = () => {
      if (cancelled) return;
      ws = openLiveSocket((msg) => {
        if (!msg || typeof msg !== "object") return;
        const m = msg as Record<string, unknown>;
        if (m.type === "detection") {
          const score = Number(m.threat_score ?? 0);
          if (!Number.isFinite(score) || score < CRIT_THRESHOLD) return;
          critCascade.push({
            alert_id: (m.alert_id as number | null) ?? null,
            detection_id: Number(m.detection_id ?? 0),
            mission_id: Number(m.mission_id ?? 0),
            class_name: String(m.class_name ?? "unknown"),
            threat_score: score,
          });
          toast.crit(
            `CRIT · ${m.class_name} ${score.toFixed(2)}`,
            `Mission #${m.mission_id} · detection #${m.detection_id}`,
          );
          return;
        }
        if (m.type === "alert_action") {
          // relay op-1's action to op-2's screens.
          const alert_id = Number(m.alert_id ?? 0);
          const mission_id = Number(m.mission_id ?? 0);
          const operator_id = String(m.operator_id ?? "?");
          const action = String(m.action ?? "?");
          if (!alert_id || !mission_id) return;
          critCascade.pushAction({
            alert_id,
            mission_id,
            action,
            operator_id,
            status: String(m.status ?? "?"),
            confirmations: Array.isArray(m.confirmations) ? (m.confirmations as string[]) : undefined,
            needed: typeof m.needed === "number" ? m.needed : undefined,
          });
          if (action === "engage" || action === "engage_partial") {
            toast.warn(
              `Alert #${alert_id} · ${operator_id} confirmed`,
              action === "engage"
                ? `dual-control complete — engaged`
                : `awaiting second confirmation`,
            );
          }
          return;
        }
      });
      ws.addEventListener("close", () => {
        if (cancelled) return;
        // Soft reconnect after 2s — the existing detection broadcaster
        // does this implicitly, but a restart of the backend should
        // re-arm us automatically.
        reopenHandle = window.setTimeout(open, 2000);
      });
    };

    open();
    return () => {
      cancelled = true;
      if (reopenHandle) window.clearTimeout(reopenHandle);
      if (ws) {
        try { ws.close(); } catch { /* noop */ }
      }
    };
  }, []);
  return null;
}

/** Top-of-screen sweep bar — renders only while a recent crit is active. */
export function CritSweep() {
  const [state, setState] = useState<State>(_state);
  useEffect(() => critCascade.subscribe(setState), []);
  if (!state.recent) return null;
  return (
    <div
      className="fixed top-0 inset-x-0 z-[10004] pointer-events-none overflow-hidden"
      style={{ height: "3px" }}
      aria-hidden
    >
      <div
        className="absolute inset-y-0 left-0"
        style={{
          width: "30%",
          background: "linear-gradient(90deg, transparent 0%, #ef4444 40%, #fca5a5 50%, #ef4444 60%, transparent 100%)",
          boxShadow: "0 0 18px 2px rgba(239,68,68,0.65)",
          animation: `crit-sweep ${SWEEP_DURATION_MS}ms ease-out forwards`,
        }}
      />
      <style>{`
        @keyframes crit-sweep {
          0%   { transform: translateX(-50%); opacity: 0.0; }
          12%  { opacity: 1.0; }
          85%  { opacity: 1.0; }
          100% { transform: translateX(380%); opacity: 0.0; }
        }
      `}</style>
    </div>
  );
}

/** Numeric badge for sidebar / Threats label. Returns null when count==0. */
export function CritUnackBadge() {
  const [state, setState] = useState<State>(_state);
  useEffect(() => critCascade.subscribe(setState), []);
  if (state.unack.size === 0) return null;
  return (
    <span
      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono uppercase tracking-wider bg-threat-crit/25 text-threat-crit border border-threat-crit/50 animate-pulse"
      title={`${state.unack.size} unacknowledged crit alert(s) — visit Threats to ack`}
    >
      <AlertOctagon size={10} />
      {state.unack.size}
    </span>
  );
}

/** Mount on /alerts to clear the badge when the operator visits. */
export function useCritAckOnMount() {
  useEffect(() => {
    critCascade.ackAll();
  }, []);
}

/** returns true while a recent crit is active (within 1.6s). */
export function useRecentCritFlash(): boolean {
  const [, setN] = useState(0);
  useEffect(() => critCascade.subscribe(() => setN((n) => n + 1)), []);
  return critCascade.recentCritGlobal() != null;
}

/** Engage prompt banner. When a fresh crit lands AND it has an
 *  alert_id, render a fixed banner top-center with an "Engage →" button
 *  for 6s. Click → write a one-shot handoff blob to localStorage and
 *  navigate to /alerts. The Alerts page reads the blob on mount,
 *  selects the matching mission + scrolls to the alert. */
const ENGAGE_BANNER_MS = 6000;
const ENGAGE_HANDOFF_KEY = "astra:engageHandoff";

export function CritEngagePrompt() {
  const navigate = useNavigate();
  const [, setN] = useState(0);
  useEffect(() => critCascade.subscribe(() => setN((n) => n + 1)), []);
  const recent = _state.recent;
  const fresh = recent && recent.alert_id != null && (Date.now() - recent.at) < ENGAGE_BANNER_MS;
  if (!fresh || !recent) return null;
  return (
    <div
      className="fixed top-3 left-1/2 -translate-x-1/2 z-[10005] flex items-center gap-3 px-3 py-2 rounded-full glass-strong border border-threat-crit/60 shadow-2xl animate-pulse-soft"
      style={{ boxShadow: "0 0 24px rgba(239,68,68,0.45)" }}
    >
      <span className="text-2xs font-mono uppercase-wide tracking-wider text-threat-crit">
        CRIT · alert #{recent.alert_id}
      </span>
      <span className="text-xs text-muted font-mono">
        {recent.class_name} {recent.threat_score.toFixed(2)}
      </span>
      <button
        onClick={() => {
          try {
            localStorage.setItem(ENGAGE_HANDOFF_KEY, JSON.stringify({
              alert_id: recent.alert_id,
              mission_id: recent.mission_id,
              ts: Date.now(),
            }));
          } catch { /* noop */ }
          // Drop the recent pointer so the prompt closes immediately.
          _state.recent = null;
          emit();
          navigate("/alerts");
        }}
        className="ml-1 inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-mono uppercase-wide tracking-wider bg-threat-crit text-bg hover:brightness-110 transition-fast"
      >
        Engage →
      </button>
      <button
        onClick={() => { _state.recent = null; emit(); }}
        className="text-muted2 hover:text-text -m-1 p-1.5"
        title="Dismiss"
        aria-label="Dismiss crit prompt"
      >
        <AlertOctagon size={11} />
      </button>
    </div>
  );
}

export const CRIT_ENGAGE_HANDOFF_KEY = ENGAGE_HANDOFF_KEY;

/** drop-in hook for /alerts. On mount: read the handoff blob, if
 *  fresh (<30s old) return its payload so the page can pre-select the
 *  mission + scroll to the alert. The blob is consumed immediately
 *  (cleared) so repeated /alerts visits don't re-trigger the flow. */
export function useEngageHandoff(): { alert_id: number; mission_id: number } | null {
  const [payload] = useState(() => {
    try {
      const raw = localStorage.getItem(ENGAGE_HANDOFF_KEY);
      if (!raw) return null;
      localStorage.removeItem(ENGAGE_HANDOFF_KEY);
      const p = JSON.parse(raw);
      if (typeof p?.alert_id !== "number" || typeof p?.mission_id !== "number") return null;
      if (typeof p?.ts !== "number" || (Date.now() - p.ts) > 30_000) return null;
      return { alert_id: p.alert_id, mission_id: p.mission_id };
    } catch {
      return null;
    }
  });
  return payload;
}

/** corner-bracket flash overlay for the Mission Bezel when a crit
 *  lands on the currently-displayed mission. Renders inside its parent
 *  (parent must be position:relative). 1.6s ease-out. */
export function CritCornerFlash({ missionId }: { missionId: number | null }) {
  const [, setN] = useState(0);
  useEffect(() => critCascade.subscribe(() => setN((n) => n + 1)), []);
  if (missionId == null) return null;
  const recent = critCascade.recentCritForMission(missionId);
  if (!recent) return null;
  return (
    <div className="absolute inset-0 z-[35] pointer-events-none" aria-hidden>
      {(["tl", "tr", "bl", "br"] as const).map((pos) => (
        <span
          key={pos}
          className="absolute"
          style={{
            top: pos.startsWith("t") ? -2 : undefined,
            bottom: pos.startsWith("b") ? -2 : undefined,
            left: pos.endsWith("l") ? -2 : undefined,
            right: pos.endsWith("r") ? -2 : undefined,
            width: 22, height: 22,
            borderTop: pos.startsWith("t") ? "3px solid #ef4444" : undefined,
            borderBottom: pos.startsWith("b") ? "3px solid #ef4444" : undefined,
            borderLeft: pos.endsWith("l") ? "3px solid #ef4444" : undefined,
            borderRight: pos.endsWith("r") ? "3px solid #ef4444" : undefined,
            boxShadow: "0 0 12px rgba(239,68,68,0.7)",
            animation: "crit-corner-flash 1.6s ease-out forwards",
          }}
        />
      ))}
      <style>{`
        @keyframes crit-corner-flash {
          0%, 70%  { opacity: 1; }
          100%     { opacity: 0; }
        }
      `}</style>
    </div>
  );
}

/** left-border pulse for an alert table row. Only fires when an
 *  alert action just landed for *this* alert id. */
export function AlertRowPulse({ alertId }: { alertId: number }) {
  const [, setN] = useState(0);
  useEffect(() => critCascade.subscribe(() => setN((n) => n + 1)), []);
  const a = critCascade.freshActionForAlert(alertId);
  if (!a) return null;
  const tone = a.action === "engage"
    ? "#ef4444"
    : a.action === "engage_partial"
    ? "#fbbf24"
    : "#22d3ee";
  return (
    <span
      className="absolute left-0 top-0 bottom-0 pointer-events-none"
      style={{
        width: 3,
        background: tone,
        boxShadow: `0 0 8px ${tone}`,
        animation: "alert-row-pulse 4s ease-out forwards",
      }}
      aria-hidden
    >
      <style>{`
        @keyframes alert-row-pulse {
          0%   { opacity: 1; }
          80%  { opacity: 0.7; }
          100% { opacity: 0; }
        }
      `}</style>
    </span>
  );
}

/** small pulsing pill that surfaces "ACKED BY <op>" on a mission
 *  tile when an alert action lands within the freshness window. Pass
 *  the mission_id; renders null when there's no fresh action. */
export function AckedByPulse({ missionId }: { missionId: number }) {
  // Re-renders whenever the cascade store emits, which it does on
  // pushAction + the deferred timer that drops staleness.
  const [, setN] = useState(0);
  useEffect(() => critCascade.subscribe(() => setN((n) => n + 1)), []);
  const action = critCascade.freshActionForMission(missionId);
  if (!action) return null;
  const partial = action.action === "engage_partial" && action.confirmations && action.needed
    ? `${action.confirmations.length}/${action.needed}`
    : null;
  const tone =
    action.action === "engage" ? "bg-threat-crit/20 text-threat-crit border-threat-crit/40"
    : action.action === "engage_partial" ? "bg-amber-400/20 text-amber-300 border-amber-400/40"
    : "bg-cyan/15 text-cyan border-cyan/40";
  return (
    <span
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono uppercase tracking-wider border animate-pulse ${tone}`}
      title={`alert #${action.alert_id} · ${action.action} · ${action.operator_id}`}
    >
      ACKED BY {action.operator_id}
      {partial && <span className="opacity-80">· {partial}</span>}
    </span>
  );
}
