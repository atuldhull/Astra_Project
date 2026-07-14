/**
 * CommandPalette — global keyboard launcher (⌘K / Ctrl+K).
 *
 * Indexes:
 *   • every sidebar page (deterministic, hard-coded)
 *   • the 50 most-recent missions (loaded lazily on first open)
 *   • the 25 most-recent alerts (loaded lazily on first open)
 *   • quick actions: verify chain, anchor now, toggle demo mode
 *
 * Fuzzy matcher: case-insensitive substring on label + sub. Sorted by
 * static priority (action > page > mission > alert).
 *
 * Keyboard:
 *   • ⌘K / Ctrl+K: open
 *   • Esc:        close
 *   • ArrowUp/Down: navigate
 *   • Enter:      fire
 *
 * Mount once at App level so it's available on every route.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Activity, AlertTriangle, Anchor, Crosshair, GitCompareArrows, HeartPulse, Inbox, LayoutGrid, Map, MessageCircle,
  Network, Search, Shield, ShieldCheck, ScrollText, Target, Terminal, Zap, type LucideIcon,
} from "lucide-react";
import { api, type Alert, type Mission } from "../lib/api";
import { toggleDemoMode, useDemoMode } from "../lib/demoMode";
import { toast } from "./Toast";

// IA group tag carried alongside the existing Item.group taxonomy. Items
// of group="page" additionally carry which IA section they live in
// ("operations" | "operator"). Operator items are filtered out when
// Demo Mode is ON, mirroring the sidebar.
type IaGroup = "operations" | "operator";

type Item = {
  id: string;
  label: string;
  sub?: string;
  icon: LucideIcon;
  group: "action" | "page" | "mission" | "alert";
  ia?: IaGroup;     // only set for group="page"
  priority: number;
  run: () => void | Promise<void>;
};

const PAGES: Array<{ to: string; label: string; sub: string; icon: LucideIcon; ia: IaGroup }> = [
  { to: "/command",     label: "Command",       sub: "tactical wall · live overview",      icon: LayoutGrid,        ia: "operations" },
  { to: "/mission",     label: "Mission",       sub: "ingest drone image / video",         icon: Target,            ia: "operations" },
  { to: "/map",         label: "Map",           sub: "geo-pinned detections + heatmap",    icon: Map,               ia: "operations" },
  { to: "/alerts",         label: "Threats",        sub: "threat queue + dual-control engage", icon: AlertTriangle,    ia: "operations" },
  { to: "/counter-drone",  label: "Counter-Drone",  sub: "Sentinel simulation · IFF + signed c2", icon: Crosshair,     ia: "operations" },
  { to: "/audit",          label: "Audit Ledger",   sub: "hash-chained ops log",               icon: ScrollText,       ia: "operations" },
  { to: "/benchmark",   label: "Benchmark",     sub: "mAP, latency, cascade",              icon: Activity,          ia: "operations" },
  { to: "/adversarial", label: "Adversarial",   sub: "FGSM A/B with retention",            icon: Shield,            ia: "operations" },
  { to: "/federated",   label: "Federated",     sub: "FedAvg + FoolsGold dashboard",       icon: Network,           ia: "operations" },
  { to: "/chat",        label: "Brief",         sub: "commander Q&A · Phi-3.5 grounded",   icon: MessageCircle,     ia: "operations" },
  { to: "/diff",            label: "Mission Diff",   sub: "compare two missions",                  icon: GitCompareArrows, ia: "operator"   },
  { to: "/public-reports",  label: "Public Reports", sub: "citizen-tip triage queue · drop pin",   icon: Inbox,            ia: "operator"   },
  { to: "/health",          label: "Health",         sub: "system metrics · models · chain · errors", icon: HeartPulse,    ia: "operator"   },
];

// D3.6: capture commands surfaced in the palette as operator-only
// quick-actions. They do NOT auto-execute — they toast the command and
// copy it to the clipboard so the operator can run it in their venv.
const HEALTH_CAPTURE_ACTIONS: Array<{ id: string; label: string; sub: string; cmd: string }> = [
  {
    id: "act:run-ood-calibration",
    label: "Run OOD calibration",
    sub: "fits Mahalanobis · operator-blocked",
    cmd: "python scripts/calibrate_ood.py",
  },
  {
    id: "act:run-latency-capture",
    label: "Run latency capture",
    sub: "p50/p95/p99 over 25 ingests",
    cmd: "python scripts/capture_latency.py --n 25",
  },
  {
    id: "act:run-detector-map",
    label: "Run detector mAP capture",
    sub: "DOTA-val · refreshes Benchmark hero",
    cmd: "python scripts/capture_detector_map.py",
  },
];

export function CommandPalette() {
  const navigate = useNavigate();
  // Subscribe so the indexed item list rebuilds when demo mode toggles.
  const [demo] = useDemoMode();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [missions, setMissions] = useState<Mission[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loadedDynamic, setLoadedDynamic] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // Open hotkey ⌘K / Ctrl+K
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const isCmdK = (e.key === "k" || e.key === "K") && (e.metaKey || e.ctrlKey);
      if (isCmdK) {
        e.preventDefault();
        setOpen((o) => !o);
      } else if (e.key === "Escape" && open) {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  // Lazy-load dynamic items on first open
  useEffect(() => {
    if (!open || loadedDynamic) return;
    setLoadedDynamic(true);
    Promise.all([
      api.listMissions(50).catch(() => []),
      api.listAlerts({}).catch(() => []),
    ]).then(([m, a]) => {
      setMissions(m);
      setAlerts(a.slice(0, 25));
    });
  }, [open, loadedDynamic]);

  // Focus input when opening
  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  const close = useCallback(() => setOpen(false), []);

  // Build the master item list
  const items = useMemo<Item[]>(() => {
    const list: Item[] = [];
    // Quick actions (priority 0 — top)
    list.push({
      id: "act:verify-chain",
      label: "Verify audit chain",
      sub: "walk SHA-256 from genesis to tip",
      icon: ShieldCheck,
      group: "action", priority: 0,
      run: async () => {
        navigate("/audit");
        // Audit page picks up its own state; toast nudges the user.
        toast.info("Audit page loaded", "Click 'verify chain' on the Audit page");
      },
    });
    list.push({
      id: "act:anchor-now",
      label: "Anchor chain tip now",
      sub: "external anchor file append",
      icon: Anchor,
      group: "action", priority: 0,
      run: async () => {
        try {
          const r = await api.anchorNow();
          if (r.ok) toast.success("Chain anchored", `count ${r.anchor?.count} · tip ${r.anchor?.tip.slice(0, 10)}…`);
          else toast.warn("Anchor skipped", r.reason ?? "");
        } catch (e) { toast.crit("Anchor failed", (e as Error).message); }
      },
    });
    list.push({
      id: "act:demo-mode",
      label: "Toggle demo mode",
      sub: "hide operator chrome",
      icon: Zap,
      group: "action", priority: 0,
      run: () => {
        const v = toggleDemoMode();
        toast.info(`Demo mode ${v ? "ON" : "OFF"}`, v ? "operator chrome hidden" : "full UI restored");
      },
    });
    // operator-only capture toggles. Hidden in demo mode (mirrors
    // sidebar). They toast + copy the command to clipboard, no automation.
    if (!demo) {
      for (const a of HEALTH_CAPTURE_ACTIONS) {
        list.push({
          id: a.id,
          label: a.label,
          sub: a.sub,
          icon: Terminal,
          group: "action", priority: 0,
          run: () => {
            toast.info("Run capture", a.cmd);
            try { void navigator.clipboard?.writeText(a.cmd); } catch { /* noop */ }
          },
        });
      }
    }

    list.push({
      id: "act:sentinel-start",
      label: "Start swarm-loiter scenario",
      sub: "counter-drone · 13 drones · 5 friendlies",
      icon: Crosshair,
      group: "action", priority: 0,
      run: async () => {
        navigate("/counter-drone");
        try {
          const r = await api.sentinelStart({ scenario: "swarm-loiter" });
          toast.success("Sentinel started", `${r.scenario} · ${r.n_drones} drones · ${r.n_friendlies} friendly`);
        } catch (e) {
          toast.crit("Sentinel start failed", (e as Error).message);
        }
      },
    });

    // Pages (priority 1). Operator-section pages are filtered when Demo
    // Mode is ON, mirroring the sidebar.
    for (const p of PAGES) {
      if (demo && p.ia === "operator") continue;
      list.push({
        id: `page:${p.to}`,
        label: p.label, sub: p.sub, icon: p.icon,
        group: "page", ia: p.ia, priority: 1,
        run: () => { navigate(p.to); },
      });
    }

    // Missions (priority 2)
    for (const m of missions) {
      list.push({
        id: `mission:${m.id}`,
        label: `Mission #${m.id} — ${m.name}`,
        sub: `created ${m.created_at}`,
        icon: Target,
        group: "mission", priority: 2,
        run: () => {
          localStorage.setItem("astra:lastMissionId", String(m.id));
          navigate("/mission");
        },
      });
    }

    // Alerts (priority 3)
    for (const a of alerts) {
      list.push({
        id: `alert:${a.id}`,
        label: `Alert #${a.id} — threat ${a.threat_score.toFixed(2)}`,
        sub: a.narrative ?? `${a.status} · mission #${a.mission_id}`,
        icon: AlertTriangle,
        group: "alert", priority: 3,
        run: () => { navigate("/alerts"); },
      });
    }

    return list;
  }, [navigate, missions, alerts, demo]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items.slice(0, 30);
    const match = items
      .filter((it) =>
        it.label.toLowerCase().includes(q) ||
        (it.sub ?? "").toLowerCase().includes(q)
      )
      .slice(0, 30);
    return match;
  }, [items, query]);

  // Clamp active index when filtered list shrinks
  useEffect(() => {
    if (active >= filtered.length) setActive(Math.max(0, filtered.length - 1));
  }, [filtered.length, active]);

  if (!open) return null;

  function fire(it: Item) {
    close();
    void it.run();
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(filtered.length - 1, a + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(0, a - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const sel = filtered[active];
      if (sel) fire(sel);
    } else if (e.key === "Escape") {
      e.preventDefault();
      close();
    }
  }

  return (
    <div
      className="fixed inset-0 z-[10002] bg-bg/70 backdrop-blur-sm flex items-start justify-center pt-24 px-4"
      onClick={close}
    >
      <div
        className="w-full max-w-2xl glass-strong border border-border rounded-lg shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 px-4 py-3 border-b border-border">
          <Search size={16} className="text-muted2" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => { setQuery(e.target.value); setActive(0); }}
            onKeyDown={onKeyDown}
            placeholder="Jump anywhere — page, mission #, alert #, or 'verify', 'anchor', 'demo'..."
            className="flex-1 bg-transparent text-sm focus:outline-none placeholder:text-muted2"
          />
          <span className="text-2xs font-mono text-muted2 uppercase-wide tracking-wider">
            ESC
          </span>
        </div>
        <div className="max-h-[60vh] overflow-auto">
          {filtered.length === 0 ? (
            <div className="px-4 py-6 text-center text-xs text-muted2">No matches.</div>
          ) : filtered.map((it, i) => {
            const Icon = it.icon;
            const isActive = i === active;
            return (
              <button
                key={it.id}
                onClick={() => fire(it)}
                onMouseEnter={() => setActive(i)}
                className={`w-full flex items-center gap-3 px-4 py-2 text-left transition-fast ${
                  isActive ? "bg-accent/10 text-text" : "text-muted hover:bg-panel2"
                }`}
              >
                <Icon size={14} className={isActive ? "text-accent" : "text-muted2"} />
                <div className="flex-1 min-w-0">
                  <div className="text-sm truncate">{it.label}</div>
                  {it.sub && <div className="text-2xs text-muted2 truncate">{it.sub}</div>}
                </div>
                <span className="text-2xs font-mono uppercase-wide tracking-wider text-muted2 shrink-0">
                  {it.group}
                  {it.ia && <span className="opacity-60"> · {it.ia}</span>}
                </span>
              </button>
            );
          })}
        </div>
        <div className="border-t border-border px-4 py-2 text-2xs text-muted2 font-mono flex items-center justify-between">
          <span>↑↓ navigate · ↵ select · esc close</span>
          <span>{filtered.length} / {items.length}</span>
        </div>
      </div>
    </div>
  );
}
