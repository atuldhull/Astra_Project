import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import L from "leaflet";

// Fix default marker icon path (Vite doesn't bundle leaflet images)
delete (L.Icon.Default.prototype as unknown as { _getIconUrl?: unknown })._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

const DEMO_CENTER: [number, number] = [12.9716, 77.5946]; // Bengaluru
const DEMO_PINS = [
  { lat: 12.972, lon: 77.590, cls: "tank", score: 0.82 },
  { lat: 12.968, lon: 77.598, cls: "large-vehicle", score: 0.54 },
  { lat: 12.974, lon: 77.593, cls: "aircraft-rotor", score: 0.71 },
];

export default function MapView() {
  return (
    <div className="h-full flex flex-col">
      <header className="px-6 py-4 border-b border-border">
        <h1 className="text-lg font-semibold">Tactical Map</h1>
        <p className="text-xs text-muted">Geo-referenced detections over the current AOI</p>
      </header>
      <div className="flex-1">
        <MapContainer center={DEMO_CENTER} zoom={14} style={{ height: "100%", width: "100%" }}>
          <TileLayer
            attribution='&copy; OpenStreetMap'
            url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {DEMO_PINS.map((p, i) => (
            <Marker key={i} position={[p.lat, p.lon]}>
              <Popup>
                <div className="font-mono text-xs">
                  <div><b>{p.cls}</b></div>
                  <div>threat: {p.score.toFixed(2)}</div>
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>
    </div>
  );
}
