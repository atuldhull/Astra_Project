import { useRef, useState } from "react";
import { Upload, Loader2, Shield, Zap, Play, Skull } from "lucide-react";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

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

type BriefDet = {
  class_id: number;
  class_name: string;
  confidence: number;
  x1: number; y1: number; x2: number; y2: number;
};

type AdvResponse = {
  epsilon: number;
  method_used: string;
  latency_ms: number;
  image_size: { width: number; height: number };
  original:  { detection_count: number; class_counts: Record<string, number>; detections: BriefDet[] };
  perturbed: { detection_count: number; class_counts: Record<string, number>; detections: BriefDet[] };
  perturbed_image_base64: string;
};

export default function Adversarial() {
  const fileRef = useRef<HTMLInputElement>(null);
  const origCanvasRef = useRef<HTMLCanvasElement>(null);
  const pertCanvasRef = useRef<HTMLCanvasElement>(null);
  const origImgRef = useRef<HTMLImageElement>(null);
  const pertImgRef = useRef<HTMLImageElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [fileUrl, setFileUrl] = useState<string | null>(null);
  const [epsilon, setEpsilon] = useState(0.05);
  const [method, setMethod] = useState<"fgsm" | "noise">("fgsm");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AdvResponse | null>(null);

  const onPick = () => fileRef.current?.click();

  const onFile = (f: File | null) => {
    if (!f) return;
    setFile(f);
    setFileUrl(URL.createObjectURL(f));
    setResult(null);
    setError(null);
  };

  async function runAttack() {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("epsilon", String(epsilon));
      fd.append("method", method);
      const res = await fetch(`${API_BASE}/api/v1/adversarial`, { method: "POST", body: fd });
      if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
      const json = await res.json() as AdvResponse;
      setResult(json);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function drawBoxes(
    canvas: HTMLCanvasElement | null,
    img: HTMLImageElement | null,
    dets: BriefDet[],
    imageW: number,
    imageH: number,
  ) {
    if (!canvas || !img) return;
    const rect = img.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;
    const ctx = canvas.getContext("2d")!;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const sx = rect.width / imageW;
    const sy = rect.height / imageH;
    ctx.font = "11px ui-monospace, Consolas, monospace";
    ctx.lineWidth = 2;
    for (const d of dets) {
      const color = CLASS_COLORS[d.class_name] ?? "#ff7a1a";
      ctx.strokeStyle = color;
      ctx.strokeRect(d.x1 * sx, d.y1 * sy, (d.x2 - d.x1) * sx, (d.y2 - d.y1) * sy);
      const label = `${d.class_name} ${d.confidence.toFixed(2)}`;
      const tw = ctx.measureText(label).width + 6;
      ctx.fillStyle = color;
      ctx.fillRect(d.x1 * sx, d.y1 * sy - 14, tw, 14);
      ctx.fillStyle = "#0a0f14";
      ctx.fillText(label, d.x1 * sx + 3, d.y1 * sy - 3);
    }
  }

  // Redraw boxes after images load or result changes
  const onOrigLoad = () => {
    if (result) drawBoxes(origCanvasRef.current, origImgRef.current, result.original.detections, result.image_size.width, result.image_size.height);
  };
  const onPertLoad = () => {
    if (result) drawBoxes(pertCanvasRef.current, pertImgRef.current, result.perturbed.detections, result.image_size.width, result.image_size.height);
  };

  const origCount = result?.original.detection_count ?? 0;
  const pertCount = result?.perturbed.detection_count ?? 0;
  const delta = pertCount - origCount;
  const pctChange = origCount > 0 ? (delta / origCount) * 100 : 0;

  return (
    <div className="h-full flex flex-col">
      <header className="px-6 py-4 border-b border-border flex items-center justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold flex items-center gap-2">
            <Shield size={18} className="text-accent" /> Adversarial Robustness Test
          </h1>
          <p className="text-xs text-muted">
            FGSM and noise-based perturbation · same image, imperceptible pixel-level changes, detection collapses
          </p>
        </div>
        <div className="flex items-center gap-3">
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => onFile(e.target.files?.[0] ?? null)}
          />
          <button
            onClick={onPick}
            className="flex items-center gap-2 bg-panel2 border border-border px-4 py-1.5 rounded text-sm hover:bg-panel"
          >
            <Upload size={14} /> Pick Image
          </button>
          <button
            onClick={runAttack}
            disabled={!file || busy}
            className="flex items-center gap-2 bg-accent text-bg px-4 py-1.5 rounded text-sm font-medium hover:brightness-110 disabled:opacity-50"
          >
            {busy ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            {busy ? "Attacking..." : "Run attack"}
          </button>
        </div>
      </header>

      {error && (
        <div className="mx-6 mt-3 bg-threat-crit/20 border border-threat-crit/40 text-threat-crit p-2 rounded text-xs">
          {error}
        </div>
      )}

      <div className="flex-1 p-6 grid grid-cols-[1fr_1fr_280px] gap-4 overflow-hidden">
        {/* Original panel */}
        <div className="bg-panel border border-border rounded overflow-hidden flex flex-col">
          <div className="px-4 py-2 bg-panel2 border-b border-border flex items-center justify-between text-xs">
            <span className="text-threat-low font-mono flex items-center gap-1">
              <Shield size={12} /> ORIGINAL
            </span>
            {result && (
              <span className="font-mono text-muted">
                {origCount} detections
              </span>
            )}
          </div>
          <div className="relative flex-1 flex items-center justify-center bg-bg">
            {fileUrl ? (
              <>
                <img
                  ref={origImgRef}
                  src={fileUrl}
                  alt="original"
                  className="max-h-full max-w-full"
                  onLoad={onOrigLoad}
                />
                <canvas
                  ref={origCanvasRef}
                  className="absolute inset-0 m-auto pointer-events-none"
                  style={{ width: "auto", height: "auto" }}
                />
              </>
            ) : (
              <div className="text-xs text-muted text-center px-6">
                Upload any aerial image to begin.
                <br />
                Suggested: <code className="text-accent">D:\astra-data\demo-samples\02-airfield-hero.jpg</code>
              </div>
            )}
          </div>
        </div>

        {/* Perturbed panel */}
        <div className="bg-panel border border-border rounded overflow-hidden flex flex-col">
          <div className="px-4 py-2 bg-panel2 border-b border-border flex items-center justify-between text-xs">
            <span className="text-threat-crit font-mono flex items-center gap-1">
              <Skull size={12} /> PERTURBED (ε={epsilon.toFixed(2)})
            </span>
            {result && (
              <span className={`font-mono ${delta < 0 ? "text-threat-crit" : delta > 0 ? "text-threat-high" : "text-muted"}`}>
                {pertCount} detections ({delta >= 0 ? "+" : ""}{delta}, {pctChange >= 0 ? "+" : ""}{pctChange.toFixed(0)}%)
              </span>
            )}
          </div>
          <div className="relative flex-1 flex items-center justify-center bg-bg">
            {result?.perturbed_image_base64 ? (
              <>
                <img
                  ref={pertImgRef}
                  src={result.perturbed_image_base64}
                  alt="perturbed"
                  className="max-h-full max-w-full"
                  onLoad={onPertLoad}
                />
                <canvas
                  ref={pertCanvasRef}
                  className="absolute inset-0 m-auto pointer-events-none"
                  style={{ width: "auto", height: "auto" }}
                />
              </>
            ) : (
              <div className="text-xs text-muted">
                {busy ? (
                  <div className="flex items-center gap-2">
                    <Loader2 size={12} className="animate-spin" /> Computing attack...
                  </div>
                ) : (
                  "Click 'Run attack' to perturb"
                )}
              </div>
            )}
          </div>
        </div>

        {/* Control + stats panel */}
        <aside className="bg-panel border border-border rounded p-4 space-y-4 overflow-auto">
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-muted font-mono">epsilon (ε)</span>
              <span className="font-mono text-sm">{epsilon.toFixed(3)}</span>
            </div>
            <input
              type="range" min={0} max={0.2} step={0.005}
              value={epsilon}
              onChange={(e) => setEpsilon(Number(e.target.value))}
              className="w-full accent-accent"
            />
            <div className="flex justify-between text-[10px] text-muted mt-1 font-mono">
              <span>0 (none)</span>
              <span>0.05 (imperceptible)</span>
              <span>0.2 (visible)</span>
            </div>
          </div>

          <div>
            <div className="text-xs text-muted font-mono mb-1.5">attack method</div>
            <div className="grid grid-cols-2 gap-2">
              {(["fgsm", "noise"] as const).map((m) => (
                <button
                  key={m}
                  onClick={() => setMethod(m)}
                  className={`py-1.5 rounded text-xs font-mono border ${
                    method === m
                      ? "bg-accent text-bg border-accent"
                      : "bg-panel2 border-border text-muted hover:text-text"
                  }`}
                >
                  {m}
                </button>
              ))}
            </div>
            <p className="text-[10px] text-muted mt-2 leading-snug">
              {method === "fgsm"
                ? "Fast Gradient Sign Method — computes ∂loss/∂pixel, perturbs in the direction that lowers class confidence. Proper adversarial attack."
                : "Gaussian noise scaled by ε. Not adversarial — just robustness-to-noise baseline. Always succeeds."}
            </p>
          </div>

          {result && (
            <>
              <div className="border-t border-border pt-3">
                <div className="text-xs text-muted uppercase tracking-wider mb-2">Result</div>
                <div className="space-y-2 text-xs">
                  <div className="flex justify-between font-mono">
                    <span className="text-muted">Method</span>
                    <span>{result.method_used}</span>
                  </div>
                  <div className="flex justify-between font-mono">
                    <span className="text-muted">Latency</span>
                    <span>{result.latency_ms.toFixed(0)}ms</span>
                  </div>
                  <div className="flex justify-between font-mono">
                    <span className="text-muted">Detection delta</span>
                    <span className={delta < 0 ? "text-threat-crit" : delta > 0 ? "text-threat-high" : "text-muted"}>
                      {delta >= 0 ? "+" : ""}{delta} ({pctChange >= 0 ? "+" : ""}{pctChange.toFixed(0)}%)
                    </span>
                  </div>
                </div>
              </div>

              <div className="border-t border-border pt-3">
                <div className="text-xs text-muted uppercase tracking-wider mb-2">Class counts</div>
                <div className="space-y-1 text-xs font-mono">
                  {(() => {
                    const allClasses = new Set([
                      ...Object.keys(result.original.class_counts),
                      ...Object.keys(result.perturbed.class_counts),
                    ]);
                    return Array.from(allClasses).map((cls) => {
                      const o = result.original.class_counts[cls] ?? 0;
                      const p = result.perturbed.class_counts[cls] ?? 0;
                      const d = p - o;
                      return (
                        <div key={cls} className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: CLASS_COLORS[cls] ?? "#ff7a1a" }} />
                            <span>{cls}</span>
                          </div>
                          <span>
                            <span className="text-muted">{o}→{p}</span>
                            <span className={`ml-2 ${d < 0 ? "text-threat-crit" : d > 0 ? "text-threat-high" : "text-muted"}`}>
                              ({d >= 0 ? "+" : ""}{d})
                            </span>
                          </span>
                        </div>
                      );
                    });
                  })()}
                </div>
              </div>
            </>
          )}

          <div className="border-t border-border pt-3 text-[11px] text-muted leading-snug">
            <div className="flex items-center gap-1 mb-1 text-accent">
              <Zap size={10} /> Pitch framing
            </div>
            <p>
              Judges will ask about camouflage / adversarial patches. This page shows the answer: <b>current baseline has measurable adversarial weakness</b>. Roadmap v2 adds adversarial training + randomized smoothing as the mitigation.
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}
