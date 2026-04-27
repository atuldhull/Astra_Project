/**
 * Loading skeletons — replace bare spinners across the app. Sized to mimic
 * the final content's layout so the page doesn't jump on data load.
 */
import { ReactNode } from "react";

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} />;
}

/** A row of N column skeletons — for table loading states. */
export function SkeletonRow({ cols = 4, className = "" }: { cols?: number; className?: string }) {
  return (
    <div className={`grid gap-3 ${className}`} style={{ gridTemplateColumns: `repeat(${cols}, minmax(0,1fr))` }}>
      {Array.from({ length: cols }).map((_, i) => (
        <Skeleton key={i} className="h-4" />
      ))}
    </div>
  );
}

/** Skeleton hero-stat card. Use 4 in a grid while metrics load. */
export function SkeletonHeroStat() {
  return (
    <div className="hero-stat">
      <Skeleton className="h-3 w-16 mb-2" />
      <Skeleton className="h-7 w-24" />
    </div>
  );
}

/** A wrapper that fades-in its children once `loading` flips false. */
export function FadeIn({ loading, children }: { loading: boolean; children: ReactNode }) {
  return (
    <div
      className="transition-opacity duration-mid"
      style={{ opacity: loading ? 0.55 : 1 }}
    >
      {children}
    </div>
  );
}
