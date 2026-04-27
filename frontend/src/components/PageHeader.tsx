/**
 * Standardised page header.
 *
 * Pattern across all pages:
 *   <icon> Title <optional pill>
 *   <one-line subtitle>
 *
 *   ...with an action cluster on the right.
 *
 * Replaces the ad-hoc <header> block at the top of each page.
 */
import { ReactNode } from "react";
import { LucideIcon } from "lucide-react";

type Props = {
  icon?: LucideIcon;
  title: string;
  subtitle?: ReactNode;
  badge?: ReactNode;        // e.g. <StatusPill>...</StatusPill>
  actions?: ReactNode;
};

export function PageHeader({ icon: Icon, title, subtitle, badge, actions }: Props) {
  return (
    <header className="px-6 py-4 border-b border-border bg-panel/40 backdrop-blur-sm flex items-center justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-lg font-semibold flex items-center gap-2.5">
          {Icon && <Icon size={18} className="text-accent" />}
          <span>{title}</span>
          {badge}
        </h1>
        {subtitle && (
          <div className="text-xs text-muted mt-0.5 truncate">{subtitle}</div>
        )}
      </div>
      {actions && (
        <div className="flex items-center gap-2 shrink-0">{actions}</div>
      )}
    </header>
  );
}
