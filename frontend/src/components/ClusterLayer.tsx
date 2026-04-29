/**
 * ClusterLayer (D4.5) — zoom-aware grid clustering for the Map page.
 *
 * Pure-JS, no dep beyond what's already shipped (react-leaflet +
 * leaflet). At higher zooms the grid cell shrinks; clusters with
 * count <= 1 fall through to the supplied per-point renderer.
 *
 * Each cluster is rendered as a filled CircleMarker with a divIcon
 * label showing the count. Click a cluster → fitBounds onto its
 * member envelope. Avoids the 500-marker DOM-stress that the Map
 * page used to hit during the worst-case ingest.
 */
import { useMap, CircleMarker, Marker, Tooltip } from "react-leaflet";
import L from "leaflet";
import { useMemo, useState, useEffect } from "react";

export type ClusterPoint = {
  id: number | string;
  lat: number;
  lon: number;
  /** Optional severity / class colour hint for the cluster halo. */
  hint?: string;
  /** D5.2 — per-point threat score 0..1. Cluster halo colour = max
   *  threat in the bucket so a 30-marker cluster with one crit reads
   *  red, not cyan. */
  threat?: number;
};

type Props = {
  points: ClusterPoint[];
  /** Per-point fallback renderer for clusters of size 1. */
  renderPoint: (p: ClusterPoint) => React.ReactNode;
  /** Approximate grid cell size in screen pixels. Default 60px. */
  cellPx?: number;
  /** Skip clustering when total points < this. Default 30 — below it
   *  the marker layer is fine on its own. */
  minPointsToCluster?: number;
};

export function ClusterLayer({ points, renderPoint, cellPx = 60, minPointsToCluster = 30 }: Props) {
  const map = useMap();
  const [zoom, setZoom] = useState(() => map.getZoom());

  // Re-cluster on zoom change.
  useEffect(() => {
    const onZoom = () => setZoom(map.getZoom());
    map.on("zoomend", onZoom);
    return () => { map.off("zoomend", onZoom); };
  }, [map]);

  const buckets = useMemo(() => {
    if (points.length < minPointsToCluster) return null;

    // Convert each point to layer-space pixels at the current zoom, bucket
    // by floor(px / cellPx). This is what leaflet.markercluster does in
    // spirit, but at a fraction of the bundle size.
    const bucketMap = new Map<string, ClusterPoint[]>();
    for (const p of points) {
      const pix = map.project([p.lat, p.lon], zoom);
      const cx = Math.floor(pix.x / cellPx);
      const cy = Math.floor(pix.y / cellPx);
      const k = `${cx}:${cy}`;
      const arr = bucketMap.get(k);
      if (arr) arr.push(p); else bucketMap.set(k, [p]);
    }
    return Array.from(bucketMap.values());
  }, [points, zoom, cellPx, map, minPointsToCluster]);

  if (!buckets) {
    // Pass-through: just render every point individually.
    return <>{points.map(renderPoint)}</>;
  }

  return (
    <>
      {buckets.map((bucket) => {
        if (bucket.length === 1) {
          return renderPoint(bucket[0]);
        }
        // Compute the cluster centroid + a bounding envelope for click-zoom.
        let sumLat = 0, sumLon = 0;
        let minLat = Infinity, minLon = Infinity, maxLat = -Infinity, maxLon = -Infinity;
        for (const p of bucket) {
          sumLat += p.lat; sumLon += p.lon;
          if (p.lat < minLat) minLat = p.lat;
          if (p.lat > maxLat) maxLat = p.lat;
          if (p.lon < minLon) minLon = p.lon;
          if (p.lon > maxLon) maxLon = p.lon;
        }
        const cLat = sumLat / bucket.length;
        const cLon = sumLon / bucket.length;
        const ids = bucket.map((b) => b.id).join(":");
        const radius = Math.min(28, 12 + Math.log2(bucket.length) * 4);
        // D5.2 — colour by worst threat in the bucket.
        const worst = bucket.reduce((m, b) => Math.max(m, b.threat ?? 0), 0);
        const colour =
          worst >= 0.75 ? "#ef4444"     // crit
          : worst >= 0.55 ? "#fb923c"   // high
          : worst >= 0.35 ? "#facc15"   // med
          : "#22d3ee";                  // low / unknown
        return (
          <CircleMarker
            key={`cluster:${ids}`}
            center={[cLat, cLon]}
            radius={radius}
            pathOptions={{
              color: colour,
              fillColor: colour,
              fillOpacity: 0.35,
              weight: 2,
            }}
            eventHandlers={{
              click: () => {
                if (bucket.length > 1) {
                  map.fitBounds(L.latLngBounds([minLat, minLon], [maxLat, maxLon]).pad(0.4));
                }
              },
            }}
          >
            <Tooltip permanent direction="center" offset={[0, 0]} className="cluster-count-tooltip">
              <span className="font-mono text-xs font-semibold text-bg">{bucket.length}</span>
            </Tooltip>
          </CircleMarker>
        );
      })}
    </>
  );
}

// Suppress unused import warnings — Marker is re-exported for consumers
// that want the same dep without importing react-leaflet themselves.
export { Marker as _Marker };
