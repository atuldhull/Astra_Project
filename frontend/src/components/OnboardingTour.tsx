/**
 * OnboardingTour — first-visit spotlight tour.
 *
 * Custom-built (no Shepherd / Driver.js / intro.js deps). Plays a sequence
 * of position-anchored callouts pointing at key UI elements. Skippable.
 * Persists "seen" flag in localStorage so it only shows on first visit.
 *
 * Each step references a target by document.querySelector. If the target
 * isn't on the current page, the step centers on the viewport with no
 * arrow.
 */
import { useEffect, useState } from "react";
import { ArrowRight, X } from "lucide-react";

// Bumped for v3.0: existing users see the refreshed tour once, then never
// again. Old keys (v1) are intentionally left in place for forensics.
const KEY = "astra:tourSeen:v3";

type Step = {
  /** CSS selector for the element to highlight; null = centered modal */
  target: string | null;
  title: string;
  body: string;
  /** Where to anchor the callout relative to the target */
  side?: "top" | "bottom" | "left" | "right";
};

const STEPS: Step[] = [
  {
    target: null,
    title: "Welcome to ASTRA v3.0",
    body: "Sovereign · on-device · defensible — three pillars, all running on a 6 GB laptop GPU. This 90-second tour walks you through every major capability. Press → to begin or ESC to skip.",
  },
  {
    target: 'a[href="/command"]',
    side: "right",
    title: "Command Center",
    body: "The home wall. Every running subsystem shown live in one tactical view. Click any tile to deep-dive.",
  },
  {
    target: 'a[href="/mission"]',
    side: "right",
    title: "Mission feed",
    body: "Drag a drone image or video here. Stage-1 detector finds objects; stage-2 cascade names specific airframes (F-22, P-3C, etc.).",
  },
  {
    target: 'a[href="/map"]',
    side: "right",
    title: "Tactical map",
    body: "Geo-referenced detections plus track polylines. Pins POP onto the map in real time as the pipeline runs.",
  },
  {
    target: 'a[href="/alerts"]',
    side: "right",
    title: "Threat queue",
    body: "Ranked threat narratives. Escalate any alert to engaged with two-operator dual control — required for engagement.",
  },
  {
    target: 'a[href="/federated"]',
    side: "right",
    title: "Federated learning",
    body: "Three bases share weights without sharing data. FoolsGold quarantines colluding Sybil attackers — see the topology graph.",
  },
  {
    target: 'a[href="/adversarial"]',
    side: "right",
    title: "Adversarial robustness",
    body: "FGSM attack with measured retention — A/B between v1 baseline and v1-hardened to see the mitigation curve.",
  },
  {
    target: 'a[href="/audit"]',
    side: "right",
    title: "Tamper-evident audit",
    body: "Every action is SHA-256 hash-chained from a genesis row. Click 'Verify chain' on the Audit page — watch the SHA walk every row in front of you with the tip hash visible.",
  },
  {
    target: 'a[href="/chat"]',
    side: "right",
    title: "Commander Q&A",
    body: "Ask the database in plain English. Mission-scoped threads persist in Postgres. Type 'details of mission #N' for a full briefing including operator notes and audit summary.",
  },
  {
    target: null,
    title: "You're set",
    body: "Press ? on any page for the contextual help overlay. Run scripts/preflight.sh before any demo to confirm ALL GREEN. Welcome to let's go.",
  },
];

export function OnboardingTour({ force = false }: { force?: boolean }) {
  const [active, setActive] = useState<boolean>(() => {
    if (force) return true;
    try { return localStorage.getItem(KEY) !== "1"; } catch { return true; }
  });
  const [idx, setIdx] = useState(0);
  const [box, setBox] = useState<DOMRect | null>(null);

  // Re-measure target on each step + on resize
  useEffect(() => {
    if (!active) return;
    const step = STEPS[idx];
    const measure = () => {
      if (!step.target) {
        setBox(null);
        return;
      }
      const el = document.querySelector(step.target);
      if (el) setBox((el as HTMLElement).getBoundingClientRect());
      else setBox(null);
    };
    measure();
    window.addEventListener("resize", measure);
    const t = window.setInterval(measure, 200);   // catch sidebar collapse-anim drift
    return () => {
      window.removeEventListener("resize", measure);
      window.clearInterval(t);
    };
  }, [active, idx]);

  // Keyboard
  useEffect(() => {
    if (!active) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") finish();
      if (e.key === "ArrowRight" || e.key === "Enter") next();
      if (e.key === "ArrowLeft") prev();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, idx]);

  if (!active) return null;
  const step = STEPS[idx];

  function next() {
    if (idx < STEPS.length - 1) setIdx(idx + 1);
    else finish();
  }
  function prev() { if (idx > 0) setIdx(idx - 1); }
  function finish() {
    try { localStorage.setItem(KEY, "1"); } catch { /* noop */ }
    setActive(false);
  }

  // Position the callout near the target
  const calloutStyle: React.CSSProperties = {};
  if (box) {
    const margin = 14;
    const w = 360;
    if (step.side === "right") {
      calloutStyle.top = box.top + box.height / 2 - 50;
      calloutStyle.left = box.right + margin;
    } else if (step.side === "left") {
      calloutStyle.top = box.top + box.height / 2 - 50;
      calloutStyle.left = Math.max(margin, box.left - w - margin);
    } else if (step.side === "top") {
      calloutStyle.top = Math.max(margin, box.top - 130);
      calloutStyle.left = box.left;
    } else {
      calloutStyle.top = box.bottom + margin;
      calloutStyle.left = box.left;
    }
  } else {
    calloutStyle.top = "50%";
    calloutStyle.left = "50%";
    calloutStyle.transform = "translate(-50%, -50%)";
  }

  return (
    <div className="fixed inset-0 z-[9999] pointer-events-none">
      {/* Dim overlay with a 'cutout' around the target */}
      <div
        className="absolute inset-0 pointer-events-auto"
        onClick={next}
        style={{
          background: "rgba(7, 9, 13, 0.78)",
          backdropFilter: "blur(2px)",
          ...(box
            ? {
                clipPath: `polygon(
                  0% 0%, 100% 0%, 100% 100%, 0% 100%, 0% 0%,
                  ${box.left - 4}px ${box.top - 4}px,
                  ${box.left - 4}px ${box.bottom + 4}px,
                  ${box.right + 4}px ${box.bottom + 4}px,
                  ${box.right + 4}px ${box.top - 4}px,
                  ${box.left - 4}px ${box.top - 4}px
                )`,
              }
            : {}),
        }}
      />

      {/* Spotlight border */}
      {box && (
        <div
          className="absolute rounded-md pointer-events-none animate-pulse-glow"
          style={{
            top: box.top - 4,
            left: box.left - 4,
            width: box.width + 8,
            height: box.height + 8,
            border: "2px solid var(--accent)",
            boxShadow: "0 0 24px 2px var(--accent-glow)",
          }}
        />
      )}

      {/* Callout */}
      <div
        className="absolute pointer-events-auto glass-strong rounded-lg p-4 w-[360px] max-w-[90vw] shadow-panel-strong"
        style={calloutStyle}
      >
        <div className="flex items-start justify-between gap-3 mb-2">
          <div>
            <div className="text-2xs uppercase-wide tracking-[0.2em] text-accent font-mono">
              STEP {idx + 1} / {STEPS.length}
            </div>
            <div className="text-base font-semibold mt-0.5">{step.title}</div>
          </div>
          <button onClick={finish} className="p-1 text-muted hover:text-text" title="Close tour">
            <X size={14} />
          </button>
        </div>
        <p className="text-xs text-muted leading-relaxed">{step.body}</p>
        <div className="flex items-center justify-between mt-4">
          <button
            onClick={prev}
            disabled={idx === 0}
            className="text-2xs uppercase-wide tracking-wider text-muted hover:text-text disabled:opacity-30 transition-fast"
          >
            ← back
          </button>
          <div className="flex gap-1">
            {STEPS.map((_, i) => (
              <span
                key={i}
                className={`w-1.5 h-1.5 rounded-full transition-fast ${i === idx ? "bg-accent" : "bg-border"}`}
              />
            ))}
          </div>
          <button
            onClick={next}
            className="flex items-center gap-1 text-2xs uppercase-wide tracking-wider text-accent hover:text-accent2 transition-fast"
          >
            {idx === STEPS.length - 1 ? "finish" : "next"} <ArrowRight size={11} />
          </button>
        </div>
      </div>
    </div>
  );
}

/** True iff the tour should auto-play on this browser. */
export function shouldShowTour(): boolean {
  try { return localStorage.getItem(KEY) !== "1"; }
  catch { return true; }
}
