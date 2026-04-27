/**
 * ChainVisual — animated SHA-256 chain ribbon for the Audit page.
 *
 * Renders the most recent N audit hashes as connected link nodes. Each
 * link shows the truncated hash + event_type. A pulsing accent glow rides
 * the chain from left → right to suggest "live integrity".
 */

type Row = {
  id: number;
  event_type: string;
  row_hash?: string | null;
};

type Props = {
  rows: Row[];
  /** how many recent rows to render */
  count?: number;
  ok?: boolean | null;
};

export function ChainVisual({ rows, count = 8, ok = true }: Props) {
  const recent = rows.slice(0, count).reverse(); // chronological L→R
  if (recent.length === 0) {
    return (
      <div className="text-2xs uppercase-wide text-muted2 font-mono tracking-wider text-center py-2">
        — no rows yet —
      </div>
    );
  }
  const dotColour = ok === false ? "var(--threat-crit)" : ok ? "var(--threat-low)" : "var(--accent)";
  const lineColour = ok === false ? "rgba(239,68,68,0.45)" : "rgba(74,222,128,0.45)";
  return (
    <div className="relative px-2 py-3">
      {/* Connecting line */}
      <div
        className="absolute left-4 right-4 top-1/2 -translate-y-1/2 h-px"
        style={{ background: `linear-gradient(90deg, transparent 0%, ${lineColour} 8%, ${lineColour} 92%, transparent 100%)` }}
      />
      {/* Travelling pulse — orange dot riding the chain */}
      <span
        className="absolute top-1/2 -translate-y-1/2 w-2 h-2 rounded-full pointer-events-none"
        style={{
          background: "var(--accent)",
          boxShadow: "0 0 10px 2px var(--accent-glow)",
          animation: "chain-pulse 4s linear infinite",
        }}
      />
      <style>{`
        @keyframes chain-pulse {
          0%   { left: 12px;  opacity: 0; }
          5%   { opacity: 1; }
          95%  { opacity: 1; }
          100% { left: calc(100% - 12px); opacity: 0; }
        }
      `}</style>

      <div className="relative flex items-center justify-between gap-1">
        {recent.map((r, idx) => {
          const short = (r.row_hash ?? "").slice(0, 6) || "—";
          return (
            <div key={r.id} className="flex flex-col items-center gap-1.5 z-10 min-w-0">
              <div
                className="w-3 h-3 rounded-full border-2"
                style={{
                  background: "var(--bg)",
                  borderColor: dotColour,
                  boxShadow: `0 0 6px 0 ${lineColour}`,
                }}
              />
              <div className="text-[9px] font-mono text-muted2 tabular-nums">#{r.id}</div>
              <div className="text-[9px] font-mono uppercase-wide tracking-wider truncate max-w-[88px] text-cyan">
                {r.event_type.replace(/_/g, " ")}
              </div>
              <div className="text-[9px] font-mono text-muted2">{short}…</div>
              {idx < recent.length - 1 && null /* line is absolute */}
            </div>
          );
        })}
      </div>
    </div>
  );
}
