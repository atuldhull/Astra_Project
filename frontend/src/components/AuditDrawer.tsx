/**
 * AuditDrawer (D4.2) — collapsible mission-scoped audit ledger that
 * follows the Replay Scrubber.
 *
 * Renders three things in one compact strip:
 *   1. "Tip as of T" — the chain head the system would have reported
 *      at the scrubbed moment. Truncated hash, mono.
 *   2. A horizontally-scrolling row of mini event chips (hash · type
 *      · operator · time). Witnessed events get a small WITNESS pill
 *      that pulses for 1.2s the first time it appears in the snapshot
 *      while scrubbing forward — that's the "co-witness sync moment".
 *   3. Per-mission witness summary (N peers).
 *
 * Self-fetches when missionId + scrubMs change; debounced 250ms so
 * dragging the slider doesn't spam the backend.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, ChevronUp, FileDown, ScrollText, ShieldCheck, Users } from "lucide-react";
import { api, type AuditSnapshot, type AuditSnapshotWitness } from "../lib/api";
import { absoluteIst, relativeTime } from "../lib/time";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

type Props = {
  missionId: number;
  scrubMs: number | null;
  /** Optional callback when a witness pulse is visible (for parent overlays). */
  onWitnessHighlight?: (peerIds: string[]) => void;
  /** D5.7 — emits the snapshot events upward so the Mission page can
   *  render pipeline-stage ticks on the ReplayScrubber. */
  onSnapshot?: (snap: AuditSnapshot) => void;
};

function trunc(h: string | null | undefined, head = 8, tail = 6): string {
  if (!h) return "—";
  if (h.length <= head + tail + 1) return h;
  return `${h.slice(0, head)}…${h.slice(-tail)}`;
}

const EVENT_COLOURS: Record<string, string> = {
  ingest_started:        "#60a5fa",
  ingest_completed:      "#4ade80",
  alert_confirmed:       "#facc15",
  alert_rejected:        "#94a3b8",
  alert_escalated:       "#fb923c",
  alert_engaged:         "#ef4444",
  alert_confirmation:    "#fbbf24",
  alert_reclassified:    "#a78bfa",
  weights_changed:       "#f472b6",
  public_report_submitted: "#22d3ee",
  public_report_pinned:    "#22d3ee",
};

export function AuditDrawer({ missionId, scrubMs, onWitnessHighlight, onSnapshot }: Props) {
  const [snapshot, setSnapshot] = useState<AuditSnapshot | null>(null);
  const [open, setOpen] = useState(true);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // Track which witness ids have been *seen* in any prior snapshot so we
  // can pulse the new ones. Using ids (not peer_ids) keeps the pulse
  // event-specific.
  const seenWitnessIds = useRef<Set<number>>(new Set());
  const [pulsingIds, setPulsingIds] = useState<Set<number>>(new Set());

  useEffect(() => {
    if (!missionId) return;
    const handle = window.setTimeout(async () => {
      setLoading(true);
      try {
        const until = scrubMs != null ? new Date(scrubMs).toISOString() : undefined;
        const snap = await api.auditSnapshot(missionId, until);
        setSnapshot(snap);
        if (onSnapshot) onSnapshot(snap);
        setErr(null);

        // Diff witnesses → pulse the just-arrived ones.
        const newIds: number[] = [];
        for (const w of snap.witnesses) {
          if (!seenWitnessIds.current.has(w.id)) {
            seenWitnessIds.current.add(w.id);
            newIds.push(w.id);
          }
        }
        if (newIds.length > 0) {
          setPulsingIds(new Set(newIds));
          if (onWitnessHighlight) {
            onWitnessHighlight(
              snap.witnesses.filter((w) => newIds.includes(w.id)).map((w) => w.peer_id),
            );
          }
          window.setTimeout(() => setPulsingIds(new Set()), 1200);
        }
      } catch (e) {
        setErr((e as Error).message);
      } finally {
        setLoading(false);
      }
    }, 250); // debounce
    return () => window.clearTimeout(handle);
  }, [missionId, scrubMs, onWitnessHighlight, onSnapshot]);

  // When the missionId itself changes, reset the seen set so a fresh
  // mission gets fresh pulses.
  useEffect(() => {
    seenWitnessIds.current = new Set();
    setPulsingIds(new Set());
  }, [missionId]);

  const witnessByEventId = useMemo(() => {
    const m: Record<number, AuditSnapshotWitness[]> = {};
    if (!snapshot) return m;
    for (const w of snapshot.witnesses) {
      if (w.audit_row_id == null) continue;
      (m[w.audit_row_id] ??= []).push(w);
    }
    return m;
  }, [snapshot]);

  const peerCount = useMemo(() => {
    if (!snapshot) return 0;
    return new Set(snapshot.witnesses.map((w) => w.peer_id)).size;
  }, [snapshot]);

  return (
    <div className="border-t border-border bg-bg/80 backdrop-blur-sm">
      {/* Header strip */}
      <div className="flex items-center gap-3 px-4 py-2 text-2xs font-mono uppercase-wide tracking-wider">
        <button
          onClick={() => setOpen(!open)}
          className="inline-flex items-center gap-1.5 text-muted hover:text-text transition-fast"
        >
          {open ? <ChevronDown size={11} /> : <ChevronUp size={11} />}
          <ScrollText size={11} />
          AUDIT TIMELINE
        </button>

        <span className="text-muted2">·</span>

        <span className="inline-flex items-center gap-1.5 text-muted">
          <ShieldCheck size={11} className="text-cyan" />
          <span className="text-muted2">tip</span>
          <span className="text-text" title={snapshot?.tip.row_hash ?? ""}>
            {trunc(snapshot?.tip.row_hash)}
          </span>
          {snapshot?.tip.id != null && (
            <span className="text-muted2 tabular-nums">#{snapshot.tip.id}</span>
          )}
        </span>

        <span className="text-muted2">·</span>

        <span className="inline-flex items-center gap-1.5 text-muted">
          <Users size={11} />
          <span className="tabular-nums text-text">{peerCount}</span>
          <span className="text-muted2">peer{peerCount === 1 ? "" : "s"}</span>
        </span>

        <span className="text-muted2">·</span>

        <span className="text-muted2 tabular-nums">
          {snapshot ? `${snapshot.events.length} events` : (loading ? "loading…" : "—")}
        </span>

        {/* D4.6 — Export replay clip PDF */}
        <a
          href={(() => {
            const q = new URLSearchParams({ mission_id: String(missionId) });
            if (snapshot?.events.length && snapshot.events[0].created_at) {
              q.set("since", snapshot.events[0].created_at);
            }
            if (snapshot?.until_ts) q.set("until", snapshot.until_ts);
            return `${API_BASE}/api/v1/audit/range-cert?${q}`;
          })()}
          target="_blank"
          rel="noreferrer"
          className="ml-auto inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono uppercase tracking-wider bg-cyan/15 text-cyan border border-cyan/40 hover:bg-cyan/25 transition-fast"
          title="Download a tamper-evident PDF certificate covering this mission up to the scrubbed moment"
        >
          <FileDown size={11} /> export clip
        </a>

        {err && <span className="text-threat-crit normal-case tracking-normal">{err}</span>}
      </div>

      {/* D5.7 — index of the last event with created_at <= scrubMs (the
          "you are here" cursor in the chip strip). When scrubMs is null
          we mark the rightmost; events come back ordered ascending. */}
      {/* Event chips row */}
      {open && snapshot && (
        <div
          className="px-4 pb-2 flex gap-2 overflow-x-auto"
          style={{ scrollbarWidth: "thin" }}
        >
          {snapshot.events.length === 0 ? (
            <div className="text-2xs text-muted2 font-mono py-1">no audit events for this mission yet</div>
          ) : (() => {
            const cursorIdx = (() => {
              if (scrubMs == null) return snapshot.events.length - 1;
              for (let i = snapshot.events.length - 1; i >= 0; i--) {
                const ts = snapshot.events[i].created_at ? Date.parse(snapshot.events[i].created_at!) : NaN;
                if (Number.isFinite(ts) && ts <= scrubMs) return i;
              }
              return -1;
            })();
            return snapshot.events.map((e, i) => {
              const colour = EVENT_COLOURS[e.event_type] ?? "#94a3b8";
              const witnesses = witnessByEventId[e.id] ?? [];
              const pulsing = witnesses.some((w) => pulsingIds.has(w.id));
              const isCursor = i === cursorIdx;
              return (
                <div
                  key={e.id}
                  className={`shrink-0 inline-flex items-center gap-1.5 px-2 py-1 rounded border bg-panel2/60 text-2xs font-mono ${
                    isCursor ? "ring-2 ring-cyan/70 shadow-[0_0_8px_rgba(34,211,238,0.4)]" : ""
                  }`}
                  style={{ borderColor: isCursor ? "#22d3ee" : colour + "40" }}
                  title={[
                    isCursor ? "▼ you are here (scrub cursor)" : "",
                    `#${e.id}  ${e.event_type}`,
                    e.operator_id ? `op: ${e.operator_id}` : "system",
                    e.row_hash ? `row_hash: ${e.row_hash}` : "",
                    e.created_at ? absoluteIst(e.created_at) : "",
                  ].filter(Boolean).join("\n")}
                >
                  <span className="tabular-nums text-muted2">#{e.id}</span>
                  <span style={{ color: colour }}>{e.event_type.replace(/_/g, " ")}</span>
                  {e.operator_id && (
                    <span className="text-muted">{e.operator_id}</span>
                  )}
                  {e.created_at && (
                    <span className="text-muted2">{relativeTime(e.created_at)}</span>
                  )}
                  {witnesses.length > 0 && (
                    <span
                      className={[
                        "ml-1 px-1.5 py-0.5 rounded text-[10px] uppercase tracking-wider",
                        pulsing
                          ? "bg-cyan/40 text-bg ring-2 ring-cyan animate-pulse"
                          : "bg-cyan/15 text-cyan border border-cyan/30",
                      ].join(" ")}
                      title={`witnessed by: ${witnesses.map((w) => w.peer_id).join(", ")}`}
                    >
                      WITNESS · {witnesses.length}
                    </span>
                  )}
                </div>
              );
            });
          })()}
        </div>
      )}
    </div>
  );
}
