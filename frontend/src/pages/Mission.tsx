import { useEffect, useRef, useState } from "react";
import { Upload, Play, Loader2, Zap } from "lucide-react";

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

  const [missionName, setMissionName] = useState("MISSION-001");
  const [fileUrl, setFileUrl] = useState<string | null>(null);
  const [fileType, setFileType] = useState<"image" | "video" | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PredictResponse | null>(null);

  const onPick = () => fileRef.current?.click();

  const onFile = (f: File | null) => {
    if (!f) return;
    setError(null);
    setResult(null);
    setFileUrl(URL.createObjectURL(f));
    setFileType(f.type.startsWith("video/") ? "video" : "image");
  };

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
    if (!fileUrl || fileType !== "image") return;
    fetch(fileUrl).then(r => r.blob()).then(b => runPredict(b, "upload.jpg"));
  }, [fileUrl, fileType]);

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
          <input
            className="bg-panel border border-border rounded px-3 py-1.5 text-sm w-48"
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
              <canvas
                ref={canvasRef}
                className="absolute inset-0 pointer-events-none m-auto"
                style={{ width: "auto", height: "auto" }}
              />
              {busy && (
                <div className="absolute top-3 right-3 bg-bg/80 border border-border px-3 py-1.5 rounded flex items-center gap-2 text-xs">
                  <Loader2 size={12} className="animate-spin" /> Running inference...
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
