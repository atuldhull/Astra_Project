/**
 * MeshFeedPanel (D6.0 — surface coverage) — chronological "what each
 * peer witnessed when" feed for the Audit page.
 *
 * The /api/v1/mesh/witnesses endpoint returns witnesses keyed by
 * audit_row_id. We pull the most recent N audit rows, ask /witnesses
 * for that id range, then flatten + sort by witnessed_at desc so the
 * operator sees a live "who ratified what, in order" stream.
 *
 * Polls every 8s. Self-fetches; no props beyond rows source. Includes
 * a "Sync mesh" button so the operator can drive the synthetic peers
 * through one full pull-verify-witness cycle (D3.4 demo behavior).
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { Loader2, RefreshCw, Users, ZapOff } from "lucide-react";
import { api, type AuditEvent, type MeshWitness } from "../lib/api";
import { absoluteIst, relativeTime } from "../lib/time";
import { toast } from "./Toast";

type FlatWitness = MeshWitness & {
  audit_row_id: number;
  event_type?: string;
  mission_id?: number | null;
};

function trunc(h: string | null | undefined, head = 8, tail = 6): string {
  if (!h) return "—";
  if (h.length <= head + tail + 1) return h;
  return `${h.slice(0, head)}…${h.slice(-tail)}`;
}

const POLL_MS = 8000;
const RECENT_AUDIT_LIMIT = 80;

export function MeshFeedPanel() {
  const [rows, setRows] = useState<FlatWitness[]>([]);
  const [nPeers, setNPeers] = useState(0);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const recent: AuditEvent[] = await api.listAudit({ limit: RECENT_AUDIT_LIMIT });
      const ids = recent.map((r) => r.id);
      if (ids.length === 0) {
        setRows([]);
        setNPeers(0);
        return;
      }
      const w = await api.meshWitnesses(ids);
      setNPeers(w.n_peers);
      const eventByRow = new Map<number, AuditEvent>(recent.map((r) => [r.id, r]));
      const flat: FlatWitness[] = [];
      for (const [rowIdStr, witnesses] of Object.entries(w.by_row)) {
        const rowId = Number(rowIdStr);
        const event = eventByRow.get(rowId);
        for (const wit of witnesses) {
          flat.push({
            ...wit,
            audit_row_id: rowId,
            event_type: event?.event_type,
            mission_id: event?.mission_id ?? null,
          });
        }
      }
      // Most recent first
      flat.sort((a, b) => {
        const ta = a.witnessed_at ? Date.parse(a.witnessed_at) : 0;
        const tb = b.witnessed_at ? Date.parse(b.witnessed_at) : 0;
        return tb - ta;
      });
      setRows(flat.slice(0, 50));
      setErr(null);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const handle = window.setInterval(refresh, POLL_MS);
    return () => window.clearInterval(handle);
  }, [refresh]);

  async function syncDemo() {
    setSyncing(true);
    try {
      const r = await api.meshSyncDemo();
      toast.success(
        `Mesh sync complete`,
        `${r.witnesses_added} new witnesses · ${r.peers.length} peers · ${r.refused_due_to_tampering} refused`,
      );
      await refresh();
    } catch (e) {
      toast.crit("Mesh sync failed", (e as Error).message);
    } finally {
      setSyncing(false);
    }
  }

  const peerCount = useMemo(
    () => new Set(rows.map((r) => r.peer_id)).size,
    [rows],
  );

  return (
    <div className="glass rounded-lg shadow-panel">
      <div className="px-4 py-2.5 border-b border-border flex items-center justify-between gap-3">
        <div>
          <div className="text-2xs uppercase-wide tracking-wider text-muted2 font-mono flex items-center gap-1.5">
            <Users size={11} className="text-cyan" />
            MESH WITNESS FEED
          </div>
          <div className="text-[10px] text-muted font-mono mt-0.5">
            chronological per-peer attestation log · D3.4 cross-agency witnessing
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-2xs font-mono tabular-nums text-text">
            {rows.length}
            <span className="text-muted2"> events · </span>
            {peerCount}/{nPeers}
            <span className="text-muted2"> peers</span>
          </span>
          <button
            onClick={syncDemo}
            disabled={syncing}
            className="inline-flex items-center gap-1.5 px-2 py-1 rounded text-2xs font-mono uppercase-wide tracking-wider bg-cyan/15 border border-cyan/40 text-cyan hover:bg-cyan/25 transition-fast disabled:opacity-50"
            title="Trigger synthetic peers (peer-IB, peer-NIA) to pull-verify-witness the recent audit chain"
          >
            {syncing ? <Loader2 size={11} className="animate-spin" /> : <ZapOff size={11} />}
            sync mesh
          </button>
          <button
            onClick={refresh}
            disabled={loading}
            className="p-1.5 rounded hover:bg-panel2 text-muted transition-fast disabled:opacity-40"
            title="Refresh"
          >
            {loading ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
          </button>
        </div>
      </div>

      <div className="max-h-72 overflow-auto">
        {err && (
          <div className="px-4 py-3 text-2xs text-threat-crit font-mono">err: {err}</div>
        )}
        {!err && rows.length === 0 && !loading && (
          <div className="px-4 py-6 text-2xs text-muted2 font-mono">
            no peer witnesses yet — click "sync mesh" to drive the synthetic peers
          </div>
        )}
        {rows.map((r, i) => (
          <div
            key={`${r.audit_row_id}:${r.peer_id}:${i}`}
            className="border-t border-border first:border-0 px-4 py-2 flex items-center gap-3 text-2xs font-mono"
          >
            <span className="px-1.5 py-0.5 rounded bg-cyan/15 border border-cyan/30 text-cyan uppercase tracking-wider shrink-0">
              {r.peer_id}
            </span>
            <span className="text-muted2 shrink-0">witnessed</span>
            <span className="text-text shrink-0">#{r.audit_row_id}</span>
            {r.event_type && (
              <span className="text-muted shrink-0">{r.event_type.replace(/_/g, " ")}</span>
            )}
            {r.mission_id != null && (
              <span className="text-muted2 shrink-0">m#{r.mission_id}</span>
            )}
            <span className="text-muted2 truncate flex-1" title={r.row_hash}>
              row {trunc(r.row_hash)}
            </span>
            <span
              className="text-muted2 shrink-0"
              title={r.witnessed_at ? absoluteIst(r.witnessed_at) : ""}
            >
              {r.witnessed_at ? relativeTime(r.witnessed_at) : "—"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
