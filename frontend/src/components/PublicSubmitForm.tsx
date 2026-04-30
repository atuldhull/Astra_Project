/**
 * PublicSubmitForm — drag-drop target for citizen tip submissions.
 *
 * Embedded on /command (OPERATIONS) so the public-input flow is visible
 * in the Operations surface; the operator-side triage lives at
 * /public-reports.
 *
 * On submit: posts to /api/v1/public/submit. Toasts the result so the
 * operator immediately knows whether EXIF-GPS auto-anchored the
 * mission or it landed in triage awaiting a pin.
 */
import { useRef, useState } from "react";
import { Upload, Loader2, MapPin, Inbox } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { toast } from "./Toast";

export function PublicSubmitForm() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [reporterId, setReporterId] = useState("citizen-001");
  const [caption, setCaption] = useState("");
  const [busy, setBusy] = useState(false);
  const [drag, setDrag] = useState(false);
  const [lastResult, setLastResult] = useState<{ id: number; gps: boolean } | null>(null);

  async function submit(file: File) {
    if (!reporterId.trim()) {
      toast.warn("reporter_id required", "Set the reporter token first.");
      return;
    }
    setBusy(true);
    try {
      const r = await api.publicSubmit(file, reporterId.trim(), caption.trim() || undefined);
      setLastResult({ id: r.mission_id, gps: r.has_gps });
      if (r.has_gps) {
        toast.success(`Mission #${r.mission_id} ingested`, "EXIF-GPS · pipeline running");
      } else {
        toast.warn(`Mission #${r.mission_id} awaiting pin`, "No EXIF GPS — triage queue ready for operator");
      }
    } catch (e) {
      toast.crit("Public submit failed", (e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function onDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDrag(false);
    const f = e.dataTransfer.files?.[0];
    if (f) submit(f);
  }

  return (
    <div className="glass rounded-lg shadow-panel p-4">
      <div className="flex items-center justify-between mb-3">
        <div>
          <div className="text-2xs uppercase-wide tracking-wider text-muted2 font-mono">PUBLIC SUBMISSION</div>
          <div className="text-[10px] text-muted font-mono mt-0.5">citizen tip · pipeline-mediated · audit-logged</div>
        </div>
        <Link
          to="/public-reports"
          className="text-2xs font-mono text-muted hover:text-text uppercase-wide tracking-wider flex items-center gap-1"
          title="Operator triage queue"
        >
          <Inbox size={11} /> triage
        </Link>
      </div>

      <div className="grid grid-cols-[1fr_240px] gap-3">
        <div
          onDragEnter={(e) => { e.preventDefault(); setDrag(true); }}
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={onDrop}
          onClick={() => fileRef.current?.click()}
          className={`relative cursor-pointer rounded-md border-2 border-dashed px-4 py-5 flex flex-col items-center justify-center gap-1.5 text-center transition-fast ${
            drag
              ? "border-accent bg-accent/10 text-accent"
              : "border-border bg-panel2/30 text-muted hover:text-text hover:border-cyan/40 hover:bg-panel2/60"
          }`}
        >
          {busy
            ? <Loader2 size={18} className="animate-spin text-accent" />
            : <Upload size={18} className={drag ? "text-accent" : "text-muted2"} />}
          <div className="text-xs font-mono">
            {busy ? "ingesting…" : "drag a tipped photo here"}
          </div>
          <div className="text-2xs text-muted2 font-mono">
            JPG / PNG · EXIF-GPS auto-anchors · otherwise → triage
          </div>
          <input
            ref={fileRef}
            type="file"
            accept="image/jpeg,image/png"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) submit(f);
              e.target.value = "";
            }}
          />
        </div>

        <div className="flex flex-col gap-2 text-2xs">
          <label className="text-muted2 uppercase-wide tracking-wider font-mono">reporter_id</label>
          <input
            value={reporterId}
            onChange={(e) => setReporterId(e.target.value)}
            placeholder="opaque submitter token"
            className="bg-panel border border-border rounded px-2 py-1.5 text-xs font-mono"
          />
          <label className="text-muted2 uppercase-wide tracking-wider font-mono mt-1">caption (optional)</label>
          <textarea
            value={caption}
            onChange={(e) => setCaption(e.target.value)}
            placeholder="brief context — visible on triage card"
            rows={3}
            className="bg-panel border border-border rounded px-2 py-1.5 text-xs font-mono resize-none"
          />
          {lastResult && (
            <div
              className={`mt-1 px-2 py-1.5 rounded border font-mono text-2xs flex items-center gap-1.5 ${
                lastResult.gps
                  ? "border-threat-low/40 bg-threat-low/10 text-threat-low"
                  : "border-threat-high/40 bg-threat-high/10 text-threat-high"
              }`}
            >
              <MapPin size={10} />
              <span>
                #{lastResult.id} · {lastResult.gps ? "auto-anchored" : "awaiting pin"}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
