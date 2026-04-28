import { useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { Activity, AlertTriangle, GitCompareArrows, LayoutGrid, Map, MessageCircle, Network, ScrollText, Shield, Target } from "lucide-react";
import Command from "./pages/Command";
import Mission from "./pages/Mission";
import MapView from "./pages/MapView";
import Alerts from "./pages/Alerts";
import Audit from "./pages/Audit";
import Benchmark from "./pages/Benchmark";
import Adversarial from "./pages/Adversarial";
import Federated from "./pages/Federated";
import MissionDiff from "./pages/MissionDiff";
import Login from "./pages/Login";
import Chat from "./pages/Chat";
import { SplashBoot, shouldShowSplash } from "./components/SplashBoot";
import { Sidebar } from "./components/Sidebar";
import { TacticalBackground } from "./components/TacticalBackground";
import { OnboardingTour } from "./components/OnboardingTour";
import { ErrorBoundary } from "./components/ErrorBoundary";

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
  { to: "/chat", label: "Chat", icon: MessageCircle },
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
          <Route path="/command" element={<ErrorBoundary scope="command"><Command /></ErrorBoundary>} />
          <Route path="/mission" element={<ErrorBoundary scope="mission"><Mission /></ErrorBoundary>} />
          <Route path="/map" element={<ErrorBoundary scope="map"><MapView /></ErrorBoundary>} />
          <Route path="/alerts" element={<ErrorBoundary scope="alerts"><Alerts /></ErrorBoundary>} />
          <Route path="/audit" element={<ErrorBoundary scope="audit"><Audit /></ErrorBoundary>} />
          <Route path="/benchmark" element={<ErrorBoundary scope="benchmark"><Benchmark /></ErrorBoundary>} />
          <Route path="/adversarial" element={<ErrorBoundary scope="adversarial"><Adversarial /></ErrorBoundary>} />
          <Route path="/federated" element={<ErrorBoundary scope="federated"><Federated /></ErrorBoundary>} />
          <Route path="/diff" element={<ErrorBoundary scope="diff"><MissionDiff /></ErrorBoundary>} />
          <Route path="/login" element={<ErrorBoundary scope="login"><Login /></ErrorBoundary>} />
          <Route path="/chat" element={<ErrorBoundary scope="chat"><Chat /></ErrorBoundary>} />
        </Routes>
      </main>
      <OnboardingTour />
    </div>
  );
}
