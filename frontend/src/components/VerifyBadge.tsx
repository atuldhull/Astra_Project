/**
 * VerifyBadge — small ✓ chip next to a signed detection.
 *
 * Click → modal with the canonical signed payload + a "Verify now"
 * button that re-runs server-side cryptographic verification. Tamper
 * with the row in the DB and the next click flips green ✓ to red ✗.
 *
 * Demo: judge clicks any detection, watches Ed25519 verify happen live.
 */
import { useState } from "react";
import { ShieldCheck, ShieldAlert, X, Loader2 } from "lucide-react";
import { api, type ProvenanceVerify } from "../lib/api";

type Props = {
  detection_id: number;
  signed: boolean;
  size?: "xs" | "sm";
  /** Optional fingerprint to render in modal footer if already known. */
  fingerprint?: string | null;
};

export function VerifyBadge({ detection_id, signed, size = "xs", fingerprint }: Props) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ProvenanceVerify | null>(null);

  if (!signed) return null;

  const px = size === "xs" ? "text-[10px] px-1.5 py-0.5" : "text-xs px-2 py-1";

  async function verify() {
    setBusy(true);
    const t0 = performance.now();
    try {
      const v = await api.provenanceVerify(detection_id);
      const elapsed = performance.now() - t0;
      // Floor at 500ms so the verification feels intentional.
      if (elapsed < 500) await new Promise((r) => setTimeout(r, 500 - elapsed));
      setResult(v);
    } catch (e) {
      setResult({
        detection_id, ok: false,
        reason: `request failed: ${(e as Error).message}`,
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button
        onClick={(e) => { e.stopPropagation(); setOpen(true); setResult(null); }}
        className={`inline-flex items-center gap-1 rounded font-mono uppercase-wide tracking-wider border border-threat-low/40 bg-threat-low/10 text-threat-low hover:bg-threat-low/20 transition-fast ${px}`}
        title="Click to verify the Ed25519 provenance signature"
      >
        <ShieldCheck size={size === "xs" ? 9 : 11} />
        signed
      </button>
      {open && (
        <div
          className="fixed inset-0 z-[10001] bg-bg/70 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => setOpen(false)}
        >
          <div
            className="glass-strong border border-border rounded-lg max-w-xl w-full p-5 space-y-4 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="font-mono text-2xs uppercase-wide tracking-wider text-muted2">
                  PROVENANCE · DETECTION #{detection_id}
                </div>
                <div className="text-base font-semibold text-text mt-0.5">Cryptographic verification</div>
              </div>
              <button
                onClick={() => setOpen(false)}
                className="text-muted hover:text-text -m-1 p-1.5 rounded"
                aria-label="Close"
              >
                <X size={16} />
              </button>
            </div>

            <div className="text-xs text-muted leading-snug">
              The detection was signed at ingest time with an Ed25519 server key over a canonical
              payload of <span className="font-mono text-text">model_hash · image_sha256 · mission_id · class_id · confidence · bbox · timestamp</span>.
              Click verify — if any of those fields drifts in the DB, the next verify will fail.
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={verify}
                disabled={busy}
                className="flex items-center gap-2 bg-accent text-bg px-3 py-1.5 rounded text-sm font-medium hover:brightness-110 disabled:opacity-50 transition-fast"
              >
                {busy
                  ? <><Loader2 size={13} className="animate-spin" /> verifying...</>
                  : <><ShieldCheck size={13} /> Verify now</>}
              </button>
              {result && (
                <div className={`flex items-center gap-2 text-sm font-mono ${result.ok ? "text-threat-low" : "text-threat-crit"}`}>
                  {result.ok
                    ? <><ShieldCheck size={14} /> Signature valid</>
                    : <><ShieldAlert size={14} /> {result.reason ?? "signature mismatch"}</>}
                </div>
              )}
            </div>

            {result?.signed_payload && (
              <div className="bg-bg/60 border border-border rounded p-3 font-mono text-2xs space-y-1">
                <Row k="mission_id" v={`#${result.signed_payload.mission_id}`} />
                <Row k="class_name" v={result.signed_payload.class_name} />
                <Row k="confidence" v={result.signed_payload.confidence.toFixed(4)} />
                <Row k="image_sha256" v={result.signed_payload.image_sha256_short} />
                <Row k="model_hash" v={result.signed_payload.model_hash_short} />
              </div>
            )}

            {(result?.fingerprint ?? fingerprint) && (
              <div className="text-2xs text-muted2 font-mono pt-2 border-t border-border">
                <span className="opacity-60">server pubkey fingerprint · </span>
                <span className="text-muted">{(result?.fingerprint ?? fingerprint ?? "").slice(0, 16)}…{(result?.fingerprint ?? fingerprint ?? "").slice(-8)}</span>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-3">
      <span className="text-muted2">{k}</span>
      <span className="text-text break-all">{v}</span>
    </div>
  );
}
