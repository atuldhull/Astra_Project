/**
 * Sidebar v2.
 *
 * Top: brand mark (animated pulse halo) + version pill.
 * Middle: nav with active-state accent bar + glow.
 * Bottom: real-time status pills — backend health, GPU device, mission count,
 *         alert count, federated state, audit chain status.
 *
 * Collapsible to icon-only mode (CTRL+B or click chevron). Persists
 * collapse state in localStorage.
 *
 * Polls /health every 5s for backend status.
 */
import { useEffect, useMemo, useState } from "react";
import { NavLink } from "react-router-dom";
import { ChevronsLeft, ChevronsRight, Cpu, Shield, Wifi, WifiOff } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { api } from "../lib/api";
import { StatusPill } from "./StatusPill";

const COLLAPSE_KEY = "astra:sidebarCollapsed:v1";

type NavItem = {
  to: string;
  label: string;
  icon: LucideIcon;
  badge?: () => string | number | null;   // optional bottom-right pill on the row
};

type Props = { items: NavItem[] };

type HealthState = {
  ok: boolean;
  device: string | null;
  modelLoaded: boolean | null;
  lastSyncMs: number | null;
};

export function Sidebar({ items }: Props) {
  // Default to expanded; user can collapse and we remember.
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try { return localStorage.getItem(COLLAPSE_KEY) === "1"; } catch { return false; }
  });
  // Slightly narrower expanded width so the dashboard gets more room.
  const [health, setHealth] = useState<HealthState>({ ok: false, device: null, modelLoaded: null, lastSyncMs: null });
  const [missionCount, setMissionCount] = useState<number | null>(null);
  const [alertCount, setAlertCount] = useState<number | null>(null);
  const [chainOk, setChainOk] = useState<boolean | null>(null);

  useEffect(() => {
    try { localStorage.setItem(COLLAPSE_KEY, collapsed ? "1" : "0"); } catch { /* noop */ }
  }, [collapsed]);

  // Health + lightweight count polling
  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const h = await api.health();
        if (cancelled) return;
        setHealth({
          ok: h.status === "ok",
          device: h.device ?? null,
          modelLoaded: !!h.model_loaded,
          lastSyncMs: Date.now(),
        });
      } catch {
        if (!cancelled) setHealth((s) => ({ ...s, ok: false }));
      }
      try {
        const ms = await api.listMissions(50);
        if (!cancelled) setMissionCount(ms.length);
      } catch { /* noop */ }
      try {
        const al = await api.listAlerts({ min_score: 0 });
        if (!cancelled) setAlertCount(al.length);
      } catch { /* noop */ }
      // Audit chain check is a separate endpoint; only ping every 30 s
    };
    tick();
    const handle = window.setInterval(tick, 5000);
    return () => { cancelled = true; window.clearInterval(handle); };
  }, []);

  // Audit chain — slower poll
  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const r = await fetch(`${import.meta.env.VITE_API_BASE_URL ?? ""}/api/v1/audit/verify`);
        if (cancelled || !r.ok) return;
        const v = await r.json();
        setChainOk(!!v.ok);
      } catch { if (!cancelled) setChainOk(null); }
    };
    tick();
    const handle = window.setInterval(tick, 30000);
    return () => { cancelled = true; window.clearInterval(handle); };
  }, []);

  const lastSyncStr = useMemo(() => {
    if (!health.lastSyncMs) return "—";
    const sec = Math.round((Date.now() - health.lastSyncMs) / 1000);
    if (sec < 5) return "live";
    if (sec < 60) return `${sec}s`;
    return `${Math.round(sec / 60)}m`;
  }, [health.lastSyncMs]);

  const widthCls = collapsed ? "w-14" : "w-52";

  return (
    <aside
      className={`${widthCls} shrink-0 bg-panel border-r border-border flex flex-col transition-[width] duration-mid ease-in-out-soft`}
    >
      {/* Brand */}
      <div className="px-4 pt-5 pb-4 border-b border-border flex items-center gap-3">
        <div className="relative shrink-0">
          <div className="absolute inset-0 rounded-md bg-accent/30 blur-md animate-pulse-soft" />
          <div className="relative w-9 h-9 rounded-md border border-accent flex items-center justify-center bg-bg">
            <Shield size={18} strokeWidth={1.5} className="text-accent" />
          </div>
        </div>
        {!collapsed && (
          <div className="min-w-0 flex-1">
            <div className="text-display text-base font-bold tracking-[0.18em] text-text leading-none">ASTRA</div>
            <div className="text-2xs uppercase-wide text-muted2 mt-1 font-mono tracking-wider">v0.3.0</div>
          </div>
        )}
        <button
          onClick={() => setCollapsed((c) => !c)}
          className="ml-auto p-1.5 text-muted hover:text-text rounded transition-fast"
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronsRight size={14} /> : <ChevronsLeft size={14} />}
        </button>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-3 overflow-y-auto">
        {items.map(({ to, label, icon: Icon, badge }) => {
          const badgeVal = badge?.() ?? null;
          return (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `relative flex items-center gap-3 px-4 py-2.5 text-sm transition-fast group ${
                  isActive
                    ? "bg-panel2 text-accent"
                    : "text-muted hover:text-text hover:bg-panel2/60"
                }`
              }
              title={collapsed ? label : undefined}
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <span className="absolute left-0 top-1.5 bottom-1.5 w-[3px] bg-accent rounded-r shadow-glow-accent" />
                  )}
                  <Icon size={16} className="shrink-0" />
                  {!collapsed && (
                    <>
                      <span className="flex-1 truncate">{label}</span>
                      {badgeVal != null && badgeVal !== "" && (
                        <span className="text-2xs text-muted font-mono tabular-nums">{badgeVal}</span>
                      )}
                    </>
                  )}
                </>
              )}
            </NavLink>
          );
        })}
      </nav>

      {/* Status block — bottom */}
      <div className="border-t border-border px-3 py-3 space-y-2 bg-bg/50">
        {!collapsed ? (
          <>
            {/* Backend status */}
            <div className="flex items-center justify-between text-2xs">
              <span className="flex items-center gap-1.5 text-muted">
                {health.ok ? <Wifi size={11} className="text-threat-low" /> : <WifiOff size={11} className="text-threat-crit" />}
                <span className="font-mono uppercase-wide">backend</span>
              </span>
              <StatusPill variant={health.ok ? "live" : "err"} size="sm">
                {health.ok ? "online" : "down"}
              </StatusPill>
            </div>

            {/* GPU */}
            {health.ok && health.device && (
              <div className="flex items-center justify-between text-2xs">
                <span className="flex items-center gap-1.5 text-muted">
                  <Cpu size={11} className="text-cyan" />
                  <span className="font-mono uppercase-wide">device</span>
                </span>
                <span className="font-mono text-2xs text-text truncate max-w-[120px]" title={health.device}>
                  {health.device}
                </span>
              </div>
            )}

            {/* Counts */}
            <div className="flex items-center justify-between text-2xs">
              <span className="font-mono text-muted uppercase-wide">missions</span>
              <span className="font-mono tabular-nums text-text">{missionCount ?? "—"}</span>
            </div>
            <div className="flex items-center justify-between text-2xs">
              <span className="font-mono text-muted uppercase-wide">alerts</span>
              <span className="font-mono tabular-nums text-text">{alertCount ?? "—"}</span>
            </div>

            {/* Audit chain */}
            <div className="flex items-center justify-between text-2xs">
              <span className="font-mono text-muted uppercase-wide">audit</span>
              <StatusPill variant={chainOk == null ? "neutral" : chainOk ? "ok" : "err"} size="sm">
                {chainOk == null ? "?" : chainOk ? "chain ok" : "broken"}
              </StatusPill>
            </div>

            <div className="flex items-center justify-between text-2xs pt-1 border-t border-border">
              <span className="font-mono text-muted2 uppercase-wide">last sync</span>
              <span className="font-mono tabular-nums text-muted2">{lastSyncStr}</span>
            </div>
          </>
        ) : (
          // Compact: a vertical stack of dots
          <div className="flex flex-col items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${health.ok ? "bg-threat-low animate-pulse-soft" : "bg-threat-crit"}`} title={health.ok ? "Backend online" : "Backend down"} />
            <span className={`w-2 h-2 rounded-full ${chainOk ? "bg-threat-low" : chainOk === false ? "bg-threat-crit" : "bg-muted"}`} title={chainOk ? "Audit chain ok" : chainOk === false ? "Audit chain broken" : "Audit not checked"} />
          </div>
        )}
      </div>
    </aside>
  );
}
