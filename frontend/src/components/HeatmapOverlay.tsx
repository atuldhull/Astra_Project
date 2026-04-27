/**
 * HeatmapOverlay — additive radial-gradient heatmap painted to a Leaflet
 * canvas pane.
 *
 * Lightweight (no leaflet.heat dep). For each lat/lon point we draw a
 * radial-gradient circle proportional to its threat-score; overlapping
 * blobs stack via lighter blend mode. Tinted from cool→hot.
 */
import { useEffect } from "react";
import { useMap } from "react-leaflet";

type Props = {
  points: { lat: number; lon: number; weight: number }[]; // weight 0..1
  radius?: number;
  visible?: boolean;
};

export function HeatmapOverlay({ points, radius = 40, visible = true }: Props) {
  const map = useMap();

  useEffect(() => {
    if (!visible) return;
    const canvas = document.createElement("canvas");
    canvas.style.position = "absolute";
    canvas.style.top = "0";
    canvas.style.left = "0";
    canvas.style.pointerEvents = "none";
    canvas.style.zIndex = "400"; // below tooltips, above tiles
    canvas.style.mixBlendMode = "screen";
    const pane = map.getPanes().overlayPane;
    pane.appendChild(canvas);
    const ctx = canvas.getContext("2d")!;

    const draw = () => {
      const size = map.getSize();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = size.x * dpr;
      canvas.height = size.y * dpr;
      canvas.style.width = `${size.x}px`;
      canvas.style.height = `${size.y}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, size.x, size.y);

      // Translate the canvas to compensate for the leaflet pane transform
      const tl = map.containerPointToLayerPoint([0, 0]);
      canvas.style.transform = `translate(${-tl.x}px, ${-tl.y}px)`;

      for (const p of points) {
        const w = Math.max(0, Math.min(1, p.weight));
        const ll = map.latLngToContainerPoint([p.lat, p.lon]);
        const r = radius * (0.6 + w * 0.8);
        const grad = ctx.createRadialGradient(ll.x, ll.y, 0, ll.x, ll.y, r);
        const hot = w >= 0.75 ? "239, 68, 68" : w >= 0.55 ? "251, 146, 60" : w >= 0.35 ? "250, 204, 21" : "74, 222, 128";
        grad.addColorStop(0, `rgba(${hot}, ${0.55 * (0.5 + w * 0.5)})`);
        grad.addColorStop(1, `rgba(${hot}, 0)`);
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(ll.x, ll.y, r, 0, Math.PI * 2);
        ctx.fill();
      }
    };

    draw();
    map.on("move zoom resize", draw);

    return () => {
      map.off("move zoom resize", draw);
      try { pane.removeChild(canvas); } catch { /* noop */ }
    };
  }, [map, points, radius, visible]);

  return null;
}
