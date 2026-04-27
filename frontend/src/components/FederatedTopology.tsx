/**
 * FederatedTopology — radial topology graph of clients around an aggregator.
 *
 * Shows the federated learning network: central aggregator node + N client
 * nodes around the perimeter, connected by lines whose stroke-width and
 * opacity scale with each client's FoolsGold aggregation weight. Quarantined
 * clients (weight ≈ 0) get a red dashed line + crossed-out node.
 *
 * Animated 'gradient flow' dots travel inbound along each edge proportionally
 * to the client's contribution.
 */

type Props = {
  /** Client id → aggregation weight (sums to ~1). */
  weights: Record<string, number>;
  /** Optional explicit list of attacker/sybil ids that should render quarantined. */
  poisonIds?: string[];
  size?: number;
  className?: string;
};

export function FederatedTopology({ weights, poisonIds = [], size = 360, className = "" }: Props) {
  const ids = Object.keys(weights).sort();
  const n = Math.max(ids.length, 1);
  const cx = size / 2;
  const cy = size / 2;
  const r = size * 0.36;
  const aggRadius = 22;
  const nodeRadius = 14;

  const isPoison = (id: string) =>
    poisonIds.includes(id) || id.toLowerCase().startsWith("attacker") || (weights[id] ?? 0) < 0.05;

  const positions = ids.map((id, i) => {
    const angle = (i / n) * Math.PI * 2 - Math.PI / 2;
    return { id, x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle), w: weights[id] ?? 0 };
  });

  return (
    <svg viewBox={`0 0 ${size} ${size}`} className={`w-full h-full ${className}`}>
      <defs>
        <radialGradient id="agg-grad" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="rgba(255, 122, 26, 1)" />
          <stop offset="60%" stopColor="rgba(255, 122, 26, 0.55)" />
          <stop offset="100%" stopColor="rgba(255, 122, 26, 0.0)" />
        </radialGradient>
        <radialGradient id="node-grad" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="rgba(34, 211, 238, 1)" />
          <stop offset="100%" stopColor="rgba(34, 211, 238, 0.45)" />
        </radialGradient>
        <radialGradient id="poison-grad" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="rgba(239, 68, 68, 0.95)" />
          <stop offset="100%" stopColor="rgba(239, 68, 68, 0.35)" />
        </radialGradient>
      </defs>

      {/* Concentric range rings centered on aggregator */}
      <g stroke="var(--border)" fill="none" strokeWidth={0.6}>
        <circle cx={cx} cy={cy} r={r * 0.4} strokeDasharray="2 4" opacity={0.5} />
        <circle cx={cx} cy={cy} r={r * 0.7} strokeDasharray="2 5" opacity={0.4} />
        <circle cx={cx} cy={cy} r={r}        strokeDasharray="2 6" opacity={0.3} />
      </g>

      {/* Edges — width and opacity ∝ weight */}
      {positions.map(({ id, x, y, w }) => {
        const poison = isPoison(id);
        const stroke = poison ? "var(--threat-crit)" : "var(--threat-low)";
        const sw = poison ? 1.0 : Math.max(0.8, w * 6);
        const op = poison ? 0.55 : Math.max(0.25, w);
        const dash = poison ? "2 3" : undefined;
        return (
          <g key={`e-${id}`}>
            <line
              x1={cx} y1={cy} x2={x} y2={y}
              stroke={stroke} strokeWidth={sw} opacity={op}
              strokeDasharray={dash}
            />
            {/* Animated flow dot — only for honest clients with non-trivial weight */}
            {!poison && w > 0.05 && (
              <circle r={2.4} fill="var(--accent)" opacity={0.9}>
                <animate
                  attributeName="cx"
                  values={`${x};${cx}`}
                  dur={`${1.6 + (1 - w) * 1.4}s`}
                  repeatCount="indefinite"
                />
                <animate
                  attributeName="cy"
                  values={`${y};${cy}`}
                  dur={`${1.6 + (1 - w) * 1.4}s`}
                  repeatCount="indefinite"
                />
                <animate
                  attributeName="opacity"
                  values="0.0;0.95;0.0"
                  dur={`${1.6 + (1 - w) * 1.4}s`}
                  repeatCount="indefinite"
                />
              </circle>
            )}
          </g>
        );
      })}

      {/* Aggregator at center */}
      <g>
        <circle cx={cx} cy={cy} r={aggRadius * 1.6} fill="url(#agg-grad)" opacity={0.6}>
          <animate attributeName="r" values={`${aggRadius * 1.4};${aggRadius * 1.8};${aggRadius * 1.4}`} dur="3s" repeatCount="indefinite" />
        </circle>
        <circle cx={cx} cy={cy} r={aggRadius} fill="var(--bg)" stroke="var(--accent)" strokeWidth={2} />
        <text x={cx} y={cy + 1} textAnchor="middle" dominantBaseline="middle" fontFamily="JetBrains Mono, monospace" fontSize="9" fill="var(--accent)" fontWeight="700">
          AGG
        </text>
      </g>

      {/* Client nodes */}
      {positions.map(({ id, x, y, w }) => {
        const poison = isPoison(id);
        const fill = poison ? "url(#poison-grad)" : "url(#node-grad)";
        const stroke = poison ? "var(--threat-crit)" : "var(--cyan)";
        return (
          <g key={`n-${id}`}>
            {poison && (
              <circle cx={x} cy={y} r={nodeRadius * 1.5} fill="none" stroke="var(--threat-crit)" strokeWidth={1} opacity={0.4}>
                <animate attributeName="r" values={`${nodeRadius * 1.4};${nodeRadius * 1.9};${nodeRadius * 1.4}`} dur="1.6s" repeatCount="indefinite" />
                <animate attributeName="opacity" values="0.5;0.0;0.5" dur="1.6s" repeatCount="indefinite" />
              </circle>
            )}
            <circle cx={x} cy={y} r={nodeRadius} fill={fill} stroke={stroke} strokeWidth={1.5} opacity={poison ? 0.85 : 1} />
            {poison && (
              <>
                <line x1={x - 7} y1={y - 7} x2={x + 7} y2={y + 7} stroke="var(--bg)" strokeWidth={1.6} />
                <line x1={x + 7} y1={y - 7} x2={x - 7} y2={y + 7} stroke="var(--bg)" strokeWidth={1.6} />
              </>
            )}
            <text
              x={x}
              y={y + nodeRadius + 12}
              textAnchor="middle"
              fontFamily="JetBrains Mono, monospace"
              fontSize="8"
              fill={poison ? "var(--threat-crit)" : "var(--text)"}
            >
              {id}
            </text>
            <text
              x={x}
              y={y + nodeRadius + 22}
              textAnchor="middle"
              fontFamily="JetBrains Mono, monospace"
              fontSize="8"
              fill="var(--muted-2)"
            >
              w={w.toFixed(2)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
