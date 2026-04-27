import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

// Replace with real numbers from docs/benchmark-report.json after training.
const PER_CLASS = [
  { cls: "small-vehicle", mAP: 0.408 },
  { cls: "large-vehicle", mAP: 0.660 },
  { cls: "fixed-wing",    mAP: 0.915 },
  { cls: "rotor",         mAP: 0.242 },
  { cls: "ship",          mAP: 0.770 },
  { cls: "storage-depot", mAP: 0.393 },
  { cls: "harbor",        mAP: 0.733 },
  { cls: "bridge",        mAP: 0.000 },
];

const LATENCY = [
  { target: "RTX 4050 FP32", ms: 22.3 },
  { target: "CPU ONNX FP32", ms: 35.7 },
  { target: "RTX 4050 p95",  ms: 33.6 },
  { target: "CPU ONNX p95",  ms: 37.2 },
];

function Card({ title, value, sub }: { title: string; value: string; sub?: string }) {
  return (
    <div className="glass shadow-panel rounded px-4 py-3">
      <div className="text-xs text-muted uppercase tracking-wider">{title}</div>
      <div className="text-2xl font-semibold mt-1">{value}</div>
      {sub && <div className="text-xs text-muted mt-0.5">{sub}</div>}
    </div>
  );
}

export default function Benchmark() {
  const mean = PER_CLASS.reduce((s, r) => s + r.mAP, 0) / PER_CLASS.length;
  return (
    <div className="h-full flex flex-col">
      <header className="px-6 py-4 border-b border-border">
        <h1 className="text-lg font-semibold">Benchmark</h1>
        <p className="text-xs text-muted">DOTA-v1.5 val set (1561 images, 67029 instances) · yolo11n · 640² input</p>
      </header>
      <div className="flex-1 p-6 space-y-6 overflow-auto">
        <div className="grid grid-cols-4 gap-4">
          <Card title="mAP@0.5 overall" value={mean.toFixed(3)} sub="across 8 classes" />
          <Card title="GPU latency (median)" value="22.3 ms" sub="RTX 4050 · FP32" />
          <Card title="CPU latency (median)" value="35.7 ms" sub="ONNX FP32" />
          <Card title="Model size" value="5.5 MB" sub="yolo11n ONNX" />
        </div>

        <div className="grid grid-cols-2 gap-6">
          <div className="glass shadow-panel rounded p-4">
            <div className="text-sm font-semibold mb-3">mAP@0.5 per class</div>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={PER_CLASS}>
                <CartesianGrid strokeDasharray="3 3" stroke="#23303d" />
                <XAxis dataKey="cls" stroke="#8b9aad" fontSize={10} angle={-20} textAnchor="end" height={60} />
                <YAxis stroke="#8b9aad" fontSize={10} domain={[0, 1]} />
                <Tooltip contentStyle={{ background: "#121821", border: "1px solid #23303d" }} />
                <Bar dataKey="mAP" fill="#ff7a1a" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="glass shadow-panel rounded p-4">
            <div className="text-sm font-semibold mb-3">Latency by target</div>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={LATENCY}>
                <CartesianGrid strokeDasharray="3 3" stroke="#23303d" />
                <XAxis dataKey="target" stroke="#8b9aad" fontSize={10} angle={-15} textAnchor="end" height={60} />
                <YAxis stroke="#8b9aad" fontSize={10} />
                <Tooltip contentStyle={{ background: "#121821", border: "1px solid #23303d" }} />
                <Bar dataKey="ms" fill="#4ade80" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
}
