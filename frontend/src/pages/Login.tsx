/**
 * Operator login page.
 *
 * Shown when the user clicks the auth chip in the sidebar OR when a
 * protected route returns 401. Default demo creds preloaded.
 */
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Shield, LogIn, Loader2, KeyRound } from "lucide-react";
import { fetchOperators, login, type OperatorListEntry } from "../lib/auth";
import { toast } from "../components/Toast";

export default function Login() {
  const navigate = useNavigate();
  const [ops, setOps] = useState<OperatorListEntry[]>([]);
  const [authEnabled, setAuthEnabled] = useState<boolean | null>(null);
  const [opId, setOpId] = useState("cmdr-01");
  const [pw, setPw] = useState("astra");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchOperators()
      .then((d) => {
        setOps(d.operators);
        setAuthEnabled(d.auth_enabled);
        if (d.operators.length > 0) setOpId(d.operators[0].operator_id);
      })
      .catch((e) => setError((e as Error).message));
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await login(opId, pw);
      toast.success(`Welcome, ${r.operator_id}`, `Role: ${r.role}`);
      navigate("/command");
    } catch (err) {
      setError((err as Error).message);
      toast.crit("Login failed", (err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="h-full flex items-center justify-center p-8">
      <div className="glass-strong rounded-lg w-[440px] max-w-full p-6 shadow-panel-strong relative overflow-hidden">
        {/* accent top bar */}
        <span className="absolute top-0 left-4 right-4 h-px bg-gradient-to-r from-transparent via-accent to-transparent" />

        <div className="flex items-center gap-3 mb-1">
          <div className="relative">
            <span className="absolute inset-0 rounded bg-accent/30 blur-md animate-pulse-soft" />
            <div className="relative w-10 h-10 rounded border border-accent flex items-center justify-center bg-bg">
              <Shield size={20} className="text-accent" />
            </div>
          </div>
          <div>
            <div className="text-display text-xl font-bold tracking-[0.18em]">ASTRA</div>
            <div className="text-2xs uppercase-wide text-muted2 font-mono tracking-[0.2em]">
              OPERATOR&nbsp;CONSOLE
            </div>
          </div>
        </div>

        {authEnabled === false && (
          <div className="mt-4 mb-2 px-3 py-2 rounded bg-cyan/10 border border-cyan/30 text-xs text-cyan">
            Auth is currently OFF on the backend (ASTRA_AUTH_ENABLED=0). Login is optional;
            actions still work without it. Set the env var to enforce.
          </div>
        )}

        <form onSubmit={submit} className="mt-5 space-y-4">
          <div>
            <label className="text-2xs uppercase-wide text-muted2 font-mono tracking-wider mb-1 block">
              Operator ID
            </label>
            {ops.length > 0 ? (
              <select
                value={opId}
                onChange={(e) => setOpId(e.target.value)}
                className="w-full bg-bg border border-border rounded px-3 py-2 text-sm font-mono"
              >
                {ops.map((o) => (
                  <option key={o.operator_id} value={o.operator_id}>
                    {o.operator_id} · {o.role}
                  </option>
                ))}
              </select>
            ) : (
              <input
                value={opId}
                onChange={(e) => setOpId(e.target.value)}
                className="w-full bg-bg border border-border rounded px-3 py-2 text-sm font-mono"
              />
            )}
          </div>
          <div>
            <label className="text-2xs uppercase-wide text-muted2 font-mono tracking-wider mb-1 block">
              Password
            </label>
            <input
              type="password"
              value={pw}
              onChange={(e) => setPw(e.target.value)}
              className="w-full bg-bg border border-border rounded px-3 py-2 text-sm font-mono"
            />
          </div>

          {error && (
            <div className="px-3 py-2 rounded bg-threat-crit/15 border border-threat-crit/40 text-threat-crit text-xs">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={busy}
            className="w-full flex items-center justify-center gap-2 bg-accent text-bg px-4 py-2 rounded text-sm font-medium hover:brightness-110 disabled:opacity-50 transition-fast shadow-glow-accent"
          >
            {busy ? <Loader2 size={14} className="animate-spin" /> : <LogIn size={14} />}
            {busy ? "Authenticating..." : "Sign in"}
          </button>
        </form>

        <div className="mt-5 pt-4 border-t border-border text-2xs text-muted leading-relaxed">
          <div className="flex items-center gap-1 mb-1 text-accent">
            <KeyRound size={11} /> demo credentials
          </div>
          <div className="font-mono">cmdr-01 / astra · cmdr-02 / astra · admin / admin123</div>
          <div className="mt-2 text-muted2">
            Roles: operator → commander (can engage alerts) → admin (everything).
          </div>
        </div>
      </div>
    </div>
  );
}
