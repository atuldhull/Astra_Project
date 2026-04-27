/**
 * One-time splash boot screen.
 *
 * Plays on first visit per session (sessionStorage flag) and exposes a
 * "skip" affordance. Renders terminal-style boot lines that look like
 * a real ISR system coming online — accent on credibility, not on
 * marketing flash.
 *
 * Total runtime: ~2.0s. Skippable on click anywhere.
 */
import { useEffect, useState } from "react";
import { Loader2, Shield } from "lucide-react";

const BOOT_LINES: { text: string; delay: number }[] = [
  { text: "[boot] ASTRA core 0.3.0 loading...",                        delay: 50 },
  { text: "[ok]   stage-1 detector  yolo11n  640²  device=cuda:0",     delay: 350 },
  { text: "[ok]   stage-2 cascade   yolo11n-cls  224²  20 airframes",  delay: 600 },
  { text: "[ok]   ood gatekeeper    conf+aspect+edge    threshold=0.55", delay: 850 },
  { text: "[ok]   websocket pool    /ws/live    backend=127.0.0.1:8000", delay: 1050 },
  { text: "[ok]   audit chain       sha-256-linked    verified",       delay: 1250 },
  { text: "[ok]   federated         fedavg + foolsgold + dp           ", delay: 1450 },
  { text: "[ok]   alerts            narrator + dual-control           ", delay: 1650 },
  { text: "ASTRA online. Hand-off to operator console.",                delay: 1900 },
];

const STORAGE_KEY = "astra:splashSeen:v1";

export function SplashBoot({ onDone }: { onDone: () => void }) {
  const [shownIdx, setShownIdx] = useState(0);
  const [exiting, setExiting] = useState(false);

  // schedule each line in
  useEffect(() => {
    const timeouts: number[] = [];
    BOOT_LINES.forEach((l, i) => {
      timeouts.push(window.setTimeout(() => setShownIdx(i + 1), l.delay));
    });
    timeouts.push(window.setTimeout(() => fadeAndDone(), BOOT_LINES[BOOT_LINES.length - 1].delay + 350));
    return () => timeouts.forEach(window.clearTimeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function fadeAndDone() {
    setExiting(true);
    window.setTimeout(() => {
      sessionStorage.setItem(STORAGE_KEY, "1");
      onDone();
    }, 320);
  }

  return (
    <div
      onClick={fadeAndDone}
      className={`fixed inset-0 z-[10000] bg-bg flex flex-col items-center justify-center cursor-pointer scanline-overlay transition-opacity duration-slow ${exiting ? "opacity-0" : "opacity-100"}`}
    >
      {/* Brand mark */}
      <div className="mb-10 flex flex-col items-center">
        <div className="relative mb-3">
          <div className="absolute inset-0 rounded-full bg-accent/30 blur-2xl animate-pulse-glow" />
          <div className="relative w-20 h-20 rounded-full border-2 border-accent flex items-center justify-center bg-panel/50 backdrop-blur-md glow-accent">
            <Shield size={36} strokeWidth={1.5} className="text-accent" />
          </div>
        </div>
        <div className="text-display text-4xl font-bold tracking-[0.3em] text-text mt-2">ASTRA</div>
        <div className="text-2xs uppercase-wide text-muted2 mt-1 font-mono tracking-[0.4em]">
          Aerial Surveillance &amp; Threat Recognition
        </div>
        <div className="text-2xs uppercase-wide text-accent mt-3 font-mono tracking-[0.3em]">
          v0.3.0 · sovereign build
        </div>
      </div>

      {/* Boot terminal */}
      <div className="font-mono text-xs leading-relaxed text-muted text-left w-[640px] max-w-[90vw] min-h-[180px]">
        {BOOT_LINES.slice(0, shownIdx).map((l, i) => (
          <div key={i} className={i === shownIdx - 1 ? "text-accent" : ""}>
            {l.text}
          </div>
        ))}
        {shownIdx < BOOT_LINES.length && (
          <div className="flex items-center gap-2 mt-1 text-muted2">
            <Loader2 size={11} className="animate-spin" />
            <span className="animate-blink-dot">▍</span>
          </div>
        )}
      </div>

      <div className="mt-12 text-2xs uppercase-wide text-muted2 tracking-[0.2em] font-mono">
        click anywhere to skip
      </div>
    </div>
  );
}

/** True iff the splash should play on this session. */
export function shouldShowSplash(): boolean {
  try { return sessionStorage.getItem(STORAGE_KEY) !== "1"; }
  catch { return true; }
}
