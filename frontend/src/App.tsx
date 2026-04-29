import { useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { Activity, AlertTriangle, Crosshair, GitCompareArrows, HeartPulse, Inbox, LayoutGrid, Map, MessageCircle, Network, ScrollText, Shield, Target } from "lucide-react";
import type { LucideIcon } from "lucide-react";
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
import CounterDrone from "./pages/CounterDrone";
import PublicReports from "./pages/PublicReports";
import Health from "./pages/Health";
import { SplashBoot, shouldShowSplash } from "./components/SplashBoot";
import { Sidebar } from "./components/Sidebar";
import { TacticalBackground } from "./components/TacticalBackground";
import { OnboardingTour } from "./components/OnboardingTour";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { CommandPalette } from "./components/CommandPalette";
import { HelpOverlay } from "./components/HelpOverlay";
import { CritCascadeListener, CritSweep } from "./components/CritCascade";
import { useDemoMode } from "./lib/demoMode";

// v3.0/D3.1 — Two-group navigation IA.
// "operations" = the operational story arc (always visible).
// "operator"   = internal/admin pages, hidden when Demo Mode is ON.
// Routes are intentionally unchanged — only display labels and grouping
// are adjusted. OnboardingTour selectors (a[href="/command"] etc.) keep
// resolving because the routes themselves are stable.
export type NavItem = { to: string; label: string; icon: LucideIcon };
export type NavGroup = {
  group: "operations" | "operator";
  label: string;
  items: NavItem[];
};

export const NAV: NavGroup[] = [
  {
    group: "operations",
    label: "OPERATIONS",
    items: [
      { to: "/command",     label: "Command",       icon: LayoutGrid },
      { to: "/mission",     label: "Mission",       icon: Target },
      { to: "/map",         label: "Map",           icon: Map },
      { to: "/alerts",         label: "Threats",            icon: AlertTriangle },
      { to: "/counter-drone",  label: "Counter-Drone",      icon: Crosshair },
      { to: "/audit",          label: "Audit Ledger",       icon: ScrollText },
      { to: "/adversarial", label: "Adversarial",   icon: Shield },
      { to: "/federated",   label: "Federated",     icon: Network },
      { to: "/benchmark",   label: "Benchmark",     icon: Activity },
      { to: "/chat",        label: "Brief",         icon: MessageCircle },
    ],
  },
  {
    group: "operator",
    label: "OPERATOR",
    items: [
      { to: "/diff",            label: "Mission Diff",   icon: GitCompareArrows },
      { to: "/public-reports",  label: "Public Reports", icon: Inbox },
      { to: "/health",          label: "Health",         icon: HeartPulse },
    ],
  },
];

export default function App() {
  const [demo] = useDemoMode();
  // Demo mode skips splash + onboarding so judges land on a populated console.
  const [showingSplash, setShowingSplash] = useState<boolean>(() => !demo && shouldShowSplash());
  if (showingSplash) {
    return <SplashBoot onDone={() => setShowingSplash(false)} />;
  }
  return (
    <div className="h-full flex relative">
      <TacticalBackground intensity={1} />
      <Sidebar groups={NAV} />

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
          <Route path="/counter-drone" element={<ErrorBoundary scope="counter-drone"><CounterDrone /></ErrorBoundary>} />
          <Route path="/public-reports" element={<ErrorBoundary scope="public-reports"><PublicReports /></ErrorBoundary>} />
          <Route path="/health" element={<ErrorBoundary scope="health"><Health /></ErrorBoundary>} />
        </Routes>
      </main>
      {!demo && <OnboardingTour />}
      <CommandPalette />
      <HelpOverlay />
      <CritCascadeListener />
      <CritSweep />
      {demo && (
        <div className="fixed top-2 left-1/2 -translate-x-1/2 z-[10000] flex items-center gap-2 px-3 py-1 rounded-full glass-strong border border-accent/40 shadow-glow-accent text-2xs font-mono text-accent uppercase-wide tracking-wider pointer-events-none">
          <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
          DEMO MODE
        </div>
      )}
    </div>
  );
}
