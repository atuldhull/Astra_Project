/**
 * Tiny inline sparkline — for HeroStat trend visuals.
 *
 * SVG path, no Recharts dep (Recharts is overkill for a 50-point trace).
 * Used inside HeroStat / sidebar pills to show last-N values trend.
 */

type Props = {
  data: number[];
  width?: number;
  height?: number;
  stroke?: string;
  fill?: string;
  className?: string;
};

export function Sparkline({
  data,
  width = 80,
  height = 22,
  stroke = "var(--accent)",
  fill = "none",
  className = "",
}: Props) {
  if (!data || data.length < 2) {
    return <svg width={width} height={height} className={className} />;
  }
  const min = Math.min(...data);
  const max = Math.max(...data);
  const span = max - min || 1;
  const dx = width / (data.length - 1);
  const points = data
    .map((v, i) => {
      const x = i * dx;
      const y = height - ((v - min) / span) * (height - 2) - 1;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  // For filled area, append closing path back to the baseline
  const filledPath =
    fill !== "none"
      ? `M ${points.split(" ")[0]} L ${points.split(" ").join(" L ")} L ${width},${height} L 0,${height} Z`
      : `M ${points.split(" ")[0]} L ${points.split(" ").join(" L ")}`;

  return (
    <svg width={width} height={height} className={className} aria-hidden="true">
      <path
        d={filledPath}
        stroke={stroke}
        strokeWidth={1.4}
        fill={fill}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
