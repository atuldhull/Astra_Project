import { useEffect, useMemo, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar } from "recharts";
import { Activity, Gauge, Layers, Target, ShieldQuestion } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { HeroStat } from "../components/HeroStat";
import { StatusPill } from "../components/StatusPill";
import { api, type DetectorMetrics, type LatencyMetrics } from "../lib/api";
import { absoluteIst, relativeTime } from "../lib/time";

// R2 hardened-model numbers (kept until T3.1 PGD finetune ships).
const R2_HARDENED_AP: Record<string, number> = {
  "small-vehicle":       0.391,
  "large-vehicle":       0.634,
  "aircraft-fixed-wing": 0.932,
  "aircraft-rotor":      0.201,
  "ship":                0.779,
  "storage-depot":       0.433,
  "harbor":              0.743,
  "bridge":              0.235,
};

const LATENCY_FALLBACK = [
  { target: "RTX 4050 FP32", ms: 22.3 },
  { target: "RTX 4050 p95",  ms: 33.6 },
  { target: "CPU ONNX FP32", ms: 35.7 },
  { target: "CPU ONNX p95",  ms: 37.2 },
];

const CASCADE = [
  { metric: "top-1 accuracy", value: 0.890 },
  { metric: "top-5 accuracy", value: 0.993 },
  { metric: "inference @ 224", value: 0.5 },
  { metric: "model size MB",  value: 3.2 },
];

const SHORT_NAME: Record<string, string> = {
  "aircraft-fixed-wing": "fixed-wing",
  "aircraft-rotor":      "rotor",
};

type OodInfo = {
  backend: string;
  heuristic_threshold: number;
  available: boolean;
  weights_path?: string;
  captured_at?: string;
  classes?: string[];
  n_samples_per_class?: Record<string, number>;
  thresholds?: Record<string, number>;
  hint?: string;
};

export default function Benchmark() {
  const [det, setDet] = useState<DetectorMetrics | null>(null);
  const [lat, setLat] = useState<LatencyMetrics | null>(null);
  const [ood, setOod] = useState<OodInfo | null>(null);

  useEffect(() => {
    api.detectorMetrics().then(setDet).catch(() => setDet({ available: false }));
    api.latencyMetrics().then(setLat).catch(() => setLat({ available: false }));
    api.oodCalibration().then(setOod).catch(() => setOod(null));
  }, []);

  // Per-class data: real v1 AP from API, R2 hardened constants (until T3.1).
  const perClass = useMemo(() => {
    const rows = (det?.per_class ?? []).map((r) => ({
      cls: SHORT_NAME[r.class_name] ?? r.class_name,
      v1: r.ap_50_95,
      hardened: R2_HARDENED_AP[r.class_name] ?? 0,
    }));
    return rows;
  }, [det]);

  const meanV1 = perClass.length ? perClass.reduce((s, r) => s + r.v1, 0) / perClass.length : 0;
  const meanHardened = perClass.length ? perClass.reduce((s, r) => s + r.hardened, 0) / perClass.length : 0;

  const heroMap50 = det?.available ? det.map_50! : 0;
  const heroMap5095 = det?.available ? det.map_50_95! : 0;
  const heroLatency = lat?.available ? lat.p50_ms! : 22.3;
  const heroLatencyP99 = lat?.available ? lat.p99_ms! : null;
  const capturedLine = det?.captured_at
    ? `captured ${new Date(det.captured_at).toLocaleString("en-IN", { hour12: false })}`
    : "no capture on disk · run scripts/capture_detector_map.py";

  return (
    <div className="h-full flex flex-col">
      <PageHeader
        icon={Activity}
        title="Benchmark"
        badge={
          det?.available
            ? <StatusPill variant="ok" size="sm">DOTA-v1 · 1561 imgs · 67k inst</StatusPill>
            : <StatusPill variant="neutral" size="sm">no capture</StatusPill>
        }
        subtitle={`yolo11n · 640² · stage-1 detector + stage-2 MAR20 cascade · ${capturedLine}`}
      />

      <div className="px-6 pt-4 grid grid-cols-4 gap-3">
        <HeroStat
          label="mAP@0.5"
          value={heroMap50}
          decimals={3}
          icon={Target}
          tone="cyan"
          sub="DOTA-val · stage-1"
          ticker={det?.available}
        />
        <HeroStat
          label="mAP@0.5:0.95"
          value={heroMap5095}
          decimals={3}
          icon={Target}
          tone="low"
          sub="strict overlap"
        />
        <HeroStat
          label="cascade top-1"
          value={89.03}
          unit="%"
          decimals={2}
          icon={Layers}
          tone="low"
          sub="MAR20 · 20 airframes"
        />
        <HeroStat
          label={heroLatencyP99 != null ? "latency p50 · p99" : "GPU latency"}
          value={heroLatency}
          unit={heroLatencyP99 != null ? `· ${heroLatencyP99}ms` : "ms"}
          decimals={1}
          icon={Gauge}
          tone="low"
          sub={lat?.available ? `n=${lat.n} ingest→alert` : "RTX 4050 · FP32"}
        />
      </div>

      <div className="flex-1 p-6 pt-4 grid grid-cols-2 gap-6 overflow-auto auto-rows-min">
        <div className="glass shadow-panel rounded-lg p-4" title="Average Precision per class on the DOTA-val split. Higher is better. Hardened bars are R2 augmentation-trained (T3.1 PGD-trained replacement pending).">
          <div className="flex items-center justify-between mb-3">
            <div className="text-sm font-semibold">AP@0.5:0.95 per class · v1 vs v1-hardened</div>
            <span className="text-2xs text-muted2 font-mono uppercase-wide tracking-wider">RACE-THE-TARGETS</span>
          </div>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={perClass}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="cls" stroke="var(--muted)" fontSize={10} angle={-20} textAnchor="end" height={60} />
              <YAxis stroke="var(--muted)" fontSize={10} domain={[0, 1]} />
              <Tooltip contentStyle={{ background: "var(--panel)", border: "1px solid var(--border)", fontSize: 11 }} />
              <Bar dataKey="v1" fill="var(--accent)" name="v1 (live)" isAnimationActive animationDuration={1200} />
              <Bar dataKey="hardened" fill="var(--cyan)" name="v1-hardened" isAnimationActive animationDuration={1200} />
            </BarChart>
          </ResponsiveContainer>
          <div className="text-2xs text-muted mt-2 leading-snug">
            v1 mean AP: <span className="text-accent font-mono">{meanV1.toFixed(3)}</span> ·
            hardened mean AP: <span className="text-cyan font-mono">{meanHardened.toFixed(3)}</span>.
            Hardened bars are R2-era; PGD finetune replaces them in T3.1.
          </div>
        </div>

        <div className="glass shadow-panel rounded-lg p-4" title="Polar view of per-class AP. Larger envelope = better all-around model. Lets you spot which classes the hardening regressed on.">
          <div className="flex items-center justify-between mb-3">
            <div className="text-sm font-semibold">Per-class radar · spectrum view</div>
            <span className="text-2xs text-muted2 font-mono uppercase-wide tracking-wider">8-AXIS</span>
          </div>
          <ResponsiveContainer width="100%" height={280}>
            <RadarChart data={perClass}>
              <PolarGrid stroke="var(--border)" />
              <PolarAngleAxis dataKey="cls" stroke="var(--muted)" fontSize={9} />
              <PolarRadiusAxis stroke="var(--border)" angle={30} domain={[0, 1]} />
              <Radar name="v1" dataKey="v1" stroke="var(--accent)" fill="var(--accent)" fillOpacity={0.30} />
              <Radar name="v1-hardened" dataKey="hardened" stroke="var(--cyan)" fill="var(--cyan)" fillOpacity={0.20} />
              <Tooltip contentStyle={{ background: "var(--panel)", border: "1px solid var(--border)", fontSize: 11 }} />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        <div className="glass shadow-panel rounded-lg p-4" title="Inference latency by deployment target. Lower is better. p99 reflects worst-case ingest-to-alert WebSocket round-trip.">
          <div className="flex items-center justify-between mb-3">
            <div className="text-sm font-semibold">Latency by deployment target</div>
            <span className="text-2xs text-muted2 font-mono uppercase-wide tracking-wider">LOWER&nbsp;IS&nbsp;BETTER</span>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={LATENCY_FALLBACK}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="target" stroke="var(--muted)" fontSize={10} angle={-15} textAnchor="end" height={60} />
              <YAxis stroke="var(--muted)" fontSize={10} unit=" ms" />
              <Tooltip contentStyle={{ background: "var(--panel)", border: "1px solid var(--border)", fontSize: 11 }} />
              <Bar dataKey="ms" fill="var(--threat-low)" isAnimationActive animationDuration={1200} />
            </BarChart>
          </ResponsiveContainer>
          {lat?.available && (
            <div className="text-2xs text-muted mt-2 leading-snug">
              End-to-end (ingest → alert via WS) · n={lat.n} · p50 <span className="text-text font-mono">{lat.p50_ms}ms</span> · p95 <span className="text-text font-mono">{lat.p95_ms}ms</span> · p99 <span className="text-text font-mono">{lat.p99_ms}ms</span>
            </div>
          )}
        </div>

        <div className="glass shadow-panel rounded-lg p-4" title="MAR20 cascade — fine-grained airframe identification. Top-1 is exact-match accuracy; top-5 is the truth being in the model's top 5 guesses.">
          <div className="flex items-center justify-between mb-3">
            <div className="text-sm font-semibold">Stage-2 cascade (MAR20)</div>
            <span className="text-2xs text-muted2 font-mono uppercase-wide tracking-wider">20-CLASS · NANO</span>
          </div>
          <div className="space-y-3">
            {CASCADE.map((m) => {
              const norm = m.metric.includes("MB") ? Math.min(1, m.value / 10) : m.metric.includes("@") ? Math.min(1, 1 - m.value / 50) : Math.min(1, m.value);
              return (
                <div key={m.metric}>
                  <div className="flex justify-between text-2xs uppercase-wide font-mono tracking-wider text-muted">
                    <span>{m.metric}</span>
                    <span className="text-text tabular-nums">
                      {m.metric === "model size MB"
                        ? `${m.value.toFixed(1)} MB`
                        : m.metric === "inference @ 224"
                        ? `${m.value.toFixed(1)} ms`
                        : `${(m.value * 100).toFixed(2)}%`}
                    </span>
                  </div>
                  <div className="h-1.5 bg-panel2 rounded-full overflow-hidden mt-1">
                    <div
                      className="h-full bg-cyan transition-all duration-slow ease-out-soft"
                      style={{ width: `${norm * 100}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
          <div className="mt-3 pt-3 border-t border-border text-2xs text-muted leading-snug">
            Trained 57 min on RTX 4050 · 22,341 crops · 50 epochs (early-stop @ 46).
            <span className="block text-cyan font-mono mt-1">Best epoch: 34 · top-1 89.03%</span>
          </div>
        </div>

        {/* OOD calibration card (T1.3 Mahalanobis fit). Surfaced
            here next to mAP + latency because it's the third operational
            gate the operator should see when reading benchmarks. */}
        <div
          className="glass shadow-panel rounded-lg p-4 col-span-2"
          title="Mahalanobis OOD calibration: per-class μ + pooled covariance + 99th-percentile τ. Detections with d² > τ are flagged as out-of-distribution. The system showing it knew it didn't know."
        >
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <ShieldQuestion size={14} className="text-cyan" />
              <div className="text-sm font-semibold">OOD calibration · "the model knows what it doesn't know"</div>
            </div>
            <div className="flex items-center gap-2">
              <StatusPill
                variant={ood?.available ? "ok" : "warn"}
                size="sm"
              >
                {ood?.available ? `backend=${ood.backend ?? "mahalanobis"}` : "uncalibrated"}
              </StatusPill>
              {ood?.captured_at && (
                <span
                  className="text-2xs text-muted2 font-mono"
                  title={absoluteIst(ood.captured_at)}
                >
                  fit {relativeTime(ood.captured_at)}
                </span>
              )}
            </div>
          </div>

          {!ood?.available ? (
            <div className="text-2xs text-muted2 font-mono">
              {ood?.hint ?? "no calibration on disk — run scripts/calibrate_ood.py"}
            </div>
          ) : (
            <>
              <div className="grid grid-cols-3 gap-3 mb-3">
                <div className="bg-panel2 rounded px-3 py-2">
                  <div className="text-2xs text-muted uppercase-wide tracking-wider">classes</div>
                  <div className="text-xl font-mono tabular-nums">
                    {ood.classes?.length ?? 0}
                  </div>
                </div>
                <div className="bg-panel2 rounded px-3 py-2">
                  <div className="text-2xs text-muted uppercase-wide tracking-wider">total samples</div>
                  <div className="text-xl font-mono tabular-nums">
                    {Object.values(ood.n_samples_per_class ?? {}).reduce((s, v) => s + v, 0)}
                  </div>
                </div>
                <div className="bg-panel2 rounded px-3 py-2">
                  <div className="text-2xs text-muted uppercase-wide tracking-wider">heuristic τ (fallback)</div>
                  <div className="text-xl font-mono tabular-nums">
                    {ood.heuristic_threshold.toFixed(2)}
                  </div>
                </div>
              </div>

              <div className="text-2xs uppercase-wide tracking-wider text-muted2 font-mono mb-1.5">
                per-class samples · 99th-percentile τ
              </div>
              <div className="space-y-1">
                {Object.entries(ood.n_samples_per_class ?? {})
                  .sort(([a], [b]) => a.localeCompare(b))
                  .map(([cls, n]) => {
                    const tau = ood.thresholds?.[cls] ?? 0;
                    return (
                      <div key={cls} className="flex items-center gap-3 text-2xs font-mono">
                        <span className="text-text w-44 truncate">{cls}</span>
                        <span className="tabular-nums text-cyan w-12 text-right">n={n}</span>
                        <div className="flex-1 h-1.5 bg-panel rounded overflow-hidden">
                          <div
                            className="h-full bg-cyan/60"
                            style={{
                              width: `${Math.min(100, (n / Math.max(1, Math.max(...Object.values(ood.n_samples_per_class ?? {})))) * 100)}%`,
                            }}
                          />
                        </div>
                        <span className="tabular-nums text-muted w-20 text-right">τ={tau.toFixed(2)}</span>
                      </div>
                    );
                  })}
              </div>

              <div className="mt-3 pt-3 border-t border-border text-2xs text-muted leading-snug">
                Mahalanobis fit replaces the R2 conf+aspect heuristic. Detections whose
                d² distance to class mean exceeds the per-class τ are flagged as OOD on
                Mission/Map (dashed grey box, "?" prefix). The same fingerprint feeds
                /health/dashboard's Calibration Freshness panel.
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
