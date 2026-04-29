import { useEffect, useMemo, useRef, useState } from "react";
import { Upload, Play, Loader2, Zap, X, Eye, Radio, MapPin, Target, Cpu, Gauge, Layers, RotateCcw } from "lucide-react";
import { DEFAULT_AOI, api, detectionLabel, type Detection as DbDetection, type Mission as DbMission } from "../lib/api";
import { PageHeader } from "../components/PageHeader";
import { HeroStat } from "../components/HeroStat";
import { EmptyState } from "../components/EmptyState";
import { StatusPill } from "../components/StatusPill";
import { toast } from "../components/Toast";
import { Bezel } from "../components/Bezel";
import { HudCornerStat, HudRecBadge, HudCrosshair, HudThreatBar } from "../components/HudOverlay";
import { ReplayScrubber } from "../components/ReplayScrubber";
import { AuditDrawer } from "../components/AuditDrawer";
import { CritCornerFlash } from "../components/CritCascade";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

// D4.1 helpers — format the scrubber label for video (relative HH:MM:SS)
// vs image (wall-clock IST).
function formatVideoClock(elapsedMs: number, totalMs: number): string {
  const fmt = (ms: number) => {
    const s = Math.max(0, Math.floor(ms / 1000));
    const hh = Math.floor(s / 3600);
    const mm = Math.floor((s % 3600) / 60);
    const ss = s % 60;
    const pad = (n: number) => n.toString().padStart(2, "0");
    return hh > 0 ? `${pad(hh)}:${pad(mm)}:${pad(ss)}` : `${pad(mm)}:${pad(ss)}`;
  };
  return `${fmt(elapsedMs)} / ${fmt(totalMs)}`;
}

function replayCounts(
  mode: "video" | "image",
  scrubMs: number,
  videoDets: import("../lib/api").Detection[],
  imageDbDets: import("../lib/api").Detection[],
): string {
  const GHOST_MS = 10_000;
  if (mode === "video") {
    const visible = videoDets.filter((d) => Math.abs(d.frame_timestamp_ms - scrubMs) <= 250).length;
    const ghost = videoDets.filter((d) => {
      const dt = scrubMs - d.frame_timestamp_ms;
      return dt > 250 && dt <= GHOST_MS;
    }).length;
    return `${visible} visible · ${ghost} ghost`;
  }
  const visible = imageDbDets.filter((d) => Date.parse(d.created_at) <= scrubMs).length;
  const ghost = imageDbDets.filter((d) => {
    const t = Date.parse(d.created_at);
    return t > scrubMs - GHOST_MS && t <= scrubMs - 250;
  }).length;
  return `${visible} visible · ${ghost} ghost`;
}

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

// Module-scope cache so the loaded image, detections, and heatmap survive
// sidebar navigation. Cleared explicitly via the "New Mission" button.
type MissionCache = {
  fileUrl: string | null;
  fileType: "image" | "video" | null;
  currentFile: File | null;
  result: PredictResponse | null;
  savedMissionId: number | null;
  savedMission: DbMission | null;
  explainUrl: string | null;
  explainedClass: string | null;
  videoDets: DbDetection[];
  imageDbDets: DbDetection[];
  missionName: string;
};
const _cache: MissionCache = {
  fileUrl: null, fileType: null, currentFile: null, result: null,
  savedMissionId: null, savedMission: null,
  explainUrl: null, explainedClass: null,
  videoDets: [], imageDbDets: [], missionName: "",
};

export default function Mission() {
  const fileRef = useRef<HTMLInputElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const [missionName, setMissionName] = useState(_cache.missionName || `MISSION-${new Date().toISOString().slice(0,16).replace(/[-T:]/g,"")}`);
  const [fileUrl, setFileUrl] = useState<string | null>(_cache.fileUrl);
  const [fileType, setFileType] = useState<"image" | "video" | null>(_cache.fileType);
  const [currentFile, setCurrentFile] = useState<File | null>(_cache.currentFile);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PredictResponse | null>(_cache.result);
  const [saveToDb, setSaveToDb] = useState(true);
  const [savedMissionId, setSavedMissionId] = useState<number | null>(_cache.savedMissionId);
  const [savedMission, setSavedMission] = useState<DbMission | null>(_cache.savedMission);
  const [explainUrl, setExplainUrl] = useState<string | null>(_cache.explainUrl);
  const [explainLoading, setExplainLoading] = useState(false);
  const [explainedClass, setExplainedClass] = useState<string | null>(_cache.explainedClass);
  const [streamUrl, setStreamUrl] = useState("");
  const [streamDialogOpen, setStreamDialogOpen] = useState(false);
  const [streamBusy, setStreamBusy] = useState(false);
  const [videoDets, setVideoDets] = useState<DbDetection[]>(_cache.videoDets);
  const [videoPolling, setVideoPolling] = useState(false);
  const [videoCurrentTime, setVideoCurrentTime] = useState(0);

  // D4.1 — Mission Replay Scrubber. scrubMs is the canonical "where am I"
  // pointer for replay; when null, replay is inactive and the existing
  // live-rendering logic plays. Bounds are derived below.
  const [scrubMs, setScrubMs] = useState<number | null>(null);
  const [replayPlaying, setReplayPlaying] = useState(false);

  // Image-mode cascade results (MAR20 airframe IDs). The /predict response
  // is stage-1 only; the cascade runs in the ingest pipeline and lands in
  // extras_json of persisted detections. We poll listDetections for the
  // saved mission so airframe IDs surface in the side panel + canvas.
  const [imageDbDets, setImageDbDets] = useState<DbDetection[]>(_cache.imageDbDets);
  const [imageDbPolling, setImageDbPolling] = useState(false);

  // Mirror state to module cache so re-mount restores it.
  useEffect(() => {
    _cache.fileUrl = fileUrl;
    _cache.fileType = fileType;
    _cache.currentFile = currentFile;
    _cache.result = result;
    _cache.savedMissionId = savedMissionId;
    _cache.savedMission = savedMission;
    _cache.explainUrl = explainUrl;
    _cache.explainedClass = explainedClass;
    _cache.videoDets = videoDets;
    _cache.imageDbDets = imageDbDets;
    _cache.missionName = missionName;
  });

  const onPick = () => fileRef.current?.click();

  function newMission() {
    if (explainUrl) URL.revokeObjectURL(explainUrl);
    if (fileUrl) URL.revokeObjectURL(fileUrl);
    setFileUrl(null);
    setFileType(null);
    setCurrentFile(null);
    setResult(null);
    setSavedMissionId(null);
    setSavedMission(null);
    setExplainUrl(null);
    setExplainedClass(null);
    setVideoDets([]);
    setVideoCurrentTime(0);
    setImageDbDets([]);
    setError(null);
    setMissionName(`MISSION-${new Date().toISOString().slice(0,16).replace(/[-T:]/g,"")}`);
    fileRef.current?.click();
  }

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
    setImageDbDets([]);
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
      const aoiLabel = m.aoi_source === "gps-exif" ? "GPS-anchored" : m.aoi_source === "explicit" ? "AOI-anchored" : "default AOI";
      toast.success(`Mission #${m.id} ingested`, `${m.name} · ${aoiLabel}`);
    } catch (e) {
      console.warn("ingest failed:", e);
      toast.crit("Ingest failed", (e as Error).message);
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

  // Auto-predict when an image loads. Skipped if state was restored from
  // the module cache (image already analyzed + ingested in prior mount).
  useEffect(() => {
    if (!fileUrl || !currentFile) return;
    const alreadyAnalyzed = fileType === "image" ? result != null : videoDets.length > 0;
    const alreadyIngested = savedMissionId != null;
    if (fileType === "image") {
      if (!alreadyAnalyzed) {
        fetch(fileUrl).then(r => r.blob()).then(b => runPredict(b, "upload.jpg"));
      }
      if (saveToDb && !alreadyIngested) saveMission(currentFile);
    } else if (fileType === "video" && saveToDb && !alreadyIngested) {
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

  // Image-mode: poll listDetections for the saved mission so the MAR20
  // cascade airframe IDs (computed server-side after ingest) surface in
  // the side panel + canvas labels. Same pattern as video polling.
  useEffect(() => {
    if (fileType !== "image" || savedMissionId == null) return;
    let cancelled = false;
    let attempts = 0;
    const MAX_ATTEMPTS = 10;  // ~20 seconds — image cascade is fast
    setImageDbPolling(true);

    const poll = async () => {
      attempts++;
      try {
        const dets = await api.listDetections({ mission_id: savedMissionId, limit: 200 });
        if (cancelled) return false;
        if (dets.length > 0) {
          setImageDbDets(dets);
          setImageDbPolling(false);
          return true;
        }
      } catch {}
      return false;
    };

    const interval = window.setInterval(async () => {
      const done = await poll();
      if (done || attempts >= MAX_ATTEMPTS || cancelled) {
        window.clearInterval(interval);
        if (!cancelled) setImageDbPolling(false);
      }
    }, 1500);
    poll().then((done) => { if (done) window.clearInterval(interval); });

    return () => {
      cancelled = true;
      window.clearInterval(interval);
      setImageDbPolling(false);
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

  // D4.1 — replay bounds. Returns null when there's not enough temporal
  // spread to scrub (single-frame image, no detections, etc).
  //   • video → 0..duration (or det timestamp range if duration unknown)
  //   • image → spread of created_at across imageDbDets (must be ≥ 1s
  //              and ≥ 2 distinct timestamps to be useful)
  const replayBounds = useMemo<{ min: number; max: number; mode: "video" | "image" } | null>(() => {
    if (fileType === "video") {
      // Prefer the video element's own duration when available; falls back
      // to detection timestamps (frame_timestamp_ms) for the rare case where
      // duration is NaN (some MP4 muxers).
      const v = videoRef.current;
      if (v && Number.isFinite(v.duration) && v.duration > 0) {
        return { min: 0, max: v.duration * 1000, mode: "video" };
      }
      if (videoDets.length >= 2) {
        const ts = videoDets.map((d) => d.frame_timestamp_ms);
        const min = Math.min(...ts);
        const max = Math.max(...ts);
        if (max - min >= 500) return { min, max, mode: "video" };
      }
      return null;
    }
    if (fileType === "image" && imageDbDets.length >= 2) {
      const ts = imageDbDets
        .map((d) => Date.parse(d.created_at))
        .filter((t) => Number.isFinite(t));
      if (ts.length < 2) return null;
      const min = Math.min(...ts);
      const max = Math.max(...ts);
      if (max - min < 1000) return null; // need ≥ 1s spread to be useful
      return { min, max, mode: "image" };
    }
    return null;
  }, [fileType, videoDets, imageDbDets, fileUrl, videoCurrentTime]);

  // Init scrubMs to the end of the timeline when bounds first appear; clear
  // when bounds disappear (e.g. New Mission button).
  useEffect(() => {
    if (replayBounds && scrubMs == null) {
      setScrubMs(replayBounds.max);
    } else if (!replayBounds && scrubMs != null) {
      setScrubMs(null);
      setReplayPlaying(false);
    }
  }, [replayBounds, scrubMs]);

  // VIDEO: when scrubMs changes, seek the video. Tolerance avoids fighting
  // with normal play (which itself drives videoCurrentTime → not scrubMs).
  useEffect(() => {
    if (replayBounds?.mode !== "video") return;
    if (scrubMs == null) return;
    const v = videoRef.current;
    if (!v) return;
    const targetSec = scrubMs / 1000;
    if (Math.abs(v.currentTime - targetSec) > 0.08) {
      try { v.currentTime = targetSec; } catch { /* seek before metadata loaded */ }
    }
  }, [scrubMs, replayBounds?.mode]);

  // D5.1 — replay thumbnails. Sample N frames from the video at evenly-
  // spaced timestamps once the video metadata is loaded. We use a hidden
  // <video> element + a temp canvas because seeking the *visible* video
  // would interfere with the operator's playback. Only re-runs when the
  // file URL or the (computed) duration changes.
  const [thumbs, setThumbs] = useState<{ url: string; at: number }[]>([]);
  useEffect(() => {
    setThumbs([]);
    if (fileType !== "video" || !fileUrl || !replayBounds || replayBounds.mode !== "video") return;
    const N = 8;
    const totalMs = replayBounds.max - replayBounds.min;
    if (totalMs < 2000) return;
    let cancelled = false;
    const created: string[] = [];
    const out: { url: string; at: number }[] = [];
    const hidden = document.createElement("video");
    hidden.src = fileUrl;
    hidden.crossOrigin = "anonymous";
    hidden.preload = "auto";
    hidden.muted = true;
    hidden.playsInline = true;

    const seekTo = (sec: number) =>
      new Promise<void>((resolve) => {
        const onSeeked = () => { hidden.removeEventListener("seeked", onSeeked); resolve(); };
        hidden.addEventListener("seeked", onSeeked);
        hidden.currentTime = sec;
      });

    const grab = (): string => {
      const c = document.createElement("canvas");
      c.width = 112;
      c.height = 72;
      const ctx = c.getContext("2d")!;
      // Letterbox into 112×72 preserving aspect.
      const vw = hidden.videoWidth || 16;
      const vh = hidden.videoHeight || 9;
      const ratio = Math.min(c.width / vw, c.height / vh);
      const dw = vw * ratio;
      const dh = vh * ratio;
      const dx = (c.width - dw) / 2;
      const dy = (c.height - dh) / 2;
      ctx.fillStyle = "#0a0f14";
      ctx.fillRect(0, 0, c.width, c.height);
      ctx.drawImage(hidden, dx, dy, dw, dh);
      return c.toDataURL("image/jpeg", 0.7);
    };

    const run = async () => {
      try {
        await new Promise<void>((res, rej) => {
          if (hidden.readyState >= 1) return res();
          hidden.addEventListener("loadedmetadata", () => res(), { once: true });
          hidden.addEventListener("error", () => rej(new Error("video load failed")), { once: true });
        });
        for (let i = 0; i < N; i++) {
          if (cancelled) return;
          const t = replayBounds.min + (totalMs * (i + 0.5)) / N; // mid-bucket
          await seekTo(t / 1000);
          if (cancelled) return;
          const url = grab();
          created.push(url);
          out.push({ url, at: t });
        }
        if (!cancelled) setThumbs(out);
      } catch { /* ignore — no thumbs is graceful */ }
    };
    run();
    return () => {
      cancelled = true;
      // Data URLs don't need revokeObjectURL; the hidden element is GC'd.
      hidden.src = "";
    };
  }, [fileUrl, fileType, replayBounds?.min, replayBounds?.max, replayBounds?.mode]);

  // D5.1 — live-tail. When scrubber is parked at the current max AND new
  // detections arrive (videoDets / imageDbDets grow with later timestamps),
  // advance scrubMs to the new max so the operator stays on "live".
  useEffect(() => {
    if (!replayBounds || scrubMs == null) return;
    // Only auto-track if the scrubber is at-or-past the previous tip.
    // We treat "within 250ms of the old max" as "at tip".
    if (scrubMs < replayBounds.max - 250) return;
    if (Math.abs(scrubMs - replayBounds.max) < 1) return; // already tip
    setScrubMs(replayBounds.max);
  }, [replayBounds?.max, replayBounds, scrubMs]);

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

      // D4.1 — image-mode replay. When scrubMs is set, gate every box on
      // the matching DbDetection's created_at:
      //   visible: created_at <= scrubMs            → full opacity, colour border
      //   ghost:   in [scrubMs - 10s, scrubMs]      → 20% opacity, grey, no label
      //   hidden:  created_at  >  scrubMs           → skip
      // When scrubMs is null (no replay), the legacy all-at-once logic plays.
      const replayActive = replayBounds?.mode === "image" && scrubMs != null;
      const GHOST_WINDOW_MS = 10_000;

      // Match each /predict result box to a saved DbDetection by IoU so
      // we can swap the generic label for the MAR20 cascade airframe ID
      // (e.g. "F-22 0.91" instead of "aircraft-fixed-wing 0.78").
      const iou = (a: { x1:number;y1:number;x2:number;y2:number }, b: { x1:number;y1:number;x2:number;y2:number }) => {
        const ix1 = Math.max(a.x1, b.x1), iy1 = Math.max(a.y1, b.y1);
        const ix2 = Math.min(a.x2, b.x2), iy2 = Math.min(a.y2, b.y2);
        if (ix2 <= ix1 || iy2 <= iy1) return 0;
        const inter = (ix2 - ix1) * (iy2 - iy1);
        const ua = (a.x2 - a.x1) * (a.y2 - a.y1) + (b.x2 - b.x1) * (b.y2 - b.y1) - inter;
        return ua > 0 ? inter / ua : 0;
      };
      const dbAircraft = imageDbDets.filter((d) => d.extras?.airframe);

      for (const d of result.detections) {
        // Match to any DbDetection (not just airframe) so we have a created_at
        // for replay gating. Then narrow to the airframe match for labelling.
        let bestAny: DbDetection | null = null;
        let bestAnyIou = 0.4;
        for (const dbd of imageDbDets) {
          const j = iou(d, dbd);
          if (j > bestAnyIou) { bestAnyIou = j; bestAny = dbd; }
        }

        // Replay gating — applies only when the image timeline is engaged.
        let mode: "visible" | "ghost" | "hidden" = "visible";
        if (replayActive && scrubMs != null) {
          const ts = bestAny ? Date.parse(bestAny.created_at) : NaN;
          if (Number.isFinite(ts)) {
            if (ts > scrubMs) mode = "hidden";
            else if (ts < scrubMs - GHOST_WINDOW_MS) mode = "visible";
            else if (ts <= scrubMs - 250) mode = "ghost";
            else mode = "visible";
          }
        }
        if (mode === "hidden") continue;

        const color = CLASS_COLORS[d.class_name] ?? "#ff7a1a";
        const x = d.x1 * scaleX;
        const y = d.y1 * scaleY;
        const w = (d.x2 - d.x1) * scaleX;
        const h = (d.y2 - d.y1) * scaleY;

        if (mode === "ghost") {
          ctx.save();
          ctx.globalAlpha = 0.2;
          ctx.strokeStyle = "#888";
          ctx.strokeRect(x, y, w, h);
          ctx.restore();
          continue;
        }

        ctx.strokeStyle = color;
        ctx.strokeRect(x, y, w, h);

        // If we have a cascade match, prefer the airframe name + cascade conf.
        const best = bestAny && bestAny.extras?.airframe ? bestAny : null;
        const label = best && best.extras?.airframe
          ? `${best.extras.airframe} ${(best.extras.airframe_confidence ?? 0).toFixed(2)}`
          : `${d.class_name} ${d.confidence.toFixed(2)}`;
        const textW = ctx.measureText(label).width + 8;
        ctx.fillStyle = color;
        ctx.fillRect(x, y - 16, textW, 16);
        ctx.fillStyle = "#0a0f14";
        ctx.fillText(label, x + 4, y - 4);
      }
      // Suppress the dbAircraft-only loop now that we already used imageDbDets.
      void dbAircraft;
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

      // D4.1 — ghost-trail boxes: detections that were live in the last
      // 10 seconds before "now" but aren't current. Renders a faded box
      // for each (independent of the per-track polyline trail below) so
      // operators can see exactly *where* something was, not just *that*
      // it moved. The polyline trails still draw.
      const GHOST_WINDOW_MS_VID = 10_000;
      const ghostDets = videoDets.filter((d) => {
        const dt = currentMs - d.frame_timestamp_ms;
        return dt > WINDOW_MS && dt <= GHOST_WINDOW_MS_VID;
      });

      // Ghost boxes — faded, grey-bordered rectangles for last-10s dets.
      ctx.save();
      ctx.globalAlpha = 0.2;
      ctx.strokeStyle = "#888";
      ctx.lineWidth = 1.5;
      for (const d of ghostDets) {
        const gx = d.x1 * scaleX;
        const gy = d.y1 * scaleY;
        const gw = (d.x2 - d.x1) * scaleX;
        const gh = (d.y2 - d.y1) * scaleY;
        ctx.strokeRect(gx, gy, gw, gh);
      }
      ctx.restore();

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
        // OOD-flagged detections render as dashed grey with "?" — the
        // system showing it knew it didn't know.
        const isOod = !!d.extras?.ood_flag;
        const color = isOod ? "#94a3b8" : (CLASS_COLORS[d.class_name] ?? "#ff7a1a");
        const x = d.x1 * scaleX;
        const y = d.y1 * scaleY;
        const w = (d.x2 - d.x1) * scaleX;
        const h = (d.y2 - d.y1) * scaleY;
        ctx.strokeStyle = color;
        if (isOod) {
          ctx.setLineDash([4, 3]);
        }
        ctx.strokeRect(x, y, w, h);
        if (isOod) ctx.setLineDash([]);

        // Prefer the MAR20 cascade airframe ID when available
        const lbl = detectionLabel(d);
        const showSub = d.extras?.airframe != null;
        const conf = showSub && d.extras?.airframe_confidence != null
          ? d.extras.airframe_confidence
          : d.confidence;
        const baseLabel = d.track_id != null
          ? `#${d.track_id} · ${lbl} ${conf.toFixed(2)}`
          : `${lbl} ${conf.toFixed(2)}`;
        const label = isOod ? `? ${baseLabel}` : baseLabel;
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
  }, [result, fileUrl, fileType, videoDets, videoCurrentTime, imageDbDets, scrubMs, replayBounds]);

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

  // Hero stats: 4 KPIs that update live with the current scene.
  const heroDetections = useMemo(() => {
    if (fileType === "video") return videoDets.length;
    return result?.detections.length ?? 0;
  }, [fileType, videoDets.length, result]);
  const heroLatency = result?.latency_ms ?? null;
  const heroTracks = videoTracks.size;
  const heroAirframes = useMemo(() => {
    const src = fileType === "video" ? videoDets : (fileType === "image" ? imageDbDets : []);
    return src.filter((d) => d.extras?.airframe).length;
  }, [fileType, videoDets, imageDbDets]);

  // Image-mode airframe summary — counts per type, plus the top-3
  // alternates from the most-confident detection of each type. Top-3
  // surfaces model uncertainty: when the cascade is 91% sure it's an
  // F-22, what were its 2nd and 3rd guesses?
  const imageAirframeCounts = useMemo(() => {
    const c: Record<string, {
      n: number;
      conf: number[];
      bestConf: number;
      top3: { name: string; conf: number }[];
    }> = {};
    for (const d of imageDbDets) {
      const name = d.extras?.airframe;
      if (!name) continue;
      const conf = d.extras?.airframe_confidence ?? 0;
      const slot = (c[name] ??= { n: 0, conf: [], bestConf: -1, top3: [] });
      slot.n += 1;
      slot.conf.push(conf);
      if (conf > slot.bestConf) {
        slot.bestConf = conf;
        slot.top3 = (d.extras?.airframe_top3 ?? []).slice(0, 3);
      }
    }
    return c;
  }, [imageDbDets]);

  return (
    <div className="h-full flex flex-col">
      <PageHeader
        icon={Target}
        title="Live Mission Feed"
        subtitle={
          <>
            Upload a drone image or clip — detections run on real yolo11n model
            {savedMissionId != null && (
              <>
                {" · "}<span className="text-threat-low">Mission #{savedMissionId}</span>
              </>
            )}
          </>
        }
        badge={savedMissionId != null ? <StatusPill variant="ok" size="sm">saved</StatusPill> : null}
        actions={
          <>
            <label className="flex items-center gap-2 text-xs text-muted cursor-pointer select-none">
              <input
                type="checkbox"
                checked={saveToDb}
                onChange={(e) => setSaveToDb(e.target.checked)}
                className="accent-accent"
              />
              Save to DB
            </label>
            {savedMission?.aoi_source === "gps-exif" && savedMission.gps_point && (
              <StatusPill variant="info" size="sm" title="GPS coordinates extracted from image EXIF metadata">
                <MapPin size={10} className="mr-1" />
                {savedMission.gps_point[0].toFixed(3)}, {savedMission.gps_point[1].toFixed(3)}
              </StatusPill>
            )}
            {savedMission?.aoi_source === "default" && (
              <StatusPill variant="neutral" size="sm" title="No GPS in image — using default AOI (Bangalore)">
                <MapPin size={10} className="mr-1" /> default AOI
              </StatusPill>
            )}
            <input
              className="bg-panel border border-border rounded px-3 py-1.5 text-sm w-44 font-mono"
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
              className="flex items-center gap-2 bg-accent text-bg px-4 py-1.5 rounded text-sm font-medium hover:brightness-110 transition-fast shadow-glow-accent"
            >
              <Upload size={14} /> Ingest
            </button>
            {fileUrl && (
              <button
                onClick={newMission}
                className="flex items-center gap-2 glass border border-border px-4 py-1.5 rounded text-sm hover:bg-panel2 transition-fast"
                title="Discard current mission and pick a new file (current image stays loaded across tab switches until you click this)"
              >
                <RotateCcw size={14} /> Next Mission
              </button>
            )}
            <button
              onClick={() => setStreamDialogOpen(true)}
              className="flex items-center gap-2 glass border border-border px-4 py-1.5 rounded text-sm hover:bg-panel2 transition-fast"
              title="Ingest from RTSP or HTTP video URL"
            >
              <Radio size={14} /> Stream
            </button>
            {fileType === "video" && (
              <button
                onClick={analyzeVideoFrame}
                disabled={busy}
                className="flex items-center gap-2 glass border border-border px-4 py-1.5 rounded text-sm hover:bg-panel2 disabled:opacity-50 transition-fast"
              >
                {busy ? <Loader2 size={14} className="animate-spin" /> : <Zap size={14} />}
                Analyze frame
              </button>
            )}
          </>
        }
      />

      {/* Hero KPI strip */}
      <div className="px-6 pt-4 grid grid-cols-4 gap-3">
        <HeroStat
          label="detections"
          value={heroDetections}
          icon={Target}
          tone={heroDetections > 0 ? "cyan" : "neutral"}
          sub={fileType === "video" ? `${heroTracks} unique tracks` : "single frame"}
        />
        <HeroStat
          label="airframes ID'd"
          value={heroAirframes}
          icon={Layers}
          tone={heroAirframes > 0 ? "low" : "neutral"}
          sub="MAR20 cascade"
        />
        <HeroStat
          label="latency"
          value={heroLatency ?? 0}
          unit="ms"
          decimals={1}
          icon={Gauge}
          tone={heroLatency && heroLatency > 50 ? "high" : "low"}
          sub="last inference"
          ticker={heroLatency != null}
        />
        <HeroStat
          label="model"
          value={"v1·yolo11n"}
          icon={Cpu}
          tone="neutral"
          sub="640² · cuda:0"
          ticker={false}
        />
      </div>

      <div className="flex-1 p-6 pt-4 grid grid-cols-[1fr_320px] gap-6 overflow-hidden">
        <div className="flex flex-col gap-3 min-h-0 overflow-hidden">
        <Bezel
          className="relative flex-1 min-h-0"
          topBar={
            <>
              <span className="text-accent">ASTRA·1</span>
              <span className="text-muted2">{fileType === "video" ? "VIDEO" : fileType === "image" ? "IMAGE" : "STDBY"}</span>
              <span className="text-muted2">FRAME</span>
              <span className="tabular-nums text-text">
                {fileType === "video" && videoDets.length > 0 ? new Set(videoDets.map(d=>d.frame_index)).size : "—"}
              </span>
              <span className="text-muted2">DET</span>
              <span className="tabular-nums text-text">{heroDetections}</span>
              {savedMissionId != null && (
                <>
                  <span className="text-muted2">MSN</span>
                  <span className="tabular-nums text-text">#{savedMissionId.toString().padStart(4, "0")}</span>
                </>
              )}
              <span className="ml-auto text-muted2 tabular-nums">{new Date().toLocaleTimeString("en-IN", { hour12: false })}</span>
            </>
          }
          bottomBar={
            <>
              <span className="text-muted2">MODEL</span>
              <span className="text-text">v1·yolo11n·640²</span>
              <span className="text-muted2">DEV</span>
              <span className="text-text">cuda:0</span>
              {result && (
                <>
                  <span className="text-muted2">LAT</span>
                  <span className="tabular-nums text-text">{result.latency_ms.toFixed(1)}ms</span>
                </>
              )}
              {fileType === "video" && videoDets.length > 0 && (
                <span className="ml-auto"><HudThreatBar value={Math.min(1, heroDetections / 50)} label="LOAD" /></span>
              )}
            </>
          }
        ><div className="relative w-full h-full flex items-center justify-center">
          <CritCornerFlash missionId={savedMissionId} />
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
                  controls={!replayBounds}
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
            <EmptyState
              icon={Play}
              title="No feed loaded"
              body="Drag in a drone image or video, or click Ingest to choose a file. Supports PNG/JPG and MP4/MOV. EXIF-GPS images auto-anchor on the Map page."
              cta={{ label: "Ingest a file", onClick: onPick }}
            />
          )}

          {/* HUD overlays — only when content is loaded */}
          {fileUrl && !explainUrl && (
            <>
              <HudRecBadge label={fileType === "video" ? "REC · LIVE" : "ANALYZE"} />
              {savedMission?.aoi_source === "gps-exif" && savedMission.gps_point && (
                <HudCornerStat
                  pos="tr"
                  label="GPS"
                  tone="ok"
                  value={`${savedMission.gps_point[0].toFixed(3)},${savedMission.gps_point[1].toFixed(3)}`}
                />
              )}
              {fileType === "video" && videoDets.length > 0 && (
                <HudCornerStat pos="bl" label="TRK" tone="neutral" value={videoTracks.size} />
              )}
              {heroAirframes > 0 && (
                <HudCornerStat pos="br" label="ID" tone="ok" value={`${heroAirframes} airframes`} />
              )}
              {!result && fileType === "image" && busy && <HudCrosshair size={120} />}
            </>
          )}
        </div></Bezel>

        {replayBounds && scrubMs != null && (
          <>
            <ReplayScrubber
              min={replayBounds.min}
              max={replayBounds.max}
              value={scrubMs}
              onChange={setScrubMs}
              playing={replayPlaying}
              onPlayingChange={setReplayPlaying}
              formatLabel={(v) =>
                replayBounds.mode === "video"
                  ? formatVideoClock(v - replayBounds.min, replayBounds.max - replayBounds.min)
                  : new Date(v).toLocaleTimeString("en-IN", { hour12: false, timeZone: "Asia/Kolkata" }) + " IST"
              }
              subLabel={replayCounts(replayBounds.mode, scrubMs, videoDets, imageDbDets)}
              thumbnails={replayBounds.mode === "video" ? thumbs : undefined}
            />
            {savedMissionId != null && (
              <AuditDrawer
                missionId={savedMissionId}
                scrubMs={
                  // Video bounds are 0..duration (relative); map to wall-clock by
                  // anchoring at the mission's created_at. Image bounds are already
                  // wall-clock ms.
                  replayBounds.mode === "video" && savedMission?.created_at
                    ? Date.parse(savedMission.created_at) + (scrubMs - replayBounds.min)
                    : scrubMs
                }
              />
            )}
          </>
        )}

        </div>

        <aside className="glass rounded-lg p-4 space-y-4 overflow-auto shadow-panel">
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

              {/* MAR20 cascade — fine-grained airframe IDs (image mode).
                  Surfaces server-side cascade results once the ingest
                  pipeline finishes (~1–2s after upload). */}
              {fileType === "image" && (
                <div className="border-t border-border pt-3">
                  <div className="flex items-center justify-between mb-2">
                    <div className="text-xs text-muted uppercase tracking-wider">
                      Airframes ID'd <span className="text-accent">·</span>
                      <span className="text-[10px] normal-case ml-1">MAR20 cascade</span>
                    </div>
                    {imageDbPolling && Object.keys(imageAirframeCounts).length === 0 && (
                      <Loader2 size={11} className="animate-spin text-muted" />
                    )}
                  </div>
                  {Object.keys(imageAirframeCounts).length > 0 ? (
                    <div className="space-y-1.5 font-mono text-xs">
                      {Object.entries(imageAirframeCounts)
                        .sort(([, a], [, b]) => b.n - a.n)
                        .map(([name, info]) => {
                          const avg = info.conf.length
                            ? info.conf.reduce((s, x) => s + x, 0) / info.conf.length
                            : 0;
                          const top3 = info.top3.filter((t) => t.name !== name).slice(0, 2);
                          return (
                            <div key={name} className="py-1 border-b border-border last:border-0">
                              <div className="flex items-center justify-between">
                                <span className="text-blue-300">{name}</span>
                                <div className="flex items-center gap-3">
                                  <span className="text-accent">× {info.n}</span>
                                  <span className="text-muted">{(avg * 100).toFixed(0)}%</span>
                                </div>
                              </div>
                              {top3.length > 0 && (
                                <div
                                  className="mt-0.5 flex items-center gap-1 text-[10px] text-muted2"
                                  title="2nd & 3rd guesses from the cascade — surfaces model uncertainty per detection"
                                >
                                  <span className="opacity-60">alt:</span>
                                  {top3.map((t) => (
                                    <span
                                      key={t.name}
                                      className="px-1.5 py-0.5 rounded bg-panel2 border border-border text-muted"
                                    >
                                      {t.name} {(t.conf * 100).toFixed(0)}%
                                    </span>
                                  ))}
                                </div>
                              )}
                            </div>
                          );
                        })}
                    </div>
                  ) : imageDbPolling ? (
                    <div className="text-[11px] text-muted">Running cascade on aircraft detections...</div>
                  ) : savedMissionId == null ? (
                    <div className="text-[11px] text-muted">Toggle "Save to DB" to run the MAR20 cascade.</div>
                  ) : (
                    <div className="text-[11px] text-muted">No aircraft passed the cascade gate (cascade only fires on aircraft-fixed-wing / aircraft-rotor detections with conf ≥ 0.4).</div>
                  )}
                </div>
              )}
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
                        <div className="space-y-1.5 font-mono text-xs">
                          {ided.map((d) => {
                            const top3 = (d.extras?.airframe_top3 ?? [])
                              .filter((t) => t.name !== d.extras!.airframe)
                              .slice(0, 2);
                            return (
                              <div key={d.id} className="py-1 border-b border-border last:border-0">
                                <div className="flex items-center justify-between">
                                  <span className="text-blue-300">{d.extras!.airframe}</span>
                                  <span className="text-muted">
                                    {((d.extras!.airframe_confidence ?? 0) * 100).toFixed(0)}%
                                  </span>
                                </div>
                                {top3.length > 0 && (
                                  <div
                                    className="mt-0.5 flex items-center gap-1 text-[10px] text-muted2"
                                    title="2nd & 3rd guesses from the cascade"
                                  >
                                    <span className="opacity-60">alt:</span>
                                    {top3.map((t) => (
                                      <span
                                        key={t.name}
                                        className="px-1.5 py-0.5 rounded bg-panel2 border border-border text-muted"
                                      >
                                        {t.name} {(t.conf * 100).toFixed(0)}%
                                      </span>
                                    ))}
                                  </div>
                                )}
                              </div>
                            );
                          })}
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
