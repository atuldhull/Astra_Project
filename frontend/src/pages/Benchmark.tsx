import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar } from "recharts";
import { Activity, Cpu, Gauge, Layers, Target, Zap } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { HeroStat } from "../components/HeroStat";
import { StatusPill } from "../components/StatusPill";

// Round-2 numbers from docs/benchmark-report.md.
const PER_CLASS = [
  { cls: "small-vehicle", v1: 0.408, hardened: 0.391 },
  { cls: "large-vehicle", v1: 0.660, hardened: 0.634 },
  { cls: "fixed-wing",    v1: 0.915, hardened: 0.932 },
  { cls: "rotor",         v1: 0.242, hardened: 0.201 },
  { cls: "ship",          v1: 0.770, hardened: 0.779 },
  { cls: "storage-depot", v1: 0.393, hardened: 0.433 },
  { cls: "harbor",        v1: 0.733, hardened: 0.743 },
  { cls: "bridge",        v1: 0.000, hardened: 0.235 },
];

const LATENCY = [
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

export default function Benchmark() {
  const meanV1 = PER_CLASS.reduce((s, r) => s + r.v1, 0) / PER_CLASS.length;
  const meanHardened = PER_CLASS.reduce((s, r) => s + r.hardened, 0) / PER_CLASS.length;

  // Race-the-targets animated bars: animate from 0 -> real value on mount
  const [animValues, setAnimValues] = useState({ v1: 0, hardened: 0, lat: 0 });
  useEffect(() => {
    const t = setTimeout(() => setAnimValues({ v1: meanV1, hardened: meanHardened, lat: 22.3 }), 100);
    return () => clearTimeout(t);
  }, [meanV1, meanHardened]);

  const radarData = PER_CLASS.map((p) => ({ cls: p.cls, v1: p.v1, hardened: p.hardened }));

  return (
    <div className="h-full flex flex-col">
      <PageHeader
        icon={Activity}
        title="Benchmark"
        badge={<StatusPill variant="ok" size="sm">DOTA-v1.5 · 1561 imgs · 67k inst</StatusPill>}
        subtitle="yolo11n · 640² · stage-1 detector + stage-2 MAR20 cascade"
      />

      {/* Hero KPI strip */}
      <div className="px-6 pt-4 grid grid-cols-4 gap-3">
        <HeroStat label="mAP@0.5 stage-1" value={meanV1} decimals={3} icon={Target} tone="cyan" sub="DOTA · 8 classes" />
        <HeroStat label="cascade top-1" value={89.03} unit="%" decimals={2} icon={Layers} tone="low" sub="MAR20 · 20 airframes" />
        <HeroStat label="GPU latency" value={22.3} unit="ms" decimals={1} icon={Gauge} tone="low" sub="RTX 4050 · FP32" />
        <HeroStat label="model size" value={5.5 + 3.2} unit="MB" decimals={1} icon={Cpu} tone="neutral" sub="both stages on disk" />
      </div>

      <div className="flex-1 p-6 pt-4 grid grid-cols-2 gap-6 overflow-auto auto-rows-min">
        {/* Per-class A/B comparison */}
        <div className="glass shadow-panel rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="text-sm font-semibold">mAP@0.5 per class · v1 vs v1-hardened</div>
            <span className="text-2xs text-muted2 font-mono uppercase-wide tracking-wider">RACE-THE-TARGETS</span>
          </div>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={PER_CLASS}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="cls" stroke="var(--muted)" fontSize={10} angle={-20} textAnchor="end" height={60} />
              <YAxis stroke="var(--muted)" fontSize={10} domain={[0, 1]} />
              <Tooltip contentStyle={{ background: "var(--panel)", border: "1px solid var(--border)", fontSize: 11 }} />
              <Bar dataKey="v1" fill="var(--accent)" name="v1" isAnimationActive animationDuration={1200} />
              <Bar dataKey="hardened" fill="var(--cyan)" name="v1-hardened" isAnimationActive animationDuration={1200} />
            </BarChart>
          </ResponsiveContainer>
          <div className="text-2xs text-muted mt-2 leading-snug">
            Heavy augmentation: bridge mAP 0.0 → 0.235 standout. Aircraft and ship slightly improved on hardened.
          </div>
        </div>

        {/* Per-class radar */}
        <div className="glass shadow-panel rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="text-sm font-semibold">Per-class radar · spectrum view</div>
            <span className="text-2xs text-muted2 font-mono uppercase-wide tracking-wider">8-AXIS</span>
          </div>
          <ResponsiveContainer width="100%" height={280}>
            <RadarChart data={radarData}>
              <PolarGrid stroke="var(--border)" />
              <PolarAngleAxis dataKey="cls" stroke="var(--muted)" fontSize={9} />
              <PolarRadiusAxis stroke="var(--border)" angle={30} domain={[0, 1]} />
              <Radar name="v1" dataKey="v1" stroke="var(--accent)" fill="var(--accent)" fillOpacity={0.30} />
              <Radar name="v1-hardened" dataKey="hardened" stroke="var(--cyan)" fill="var(--cyan)" fillOpacity={0.20} />
              <Tooltip contentStyle={{ background: "var(--panel)", border: "1px solid var(--border)", fontSize: 11 }} />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        {/* Latency targets */}
        <div className="glass shadow-panel rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="text-sm font-semibold">Latency by deployment target</div>
            <span className="text-2xs text-muted2 font-mono uppercase-wide tracking-wider">LOWER&nbsp;IS&nbsp;BETTER</span>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={LATENCY}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="target" stroke="var(--muted)" fontSize={10} angle={-15} textAnchor="end" height={60} />
              <YAxis stroke="var(--muted)" fontSize={10} unit=" ms" />
              <Tooltip contentStyle={{ background: "var(--panel)", border: "1px solid var(--border)", fontSize: 11 }} />
              <Bar dataKey="ms" fill="var(--threat-low)" isAnimationActive animationDuration={1200} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Cascade mini-board */}
        <div className="glass shadow-panel rounded-lg p-4">
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
            <span className="block text-cyan font-mono mt-1">{`Best epoch: 34  · top-1 89.03%`}</span>
          </div>
        </div>
      </div>

      {/* Suppress unused-import warning if Zap isn't used elsewhere */}
      {void [Zap, animValues]}
    </div>
  );
}
