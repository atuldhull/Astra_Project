/**
 * AlertVerifyBadge — tiny "verified" pill on each alert row.
 *
 * On hover/click:
 *   1. Fetches /api/v1/audit?alert_id=N&limit=1 — grabs the most recent
 *      audit row that mentions this alert.
 *   2. If found, calls /api/v1/audit/verify-row/{row_id} to re-walk
 *      SHA-256 from genesis to that row.
 *   3. Renders ok / broken / no-audit states.
 *
 * Lazy: nothing fetched until the badge enters viewport via the
 * popover trigger. Cached per (alertId, row_id) so re-opens are cheap.
 */
import { useEffect, useRef, useState } from "react";
import { ShieldCheck, ShieldAlert, ShieldOff, Loader2 } from "lucide-react";
import { api, type AuditEvent } from "../lib/api";

type VerifyResult = {
  ok: boolean;
  checked: number;
  broken_at_id: number | null;
  reason: string | null;
  row_hash: string | null;
  prev_hash: string | null;
};

type Props = {
  alertId: number;
  /** Compact (icon-only) or full pill. Default compact. */
  size?: "xs" | "sm";
};

const _cache = new Map<number, { row: AuditEvent | null; verify: VerifyResult | null }>();

/** seed the cache with an alert→row_id mapping pre-fetched in
 *  one batch by the parent. The verify popover will still call the
 *  chain-walk endpoint on click, but the list-fetch step is skipped. */
export function seedAlertVerifyRows(map: Record<string, number | null>) {
  for (const [k, v] of Object.entries(map)) {
    const id = Number(k);
    if (!Number.isFinite(id)) continue;
    // Don't blast over an already-populated entry that has a verify result.
    if (_cache.has(id) && _cache.get(id)?.verify != null) continue;
    if (v == null) {
      _cache.set(id, { row: null, verify: null });
    } else {
      // We only know the row id; the actual AuditEvent shape isn't here.
      // Stash a partial row stub; ensure() below will fall through to a
      // direct verify-row/{id} call instead of listAudit.
      _cache.set(id, {
        row: { id: v, event_type: "?", operator_id: null, mission_id: null, alert_id: id, payload_json: null, prev_hash: null, row_hash: null, created_at: "" } as unknown as AuditEvent,
        verify: null,
      });
    }
  }
}

function trunc(h: string | null | undefined, head = 8, tail = 6): string {
  if (!h) return "—";
  if (h.length <= head + tail + 1) return h;
  return `${h.slice(0, head)}…${h.slice(-tail)}`;
}

export function AlertVerifyBadge({ alertId, size = "xs" }: Props) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [row, setRow] = useState<AuditEvent | null>(null);
  const [verify, setVerify] = useState<VerifyResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const popRef = useRef<HTMLDivElement>(null);

  const ensure = async () => {
    const cached = _cache.get(alertId);
    // Fully resolved (row + verify) → just sync.
    if (cached && cached.verify != null) {
      setRow(cached.row); setVerify(cached.verify);
      return;
    }
    // Partial (seeded row, no verify) → skip listAudit, go straight to walk.
    if (cached && cached.row && cached.verify == null && cached.row.id) {
      setLoading(true);
      try {
        const v = await api.verifyAuditRow(cached.row.id);
        _cache.set(alertId, { row: cached.row, verify: v });
        setRow(cached.row); setVerify(v);
        setErr(null);
      } catch (e) {
        setErr((e as Error).message);
      } finally {
        setLoading(false);
      }
      return;
    }
    // Seeded as known-empty (alert has no audit row) → no-op.
    if (cached && cached.row == null) {
      setRow(null); setVerify(null);
      return;
    }
    // Cold path — fetch list + walk.
    setLoading(true);
    try {
      const rows = await api.listAudit({ alert_id: alertId, limit: 1 });
      const r = rows[0] ?? null;
      let v: VerifyResult | null = null;
      if (r) {
        v = await api.verifyAuditRow(r.id);
      }
      _cache.set(alertId, { row: r, verify: v });
      setRow(r); setVerify(v);
      setErr(null);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!open) return;
    ensure();
    const onClickAway = (e: MouseEvent) => {
      if (popRef.current && !popRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onEsc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onClickAway);
    document.addEventListener("keydown", onEsc);
    return () => {
      document.removeEventListener("mousedown", onClickAway);
      document.removeEventListener("keydown", onEsc);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const status: "loading" | "ok" | "broken" | "absent" | "err" =
    loading ? "loading"
    : err ? "err"
    : !row ? "absent"
    : verify?.ok ? "ok"
    : "broken";

  const Icon = status === "ok" ? ShieldCheck
            : status === "broken" ? ShieldAlert
            : status === "loading" ? Loader2
            : ShieldOff;

  const tone = status === "ok"
    ? "text-threat-low"
    : status === "broken"
    ? "text-threat-crit"
    : "text-muted2";

  const px = size === "xs" ? "px-1 py-0.5 text-[10px]" : "px-1.5 py-0.5 text-2xs";

  return (
    <span className="relative inline-block">
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); setOpen(!open); }}
        onMouseEnter={() => { if (!_cache.has(alertId)) ensure(); }}
        className={`inline-flex items-center gap-1 rounded font-mono uppercase tracking-wider border border-border ${tone} ${px} hover:bg-panel2 transition-fast`}
        title="Audit-chain verify for this alert"
        aria-label={`verify alert ${alertId}`}
      >
        <Icon size={10} className={status === "loading" ? "animate-spin" : ""} />
        verify
      </button>
      {open && (
        <div
          ref={popRef}
          className="absolute right-0 top-full mt-1 w-64 z-30 glass-strong border border-border rounded shadow-2xl p-2.5 text-2xs font-mono"
          onClick={(e) => e.stopPropagation()}
        >
          {loading && <div className="text-muted">verifying…</div>}
          {!loading && err && <div className="text-threat-crit">err: {err}</div>}
          {!loading && !err && !row && (
            <div className="text-muted2">no audit row tied to this alert yet — open the row in /audit ledger to inspect</div>
          )}
          {!loading && !err && row && verify && (
            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-muted2 uppercase">audit row</span>
                <span className="text-text">#{row.id}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted2 uppercase">type</span>
                <span className="text-text">{row.event_type}</span>
              </div>
              {row.operator_id && (
                <div className="flex items-center justify-between">
                  <span className="text-muted2 uppercase">operator</span>
                  <span className="text-text">{row.operator_id}</span>
                </div>
              )}
              <div className="flex items-center justify-between">
                <span className="text-muted2 uppercase">chain</span>
                <span className={verify.ok ? "text-threat-low" : "text-threat-crit"}>
                  {verify.ok ? `ok · walked ${verify.checked}` : `broken at #${verify.broken_at_id}`}
                </span>
              </div>
              <div className="border-t border-border pt-1.5 mt-1.5 space-y-0.5">
                <div className="text-muted2 uppercase">prev_hash</div>
                <div className="text-text break-all" title={verify.prev_hash ?? ""}>
                  {trunc(verify.prev_hash, 12, 12)}
                </div>
                <div className="text-muted2 uppercase">row_hash</div>
                <div className="text-text break-all" title={verify.row_hash ?? ""}>
                  {trunc(verify.row_hash, 12, 12)}
                </div>
              </div>
              {verify.reason && (
                <div className="border-t border-border pt-1.5 mt-1.5 text-threat-crit">
                  {verify.reason}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </span>
  );
}
