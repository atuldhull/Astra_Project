/**
 * Public Reports — citizen-submission triage with manual-pin fallback.
 *
 * Lives in the OPERATOR group at /public-reports. The public-facing
 * submit form is embedded on /command (OPERATIONS) so judges see the
 * flow without leaving Operations; this page handles the triage side.
 *
 * Aesthetic Spec: dense list, mono IDs, status pills, modal pin-drop.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { MapContainer, Marker, TileLayer, useMapEvents } from "react-leaflet";
import L from "leaflet";
import {
  Inbox, Loader2, MapPin, RefreshCw, ExternalLink, X,
} from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { HeroStat } from "../components/HeroStat";
import { StatusPill } from "../components/StatusPill";
import { EmptyState } from "../components/EmptyState";
import { toast } from "../components/Toast";
import { useStallTimeout } from "../lib/useStallTimeout";
import { absoluteIst, relativeTime } from "../lib/time";
import {
  api, type RecentPublicRow, type TriageRow,
} from "../lib/api";

const OPERATOR_ID = "triage-op"; // would come from auth in production

// ── Pin-drop modal ──────────────────────────────────────────────────

function ClickToPin({ onClick }: { onClick: (lat: number, lon: number) => void }) {
  useMapEvents({
    click(e) { onClick(e.latlng.lat, e.latlng.lng); },
  });
  return null;
}

function PinModal({
  row, onClose, onSubmit, busy,
}: {
  row: TriageRow;
  onClose: () => void;
  onSubmit: (lat: number, lon: number) => void;
  busy: boolean;
}) {
  const [pin, setPin] = useState<{ lat: number; lon: number } | null>(null);

  return (
    <div
      className="fixed inset-0 z-[10001] bg-bg/70 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={() => !busy && onClose()}
    >
      <div
        className="glass-strong border border-border rounded-lg w-full max-w-3xl shadow-2xl flex flex-col"
        onClick={(e) => e.stopPropagation()}
        style={{ maxHeight: "82vh" }}
      >
        <div className="px-4 py-3 border-b border-border flex items-center justify-between">
          <div>
            <div className="font-mono text-2xs uppercase-wide tracking-wider text-muted2">
              DROP PIN · MISSION #{row.mission_id}
            </div>
            <div className="text-base font-semibold text-text mt-0.5">{row.name}</div>
            <div className="text-2xs text-muted2 font-mono mt-0.5">
              reporter <span className="text-muted">{row.reporter_id ?? "anonymous"}</span>
              {" · "}
              <span title={absoluteIst(row.created_at)}>{relativeTime(row.created_at)}</span>
            </div>
          </div>
          <button
            onClick={() => !busy && onClose()}
            className="text-muted hover:text-text -m-1 p-1.5 rounded"
            aria-label="Close"
          >
            <X size={16} />
          </button>
        </div>
        <div className="flex-1 grid grid-cols-[1fr_220px] gap-0 overflow-hidden">
          <div className="relative bg-panel">
            <MapContainer
              center={[12.9716, 77.5946]}
              zoom={3}
              style={{ height: "100%", width: "100%", minHeight: "440px" }}
              preferCanvas
            >
              <TileLayer
                attribution="&copy; OpenStreetMap"
                url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              <ClickToPin onClick={(lat, lon) => setPin({ lat, lon })} />
              {pin && (
                <Marker
                  position={[pin.lat, pin.lon]}
                  icon={L.divIcon({
                    className: "",
                    html: `<div style="color:#22d3ee;font-size:22px;line-height:1;text-shadow:0 0 6px rgba(0,0,0,0.7);">●</div>`,
                    iconSize: [22, 22],
                    iconAnchor: [11, 11],
                  })}
                />
              )}
            </MapContainer>
          </div>
          <aside className="border-l border-border p-3 flex flex-col gap-3 bg-panel/40">
            <img
              src={api.publicThumbnailUrl(row.mission_id)}
              alt="submission"
              className="w-full h-32 object-cover rounded border border-border"
            />
            {row.caption && (
              <div className="text-xs text-muted leading-snug border-l-2 border-cyan/40 pl-2">
                {row.caption}
              </div>
            )}
            <div className="text-2xs font-mono text-muted2 uppercase-wide tracking-wider">PIN</div>
            <div className="bg-bg/60 border border-border rounded px-2 py-1.5 text-2xs font-mono text-text break-all">
              {pin ? `${pin.lat.toFixed(5)}, ${pin.lon.toFixed(5)}` : "click anywhere on the map"}
            </div>
            <div className="flex flex-col gap-2 mt-auto">
              <button
                onClick={() => pin && onSubmit(pin.lat, pin.lon)}
                disabled={!pin || busy}
                className="flex items-center justify-center gap-2 bg-accent text-bg px-3 py-1.5 rounded text-sm font-medium hover:brightness-110 disabled:opacity-50 transition-fast"
              >
                {busy ? <Loader2 size={13} className="animate-spin" /> : <MapPin size={13} />}
                confirm pin
              </button>
              <button
                onClick={() => !busy && onClose()}
                disabled={busy}
                className="px-3 py-1.5 rounded text-xs text-muted hover:text-text disabled:opacity-50"
              >
                cancel
              </button>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}

// ── Page ────────────────────────────────────────────────────────────

function statusVariant(s: string): "ok" | "warn" | "neutral" | "info" | "live" {
  if (s === "complete" || s === "pinned") return "ok";
  if (s === "processing") return "live";
  if (s === "awaiting") return "warn";
  return "neutral";
}

export default function PublicReports() {
  const [triage, setTriage] = useState<TriageRow[]>([]);
  const [recent, setRecent] = useState<RecentPublicRow[]>([]);
  const [loading, setLoading] = useState(false);
  const stalled = useStallTimeout(loading, 15_000);
  const [pinTarget, setPinTarget] = useState<TriageRow | null>(null);
  const [busyPin, setBusyPin] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [t, r] = await Promise.all([
        api.publicTriage(50).catch(() => []),
        api.publicRecent(20).catch(() => []),
      ]);
      setTriage(t);
      setRecent(r);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const handle = window.setInterval(refresh, 6000);
    return () => window.clearInterval(handle);
  }, [refresh]);

  async function submitPin(lat: number, lon: number) {
    if (!pinTarget) return;
    setBusyPin(true);
    try {
      await api.publicPin(pinTarget.mission_id, { lat, lon, operator_id: OPERATOR_ID });
      toast.success(
        `Mission #${pinTarget.mission_id} pinned`,
        `${lat.toFixed(4)}, ${lon.toFixed(4)} · pipeline running`,
      );
      setPinTarget(null);
      await refresh();
    } catch (e) {
      toast.crit("Pin failed", (e as Error).message);
    } finally {
      setBusyPin(false);
    }
  }

  const awaitingCount = triage.length;
  const pinnedToday = useMemo(
    () => recent.filter((r) =>
      ["complete", "pinned", "processing"].includes(r.status) &&
      Date.now() - new Date(r.created_at).getTime() < 86_400_000,
    ).length,
    [recent],
  );

  return (
    <div className="h-full flex flex-col">
      <PageHeader
        icon={Inbox}
        title="Public Reports"
        badge={
          awaitingCount > 0
            ? <StatusPill variant="warn" size="sm">{awaitingCount} awaiting pin</StatusPill>
            : <StatusPill variant="ok" size="sm">queue clear</StatusPill>
        }
        subtitle="Citizen submissions — pipeline-mediated triage"
        actions={
          <button
            onClick={refresh}
            className="p-1.5 rounded hover:bg-panel2 text-muted transition-fast"
            title="Refresh"
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
          </button>
        }
      />

      <div className="px-6 pt-4 grid grid-cols-4 gap-3">
        <HeroStat label="awaiting pin" value={awaitingCount} icon={MapPin} tone={awaitingCount > 0 ? "high" : "neutral"} sub="public-report queue" />
        <HeroStat label="processed (24h)" value={pinnedToday} icon={Inbox} tone="low" sub="auto-GPS or pinned" />
        <HeroStat label="recent reports" value={recent.length} icon={Inbox} tone="cyan" sub="last 20 across all states" />
        <HeroStat
          label="reporters"
          value={new Set(recent.map((r) => r.reporter_id ?? "?")).size}
          icon={Inbox}
          tone="neutral"
          sub="distinct submitters"
        />
      </div>

      <div className="flex-1 px-6 pt-3 pb-6 grid grid-cols-[1fr_360px] gap-4 overflow-hidden">
        {/* Triage queue */}
        <div className="glass rounded-lg shadow-panel flex flex-col overflow-hidden">
          <div className="px-4 py-2.5 border-b border-border flex items-center justify-between">
            <div>
              <div className="text-2xs uppercase-wide tracking-wider text-muted2 font-mono">TRIAGE QUEUE</div>
              <div className="text-[10px] text-muted font-mono mt-0.5">awaiting operator pin · no EXIF GPS detected</div>
            </div>
            <span className="text-2xs font-mono tabular-nums text-accent">{awaitingCount}</span>
          </div>
          <div className="flex-1 overflow-auto">
            {loading && triage.length === 0 ? (
              <div className="px-4 py-4 text-2xs text-muted2">
                <Loader2 size={12} className="animate-spin inline mr-1" /> loading…
                {stalled && <div className="text-threat-high mt-2">backend slow or unreachable</div>}
              </div>
            ) : triage.length === 0 ? (
              <EmptyState
                icon={MapPin}
                title="No reports awaiting pin"
                body="When a citizen submits a photo without EXIF GPS, it lands here for one-click triage."
              />
            ) : (
              triage.map((t) => (
                <div
                  key={t.mission_id}
                  className="border-b border-border last:border-0 px-4 py-3 flex items-center gap-3 hover:bg-panel2/60"
                >
                  <img
                    src={api.publicThumbnailUrl(t.mission_id)}
                    alt=""
                    className="w-14 h-14 object-cover rounded border border-border shrink-0"
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 text-xs">
                      <span className="font-mono text-text">#{t.mission_id}</span>
                      <span className="text-muted truncate">{t.name}</span>
                    </div>
                    <div className="flex items-center gap-2 text-2xs font-mono text-muted2 mt-0.5">
                      <span title={absoluteIst(t.created_at)}>{relativeTime(t.created_at)}</span>
                      <span className="opacity-50">·</span>
                      <span>reporter <span className="text-muted">{t.reporter_id ?? "anonymous"}</span></span>
                    </div>
                    {t.caption && (
                      <div className="text-2xs text-muted truncate mt-0.5 italic" title={t.caption}>
                        “{t.caption}”
                      </div>
                    )}
                  </div>
                  <button
                    onClick={() => setPinTarget(t)}
                    className="flex items-center gap-1.5 bg-cyan/15 border border-cyan/40 text-cyan px-3 py-1.5 rounded text-xs font-medium hover:bg-cyan/25 transition-fast shrink-0"
                  >
                    <MapPin size={12} /> drop pin
                  </button>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Recent feed */}
        <aside className="glass rounded-lg shadow-panel flex flex-col overflow-hidden">
          <div className="px-3 py-2.5 border-b border-border">
            <div className="text-2xs uppercase-wide tracking-wider text-muted2 font-mono">RECENT REPORTS</div>
            <div className="text-[10px] text-muted font-mono mt-0.5">last {recent.length} across all statuses</div>
          </div>
          <div className="flex-1 overflow-auto">
            {recent.length === 0 ? (
              <div className="px-3 py-4 text-2xs text-muted2">none yet.</div>
            ) : recent.map((r) => (
              <div key={r.mission_id} className="border-b border-border last:border-0 px-3 py-2 text-2xs">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-text truncate">#{r.mission_id}</span>
                  <StatusPill variant={statusVariant(r.status)} size="sm">{r.status}</StatusPill>
                </div>
                <div className="flex items-center justify-between mt-1 font-mono text-muted2">
                  <span title={absoluteIst(r.created_at)}>{relativeTime(r.created_at)}</span>
                  <span className="opacity-70">{r.aoi_source ?? "—"}</span>
                </div>
                {r.aoi_source && r.aoi_source !== "unknown" && (
                  <a
                    href={`/map?mission=${r.mission_id}`}
                    className="mt-1 text-cyan hover:text-text inline-flex items-center gap-1 text-[10px] uppercase-wide tracking-wider font-mono"
                  >
                    open on map <ExternalLink size={9} />
                  </a>
                )}
              </div>
            ))}
          </div>
        </aside>
      </div>

      {pinTarget && (
        <PinModal
          row={pinTarget}
          busy={busyPin}
          onClose={() => setPinTarget(null)}
          onSubmit={submitPin}
        />
      )}
    </div>
  );
}
