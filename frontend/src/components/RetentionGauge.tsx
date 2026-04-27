/**
 * RetentionGauge — semi-circular gauge for "X% detections retained under attack".
 *
 * Used on the Adversarial page A/B retention strip. 270° arc, color tinted
 * by retention bucket, animated needle.
 */

type Props = {
  value: number;          // 0..1
  label?: string;
  size?: number;
  className?: string;
};

export function RetentionGauge({ value, label = "RETENTION", size = 140, className = "" }: Props) {
  const v = Math.max(0, Math.min(1, value));
  const pct = (v * 100).toFixed(0);
  const tone =
    v >= 0.75 ? "var(--threat-low)"
    : v >= 0.45 ? "var(--threat-high)"
    : "var(--threat-crit)";
  const toneGlow =
    v >= 0.75 ? "var(--threat-low-glow)"
    : v >= 0.45 ? "var(--threat-high-glow)"
    : "var(--threat-crit-glow)";

  // Gauge geometry: 270° arc from -135° to +135°
  const cx = size / 2;
  const cy = size / 2 + size * 0.05;
  const r = size * 0.4;
  const startAngle = -225;
  const endAngle = 45;
  const sweepValue = startAngle + v * (endAngle - startAngle);

  const polar = (deg: number, radius = r) => {
    const rad = (deg * Math.PI) / 180;
    return [cx + radius * Math.cos(rad), cy + radius * Math.sin(rad)];
  };

  const [bgX1, bgY1] = polar(startAngle);
  const [bgX2, bgY2] = polar(endAngle);
  const [fgX1, fgY1] = [bgX1, bgY1];
  const [fgX2, fgY2] = polar(sweepValue);
  const largeArc = sweepValue - startAngle > 180 ? 1 : 0;

  const [needleX, needleY] = polar(sweepValue, r * 0.96);

  return (
    <svg viewBox={`0 0 ${size} ${size}`} className={className} style={{ width: size, height: size, filter: `drop-shadow(0 0 8px ${toneGlow})` }}>
      {/* Background arc */}
      <path
        d={`M ${bgX1} ${bgY1} A ${r} ${r} 0 1 1 ${bgX2} ${bgY2}`}
        fill="none"
        stroke="var(--border)"
        strokeWidth={size * 0.06}
        strokeLinecap="round"
      />
      {/* Foreground arc — coloured by retention bucket */}
      <path
        d={`M ${fgX1} ${fgY1} A ${r} ${r} 0 ${largeArc} 1 ${fgX2} ${fgY2}`}
        fill="none"
        stroke={tone}
        strokeWidth={size * 0.06}
        strokeLinecap="round"
        style={{ transition: "all 600ms cubic-bezier(0.16, 1, 0.3, 1)" }}
      />
      {/* Needle */}
      <line x1={cx} y1={cy} x2={needleX} y2={needleY} stroke={tone} strokeWidth={1.5} strokeLinecap="round" />
      <circle cx={cx} cy={cy} r={size * 0.045} fill={tone} />

      {/* Big number */}
      <text x={cx} y={cy - size * 0.05} textAnchor="middle" fontFamily="JetBrains Mono, monospace" fontSize={size * 0.22} fontWeight="700" fill={tone}>
        {pct}
      </text>
      <text x={cx} y={cy + size * 0.10} textAnchor="middle" fontFamily="JetBrains Mono, monospace" fontSize={size * 0.07} fill="var(--muted)">
        % {label}
      </text>
    </svg>
  );
}
