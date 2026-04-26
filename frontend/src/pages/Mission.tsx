import { useEffect, useRef, useState } from "react";
import { Upload, Play, Loader2, Zap, Check, X, Eye, Radio, MapPin } from "lucide-react";
import { DEFAULT_AOI, api, detectionLabel, type Detection as DbDetection, type Mission as DbMission } from "../lib/api";

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
  const [savedMission, setSavedMission] = useState<DbMission | null>(null);
  const [explainUrl, setExplainUrl] = useState<string | null>(null);
  const [explainLoading, setExplainLoading] = useState(false);
  const [explainedClass, setExplainedClass] = useState<string | null>(null);
  const [streamUrl, setStreamUrl] = useState("");
  const [streamDialogOpen, setStreamDialogOpen] = useState(false);
  const [streamBusy, setStreamBusy] = useState(false);
  const [videoDets, setVideoDets] = useState<DbDetection[]>([]);
  const [videoPolling, setVideoPolling] = useState(false);
  const [videoCurrentTime, setVideoCurrentTime] = useState(0);

  const onPick = () => fileRef.current?.click();

  const onFile = (f: File | null) => {
    if (!f) return;
    if (explainUrl) URL.revokeObjectURL(explainUrl);
    setExplainUrl(null);
    setExplainedClass(null);
    setError(null);
    setResult(null);
    setSavedMissionId(null);
    setSavedMission(null);
    setVideoDets([]);
    setVideoCurrentTime(0);
    setFileUrl(URL.createObjectURL(f));
    setFileType(f.type.startsWith("video/") ? "video" : "image");
    setCurrentFile(f);
  };

  // Fire-and-forget ingest to DB so Map/Alerts/Audit pages populate.
  // Note: we only pass DEFAULT_AOI for videos. For images we leave aoi empty
  // so the backend can try EXIF-GPS extraction first, falling back to the
  // default only if no GPS is present.
  async function saveMission(f: File) {
    try {
      let m: DbMission;
      if (f.type.startsWith("video/")) {
        m = await api.ingest(f, missionName, DEFAULT_AOI);
      } else {
        // Let backend auto-detect GPS or use its default
        m = await api.ingestAuto(f, missionName);
      }
      setSavedMissionId(m.id);
      setSavedMission(m);
      localStorage.setItem("astra:lastMissionId", String(m.id));
    } catch (e) {
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

  // Ingest from a live URL / RTSP stream
  async function submitStreamUrl() {
    if (!streamUrl.trim()) return;
    setStreamBusy(true);
    setError(null);
    try {
      const m = await api.ingestUrl(streamUrl.trim(), missionName, DEFAULT_AOI, {
        max_frames: 30, duration_s: 5,
      });
      setSavedMissionId(m.id);
      localStorage.setItem("astra:lastMissionId", String(m.id));
      setStreamDialogOpen(false);
      // Show a friendly message via error banner acting as a toast
      setError(`✓ Stream captured · Mission #${m.id}. Switch to Map/Alerts to see results.`);
    } catch (e) {
      setError(`stream: ${(e as Error).message}`);
    } finally {
      setStreamBusy(false);
    }
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
    if (!fileUrl || !currentFile) return;
    if (fileType === "image") {
      fetch(fileUrl).then(r => r.blob()).then(b => runPredict(b, "upload.jpg"));
      if (saveToDb) saveMission(currentFile);
    } else if (fileType === "video" && saveToDb) {
      // Videos can't run /predict on a single frame reliably — we ingest,
      // wait for the pipeline to produce tracked detections, then overlay
      // them on playback.
      saveMission(currentFile);
    }
  }, [fileUrl, fileType, currentFile]);

  // Poll detections for video missions until we have results
  useEffect(() => {
    if (fileType !== "video" || savedMissionId == null) return;
    let cancelled = false;
    let attempts = 0;
    const MAX_ATTEMPTS = 15;  // ~30 seconds of polling
    setVideoPolling(true);

    const poll = async () => {
      attempts++;
      try {
        const dets = await api.listDetections({ mission_id: savedMissionId, limit: 1000 });
        if (cancelled) return;
        if (dets.length > 0) {
          setVideoDets(dets);
          setVideoPolling(false);
          return true;  // stop polling
        }
      } catch {}
      return false;
    };

    const interval = window.setInterval(async () => {
      const done = await poll();
      if (done || attempts >= MAX_ATTEMPTS || cancelled) {
        window.clearInterval(interval);
        if (!cancelled) setVideoPolling(false);
      }
    }, 2000);

    // Initial probe
    poll().then((done) => {
      if (done) window.clearInterval(interval);
    });

    return () => {
      cancelled = true;
      window.clearInterval(interval);
      setVideoPolling(false);
    };
  }, [fileType, savedMissionId]);

  // Track the video's current time so the canvas redraw effect re-fires
  useEffect(() => {
    const video = videoRef.current;
    if (!video || fileType !== "video") return;
    const onTime = () => setVideoCurrentTime(video.currentTime);
    video.addEventListener("timeupdate", onTime);
    video.addEventListener("seeked", onTime);
    return () => {
      video.removeEventListener("timeupdate", onTime);
      video.removeEventListener("seeked", onTime);
    };
  }, [fileType, fileUrl]);

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

  // Draw boxes whenever result/time/detections change
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    // ── IMAGE MODE ────────────────────────────────────────────────────
    if (fileType === "image" && result) {
      const base = imgRef.current;
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
      return;
    }

    // ── VIDEO MODE ────────────────────────────────────────────────────
    if (fileType === "video" && videoDets.length > 0) {
      const video = videoRef.current;
      if (!video || !video.videoWidth || !video.videoHeight) return;
      const rect = video.getBoundingClientRect();
      canvas.width = rect.width;
      canvas.height = rect.height;

      const ctx = canvas.getContext("2d")!;
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Scale from original video pixels -> rendered display
      const scaleX = rect.width / video.videoWidth;
      const scaleY = rect.height / video.videoHeight;

      // Find detections near current video time (±200ms window)
      const currentMs = videoCurrentTime * 1000;
      const WINDOW_MS = 250;
      const current = videoDets.filter(
        (d) => Math.abs(d.frame_timestamp_ms - currentMs) <= WINDOW_MS
      );

      // Draw trails for tracked detections (all past points up to now, per track)
      const trackGroups: Record<number, DbDetection[]> = {};
      for (const d of videoDets) {
        if (d.track_id == null) continue;
        if (d.frame_timestamp_ms > currentMs) continue;  // future, skip
        (trackGroups[d.track_id] ??= []).push(d);
      }

      ctx.lineWidth = 1.5;
      for (const tid of Object.keys(trackGroups)) {
        const group = trackGroups[Number(tid)].sort(
          (a, b) => a.frame_timestamp_ms - b.frame_timestamp_ms
        );
        if (group.length < 2) continue;
        const color = CLASS_COLORS[group[0].class_name] ?? "#ff7a1a";
        ctx.strokeStyle = color;
        ctx.globalAlpha = 0.35;
        ctx.beginPath();
        for (let i = 0; i < group.length; i++) {
          const d = group[i];
          const cx = ((d.x1 + d.x2) / 2) * scaleX;
          const cy = ((d.y1 + d.y2) / 2) * scaleY;
          if (i === 0) ctx.moveTo(cx, cy);
          else ctx.lineTo(cx, cy);
        }
        ctx.stroke();
        ctx.globalAlpha = 1;
      }

      // Draw current boxes
      ctx.font = "12px ui-monospace, Consolas, monospace";
      ctx.lineWidth = 2;
      for (const d of current) {
        const color = CLASS_COLORS[d.class_name] ?? "#ff7a1a";
        const x = d.x1 * scaleX;
        const y = d.y1 * scaleY;
        const w = (d.x2 - d.x1) * scaleX;
        const h = (d.y2 - d.y1) * scaleY;
        ctx.strokeStyle = color;
        ctx.strokeRect(x, y, w, h);

        // Prefer the MAR20 cascade airframe ID when available
        const lbl = detectionLabel(d);
        const showSub = d.extras?.airframe != null;
        const conf = showSub && d.extras?.airframe_confidence != null
          ? d.extras.airframe_confidence
          : d.confidence;
        const label = d.track_id != null
          ? `#${d.track_id} · ${lbl} ${conf.toFixed(2)}`
          : `${lbl} ${conf.toFixed(2)}`;
        const textW = ctx.measureText(label).width + 8;
        ctx.fillStyle = color;
        ctx.fillRect(x, y - 16, textW, 16);
        ctx.fillStyle = "#0a0f14";
        ctx.fillText(label, x + 4, y - 4);
      }
      return;
    }

    // Fallback: no data — clear
    const ctx = canvas.getContext("2d")!;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  }, [result, fileUrl, fileType, videoDets, videoCurrentTime]);

  const classCounts: Record<string, number> = {};
  for (const d of result?.detections ?? []) {
    classCounts[d.class_name] = (classCounts[d.class_name] ?? 0) + 1;
  }

  // Video-mode aggregates
  const currentMs = videoCurrentTime * 1000;
  const videoCurrentDets = fileType === "video"
    ? videoDets.filter((d) => Math.abs(d.frame_timestamp_ms - currentMs) <= 250)
    : [];
  const videoClassCounts: Record<string, number> = {};
  for (const d of videoCurrentDets) {
    videoClassCounts[d.class_name] = (videoClassCounts[d.class_name] ?? 0) + 1;
  }
  const videoTracks = new Set(videoDets.map((d) => d.track_id).filter((t) => t != null));

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
          {savedMission?.aoi_source === "gps-exif" && savedMission.gps_point && (
            <span
              className="flex items-center gap-1 text-xs text-blue-400 font-mono"
              title="GPS coordinates extracted from image EXIF metadata"
            >
              <MapPin size={12} />
              {savedMission.gps_point[0].toFixed(4)}, {savedMission.gps_point[1].toFixed(4)}
            </span>
          )}
          {savedMission?.aoi_source === "default" && (
            <span
              className="flex items-center gap-1 text-xs text-muted font-mono"
              title="No GPS in image — using default AOI (Bangalore)"
            >
              <MapPin size={12} /> default AOI
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
          <button
            onClick={() => setStreamDialogOpen(true)}
            className="flex items-center gap-2 bg-panel2 border border-border px-4 py-1.5 rounded text-sm hover:bg-panel"
            title="Ingest from RTSP or HTTP video URL"
          >
            <Radio size={14} /> Stream
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
                onClick={fileType === "image" ? onCanvasClick : undefined}
                className={`absolute inset-0 m-auto ${
                  explainUrl ? "pointer-events-none opacity-0"
                  : fileType === "video" ? "pointer-events-none"
                  : "cursor-pointer"
                }`}
                style={{ width: "auto", height: "auto" }}
                title={fileType === "image" ? "Click any detection to see why the model chose it" : undefined}
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
              {result && !explainUrl && !busy && fileType === "image" && (
                <div className="absolute bottom-3 left-3 bg-bg/80 border border-border px-2.5 py-1 rounded text-[11px] text-muted">
                  💡 Click a box to see why the model chose it (Grad-CAM)
                </div>
              )}
              {fileType === "video" && videoDets.length > 0 && !videoPolling && (
                <div className="absolute bottom-3 left-3 bg-bg/80 border border-border px-2.5 py-1 rounded text-[11px] text-muted">
                  ▶ Play — boxes sync to playback, tracks leave movement trails
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

          {!result && !busy && fileUrl && fileType === "image" && (
            <div className="text-xs text-muted">Running first inference...</div>
          )}

          {/* Video-mode panel */}
          {fileType === "video" && (
            <>
              {videoPolling && (
                <div className="flex items-center gap-2 bg-panel2 border border-border rounded px-3 py-2 text-xs">
                  <Loader2 size={12} className="animate-spin text-accent" />
                  <span>Processing video through pipeline...</span>
                </div>
              )}
              {videoDets.length > 0 && (
                <>
                  <div className="grid grid-cols-3 gap-2">
                    <div className="bg-panel2 rounded px-2 py-2">
                      <div className="text-muted text-[10px] uppercase">Frames</div>
                      <div className="text-lg font-mono">{new Set(videoDets.map(d => d.frame_index)).size}</div>
                    </div>
                    <div className="bg-panel2 rounded px-2 py-2">
                      <div className="text-muted text-[10px] uppercase">Tracks</div>
                      <div className="text-lg font-mono">{videoTracks.size}</div>
                    </div>
                    <div className="bg-panel2 rounded px-2 py-2">
                      <div className="text-muted text-[10px] uppercase">Total dets</div>
                      <div className="text-lg font-mono">{videoDets.length}</div>
                    </div>
                  </div>

                  <div>
                    <div className="text-xs text-muted uppercase tracking-wider mb-2">
                      At current frame ({videoCurrentTime.toFixed(1)}s)
                    </div>
                    {videoCurrentDets.length === 0 ? (
                      <div className="text-xs text-muted">No detections in this frame.</div>
                    ) : (
                      <div className="space-y-1">
                        {Object.entries(videoClassCounts)
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
                    )}
                  </div>

                  {/* MAR20 cascade — show specific airframes ID'd in current frame */}
                  {(() => {
                    const ided = videoCurrentDets.filter((d) => d.extras?.airframe);
                    if (ided.length === 0) return null;
                    return (
                      <div className="border-t border-border pt-2">
                        <div className="text-xs text-muted uppercase tracking-wider mb-2">
                          Airframes ID'd <span className="text-accent">·</span>
                          <span className="text-[10px] normal-case ml-1">MAR20 cascade</span>
                        </div>
                        <div className="space-y-1 font-mono text-xs">
                          {ided.map((d) => (
                            <div key={d.id} className="flex items-center justify-between">
                              <span className="text-blue-300">{d.extras!.airframe}</span>
                              <span className="text-muted">
                                {((d.extras!.airframe_confidence ?? 0) * 100).toFixed(0)}%
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    );
                  })()}

                  <div className="text-[11px] text-muted leading-snug pt-2 border-t border-border">
                    ⟶ Play the video — boxes move in sync with detections, tracks leave fading trails showing movement paths.
                  </div>
                </>
              )}
              {!videoPolling && videoDets.length === 0 && fileUrl && (
                <div className="text-xs text-muted">
                  No detections yet. Toggle "Save to DB" if not already on, or click "Analyze frame" for a one-shot preview.
                </div>
              )}
            </>
          )}
        </aside>
      </div>

      {/* Stream URL dialog */}
      {streamDialogOpen && (
        <div
          className="fixed inset-0 bg-bg/70 backdrop-blur-sm z-50 flex items-center justify-center"
          onClick={() => !streamBusy && setStreamDialogOpen(false)}
        >
          <div
            className="bg-panel border border-border rounded-lg p-6 w-[520px] max-w-full mx-4 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-2 mb-4">
              <Radio size={18} className="text-accent" />
              <h2 className="text-lg font-semibold">Live Stream Ingest</h2>
            </div>
            <p className="text-xs text-muted mb-3 leading-relaxed">
              Enter an <code className="text-accent">rtsp://</code>, <code className="text-accent">http://</code>, or <code className="text-accent">https://</code> URL.
              ASTRA will capture ~30 frames over 5 seconds, run detection, and populate Map + Alerts
              just like a file upload.
            </p>
            <input
              type="text"
              placeholder="rtsp://192.168.1.10:554/drone-feed  or  https://example.com/clip.mp4"
              value={streamUrl}
              onChange={(e) => setStreamUrl(e.target.value)}
              disabled={streamBusy}
              className="w-full bg-bg border border-border rounded px-3 py-2 text-sm font-mono disabled:opacity-50"
              autoFocus
            />
            <div className="flex items-center justify-between mt-4">
              <div className="text-[11px] text-muted">
                Cap: 30 frames / 5 seconds · timeout 8s
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => !streamBusy && setStreamDialogOpen(false)}
                  disabled={streamBusy}
                  className="px-3 py-1.5 rounded text-sm text-muted hover:text-text disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  onClick={submitStreamUrl}
                  disabled={streamBusy || !streamUrl.trim()}
                  className="flex items-center gap-2 bg-accent text-bg px-4 py-1.5 rounded text-sm font-medium hover:brightness-110 disabled:opacity-50"
                >
                  {streamBusy ? <Loader2 size={14} className="animate-spin" /> : <Radio size={14} />}
                  {streamBusy ? "Capturing…" : "Capture + detect"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
