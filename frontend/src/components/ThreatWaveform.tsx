/**
 * ThreatWaveform — audio-style bar visualization of N alert threat scores.
 *
 * Renders one vertical bar per alert, height ∝ threat_score, color tinted
 * by severity. Newest alerts on the right. Subtle scan-line pulse on the
 * tallest bars draws the eye like a real waveform monitor.
 */
type Props = {
  scores: number[];      // 0..1 each
  height?: number;       // px
  className?: string;
};

export function ThreatWaveform({ scores, height = 56, className = "" }: Props) {
  if (scores.length === 0) {
    return (
      <div className={`flex items-center justify-center text-2xs text-muted2 font-mono uppercase-wide tracking-wider ${className}`} style={{ height }}>
        — no alerts in queue —
      </div>
    );
  }
  const w = 100; // viewbox width units, will scale to container
  const barW = w / Math.max(scores.length, 1);
  return (
    <svg
      viewBox={`0 0 ${w} ${height}`}
      preserveAspectRatio="none"
      className={`w-full ${className}`}
      style={{ height }}
      aria-hidden="true"
    >
      {scores.map((s, i) => {
        const h = Math.max(2, s * (height - 4));
        const tone =
          s >= 0.75 ? "var(--threat-crit)"
          : s >= 0.55 ? "var(--threat-high)"
          : s >= 0.35 ? "var(--threat-med)"
          : "var(--threat-low)";
        const x = i * barW + 0.5;
        const y = (height - h) / 2;
        return (
          <rect
            key={i}
            x={x}
            y={y}
            width={Math.max(0.5, barW - 1)}
            height={h}
            fill={tone}
            opacity={s >= 0.55 ? 0.95 : 0.6}
          >
            {s >= 0.85 && (
              <animate attributeName="opacity" values="0.95;0.55;0.95" dur="1.4s" repeatCount="indefinite" />
            )}
          </rect>
        );
      })}
      {/* Center reference line */}
      <line x1={0} x2={w} y1={height / 2} y2={height / 2} stroke="var(--border-2)" strokeWidth={0.3} />
    </svg>
  );
}
