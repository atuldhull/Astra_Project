import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup, Polygon, Polyline, Marker, useMap } from "react-leaflet";
import L from "leaflet";
import { Loader2, RefreshCw, Route, Radio, Map as MapIcon, MapPin, Crosshair, GitBranch } from "lucide-react";
import { api, openLiveSocket, type Detection, type Mission, type Track, DEFAULT_AOI } from "../lib/api";
import { PageHeader } from "../components/PageHeader";
import { HeroStat } from "../components/HeroStat";
import { StatusPill } from "../components/StatusPill";
import { Bezel } from "../components/Bezel";
import { HudCornerStat } from "../components/HudOverlay";

// Friendly asset locations (must match backend config.py defaults)
const FRIENDLY_ASSETS: { name: string; lat: number; lon: number }[] = [
  { name: "FOB Delta",     lat: 12.9716, lon: 77.5946 },
  { name: "Outpost Bravo", lat: 12.9750, lon: 77.5900 },
];

// Same class colors as Mission page
const CLASS_COLORS: Record<string, string> = {
  "small-vehicle":       "#4ade80",
  "large-vehicle":       "#facc15",
  "aircraft-fixed-wing": "#60a5fa",
  "aircraft-rotor":      "#a78bfa",
  "ship":                "#22d3ee",
  "storage-depot":       "#fb923c",
  "harbor":              "#f472b6",
  "bridge":              "#94a3b8",
};

// AOI corner polygon (TL, TR, BR, BL) — closed polygon needs TL at end too
const AOI_POLYGON: [number, number][] = [
  DEFAULT_AOI.top_left,
  DEFAULT_AOI.top_right,
  DEFAULT_AOI.bottom_right,
  DEFAULT_AOI.bottom_left,
  DEFAULT_AOI.top_left,
];

// Asset marker icon (distinct from detection pins)
const assetIcon = L.divIcon({
  className: "",
  html: `<div style="
    width:16px;height:16px;background:#22d3ee;border:2px solid #fff;
    border-radius:50%;box-shadow:0 0 8px #22d3ee;
  "></div>`,
  iconSize: [16, 16],
  iconAnchor: [8, 8],
});

function FitToBounds({ bounds }: { bounds: L.LatLngBoundsExpression | null }) {
  const map = useMap();
  useEffect(() => {
    if (bounds) map.fitBounds(bounds, { padding: [30, 30] });
  }, [bounds, map]);
  return null;
}

export default function MapView() {
  const [missions, setMissions] = useState<Mission[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detections, setDetections] = useState<Detection[]>([]);
  const [tracks, setTracks] = useState<Track[]>([]);
  const [showTracks, setShowTracks] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [liveConnected, setLiveConnected] = useState(false);
  const [livePulse, setLivePulse] = useState(0);     // increments on each WS detection — used for radio-icon flash
  const pollRef = useRef<number | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  // Triggers a refetch when an in-flight WS detection arrives. Decoupled
  // from `selectedId` so the effect that owns the polling can honor both.
  const [refetchTick, setRefetchTick] = useState(0);

  // Load missions list on mount + auto-select latest
  useEffect(() => {
    api.listMissions(50)
      .then((m) => {
        setMissions(m);
        if (m.length > 0) {
          // Prefer the one Mission page just saved (stored in localStorage)
          const stored = Number(localStorage.getItem("astra:lastMissionId") ?? "");
          const preferred = m.find((x) => x.id === stored) ?? m[0];
          setSelectedId(preferred.id);
        }
      })
      .catch((e) => setError(`missions: ${(e as Error).message}`));
  }, []);

  // Load detections + tracks when mission changes + set up polling
  useEffect(() => {
    if (selectedId == null) return;
    let cancelled = false;
    const fetchAll = async () => {
      try {
        setLoading(true);
        const [d, t] = await Promise.all([
          api.listDetections({ mission_id: selectedId, limit: 500 }),
          api.listTracks(selectedId).catch(() => [] as Track[]),
        ]);
        if (!cancelled) {
          setDetections(d);
          setTracks(t);
        }
      } catch (e) {
        if (!cancelled) setError(`fetch: ${(e as Error).message}`);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchAll();
    pollRef.current = window.setInterval(fetchAll, 5000);
    return () => {
      cancelled = true;
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, [selectedId, refetchTick]);

  // Live push: subscribe to /ws/live for the lifetime of the page. Each
  // 'detection' event for the currently-selected mission triggers a refetch
  // (cheap — list is capped at 500 rows) and pulses the LIVE indicator.
  // Polling stays as a safety net in case the WS drops.
  useEffect(() => {
    let closed = false;
    let reconnectTimer: number | null = null;

    const connect = () => {
      try {
        const ws = openLiveSocket((msg) => {
          if (closed) return;
          const m = msg as { type?: string; mission_id?: number };
          if (m?.type === "detection" && (selectedId == null || m.mission_id === selectedId)) {
            setLivePulse((p) => p + 1);
            setRefetchTick((t) => t + 1);
          }
        });
        ws.onopen = () => setLiveConnected(true);
        ws.onclose = () => {
          setLiveConnected(false);
          if (!closed) reconnectTimer = window.setTimeout(connect, 2000);
        };
        ws.onerror = () => { /* onclose handles reconnect */ };
        wsRef.current = ws;
      } catch {
        // WS URL invalid or browser blocked — silent fail, polling still works
      }
    };

    connect();
    return () => {
      closed = true;
      if (reconnectTimer) window.clearTimeout(reconnectTimer);
      try { wsRef.current?.close(); } catch { /* noop */ }
    };
  }, [selectedId]);

  const geoDetections = detections.filter((d) => d.lat != null && d.lon != null);

  const bounds: L.LatLngBoundsExpression | null = useMemo(() => {
    if (geoDetections.length === 0) {
      return [
        [DEFAULT_AOI.bottom_left[0], DEFAULT_AOI.bottom_left[1]],
        [DEFAULT_AOI.top_right[0], DEFAULT_AOI.top_right[1]],
      ];
    }
    const lats = geoDetections.map((d) => d.lat!);
    const lons = geoDetections.map((d) => d.lon!);
    return [
      [Math.min(...lats), Math.min(...lons)],
      [Math.max(...lats), Math.max(...lons)],
    ];
  }, [geoDetections]);

  // Class counts for legend
  const counts: Record<string, number> = {};
  for (const d of geoDetections) counts[d.class_name] = (counts[d.class_name] ?? 0) + 1;

  // OOD count for hero stats
  const oodCount = geoDetections.filter((d) => d.extras?.ood_flag).length;

  return (
    <div className="h-full flex flex-col">
      <PageHeader
        icon={MapIcon}
        title="Tactical Map"
        badge={
          <StatusPill
            variant={liveConnected ? "live" : "neutral"}
            size="sm"
            title={liveConnected ? "WebSocket connected — pins pop in real time" : "WebSocket disconnected — 5s polling fallback"}
          >
            <Radio size={9} className="mr-1" key={livePulse} />
            {liveConnected ? "live" : "offline"}
          </StatusPill>
        }
        subtitle={
          <>
            {geoDetections.length} geo-pins
            {tracks.length > 0 && ` · ${tracks.length} tracks`}
            {oodCount > 0 && (<>{' · '}<span className="text-muted">{oodCount} OOD-flagged</span></>)}
            {loading && " · refreshing..."}
          </>
        }
        actions={
          <>
            {tracks.length > 0 && (
              <label className="flex items-center gap-1.5 text-xs text-muted cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={showTracks}
                  onChange={(e) => setShowTracks(e.target.checked)}
                  className="accent-accent"
                />
                <Route size={12} /> Tracks
              </label>
            )}
            <label className="text-xs text-muted">Mission:</label>
            <select
              className="bg-panel border border-border rounded px-3 py-1.5 text-sm font-mono min-w-[220px]"
              value={selectedId ?? ""}
              onChange={(e) => setSelectedId(Number(e.target.value))}
            >
              {missions.length === 0 && <option>(no missions yet)</option>}
              {missions.map((m) => (
                <option key={m.id} value={m.id}>
                  #{m.id} · {m.name}
                </option>
              ))}
            </select>
            <button
              onClick={() => selectedId != null && setSelectedId(selectedId)}
              className="p-1.5 rounded hover:bg-panel2 text-muted transition-fast"
              title="Refresh"
            >
              {loading ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
            </button>
          </>
        }
      />

      {/* Hero KPI strip */}
      <div className="px-6 pt-4 grid grid-cols-4 gap-3">
        <HeroStat
          label="geo-pins"
          value={geoDetections.length}
          icon={MapPin}
          tone={geoDetections.length > 0 ? "cyan" : "neutral"}
          sub={`${detections.length} total dets`}
        />
        <HeroStat
          label="tracks"
          value={tracks.length}
          icon={Route}
          tone={tracks.length > 0 ? "low" : "neutral"}
          sub={tracks.length > 0 ? `avg ${(tracks.reduce((s,t)=>s+t.point_count,0)/tracks.length).toFixed(1)} pts/track` : "no movement"}
        />
        <HeroStat
          label="OOD-flagged"
          value={oodCount}
          icon={Crosshair}
          tone={oodCount > 0 ? "high" : "neutral"}
          sub="conf+aspect+edge"
        />
        <HeroStat
          label="missions"
          value={missions.length}
          icon={GitBranch}
          tone="neutral"
          sub="loaded"
        />
      </div>

      {error && (
        <div className="mx-6 mt-3 bg-threat-crit/20 border border-threat-crit/40 text-threat-crit p-2 rounded text-xs">
          {error}
        </div>
      )}

      <div className="flex-1 px-6 pb-6 pt-3 relative">
        <Bezel
          className="h-full"
          topBar={
            <>
              <span className="text-accent">TAC·MAP</span>
              <span className="text-muted2">AOI</span>
              <span className="text-text">FOB-DELTA</span>
              <span className="text-muted2">PINS</span>
              <span className="tabular-nums text-text">{geoDetections.length}</span>
              <span className="text-muted2">TRK</span>
              <span className="tabular-nums text-text">{tracks.length}</span>
              {oodCount > 0 && (
                <>
                  <span className="text-muted2">OOD</span>
                  <span className="tabular-nums text-threat-high">{oodCount}</span>
                </>
              )}
              <span className="ml-auto text-muted2 tabular-nums">SECTOR 12.97N · 77.59E</span>
            </>
          }
          bottomBar={
            <>
              <span className="text-muted2">PROJ</span>
              <span className="text-text">WGS84</span>
              <span className="text-muted2">SCALE</span>
              <span className="text-text">~500m/grid</span>
              <span className="text-muted2">REFRESH</span>
              <span className="text-text">{liveConnected ? "WS·5s" : "POLL·5s"}</span>
              <span className="ml-auto text-muted2 tabular-nums">{new Date().toLocaleTimeString("en-IN", { hour12: false })}</span>
            </>
          }
        ><div className="relative w-full h-full">
          <HudCornerStat pos="tr" label="LIVE" tone={liveConnected ? "ok" : "warn"} value={liveConnected ? "WS" : "POLL"} />
        <MapContainer
          center={[12.9716, 77.5946]}
          zoom={15}
          style={{ height: "100%", width: "100%" }}
          preferCanvas
        >
          <TileLayer
            attribution="&copy; OpenStreetMap"
            url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          <Polygon
            positions={AOI_POLYGON}
            pathOptions={{ color: "#ff7a1a", weight: 2, fillOpacity: 0.04, dashArray: "6 4" }}
          />

          {FRIENDLY_ASSETS.map((a) => (
            <Marker key={a.name} position={[a.lat, a.lon]} icon={assetIcon}>
              <Popup>
                <div className="font-mono text-xs">
                  <div><b>{a.name}</b></div>
                  <div>Friendly asset</div>
                </div>
              </Popup>
            </Marker>
          ))}

          {/* Track trails: draw polylines for each track with >=2 geo-points */}
          {showTracks && tracks.map((t) => {
            const color = CLASS_COLORS[t.class_name] ?? "#ff7a1a";
            const geoPoints = t.points.filter((p) => p.lat != null && p.lon != null);
            if (geoPoints.length < 2) return null;
            const latlngs: [number, number][] = geoPoints.map((p) => [p.lat!, p.lon!]);
            const last = geoPoints[geoPoints.length - 1];
            return (
              <Fragment key={`track-${t.track_id}`}>
                <Polyline
                  positions={latlngs}
                  pathOptions={{ color, weight: 3, opacity: 0.75, dashArray: "4 2" }}
                />
                {/* Head marker at the latest position, slightly bigger */}
                <CircleMarker
                  center={[last.lat!, last.lon!]}
                  radius={7}
                  pathOptions={{ color: "#fff", fillColor: color, fillOpacity: 1, weight: 2 }}
                >
                  <Popup>
                    <div className="font-mono text-xs leading-tight">
                      <div><b>Track #{t.track_id}</b> · {t.class_name}</div>
                      <div>points: {t.point_count}</div>
                      <div>avg conf: {t.avg_confidence.toFixed(3)}</div>
                      <div>latest: frame {last.frame_index} ({last.frame_timestamp_ms}ms)</div>
                    </div>
                  </Popup>
                </CircleMarker>
              </Fragment>
            );
          })}

          {/* Individual detections: only show ones NOT already in a visible track */}
          {geoDetections
            .filter((d) => !(showTracks && d.track_id != null && tracks.some((t) => t.track_id === d.track_id && t.point_count >= 2)))
            .map((d) => {
              const isOod = !!d.extras?.ood_flag;
              const color = isOod ? "#94a3b8" : (CLASS_COLORS[d.class_name] ?? "#ff7a1a");
              return (
                <CircleMarker
                  key={d.id}
                  center={[d.lat!, d.lon!]}
                  radius={isOod ? 4 : 5}
                  pathOptions={{
                    color,
                    fillColor: color,
                    fillOpacity: isOod ? 0.4 : 0.8,
                    weight: 1,
                    dashArray: isOod ? "3 2" : undefined,
                  }}
                >
                  <Popup>
                    <div className="font-mono text-xs leading-tight">
                      <div>
                        <b>{d.class_name}</b>
                        {d.extras?.ood_flag && (
                          <span className="ml-1 text-gray-500" title={d.extras.ood_reasons?.join(", ")}>
                            ? unknown ({((d.extras.ood_score ?? 0) * 100).toFixed(0)}%)
                          </span>
                        )}
                      </div>
                      {d.extras?.airframe && (
                        <div className="text-blue-600">
                          ⤷ <b>{d.extras.airframe}</b> ({((d.extras.airframe_confidence ?? 0) * 100).toFixed(0)}%)
                        </div>
                      )}
                      <div>conf: {d.confidence.toFixed(2)}</div>
                      <div>lat: {d.lat!.toFixed(5)}</div>
                      <div>lon: {d.lon!.toFixed(5)}</div>
                      {d.track_id != null && <div>track: #{d.track_id}</div>}
                      {d.extras?.ood_reasons && d.extras.ood_reasons.length > 0 && (
                        <div className="text-gray-500 mt-1 italic">{d.extras.ood_reasons.join(" · ")}</div>
                      )}
                    </div>
                  </Popup>
                </CircleMarker>
              );
            })}

          <FitToBounds bounds={bounds} />
        </MapContainer>

        {/* Legend */}
        <div className="absolute bottom-12 left-12 glass-strong rounded-lg p-3 text-xs z-[1000] min-w-[180px]">
          <div className="text-muted uppercase tracking-wider mb-2">Legend</div>
          {Object.entries(counts).length === 0 ? (
            <div className="text-muted">No detections — upload via Mission page</div>
          ) : (
            <div className="space-y-1">
              {Object.entries(counts)
                .sort(([, a], [, b]) => b - a)
                .map(([name, n]) => (
                  <div key={name} className="flex items-center justify-between gap-2 font-mono">
                    <div className="flex items-center gap-2">
                      <span
                        className="w-2.5 h-2.5 rounded-full"
                        style={{ background: CLASS_COLORS[name] ?? "#ff7a1a" }}
                      />
                      <span>{name}</span>
                    </div>
                    <span className="text-accent">{n}</span>
                  </div>
                ))}
              <div className="pt-2 mt-2 border-t border-border flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-[#22d3ee] shadow-[0_0_6px_#22d3ee]" />
                <span>Friendly assets</span>
              </div>
            </div>
          )}
        </div></div></Bezel>
      </div>
    </div>
  );
}
