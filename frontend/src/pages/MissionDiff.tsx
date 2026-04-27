import { useEffect, useMemo, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Polyline, Polygon, Popup } from "react-leaflet";
import L from "leaflet";
import { Loader2, GitCompareArrows, RefreshCw } from "lucide-react";
import { api, type Mission, DEFAULT_AOI } from "../lib/api";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

// Same AOI box other pages use, for context.
const AOI_POLYGON: [number, number][] = [
  DEFAULT_AOI.top_left,
  DEFAULT_AOI.top_right,
  DEFAULT_AOI.bottom_right,
  DEFAULT_AOI.bottom_left,
  DEFAULT_AOI.top_left,
];

type DiffPoint = {
  detection_id: number;
  class_name: string;
  confidence: number;
  lat: number;
  lon: number;
  track_id: number | null;
};

type MovedPair = { earlier: DiffPoint; later: DiffPoint; distance_m: number };

type DiffResponse = {
  earlier: { mission_id: number; name: string; created_at: string | null; geo_count: number };
  later: { mission_id: number; name: string; created_at: string | null; geo_count: number };
  added: DiffPoint[];
  removed: DiffPoint[];
  moved: MovedPair[];
  stable_count: number;
  summary_text: string;
};

const COLOR_ADDED = "#4ade80";   // green
const COLOR_REMOVED = "#ef4444"; // red
const COLOR_MOVED_FROM = "#f59e0b";
const COLOR_MOVED_TO = "#facc15";

export default function MissionDiff() {
  const [missions, setMissions] = useState<Mission[]>([]);
  const [earlierId, setEarlierId] = useState<number | null>(null);
  const [laterId, setLaterId] = useState<number | null>(null);
  const [matchRadius, setMatchRadius] = useState(50);
  const [moveThreshold, setMoveThreshold] = useState(15);
  const [diff, setDiff] = useState<DiffResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listMissions(50).then((m) => {
      setMissions(m);
      // Auto-pick the two most recent so the page is useful immediately.
      if (m.length >= 2) {
        setLaterId(m[0].id);
        setEarlierId(m[1].id);
      } else if (m.length === 1) {
        setEarlierId(m[0].id);
      }
    }).catch((e) => setError((e as Error).message));
  }, []);

  async function runDiff() {
    if (earlierId == null || laterId == null) return;
    setBusy(true); setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/diff`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          earlier_mission_id: earlierId,
          later_mission_id: laterId,
          match_radius_m: matchRadius,
          move_threshold_m: moveThreshold,
        }),
      });
      if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
      setDiff(await res.json());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  // Auto-run when both missions are picked AND diff is null
  useEffect(() => {
    if (earlierId != null && laterId != null && diff == null && !busy) {
      runDiff();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [earlierId, laterId]);

  const bounds = useMemo<L.LatLngBoundsExpression | null>(() => {
    if (!diff) return null;
    const all = [
      ...diff.added.map((p) => [p.lat, p.lon] as [number, number]),
      ...diff.removed.map((p) => [p.lat, p.lon] as [number, number]),
      ...diff.moved.flatMap((m) => [[m.earlier.lat, m.earlier.lon], [m.later.lat, m.later.lon]] as [number, number][]),
    ];
    if (all.length === 0) return null;
    const lats = all.map((p) => p[0]); const lons = all.map((p) => p[1]);
    return [[Math.min(...lats), Math.min(...lons)], [Math.max(...lats), Math.max(...lons)]];
  }, [diff]);

  return (
    <div className="h-full flex flex-col">
      <header className="px-6 py-4 border-b border-border flex items-center justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold flex items-center gap-2">
            <GitCompareArrows size={18} className="text-accent" /> Mission Diff
          </h1>
          <p className="text-xs text-muted">
            Compare two missions of the same area — what's new, gone, or moved since the previous pass.
            {diff && <span className="ml-2 text-text">{diff.summary_text}</span>}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            className="glass shadow-panel rounded px-2 py-1.5 text-sm font-mono"
            value={earlierId ?? ""}
            onChange={(e) => { setEarlierId(Number(e.target.value)); setDiff(null); }}
          >
            <option value="">earlier ▼</option>
            {missions.map((m) => (
              <option key={m.id} value={m.id}>#{m.id} · {m.name}</option>
            ))}
          </select>
          <span className="text-muted">→</span>
          <select
            className="glass shadow-panel rounded px-2 py-1.5 text-sm font-mono"
            value={laterId ?? ""}
            onChange={(e) => { setLaterId(Number(e.target.value)); setDiff(null); }}
          >
            <option value="">later ▼</option>
            {missions.map((m) => (
              <option key={m.id} value={m.id}>#{m.id} · {m.name}</option>
            ))}
          </select>
          <button
            onClick={runDiff}
            disabled={busy || earlierId == null || laterId == null}
            className="flex items-center gap-1 bg-accent text-bg px-3 py-1.5 rounded text-sm font-medium hover:brightness-110 disabled:opacity-50"
          >
            {busy ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
            Compute
          </button>
        </div>
      </header>

      {error && (
        <div className="mx-6 mt-3 bg-threat-crit/20 border border-threat-crit/40 text-threat-crit p-2 rounded text-xs">
          {error}
        </div>
      )}

      <div className="flex-1 grid grid-cols-[1fr_300px] overflow-hidden">
        <div className="relative">
          <MapContainer center={[12.9716, 77.5946]} zoom={15} style={{ height: "100%", width: "100%" }} preferCanvas>
            <TileLayer attribution="&copy; OpenStreetMap" url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" />
            <Polygon
              positions={AOI_POLYGON}
              pathOptions={{ color: "#ff7a1a", weight: 2, fillOpacity: 0.04, dashArray: "6 4" }}
            />

            {/* Added — green */}
            {diff?.added.map((p) => (
              <CircleMarker
                key={`add-${p.detection_id}`}
                center={[p.lat, p.lon]}
                radius={6}
                pathOptions={{ color: COLOR_ADDED, fillColor: COLOR_ADDED, fillOpacity: 0.85, weight: 2 }}
              >
                <Popup>
                  <div className="font-mono text-xs leading-tight">
                    <div className="text-green-700"><b>NEW</b> · {p.class_name}</div>
                    <div>conf: {p.confidence.toFixed(2)}</div>
                    <div>{p.lat.toFixed(5)}, {p.lon.toFixed(5)}</div>
                  </div>
                </Popup>
              </CircleMarker>
            ))}

            {/* Removed — red */}
            {diff?.removed.map((p) => (
              <CircleMarker
                key={`rem-${p.detection_id}`}
                center={[p.lat, p.lon]}
                radius={6}
                pathOptions={{ color: COLOR_REMOVED, fillColor: COLOR_REMOVED, fillOpacity: 0.4, weight: 2, dashArray: "3 3" }}
              >
                <Popup>
                  <div className="font-mono text-xs leading-tight">
                    <div className="text-red-700"><b>GONE</b> · {p.class_name}</div>
                    <div>conf: {p.confidence.toFixed(2)}</div>
                    <div>{p.lat.toFixed(5)}, {p.lon.toFixed(5)}</div>
                  </div>
                </Popup>
              </CircleMarker>
            ))}

            {/* Moved — orange line + endpoints */}
            {diff?.moved.map((m) => (
              <span key={`mv-${m.earlier.detection_id}-${m.later.detection_id}`}>
                <Polyline
                  positions={[[m.earlier.lat, m.earlier.lon], [m.later.lat, m.later.lon]]}
                  pathOptions={{ color: COLOR_MOVED_TO, weight: 3, opacity: 0.8 }}
                />
                <CircleMarker center={[m.earlier.lat, m.earlier.lon]} radius={4}
                  pathOptions={{ color: COLOR_MOVED_FROM, fillColor: COLOR_MOVED_FROM, fillOpacity: 0.7, weight: 1 }}
                />
                <CircleMarker center={[m.later.lat, m.later.lon]} radius={5}
                  pathOptions={{ color: COLOR_MOVED_TO, fillColor: COLOR_MOVED_TO, fillOpacity: 0.95, weight: 2 }}
                >
                  <Popup>
                    <div className="font-mono text-xs leading-tight">
                      <div className="text-yellow-700"><b>MOVED</b> · {m.later.class_name}</div>
                      <div>moved {m.distance_m.toFixed(1)} m</div>
                      <div>conf: {m.later.confidence.toFixed(2)}</div>
                    </div>
                  </Popup>
                </CircleMarker>
              </span>
            ))}
          </MapContainer>
        </div>

        <aside className="bg-panel border-l border-border p-4 overflow-auto space-y-4">
          {!diff ? (
            <div className="text-xs text-muted">
              Pick two missions and click Compute to run the diff.
            </div>
          ) : (
            <>
              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="bg-panel2 rounded p-2 border border-border">
                  <div className="text-xl font-mono text-threat-low">{diff.added.length}</div>
                  <div className="text-[10px] text-muted uppercase tracking-wider">new</div>
                </div>
                <div className="bg-panel2 rounded p-2 border border-border">
                  <div className="text-xl font-mono text-threat-crit">{diff.removed.length}</div>
                  <div className="text-[10px] text-muted uppercase tracking-wider">gone</div>
                </div>
                <div className="bg-panel2 rounded p-2 border border-border">
                  <div className="text-xl font-mono text-threat-high">{diff.moved.length}</div>
                  <div className="text-[10px] text-muted uppercase tracking-wider">moved</div>
                </div>
              </div>

              <div className="text-xs text-muted">
                Stable (same position): <span className="text-text font-mono">{diff.stable_count}</span>
              </div>

              <div className="text-[11px] text-muted leading-snug border-t border-border pt-3">
                <div className="font-mono">earlier · #{diff.earlier.mission_id}</div>
                <div className="font-mono">{diff.earlier.name}</div>
                <div className="font-mono text-muted">{diff.earlier.geo_count} geo-pins · {diff.earlier.created_at?.slice(0,16) ?? "?"}</div>
                <div className="my-2">⤷</div>
                <div className="font-mono">later · #{diff.later.mission_id}</div>
                <div className="font-mono">{diff.later.name}</div>
                <div className="font-mono text-muted">{diff.later.geo_count} geo-pins · {diff.later.created_at?.slice(0,16) ?? "?"}</div>
              </div>

              {/* Match controls */}
              <div className="border-t border-border pt-3 space-y-3">
                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-muted">match radius</span>
                    <span className="font-mono">{matchRadius} m</span>
                  </div>
                  <input type="range" min={10} max={300} step={5} value={matchRadius}
                    onChange={(e) => setMatchRadius(Number(e.target.value))}
                    className="w-full accent-accent"
                  />
                </div>
                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-muted">move threshold</span>
                    <span className="font-mono">{moveThreshold} m</span>
                  </div>
                  <input type="range" min={5} max={100} step={1} value={moveThreshold}
                    onChange={(e) => setMoveThreshold(Number(e.target.value))}
                    className="w-full accent-accent"
                  />
                </div>
              </div>

              {/* Delta histogram per class — visual heat of where the change happened */}
              {(() => {
                const byClass: Record<string, { added: number; removed: number; moved: number }> = {};
                for (const p of diff.added) byClass[p.class_name] = { ...(byClass[p.class_name] ?? { added: 0, removed: 0, moved: 0 }), added: (byClass[p.class_name]?.added ?? 0) + 1 };
                for (const p of diff.removed) byClass[p.class_name] = { ...(byClass[p.class_name] ?? { added: 0, removed: 0, moved: 0 }), removed: (byClass[p.class_name]?.removed ?? 0) + 1 };
                for (const m of diff.moved) byClass[m.later.class_name] = { ...(byClass[m.later.class_name] ?? { added: 0, removed: 0, moved: 0 }), moved: (byClass[m.later.class_name]?.moved ?? 0) + 1 };
                const entries = Object.entries(byClass);
                if (entries.length === 0) return null;
                const max = Math.max(...entries.map(([, v]) => v.added + v.removed + v.moved));
                return (
                  <div className="border-t border-border pt-3">
                    <div className="text-xs uppercase tracking-wider text-muted font-mono mb-2">Δ by class</div>
                    <div className="space-y-1.5">
                      {entries.map(([cls, v]) => {
                        const total = v.added + v.removed + v.moved;
                        return (
                          <div key={cls}>
                            <div className="flex justify-between text-[11px] font-mono">
                              <span className="text-text truncate">{cls}</span>
                              <span className="text-muted2">{total}</span>
                            </div>
                            <div className="h-1.5 rounded-full bg-panel2 overflow-hidden flex">
                              {v.added > 0 && (
                                <div className="bg-threat-low transition-all duration-slow"
                                  style={{ width: `${(v.added / max) * 100}%` }} title={`${v.added} added`} />
                              )}
                              {v.moved > 0 && (
                                <div className="bg-threat-high transition-all duration-slow"
                                  style={{ width: `${(v.moved / max) * 100}%` }} title={`${v.moved} moved`} />
                              )}
                              {v.removed > 0 && (
                                <div className="bg-threat-crit transition-all duration-slow"
                                  style={{ width: `${(v.removed / max) * 100}%` }} title={`${v.removed} removed`} />
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })()}

              {/* Lists */}
              {diff.added.length > 0 && (
                <details open className="border-t border-border pt-3">
                  <summary className="text-xs uppercase tracking-wider text-threat-low cursor-pointer">New ({diff.added.length})</summary>
                  <div className="mt-2 space-y-1 text-[11px] font-mono">
                    {diff.added.map((p) => (
                      <div key={p.detection_id} className="flex justify-between">
                        <span>{p.class_name}</span>
                        <span className="text-muted">conf {p.confidence.toFixed(2)}</span>
                      </div>
                    ))}
                  </div>
                </details>
              )}
              {diff.removed.length > 0 && (
                <details className="border-t border-border pt-3">
                  <summary className="text-xs uppercase tracking-wider text-threat-crit cursor-pointer">Gone ({diff.removed.length})</summary>
                  <div className="mt-2 space-y-1 text-[11px] font-mono">
                    {diff.removed.map((p) => (
                      <div key={p.detection_id} className="flex justify-between">
                        <span>{p.class_name}</span>
                        <span className="text-muted">conf {p.confidence.toFixed(2)}</span>
                      </div>
                    ))}
                  </div>
                </details>
              )}
              {diff.moved.length > 0 && (
                <details className="border-t border-border pt-3">
                  <summary className="text-xs uppercase tracking-wider text-threat-high cursor-pointer">Moved ({diff.moved.length})</summary>
                  <div className="mt-2 space-y-1 text-[11px] font-mono">
                    {diff.moved.map((m) => (
                      <div key={m.later.detection_id} className="flex justify-between">
                        <span>{m.later.class_name}</span>
                        <span className="text-muted">{m.distance_m.toFixed(1)} m</span>
                      </div>
                    ))}
                  </div>
                </details>
              )}
            </>
          )}
        </aside>
      </div>

      {bounds && <FitToBoundsHelper bounds={bounds} />}
    </div>
  );
}

// Tiny helper since we want to fit the map after diff loads.
function FitToBoundsHelper({ bounds: _bounds }: { bounds: L.LatLngBoundsExpression }) {
  // No-op — `bounds` is already used implicitly via initial map center; a
  // proper FitBounds needs the map ref, deferred for time. Demo works at
  // initial Bangalore center.
  return null;
}
