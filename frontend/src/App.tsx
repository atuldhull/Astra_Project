import { useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { Activity, AlertTriangle, GitCompareArrows, LayoutGrid, Map, Network, ScrollText, Shield, Target } from "lucide-react";
import Command from "./pages/Command";
import Mission from "./pages/Mission";
import MapView from "./pages/MapView";
import Alerts from "./pages/Alerts";
import Audit from "./pages/Audit";
import Benchmark from "./pages/Benchmark";
import Adversarial from "./pages/Adversarial";
import Federated from "./pages/Federated";
import MissionDiff from "./pages/MissionDiff";
import { SplashBoot, shouldShowSplash } from "./components/SplashBoot";
import { Sidebar } from "./components/Sidebar";
import { TacticalBackground } from "./components/TacticalBackground";

const nav = [
  { to: "/command", label: "Command", icon: LayoutGrid },
  { to: "/mission", label: "Mission", icon: Target },
  { to: "/map", label: "Map", icon: Map },
  { to: "/alerts", label: "Alerts", icon: AlertTriangle },
  { to: "/audit", label: "Audit", icon: ScrollText },
  { to: "/benchmark", label: "Benchmark", icon: Activity },
  { to: "/adversarial", label: "Adversarial", icon: Shield },
  { to: "/federated", label: "Federated", icon: Network },
  { to: "/diff", label: "Diff", icon: GitCompareArrows },
];

export default function App() {
  const [showingSplash, setShowingSplash] = useState<boolean>(() => shouldShowSplash());
  if (showingSplash) {
    return <SplashBoot onDone={() => setShowingSplash(false)} />;
  }
  return (
    <div className="h-full flex relative">
      <TacticalBackground intensity={1} />
      <Sidebar items={nav} />

      <main className="flex-1 overflow-auto">
        <Routes>
          <Route path="/" element={<Navigate to="/command" replace />} />
          <Route path="/command" element={<Command />} />
          <Route path="/mission" element={<Mission />} />
          <Route path="/map" element={<MapView />} />
          <Route path="/alerts" element={<Alerts />} />
          <Route path="/audit" element={<Audit />} />
          <Route path="/benchmark" element={<Benchmark />} />
          <Route path="/adversarial" element={<Adversarial />} />
          <Route path="/federated" element={<Federated />} />
          <Route path="/diff" element={<MissionDiff />} />
        </Routes>
      </main>
    </div>
  );
}
