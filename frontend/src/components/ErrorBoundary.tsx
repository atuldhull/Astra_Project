/**
 * ErrorBoundary — React error boundary with a defence-genre fallback UI.
 *
 * Catches render-time exceptions in any descendant. Without this, a
 * single throwing component would white-screen the whole console.
 *
 * The fallback is intentionally informative — operators need to know
 * which subsystem failed and how to recover, not see a blank page.
 *
 * "Reset" remounts children. "Reload" hard-refreshes. "Copy details"
 * puts the stack trace on the clipboard for incident reporting.
 */
import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertOctagon, RotateCcw, RefreshCw, Copy } from "lucide-react";

type Props = {
  children: ReactNode;
  /** Label rendered in the fallback header — typically the subsystem name. */
  scope?: string;
};

type State = {
  hasError: boolean;
  error: Error | null;
  info: ErrorInfo | null;
  resetCount: number;
};

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null, info: null, resetCount: 0 };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    this.setState({ info });
    // Best-effort POST to a future error-collection endpoint. Silent on
    // network failure so the boundary itself can't throw.
    try {
      fetch("/api/v1/errors", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scope: this.props.scope ?? "global",
          message: error.message,
          stack: error.stack ?? null,
          component_stack: info.componentStack ?? null,
          ts: new Date().toISOString(),
          ua: navigator.userAgent,
        }),
        keepalive: true,
      }).catch(() => { /* ignore */ });
    } catch {
      // ignore
    }
    // eslint-disable-next-line no-console
    console.error(`[ErrorBoundary:${this.props.scope ?? "global"}]`, error, info);
  }

  reset = () => {
    this.setState((s) => ({
      hasError: false, error: null, info: null, resetCount: s.resetCount + 1,
    }));
  };

  copyDetails = () => {
    const { error, info } = this.state;
    const blob = [
      `scope: ${this.props.scope ?? "global"}`,
      `message: ${error?.message ?? ""}`,
      `stack: ${error?.stack ?? ""}`,
      `component_stack: ${info?.componentStack ?? ""}`,
      `ts: ${new Date().toISOString()}`,
    ].join("\n\n");
    navigator.clipboard?.writeText(blob).catch(() => { /* ignore */ });
  };

  render() {
    if (!this.state.hasError) {
      // Re-keying with resetCount forces unmount+remount of subtree on reset
      return <div key={this.state.resetCount} style={{ display: "contents" }}>{this.props.children}</div>;
    }
    const { error } = this.state;
    return (
      <div className="h-full flex items-center justify-center p-8">
        <div className="max-w-2xl glass-strong border border-threat-crit/40 shadow-glow-crit rounded-lg p-6 space-y-4">
          <div className="flex items-center gap-3">
            <AlertOctagon size={24} className="text-threat-crit" />
            <div>
              <div className="font-mono text-2xs uppercase-wide tracking-wider text-muted2">
                SUBSYSTEM FAULT · {this.props.scope ?? "GLOBAL"}
              </div>
              <div className="text-lg font-semibold text-text">A render-time exception was caught.</div>
            </div>
          </div>

          <div className="bg-bg/60 rounded p-3 font-mono text-xs text-muted overflow-auto max-h-64">
            <div className="text-threat-crit mb-1">{error?.name ?? "Error"}: {error?.message ?? "(no message)"}</div>
            {error?.stack && (
              <pre className="text-2xs leading-snug whitespace-pre-wrap opacity-75">{error.stack.split("\n").slice(0, 8).join("\n")}</pre>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={this.reset}
              className="flex items-center gap-1.5 bg-accent text-bg px-3 py-1.5 rounded text-sm font-medium hover:brightness-110 transition-fast"
            >
              <RotateCcw size={13} /> Reset subsystem
            </button>
            <button
              onClick={() => window.location.reload()}
              className="flex items-center gap-1.5 glass border border-border px-3 py-1.5 rounded text-sm hover:bg-panel2 transition-fast"
            >
              <RefreshCw size={13} /> Reload page
            </button>
            <button
              onClick={this.copyDetails}
              className="ml-auto flex items-center gap-1.5 glass border border-border px-3 py-1.5 rounded text-xs text-muted hover:text-text hover:bg-panel2 transition-fast"
              title="Copy full stack trace + component path to clipboard"
            >
              <Copy size={12} /> Copy details
            </button>
          </div>
          <div className="text-2xs text-muted2 pt-2 border-t border-border">
            Other subsystems are unaffected — sidebar navigation still works. If reset doesn't recover, reload.
          </div>
        </div>
      </div>
    );
  }
}
