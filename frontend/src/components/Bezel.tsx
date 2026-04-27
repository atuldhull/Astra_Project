/**
 * Bezel — military display chrome around any frame.
 *
 * Wraps a child element with corner marks, edge brackets, and an optional
 * top-bar telemetry strip. Used on the Mission viewer canvas + Map
 * container + Adversarial side-by-side panels.
 */
import { ReactNode } from "react";

type Props = {
  children: ReactNode;
  /** Top-bar status strip — usually a row of monospace key=value pairs. */
  topBar?: ReactNode;
  /** Bottom-bar strip — typically scale, frame-rate, time stamp. */
  bottomBar?: ReactNode;
  /** Corner-mark colour (defaults to accent orange). */
  cornerColour?: string;
  className?: string;
};

export function Bezel({ children, topBar, bottomBar, cornerColour = "var(--accent)", className = "" }: Props) {
  return (
    <div className={`relative ${className}`}>
      {/* The canvas container itself */}
      <div className="relative w-full h-full overflow-hidden rounded-md border border-border2 bg-bg">
        {topBar && (
          <div className="absolute top-0 inset-x-0 z-20 px-3 py-1.5 flex items-center gap-3 text-2xs font-mono uppercase-wide tracking-wider text-muted bg-gradient-to-b from-bg/90 to-transparent">
            {topBar}
          </div>
        )}
        {bottomBar && (
          <div className="absolute bottom-0 inset-x-0 z-20 px-3 py-1.5 flex items-center gap-3 text-2xs font-mono uppercase-wide tracking-wider text-muted bg-gradient-to-t from-bg/90 to-transparent">
            {bottomBar}
          </div>
        )}
        {children}
      </div>

      {/* Corner brackets, drawn outside the bezel content for that HUD feel */}
      <Corner pos="tl" colour={cornerColour} />
      <Corner pos="tr" colour={cornerColour} />
      <Corner pos="bl" colour={cornerColour} />
      <Corner pos="br" colour={cornerColour} />
    </div>
  );
}

function Corner({ pos, colour }: { pos: "tl" | "tr" | "bl" | "br"; colour: string }) {
  const size = 14;
  const thickness = 2;
  const offset = -1;
  const v: Record<string, React.CSSProperties> = {
    tl: { top: offset,    left: offset },
    tr: { top: offset,    right: offset },
    bl: { bottom: offset, left: offset },
    br: { bottom: offset, right: offset },
  };
  const orient: Record<string, React.CSSProperties> = {
    tl: { borderTop: `${thickness}px solid ${colour}`, borderLeft: `${thickness}px solid ${colour}` },
    tr: { borderTop: `${thickness}px solid ${colour}`, borderRight: `${thickness}px solid ${colour}` },
    bl: { borderBottom: `${thickness}px solid ${colour}`, borderLeft: `${thickness}px solid ${colour}` },
    br: { borderBottom: `${thickness}px solid ${colour}`, borderRight: `${thickness}px solid ${colour}` },
  };
  return (
    <span
      aria-hidden
      className="absolute pointer-events-none z-30"
      style={{ width: size, height: size, ...v[pos], ...orient[pos] }}
    />
  );
}
