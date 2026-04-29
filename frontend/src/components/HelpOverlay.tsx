/**
 * HelpOverlay (T1.8) — press `?` to open a context-sensitive cheat sheet.
 *
 * Listens globally for the `?` keypress (Shift+/). Esc dismisses.
 * Content adapts to the current route via window.location.pathname so
 * the operator gets relevant hints without leaving the page.
 */
import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { HelpCircle, X } from "lucide-react";

type Section = { title: string; lines: string[] };

const GLOBAL_KEYS: Section = {
  title: "Global",
  lines: [
    "⌘K / Ctrl+K — open command palette",
    "?           — this help",
    "Esc         — close any modal",
    "Sidebar status pills — green = nominal, red = subsystem fault",
  ],
};

const ROUTE_HELP: Record<string, Section[]> = {
  "/command": [
    { title: "Command Center", lines: [
      "Live tactical wall — every subsystem one tile.",
      "Click any tile (or its ↗) to deep-dive.",
      "Pulsing red BACKEND DOWN = restart with scripts/dev-restart.sh.",
    ]},
  ],
  "/mission": [
    { title: "Mission feed", lines: [
      "Drag a drone image (PNG/JPG) or video (MP4/MOV) onto the bezel.",
      "Stage-1 detector runs in <30ms; cascade IDs airframes 1-2s later.",
      "Click any drawn box on an image → Grad-CAM heatmap (model attention).",
      "EXIF-GPS images auto-anchor on the Map; AOI default Bangalore otherwise.",
      "'New Mission' clears state — the current image survives tab switches until then.",
    ]},
  ],
  "/map": [
    { title: "Tactical map", lines: [
      "CircleMarkers = detections, color = class, opacity = confidence.",
      "Toggle Heatmap for additive density blobs (great for clustering).",
      "Click any marker for full detail incl. cascade airframe + Ed25519 verify badge.",
      "Mission selector top-right scopes the view.",
    ]},
  ],
  "/alerts": [
    { title: "Threat queue", lines: [
      "Threats sorted by score — ≥0.75 critical, ≥0.55 high, etc.",
      "Engage = dual-control: 2 distinct operators must confirm.",
      "Threat-frequency waveform at top is a glance-view of recent severity.",
    ]},
  ],
  "/audit": [
    { title: "Audit · hash chain", lines: [
      "Append-only. Every operator action SHA-256-chained from genesis.",
      "Click 'verify chain' — re-walks every row in front of you.",
      "Anchor strip: 'Anchor now' captures tip externally; 'Verify anchors' detects rewrites.",
      "Server pubkey fingerprint shown in subtitle — that's what signs detections.",
    ]},
  ],
  "/benchmark": [
    { title: "Benchmark", lines: [
      "Hero stats are LIVE — pulled from benchmarks/*.json.",
      "Run scripts/capture_detector_map.py to refresh mAP numbers.",
      "Run scripts/capture_latency.py --n 25 to refresh latency.",
    ]},
  ],
  "/adversarial": [
    { title: "Adversarial", lines: [
      "FGSM attack with measured retention — clean→attacked detections.",
      "RetentionGauge: ≥75% green, 45-75% amber, <45% red.",
      "v1 = baseline, v1-hardened = adversarially trained.",
    ]},
  ],
  "/federated": [
    { title: "Federated", lines: [
      "FedAvg + FoolsGold (Sybil quarantine) + DP-SGD (privacy noise).",
      "Topology graph: edge stroke ∝ aggregation weight; quarantined dashed-red.",
      "Synthetic task is the safe demo; MAR20 task uses real airframe data.",
    ]},
  ],
  "/diff": [
    { title: "Mission diff", lines: [
      "Pick two missions to compare detections side-by-side.",
      "Useful for 'what changed in this AOI between yesterday and today?'",
    ]},
  ],
  "/public-reports": [
    { title: "Public Reports · operator triage", lines: [
      "Citizen submissions land here when no EXIF GPS is on the photo.",
      "Click 'drop pin' on a row → world map modal → click anywhere → confirm pin.",
      "Pinning kicks off the same pipeline as a normal /ingest.",
      "EXIF-GPS submissions skip this queue and run automatically.",
      "Submit form lives on /command (Operations) — drag a photo onto it.",
    ]},
  ],
  "/counter-drone": [
    { title: "Counter-Drone Sentinel", lines: [
      "Pick a scenario at the bottom (line-abreast / pincer / swarm-loiter) and Start.",
      "Friendlies render green with valid Ed25519 IFF tokens; foes render red (no/expired/tampered).",
      "Decision matrix on the right is sorted by time-to-target. <5s recommends hard-kill, <30s soft-kill.",
      "vrfy / soft / hard buttons per row. Engage opens a confirmation modal; ack stamps server-side latency.",
      "Every engage writes a chain-of-custody row to the audit ledger.",
      "This is a SIMULATION. Real RF/kinetics are R4 hardware integration.",
    ]},
  ],
  "/health": [
    { title: "Health · System Metrics", lines: [
      "Single-pane readout — auto-polls /health/dashboard every 10s.",
      "Models row shows detector / cascade / Phi-3.5 ready/absent + model_hash.",
      "Chain panel shows tip, last anchor, and peer witness count.",
      "Calibration freshness flags OOD / latency / mAP files older than 7 days.",
      "'Run capture' copies the venv command to clipboard — operator runs it.",
    ]},
  ],
  "/chat": [
    { title: "Commander Q&A", lines: [
      "Mission-scoped: pick a mission to bind the thread.",
      "Phi-3.5 if installed; rule-matcher otherwise — both grounded in DB.",
      "Try 'details of mission #14' for a formatted briefing.",
      "Type 'note: <text>' or click the note button to attach a note.",
    ]},
  ],
};

function lookup(pathname: string): Section[] {
  const trimmed = pathname.replace(/\/$/, "") || "/command";
  return ROUTE_HELP[trimmed] ?? [];
}

export function HelpOverlay() {
  const [open, setOpen] = useState(false);
  const loc = useLocation();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // Don't intercept when typing in a field
      const t = e.target as HTMLElement | null;
      const tag = (t?.tagName ?? "").toUpperCase();
      const editable = tag === "INPUT" || tag === "TEXTAREA" || (t?.isContentEditable ?? false);
      if (e.key === "?" && !editable) {
        e.preventDefault();
        setOpen((o) => !o);
      } else if (e.key === "Escape" && open) {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  if (!open) return null;

  const sections = [GLOBAL_KEYS, ...lookup(loc.pathname)];

  return (
    <div
      className="fixed inset-0 z-[10003] bg-bg/70 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={() => setOpen(false)}
    >
      <div
        className="glass-strong border border-border rounded-lg max-w-xl w-full p-5 space-y-4 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <HelpCircle size={16} className="text-cyan" />
            <span className="font-semibold text-text">Keys & hints · {loc.pathname}</span>
          </div>
          <button
            onClick={() => setOpen(false)}
            className="text-muted hover:text-text -m-1 p-1.5 rounded"
            aria-label="Close"
          >
            <X size={16} />
          </button>
        </div>
        <div className="space-y-3">
          {sections.map((s) => (
            <div key={s.title}>
              <div className="text-2xs uppercase-wide font-mono tracking-wider text-muted2 mb-1.5">{s.title}</div>
              <ul className="space-y-1 text-xs text-muted leading-snug">
                {s.lines.map((l, i) => (
                  <li key={i} className="font-mono">
                    <span className="text-text">{l.split(" — ")[0]}</span>
                    {l.includes(" — ") && <span> — {l.split(" — ").slice(1).join(" — ")}</span>}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="text-2xs text-muted2 pt-2 border-t border-border">
          Press <span className="font-mono text-text">?</span> again or <span className="font-mono text-text">Esc</span> to close.
        </div>
      </div>
    </div>
  );
}
