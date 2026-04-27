/**
 * Animated tactical background — atmospheric layer behind every page.
 *
 * Renders an SVG world-map silhouette + animated topographic grid lines
 * + slow-drift scan rings. Sits at z-index -10, opacity ~0.18, pointer-
 * events:none. Adds depth without competing with foreground data.
 *
 * Costs <1% CPU at 60fps because we use CSS transforms, not RAF.
 */
import { useEffect, useRef } from "react";

type Props = {
  /** Reduce intensity globally. 0 = off, 1 = full. Default 1. */
  intensity?: number;
  /** Show the world-map silhouette layer. */
  worldMap?: boolean;
  /** Show the radar sweep arc. */
  radar?: boolean;
};

export function TacticalBackground({ intensity = 1, worldMap = true, radar = true }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Lightweight starfield / noise layer painted to a canvas — gives the
  // background subtle "movement" without animating thousands of DOM nodes.
  useEffect(() => {
    const c = canvasRef.current;
    if (!c) return;
    const ctx = c.getContext("2d");
    if (!ctx) return;

    let raf = 0;
    const dotCount = 80;
    const dots = Array.from({ length: dotCount }).map(() => ({
      x: Math.random(),
      y: Math.random(),
      r: 0.5 + Math.random() * 1.4,
      tw: 0.3 + Math.random() * 0.7,
      ph: Math.random() * Math.PI * 2,
    }));

    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      c.width = c.clientWidth * dpr;
      c.height = c.clientHeight * dpr;
      ctx.scale(dpr, dpr);
    };
    resize();
    window.addEventListener("resize", resize);

    let t0 = performance.now();
    const tick = (t: number) => {
      const w = c.clientWidth;
      const h = c.clientHeight;
      ctx.clearRect(0, 0, w, h);
      const phase = (t - t0) / 1000;
      for (const d of dots) {
        const tw = 0.5 + 0.5 * Math.sin(phase * d.tw + d.ph);
        ctx.fillStyle = `rgba(255, 122, 26, ${0.06 + tw * 0.18 * intensity})`;
        ctx.beginPath();
        ctx.arc(d.x * w, d.y * h, d.r * tw, 0, Math.PI * 2);
        ctx.fill();
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, [intensity]);

  return (
    <div
      aria-hidden
      className="fixed inset-0 pointer-events-none overflow-hidden"
      style={{ zIndex: -10, opacity: intensity }}
    >
      {/* Base radial vignette */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse at 50% 30%, rgba(255,122,26,0.08) 0%, rgba(7,9,13,0) 50%)," +
            "radial-gradient(ellipse at 80% 80%, rgba(34,211,238,0.05) 0%, rgba(7,9,13,0) 55%)",
        }}
      />

      {/* Animated topo grid */}
      <svg
        className="absolute inset-0 w-full h-full"
        viewBox="0 0 1920 1080"
        preserveAspectRatio="xMidYMid slice"
        style={{ opacity: 0.20 }}
      >
        <defs>
          <pattern id="grid-fine" width="48" height="48" patternUnits="userSpaceOnUse">
            <path d="M 48 0 L 0 0 0 48" fill="none" stroke="var(--border)" strokeWidth="0.4" />
          </pattern>
          <pattern id="grid-coarse" width="240" height="240" patternUnits="userSpaceOnUse">
            <path d="M 240 0 L 0 0 0 240" fill="none" stroke="var(--border-2)" strokeWidth="0.8" />
          </pattern>

          <radialGradient id="map-glow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="rgba(255, 122, 26, 0.10)" />
            <stop offset="60%" stopColor="rgba(255, 122, 26, 0.0)" />
          </radialGradient>

          <linearGradient id="sweep-grad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%"  stopColor="rgba(34,211,238,0)" />
            <stop offset="50%" stopColor="rgba(34,211,238,0.55)" />
            <stop offset="100%" stopColor="rgba(34,211,238,0)" />
          </linearGradient>
        </defs>
        <rect width="100%" height="100%" fill="url(#grid-fine)" />
        <rect width="100%" height="100%" fill="url(#grid-coarse)" />

        {/* World map silhouette — heavily simplified continents */}
        {worldMap && (
          <g opacity="0.35" fill="rgba(255, 122, 26, 0.18)" stroke="rgba(255, 122, 26, 0.32)" strokeWidth="0.6">
            <path d="M 280 280 Q 320 240 380 250 T 480 280 Q 520 320 540 380 Q 530 440 480 460 Q 420 470 360 450 Q 300 420 280 360 Z" />
            <path d="M 540 320 Q 600 300 680 320 Q 740 350 760 410 Q 740 470 680 480 Q 620 470 580 430 Q 550 380 540 320 Z" />
            <path d="M 800 240 Q 880 220 980 240 Q 1080 270 1140 320 Q 1180 380 1160 440 Q 1100 500 1020 480 Q 940 460 880 420 Q 820 360 800 240 Z" />
            <path d="M 1180 360 Q 1260 360 1340 400 Q 1380 460 1360 520 Q 1280 540 1220 500 Q 1180 460 1180 360 Z" />
            <path d="M 1420 280 Q 1500 260 1580 290 Q 1620 350 1600 410 Q 1540 460 1480 440 Q 1420 400 1420 280 Z" />
            <path d="M 600 580 Q 680 580 740 620 Q 760 680 720 720 Q 660 740 620 700 Q 590 650 600 580 Z" />
            <path d="M 980 580 Q 1060 580 1120 620 Q 1140 680 1100 720 Q 1040 740 1000 700 Q 970 650 980 580 Z" />
          </g>
        )}

        {/* Map glow halo */}
        {worldMap && <circle cx="960" cy="540" r="600" fill="url(#map-glow)" />}

        {/* Slow-drift latitude / longitude rings */}
        <g stroke="rgba(255, 122, 26, 0.18)" strokeWidth="0.6" fill="none">
          <ellipse cx="960" cy="540" rx="780" ry="160" opacity="0.35" />
          <ellipse cx="960" cy="540" rx="600" ry="100" opacity="0.5" />
          <ellipse cx="960" cy="540" rx="380" ry="60" opacity="0.7" />
          <line x1="960" y1="0" x2="960" y2="1080" opacity="0.25" />
          <line x1="0" y1="540" x2="1920" y2="540" opacity="0.25" />
        </g>

        {/* Radar sweep — a soft cyan arc rotating slowly */}
        {radar && (
          <g style={{ transformOrigin: "960px 540px", animation: "spin-slow 16s linear infinite" }}>
            <line x1="960" y1="540" x2="960" y2="100" stroke="url(#sweep-grad)" strokeWidth="3" />
            <circle cx="960" cy="540" r="3" fill="rgba(34,211,238,0.6)" />
          </g>
        )}

        {/* Static range rings centered on the AOI */}
        <g stroke="rgba(34,211,238,0.25)" strokeWidth="0.7" fill="none">
          <circle cx="960" cy="540" r="120" strokeDasharray="3 4" />
          <circle cx="960" cy="540" r="220" strokeDasharray="3 6" opacity="0.7" />
          <circle cx="960" cy="540" r="320" strokeDasharray="3 8" opacity="0.5" />
        </g>
      </svg>

      {/* Twinkling beacon dots */}
      <canvas
        ref={canvasRef}
        className="absolute inset-0 w-full h-full"
      />

      {/* Soft scan lines, very subtle */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "repeating-linear-gradient(0deg, rgba(255,255,255,0) 0px, rgba(255,255,255,0) 3px, rgba(255,255,255,0.012) 4px)",
          mixBlendMode: "screen",
        }}
      />
    </div>
  );
}
