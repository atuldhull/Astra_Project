/**
 * ReplayScrubber (D4.1) — timeline scrubber bar for the Mission page.
 *
 * Drives a single scalar `value` (ms) between [min, max]. Used by:
 *   • Video missions — value is video.currentTime in ms; advancing the
 *     scrubber seeks the video, which in turn re-fires the existing
 *     box-draw effect (no double drawing here).
 *   • Image missions with multi-stage audit timelines — value is
 *     wall-clock ms (created_at-derived); the canvas re-renders ghost-
 *     trail boxes for [value-10s, value].
 *
 * Auto-play tick: +stepMs every intervalMs. Default = +2000ms / 300ms.
 * Stops + resets the toggle when value reaches max.
 *
 * Stays minimal — top border, page-bg fill, no card chrome.
 */
import { useCallback, useEffect, useRef } from "react";
import { Pause, Play, RotateCcw } from "lucide-react";

type Props = {
  /** Min epoch ms (or 0 for relative video time). */
  min: number;
  /** Max epoch ms (or video duration in ms). */
  max: number;
  /** Current scrub position. */
  value: number;
  /** Setter — called on slider drag, auto-tick, reset. */
  onChange: (next: number) => void;
  /** Auto-play active flag (controlled). */
  playing: boolean;
  onPlayingChange: (playing: boolean) => void;
  /** Format the value for the label. Receives the numeric value. */
  formatLabel: (value: number) => string;
  /** Optional sub-label (e.g. "12 visible · 3 ghost"). */
  subLabel?: string;
  /** Auto-play step size in ms. Default 2000. */
  stepMs?: number;
  /** Auto-play tick interval. Default 300ms. */
  intervalMs?: number;
  /** Slider step. Default 100ms — fine for both video + audit timelines. */
  sliderStep?: number;
  /** D5.1 — optional thumbnail strip below the slider. Each entry is a
   *  data-URL (or http URL) + the absolute scrub position it represents.
   *  Clicking a thumb seeks to that position. */
  thumbnails?: { url: string; at: number }[];
};

export function ReplayScrubber({
  min, max, value, onChange,
  playing, onPlayingChange,
  formatLabel, subLabel,
  stepMs = 2000, intervalMs = 300, sliderStep = 100,
  thumbnails,
}: Props) {
  const valueRef = useRef(value);
  valueRef.current = value;

  const tick = useCallback(() => {
    const cur = valueRef.current;
    const next = cur + stepMs;
    if (next >= max) {
      onChange(max);
      onPlayingChange(false);
      return;
    }
    onChange(next);
  }, [max, stepMs, onChange, onPlayingChange]);

  useEffect(() => {
    if (!playing) return;
    // If we're already at the end, kick the toggle back off rather than
    // burning ticks at the boundary.
    if (valueRef.current >= max) {
      onPlayingChange(false);
      return;
    }
    const handle = window.setInterval(tick, intervalMs);
    return () => window.clearInterval(handle);
  }, [playing, intervalMs, tick, max, onPlayingChange]);

  const atEnd = value >= max;

  return (
    <div
      className="border-t border-border bg-bg/80 backdrop-blur-sm"
      style={{ padding: "12px 16px" }}
    >
      <div className="flex items-center gap-3">
        <button
          onClick={() => onPlayingChange(!playing)}
          className={`shrink-0 inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-mono uppercase-wide tracking-wider transition-fast ${
            playing
              ? "bg-cyan/15 border border-cyan/40 text-cyan"
              : "bg-panel2 border border-border text-muted hover:text-text"
          }`}
          title={playing ? "Pause auto-play" : "Auto-play replay"}
        >
          {playing ? <Pause size={12} /> : <Play size={12} />}
          {playing ? "pause" : "play"}
        </button>

        <button
          onClick={() => { onPlayingChange(false); onChange(min); }}
          className="shrink-0 inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-mono uppercase-wide tracking-wider bg-panel2 border border-border text-muted hover:text-text transition-fast"
          title="Reset to start"
        >
          <RotateCcw size={12} />
          reset
        </button>

        <input
          type="range"
          min={min}
          max={max}
          step={sliderStep}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className="flex-1 accent-cyan-400 cursor-pointer"
          aria-label="Replay scrubber"
        />

        <div className="shrink-0 min-w-[140px] text-right">
          <div className="font-mono tabular-nums text-xs text-text">
            {formatLabel(value)}
            {atEnd && (
              <span className="ml-2 text-[10px] text-muted2 uppercase-wide tracking-wider">
                · live
              </span>
            )}
          </div>
          {subLabel && (
            <div className="font-mono text-[10px] text-muted2 uppercase-wide tracking-wider">
              {subLabel}
            </div>
          )}
        </div>
      </div>

      {/* D5.1 — frame thumbnail strip. Active thumb = the one whose `at`
          is closest to the current value. Click any to seek. */}
      {thumbnails && thumbnails.length > 0 && (
        <div className="mt-2 flex gap-1 overflow-x-auto" style={{ scrollbarWidth: "thin" }}>
          {(() => {
            // Compute the index whose `at` is closest to value.
            let activeIdx = 0;
            let bestDelta = Infinity;
            for (let i = 0; i < thumbnails.length; i++) {
              const d = Math.abs(thumbnails[i].at - value);
              if (d < bestDelta) { bestDelta = d; activeIdx = i; }
            }
            return thumbnails.map((t, i) => (
              <button
                key={i}
                onClick={() => onChange(t.at)}
                className={`shrink-0 rounded overflow-hidden border transition-fast ${
                  i === activeIdx
                    ? "border-cyan ring-2 ring-cyan/50"
                    : "border-border hover:border-cyan/40 opacity-70 hover:opacity-100"
                }`}
                style={{ width: 56, height: 36 }}
                title={`seek ${formatLabel(t.at)}`}
                aria-label={`seek to thumbnail ${i + 1}`}
              >
                <img
                  src={t.url}
                  alt=""
                  className="w-full h-full object-cover"
                  draggable={false}
                />
              </button>
            ));
          })()}
        </div>
      )}
    </div>
  );
}
