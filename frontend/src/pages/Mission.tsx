import { useEffect, useRef, useState } from "react";
import { Upload, Play, Loader2, Zap, Check, X, Eye } from "lucide-react";
import { DEFAULT_AOI, api } from "../lib/api";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

// Brand-aligned colors per class
const CLASS_COLORS: Record<string, string> = {
  "small-vehicle":       "#4ade80",
  "large-vehicle":       "#facc15",
  "aircraft-fixed-wing": "#60a5fa",
  "aircraft-rotor":      "#a78bfa",
  "ship":                "#22d3ee",
  "storage-depot":       "#fb923c",
  "harbor":              "#f472b6",
  "bridge":              "#94a3b8",
};

type Detection = {
  class_id: number;
  class_name: string;
  confidence: number;
  x1: number; y1: number; x2: number; y2: number;
};

type PredictResponse = {
  image: { width: number; height: number };
  detections: Detection[];
  latency_ms: number;
  model: { name: string; backbone: string; imgsz: number };
};

export default function Mission() {
  const fileRef = useRef<HTMLInputElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const [missionName, setMissionName] = useState(`MISSION-${new Date().toISOString().slice(0,16).replace(/[-T:]/g,"")}`);
  const [fileUrl, setFileUrl] = useState<string | null>(null);
  const [fileType, setFileType] = useState<"image" | "video" | null>(null);
  const [currentFile, setCurrentFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PredictResponse | null>(null);
  const [saveToDb, setSaveToDb] = useState(true);
  const [savedMissionId, setSavedMissionId] = useState<number | null>(null);
  const [explainUrl, setExplainUrl] = useState<string | null>(null);
  const [explainLoading, setExplainLoading] = useState(false);
  const [explainedClass, setExplainedClass] = useState<string | null>(null);

  const onPick = () => fileRef.current?.click();

  const onFile = (f: File | null) => {
    if (!f) return;
    if (explainUrl) URL.revokeObjectURL(explainUrl);
    setExplainUrl(null);
    setExplainedClass(null);
    setError(null);
    setResult(null);
    setSavedMissionId(null);
    setFileUrl(URL.createObjectURL(f));
    setFileType(f.type.startsWith("video/") ? "video" : "image");
    setCurrentFile(f);
  };

  // Fire-and-forget ingest to DB so Map/Alerts/Audit pages populate.
  async function saveMission(f: File) {
    try {
      const m = await api.ingest(f, missionName, DEFAULT_AOI);
      setSavedMissionId(m.id);
      localStorage.setItem("astra:lastMissionId", String(m.id));
    } catch (e) {
      // don't interrupt the live preview — just log
      console.warn("ingest failed:", e);
    }
  }

  // Click-to-explain: find which box was clicked, fetch heatmap, show it.
  async function onCanvasClick(e: React.MouseEvent<HTMLCanvasElement>) {
    if (!result || !currentFile) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    // Click coords in canvas-display space
    const cx = e.clientX - rect.left;
    const cy = e.clientY - rect.top;
    // Convert to original-image coords (inverse of the box-draw scale)
    const scaleX = result.image.width / rect.width;
    const scaleY = result.image.height / rect.height;
    const ix = cx * scaleX;
    const iy = cy * scaleY;
    // Find the first detection that contains this point
    const hit = result.detections.find(
      (d) => ix >= d.x1 && ix <= d.x2 && iy >= d.y1 && iy <= d.y2
    );
    if (!hit) return;
    setExplainLoading(true);
    setExplainedClass(hit.class_name);
    try {
      const fd = new FormData();
      fd.append("file", currentFile);
      fd.append("x1", String(hit.x1));
      fd.append("y1", String(hit.y1));
      fd.append("x2", String(hit.x2));
      fd.append("y2", String(hit.y2));
      const res = await fetch(`${API_BASE}/api/v1/explain`, { method: "POST", body: fd });
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const blob = await res.blob();
      // Revoke old URL if any
      if (explainUrl) URL.revokeObjectURL(explainUrl);
      setExplainUrl(URL.createObjectURL(blob));
    } catch (err) {
      setError(`explain failed: ${(err as Error).message}`);
    } finally {
      setExplainLoading(false);
    }
  }

  function closeExplanation() {
    if (explainUrl) URL.revokeObjectURL(explainUrl);
    setExplainUrl(null);
    setExplainedClass(null);
  }

  async function runPredict(blob: Blob, filename: string) {
    setBusy(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", blob, filename);
      const res = await fetch(`${API_BASE}/api/v1/predict`, { method: "POST", body: fd });
      if (!res.ok) throw new Error(`${res.status} ${res.statusText} — ${await res.text()}`);
      const json = (await res.json()) as PredictResponse;
      setResult(json);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  // Auto-predict when an image loads
  useEffect(() => {
    if (!fileUrl || fileType !== "image" || !currentFile) return;
    fetch(fileUrl).then(r => r.blob()).then(b => runPredict(b, "upload.jpg"));
    if (saveToDb) saveMission(currentFile);
  }, [fileUrl, fileType, currentFile]);

  // Analyze current frame from video
  async function analyzeVideoFrame() {
    const v = videoRef.current;
    if (!v) return;
    const tmpCanvas = document.createElement("canvas");
    tmpCanvas.width = v.videoWidth;
    tmpCanvas.height = v.videoHeight;
    tmpCanvas.getContext("2d")!.drawImage(v, 0, 0);
    const blob: Blob = await new Promise(resolve =>
      tmpCanvas.toBlob(b => resolve(b!), "image/jpeg", 0.9)
    );
    await runPredict(blob, "frame.jpg");
  }

  // Draw boxes whenever result or image changes
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !result) return;
    const base = fileType === "video" ? videoRef.current : imgRef.current;
    if (!base) return;

    const rect = base.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;

    const ctx = canvas.getContext("2d")!;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const scaleX = canvas.width / result.image.width;
    const scaleY = canvas.height / result.image.height;

    ctx.font = "12px ui-monospace, Consolas, monospace";
    ctx.lineWidth = 2;

    for (const d of result.detections) {
      const color = CLASS_COLORS[d.class_name] ?? "#ff7a1a";
      const x = d.x1 * scaleX;
      const y = d.y1 * scaleY;
      const w = (d.x2 - d.x1) * scaleX;
      const h = (d.y2 - d.y1) * scaleY;
      ctx.strokeStyle = color;
      ctx.strokeRect(x, y, w, h);

      const label = `${d.class_name} ${d.confidence.toFixed(2)}`;
      const textW = ctx.measureText(label).width + 8;
      ctx.fillStyle = color;
      ctx.fillRect(x, y - 16, textW, 16);
      ctx.fillStyle = "#0a0f14";
      ctx.fillText(label, x + 4, y - 4);
    }
  }, [result, fileUrl, fileType]);

  const classCounts: Record<string, number> = {};
  for (const d of result?.detections ?? []) {
    classCounts[d.class_name] = (classCounts[d.class_name] ?? 0) + 1;
  }

  return (
    <div className="h-full flex flex-col">
      <header className="px-6 py-4 border-b border-border flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">Live Mission Feed</h1>
          <p className="text-xs text-muted">
            Upload a drone image or clip — detections run on real yolo11n model
          </p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-xs text-muted cursor-pointer select-none">
            <input
              type="checkbox"
              checked={saveToDb}
              onChange={(e) => setSaveToDb(e.target.checked)}
              className="accent-accent"
            />
            Save to DB
          </label>
          {savedMissionId != null && (
            <span className="flex items-center gap-1 text-xs text-threat-low">
              <Check size={12} /> Mission #{savedMissionId}
            </span>
          )}
          <input
            className="bg-panel border border-border rounded px-3 py-1.5 text-sm w-48 font-mono"
            value={missionName}
            onChange={(e) => setMissionName(e.target.value)}
          />
          <input
            ref={fileRef}
            type="file"
            accept="image/*,video/*"
            className="hidden"
            onChange={(e) => onFile(e.target.files?.[0] ?? null)}
          />
          <button
            onClick={onPick}
            className="flex items-center gap-2 bg-accent text-bg px-4 py-1.5 rounded text-sm font-medium hover:brightness-110"
          >
            <Upload size={14} /> Ingest
          </button>
          {fileType === "video" && (
            <button
              onClick={analyzeVideoFrame}
              disabled={busy}
              className="flex items-center gap-2 bg-panel2 border border-border px-4 py-1.5 rounded text-sm hover:bg-panel disabled:opacity-50"
            >
              {busy ? <Loader2 size={14} className="animate-spin" /> : <Zap size={14} />}
              Analyze frame
            </button>
          )}
        </div>
      </header>

      <div className="flex-1 p-6 grid grid-cols-[1fr_320px] gap-6 overflow-hidden">
        <div className="relative bg-panel border border-border rounded overflow-hidden flex items-center justify-center">
          {fileUrl ? (
            <>
              {fileType === "image" ? (
                <img
                  ref={imgRef}
                  src={fileUrl}
                  alt="uploaded"
                  className="max-h-full max-w-full"
                  onLoad={() => {
                    // Re-trigger box redraw by touching state
                    if (result) setResult({ ...result });
                  }}
                />
              ) : (
                <video
                  ref={videoRef}
                  src={fileUrl}
                  controls
                  className="max-h-full max-w-full"
                />
              )}
              {/* Heatmap overlay (shown when an explanation is active) */}
              {explainUrl && (
                <img
                  src={explainUrl}
                  alt="Grad-CAM heatmap"
                  className="absolute inset-0 m-auto max-h-full max-w-full"
                />
              )}
              <canvas
                ref={canvasRef}
                onClick={onCanvasClick}
                className={`absolute inset-0 m-auto ${
                  explainUrl ? "pointer-events-none opacity-0" : "cursor-pointer"
                }`}
                style={{ width: "auto", height: "auto" }}
                title="Click any detection to see why the model chose it"
              />
              {busy && (
                <div className="absolute top-3 right-3 bg-bg/80 border border-border px-3 py-1.5 rounded flex items-center gap-2 text-xs">
                  <Loader2 size={12} className="animate-spin" /> Running inference...
                </div>
              )}
              {explainLoading && (
                <div className="absolute top-3 right-3 bg-bg/80 border border-border px-3 py-1.5 rounded flex items-center gap-2 text-xs">
                  <Loader2 size={12} className="animate-spin" /> Computing heatmap for {explainedClass}...
                </div>
              )}
              {explainUrl && !explainLoading && (
                <div className="absolute top-3 left-3 bg-bg/90 border border-border px-3 py-1.5 rounded flex items-center gap-2 text-xs">
                  <Eye size={12} className="text-accent" />
                  <span className="font-mono">{explainedClass} — model attention</span>
                  <button
                    onClick={closeExplanation}
                    className="ml-2 p-0.5 rounded hover:bg-panel2 text-muted"
                    title="Close heatmap"
                  >
                    <X size={12} />
                  </button>
                </div>
              )}
              {result && !explainUrl && !busy && (
                <div className="absolute bottom-3 left-3 bg-bg/80 border border-border px-2.5 py-1 rounded text-[11px] text-muted">
                  💡 Click a box to see why the model chose it (Grad-CAM)
                </div>
              )}
            </>
          ) : (
            <div className="text-center text-muted">
              <Play size={48} className="mx-auto mb-3 opacity-30" />
              <p className="text-sm">
                No feed loaded. Click <span className="text-accent">Ingest</span> to begin.
              </p>
              <p className="text-xs mt-1 text-muted">
                Supports images (PNG/JPG) and videos (MP4/MOV)
              </p>
            </div>
          )}
        </div>

        <aside className="bg-panel border border-border rounded p-4 space-y-4 overflow-auto">
          <div>
            <div className="text-xs text-muted uppercase tracking-wider mb-1">Model</div>
            <div className="font-mono text-sm">astra-v1 · yolo11n · 640²</div>
          </div>
          <div>
            <div className="text-xs text-muted uppercase tracking-wider mb-1">Device</div>
            <div className="font-mono text-sm">RTX 4050 Laptop · FP32</div>
          </div>

          {error && (
            <div className="bg-threat-crit/20 border border-threat-crit/40 text-threat-crit p-3 rounded text-xs">
              {error}
            </div>
          )}

          {result && (
            <>
              <div className="grid grid-cols-2 gap-2">
                <div className="bg-panel2 rounded px-3 py-2">
                  <div className="text-muted text-xs">Latency</div>
                  <div className="text-xl font-mono">{result.latency_ms.toFixed(1)}ms</div>
                </div>
                <div className="bg-panel2 rounded px-3 py-2">
                  <div className="text-muted text-xs">Detections</div>
                  <div className="text-xl font-mono">{result.detections.length}</div>
                </div>
              </div>

              <div>
                <div className="text-xs text-muted uppercase tracking-wider mb-2">By class</div>
                <div className="space-y-1">
                  {Object.entries(classCounts)
                    .sort(([, a], [, b]) => b - a)
                    .map(([name, n]) => (
                      <div key={name} className="flex items-center justify-between text-xs font-mono">
                        <div className="flex items-center gap-2">
                          <span
                            className="w-2 h-2 rounded-sm"
                            style={{ background: CLASS_COLORS[name] ?? "#ff7a1a" }}
                          />
                          <span>{name}</span>
                        </div>
                        <span className="text-accent">{n}</span>
                      </div>
                    ))}
                </div>
              </div>

              <div>
                <div className="text-xs text-muted uppercase tracking-wider mb-2">
                  Top detections
                </div>
                <div className="space-y-1 font-mono text-xs">
                  {result.detections
                    .slice()
                    .sort((a, b) => b.confidence - a.confidence)
                    .slice(0, 8)
                    .map((d, i) => (
                      <div
                        key={i}
                        className="flex justify-between items-center py-1 border-b border-border last:border-0"
                      >
                        <span>{d.class_name}</span>
                        <span className="text-muted">{(d.confidence * 100).toFixed(0)}%</span>
                      </div>
                    ))}
                </div>
              </div>
            </>
          )}

          {!result && !busy && fileUrl && (
            <div className="text-xs text-muted">
              {fileType === "video"
                ? "Click \"Analyze frame\" to run detection"
                : "Running first inference..."}
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
