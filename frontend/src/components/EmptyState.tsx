/**
 * Standardised empty-state component.
 *
 * Replaces ad-hoc "No X yet" text scattered across pages. Icon + 1-line
 * description + optional CTA button. Fits inside any card.
 */
import { ReactNode } from "react";
import { LucideIcon } from "lucide-react";

type Props = {
  icon: LucideIcon;
  title: string;
  body?: string;
  cta?: { label: string; onClick?: () => void; href?: string };
  children?: ReactNode;
  className?: string;
};

export function EmptyState({ icon: Icon, title, body, cta, children, className = "" }: Props) {
  return (
    <div className={`flex flex-col items-center justify-center text-center px-8 py-12 ${className}`}>
      <div className="mb-4 p-3 rounded-full bg-panel2 border border-border text-muted2">
        <Icon size={28} strokeWidth={1.5} />
      </div>
      <h3 className="text-sm font-semibold text-text uppercase-wide tracking-wider mb-1">{title}</h3>
      {body && <p className="text-xs text-muted max-w-md leading-relaxed">{body}</p>}
      {cta && (
        cta.href ? (
          <a
            href={cta.href}
            className="mt-4 px-4 py-1.5 bg-accent text-bg rounded text-xs font-medium hover:brightness-110 transition-fast"
          >
            {cta.label}
          </a>
        ) : (
          <button
            onClick={cta.onClick}
            className="mt-4 px-4 py-1.5 bg-accent text-bg rounded text-xs font-medium hover:brightness-110 transition-fast"
          >
            {cta.label}
          </button>
        )
      )}
      {children && <div className="mt-3">{children}</div>}
    </div>
  );
}
