import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { Activity, AlertTriangle, Map, ScrollText, Target } from "lucide-react";
import Mission from "./pages/Mission";
import MapView from "./pages/MapView";
import Alerts from "./pages/Alerts";
import Audit from "./pages/Audit";
import Benchmark from "./pages/Benchmark";

const nav = [
  { to: "/mission", label: "Mission", icon: Target },
  { to: "/map", label: "Map", icon: Map },
  { to: "/alerts", label: "Alerts", icon: AlertTriangle },
  { to: "/audit", label: "Audit", icon: ScrollText },
  { to: "/benchmark", label: "Benchmark", icon: Activity },
];

export default function App() {
  return (
    <div className="h-full flex">
      <aside className="w-56 bg-panel border-r border-border flex flex-col">
        <div className="px-5 py-5 border-b border-border">
          <div className="text-2xl font-bold tracking-wider text-accent">ASTRA</div>
          <div className="text-xs text-muted mt-1">Aerial Surveillance<br />& Threat Recognition</div>
        </div>
        <nav className="flex-1 py-4">
          {nav.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-5 py-2.5 text-sm ${
                  isActive
                    ? "bg-panel2 text-accent border-l-2 border-accent"
                    : "text-muted hover:text-text hover:bg-panel2"
                }`
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="px-5 py-3 border-t border-border text-xs text-muted">
          v0.1.0 · sovereign build
        </div>
      </aside>

      <main className="flex-1 overflow-auto">
        <Routes>
          <Route path="/" element={<Navigate to="/mission" replace />} />
          <Route path="/mission" element={<Mission />} />
          <Route path="/map" element={<MapView />} />
          <Route path="/alerts" element={<Alerts />} />
          <Route path="/audit" element={<Audit />} />
          <Route path="/benchmark" element={<Benchmark />} />
        </Routes>
      </main>
    </div>
  );
}
