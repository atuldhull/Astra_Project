/**
 * AnchorStrip — Audit page strip showing the chain-anchor state.
 *
 * Anchors are external-ish references to the audit chain tip at a
 * given count. They prove "history at point N had this tip". Mismatch
 * between the anchor's claimed tip and the live chain at that count =
 * tampering.
 *
 * Three actions in one strip:
 *   • Anchor now (force a fresh entry)
 *   • Verify all anchors against the live chain
 *   • Hover to see last anchor timestamp + tip
 */
import { useEffect, useState } from "react";
import { Anchor, Loader2, ShieldCheck, ShieldAlert, Network } from "lucide-react";
import { api } from "../lib/api";
import { absoluteIst, relativeTime } from "../lib/time";

type LastAnchor = { ts: string; count: number; tip: string; backend: string };
type Status = { enabled: boolean; total: number; interval: number; last: LastAnchor | null };
type VerifyResult = {
  ok: boolean;
  total: number;
  mismatches: { count: number; ts: string; reason: string }[];
  last: LastAnchor | null;
};

export function AnchorStrip() {
  const [status, setStatus] = useState<Status | null>(null);
  const [busyAnchor, setBusyAnchor] = useState(false);
  const [busyVerify, setBusyVerify] = useState(false);
  const [verifyResult, setVerifyResult] = useState<VerifyResult | null>(null);
  // D3.4 — peer count for the inline metric (read-only here; actual sync
  // lives on the Audit page header).
  const [peerCount, setPeerCount] = useState<number | null>(null);
  const [lastMeshSync, setLastMeshSync] = useState<string | null>(null);

  async function refreshStatus() {
    try {
      const s = await api.anchorStatus();
      setStatus(s);
    } catch { /* ignore */ }
    try {
      const p = await api.meshPeers();
      setPeerCount(p.n_peers);
    } catch { /* mesh is optional */ }
  }

  useEffect(() => {
    refreshStatus();
    // localStorage receives the last sync ts from the Audit page when
    // syncMesh runs there — read it here for the strip.
    try {
      const ts = localStorage.getItem("astra:meshLastSync");
      if (ts) setLastMeshSync(ts);
    } catch { /* noop */ }
    const onStorage = (e: StorageEvent) => {
      if (e.key === "astra:meshLastSync" && e.newValue) setLastMeshSync(e.newValue);
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  async function anchorNow() {
    setBusyAnchor(true);
    try {
      await api.anchorNow();
      await refreshStatus();
    } finally {
      setBusyAnchor(false);
    }
  }

  async function verifyAll() {
    setBusyVerify(true);
    setVerifyResult(null);
    const t0 = performance.now();
    try {
      const v = await api.anchorVerify();
      const elapsed = performance.now() - t0;
      if (elapsed < 600) await new Promise((r) => setTimeout(r, 600 - elapsed));
      setVerifyResult(v);
    } catch (e) {
      setVerifyResult({ ok: false, total: 0, mismatches: [{ count: 0, ts: "", reason: (e as Error).message }], last: null });
    } finally {
      setBusyVerify(false);
    }
  }

  if (!status?.enabled) return null;

  const last = status.last;

  return (
    <div className="mx-6 mt-3 px-4 py-2.5 rounded-lg border border-border bg-panel/40 flex items-center gap-3 text-xs">
      <div className="flex items-center gap-2 text-muted2 font-mono uppercase-wide tracking-wider text-[11px]">
        <Anchor size={12} className="text-cyan" />
        CHAIN ANCHOR
      </div>

      <div className="text-muted">
        {status.total > 0
          ? <>{status.total} anchor{status.total === 1 ? "" : "s"} on disk</>
          : <>no anchors yet — interval every {status.interval} events</>}
      </div>

      {last && (
        <div className="text-muted2 font-mono" title={absoluteIst(last.ts)}>
          last: <span className="text-text">{relativeTime(last.ts)}</span> ·
          tip <span className="text-text">{last.tip.slice(0, 10)}…{last.tip.slice(-6)}</span> ·
          @ count <span className="text-text">{last.count}</span>
        </div>
      )}

      {peerCount != null && (
        <div className="text-muted2 font-mono flex items-center gap-1.5" title="Cross-agency peers configured to witness the audit chain">
          <Network size={11} className="text-cyan" />
          <span>peers witnessing: <span className="text-text tabular-nums">{peerCount}</span></span>
          {lastMeshSync && (
            <span className="opacity-60" title={absoluteIst(lastMeshSync)}>· last sync {relativeTime(lastMeshSync)}</span>
          )}
        </div>
      )}

      <div className="ml-auto flex items-center gap-2">
        <button
          onClick={anchorNow}
          disabled={busyAnchor}
          className="flex items-center gap-1 glass border border-border px-2.5 py-1 rounded text-2xs uppercase-wide tracking-wider hover:bg-panel2 disabled:opacity-50 transition-fast"
          title="Force a fresh anchor entry capturing the current chain tip"
        >
          {busyAnchor ? <Loader2 size={11} className="animate-spin" /> : <Anchor size={11} />}
          Anchor now
        </button>
        <button
          onClick={verifyAll}
          disabled={busyVerify}
          className="flex items-center gap-1 glass border border-border px-2.5 py-1 rounded text-2xs uppercase-wide tracking-wider hover:bg-panel2 disabled:opacity-50 transition-fast"
          title="Re-check every anchor against the live chain"
        >
          {busyVerify ? <Loader2 size={11} className="animate-spin" /> : <ShieldCheck size={11} />}
          Verify anchors
        </button>
      </div>

      {verifyResult && (
        <div className={`flex items-center gap-1.5 font-mono ${verifyResult.ok ? "text-threat-low" : "text-threat-crit"}`}>
          {verifyResult.ok
            ? <><ShieldCheck size={12} /> {verifyResult.total} anchors valid</>
            : <><ShieldAlert size={12} /> {verifyResult.mismatches.length} mismatch(es)</>}
        </div>
      )}
    </div>
  );
}
