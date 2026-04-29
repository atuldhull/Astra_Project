import { authHeaders } from "./auth";

const BASE = import.meta.env.VITE_API_BASE_URL ?? "";

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...authHeaders(init?.headers) },
    ...init,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export type AirframeExtra = {
  airframe?: string;                   // e.g. "F-22"
  airframe_confidence?: number;        // 0..1
  airframe_top3?: { name: string; conf: number }[];
  // OOD gatekeeper (lightweight conf+aspect+edge-density heuristic)
  ood_score?: number;                  // 0..1 — higher = more likely OOD
  ood_flag?: boolean;                  // ood_score >= 0.55
  ood_reasons?: string[];              // human-readable triggers (e.g. "low_conf(0.32)")
};

export type Detection = {
  id: number;
  mission_id: number;
  frame_index: number;
  frame_timestamp_ms: number;
  class_id: number;
  class_name: string;
  confidence: number;
  x1: number; y1: number; x2: number; y2: number;
  lat: number | null; lon: number | null;
  track_id: number | null;
  extras?: AirframeExtra | null;
  // v3.0/T1.1 — Ed25519 provenance signature; presence enables the verify badge.
  signature_b64?: string | null;
  image_sha256?: string | null;
  created_at: string;
};

export type ProvenanceStatus = {
  enabled: boolean;
  key_file: string;
  key_present: boolean;
  fingerprint: string | null;
  public_key_pem: string | null;
  model_hash: string | null;
};

export type ProvenanceVerify = {
  ok: boolean;
  reason?: string;
  fingerprint?: string;
  detection_id: number;
  signed_payload?: {
    mission_id: number;
    class_name: string;
    confidence: number;
    image_sha256_short: string;
    model_hash_short: string;
  };
};

/** Render the most specific label we have: airframe sub-class if MAR20
 *  cascade fired, otherwise the generic stage-1 class name. */
export function detectionLabel(d: Pick<Detection, "class_name" | "extras">): string {
  if (d.extras?.airframe) return d.extras.airframe;
  return d.class_name;
}

export type AlertStatus = "pending" | "confirmed" | "rejected" | "escalated" | "engaged";

export type AlertConfirmation = {
  operator_id: string;
  ts: string;
};

export type Alert = {
  id: number;
  mission_id: number;
  detection_id: number;
  threat_score: number;
  score_breakdown: {
    class_term: number;
    proximity_term: number;
    motion_term: number;
    count_term: number;
    confidence_term: number;
    distance_km: number | null;
    nearest_asset: string | null;
  };
  status: AlertStatus;
  operator_id: string | null;
  narrative: string | null;
  // Round-2 dual-control: who has signed off so far
  confirmations?: AlertConfirmation[];
  created_at: string;
  updated_at: string;
};

export type AuditEvent = {
  id: number;
  event_type: string;
  operator_id: string | null;
  mission_id: number | null;
  alert_id: number | null;
  payload_json: Record<string, unknown> | null;
  created_at: string;
};

export type Mission = {
  id: number;
  name: string;
  source_path: string;
  created_at: string;
  aoi_source?: "default" | "explicit" | "gps-exif" | null;
  gps_point?: [number, number] | null;
};

export type DetectorMetrics = {
  available: boolean;
  hint?: string;
  captured_at?: string;
  map_50?: number;
  map_50_95?: number;
  precision?: number;
  recall?: number;
  per_class?: { class_id: number; class_name: string; ap_50_95: number }[];
};

export type LatencyMetrics = {
  available: boolean;
  hint?: string;
  captured_at?: string;
  n?: number;
  p50_ms?: number;
  p95_ms?: number;
  p99_ms?: number;
  max_ms?: number;
};

export type AdversarialMetrics = {
  available: boolean;
  hint?: string;
  captured_at?: string;
  baseline_retention?: number;
  hardened_retention?: number;
  per_sample?: { sample: string; baseline: number; hardened: number }[];
};

// ── Public reports (D3.5) ────────────────────────────────────────────
export type PublicSubmitResult = {
  mission_id: number;
  has_gps: boolean;
  aoi_source: string;
  name: string;
};

export type TriageRow = {
  mission_id: number;
  name: string;
  reporter_id: string | null;
  source_path: string;
  created_at: string;
  caption: string | null;
};

export type RecentPublicRow = {
  mission_id: number;
  name: string;
  reporter_id: string | null;
  aoi_source: string | null;
  status: string;       // awaiting | pinned | processing | complete
  created_at: string;
};

// ── Mission audit snapshot (D4.2) ────────────────────────────────────
export type AuditSnapshotEvent = {
  id: number;
  event_type: string;
  operator_id: string | null;
  mission_id: number | null;
  alert_id: number | null;
  row_hash: string | null;
  prev_hash: string | null;
  created_at: string | null;
};
export type AuditSnapshotWitness = {
  id: number;
  peer_id: string;
  audit_row_id: number | null;
  row_hash: string;
  witnessed_at: string | null;
};
export type AuditSnapshot = {
  mission_id: number;
  until_ts: string;
  events: AuditSnapshotEvent[];
  tip: { id: number | null; row_hash: string | null; created_at: string | null };
  witnesses: AuditSnapshotWitness[];
};

// ── Health dashboard (D3.6) ──────────────────────────────────────────
export type HealthDashboard = {
  captured_at: string;
  operator: { id: string; role: string };
  backend: {
    uptime_s: number;
    version: string;
    device: string;
    model_path: string;
    cuda_available: boolean;
    python: string;
    platform: string;
  };
  models: {
    detector_ready: boolean;
    cascade_ready: boolean;
    llm_ready: boolean;
    model_hash: string;
    llm_path: string;
  };
  db: {
    mission_count: number;
    deleted_mission_count: number;
    detection_count: number;
    alert_count: number;
    audit_count: number;
    chat_message_count: number;
    peer_witness_count: number;
  };
  chain: {
    tip: string | null;
    tip_id: number | null;
    last_anchor: { ts: string; count: number; tip: string; backend: string } | null;
    anchor_total: number;
  };
  ood: {
    available: boolean;
    weights_path?: string;
    captured_at?: string;
    classes?: string[];
    n_samples_per_class?: Record<string, number>;
    thresholds?: Record<string, number>;
    hint?: string;
    error?: string;
  };
  errors: { count_24h: number; last_message: string | null; last_ts: string | null };
  latency: {
    captured_at: string | null;
    path: string;
    data: { p50_ms: number; p95_ms: number; p99_ms: number; n: number; mean_ms: number };
  } | null;
  map: {
    captured_at: string | null;
    path: string;
    data: { map_50: number; map_50_95: number; precision: number; recall: number };
  } | null;
};

// ── Mesh witnessing (D3.4) ───────────────────────────────────────────
export type MeshPeer = {
  peer_id: string;
  key_present: boolean;
  public_key_pem: string;
};

export type MeshWitness = {
  peer_id: string;
  witnessed_at: string | null;
  row_hash: string;
};

// ── Sentinel WS payloads (D3.3) ──────────────────────────────────────
export type SentinelDrone = {
  id: string;
  role: "friendly" | "foe";
  state: "active" | "signal_lost" | "destroyed";
  lat: number; lon: number;
  vx_mps: number; vy_mps: number;
  speed_mps: number;
  signal: number;
  trail: [number, number][];
  range_km: number | null;
  ttt_s: number | null;
  category: "monitor" | "soft_kill" | "hard_kill" | null;
  nearest_asset: string | null;
  asset_value: number;
};

export type SentinelTick = {
  type: "sentinel_tick";
  t: number;
  run_id: string;
  scenario: string;
  drones: SentinelDrone[];
};

export type SentinelAck = {
  type: "sentinel_ack";
  drone_id: string;
  action: "soft_kill" | "hard_kill";
  operator_id: string;
  latency_ms: number;
  ts: number;
};

export type ChatMessage = {
  id: number;
  mission_id: number | null;
  role: "user" | "astra";
  text: string;
  source: "rule" | "llm" | "error" | "note" | "briefing" | null;
  citations: Record<string, unknown>[];
  operator_id: string | null;
  created_at: string;
};

export type TrackPoint = {
  frame_index: number;
  frame_timestamp_ms: number;
  lat: number | null;
  lon: number | null;
  x1: number; y1: number; x2: number; y2: number;
  confidence: number;
};

export type Track = {
  track_id: number;
  class_id: number;
  class_name: string;
  point_count: number;
  avg_confidence: number;
  points: TrackPoint[];
};

export type AoiCorners = {
  top_left: [number, number];
  top_right: [number, number];
  bottom_right: [number, number];
  bottom_left: [number, number];
};

export const api = {
  health: () => json<{ status: string; device: string; model_loaded: boolean }>("/health"),
  chatThread: (mission_id: number | null) => {
    const q = mission_id != null ? `?mission_id=${mission_id}` : "";
    return json<ChatMessage[]>(`/api/v1/chat/thread${q}`);
  },
  chatAsk: (body: { question: string; mission_id?: number | null; operator_id?: string | null }) =>
    json<{ answer: string; source: string; citations: Record<string, unknown>[]; llm_available: boolean }>(
      `/api/v1/chat`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  chatNote: (body: { text: string; mission_id: number; operator_id?: string | null }) =>
    json<ChatMessage>(`/api/v1/chat/note`, { method: "POST", body: JSON.stringify(body) }),
  deleteMission: (mission_id: number) =>
    json<{ id: number; deleted_at: string; already: boolean }>(
      `/api/v1/ingest/${mission_id}`, { method: "DELETE" },
    ),
  detectorMetrics: () => json<DetectorMetrics>(`/api/v1/benchmarks/detector`),
  provenanceKey: () => json<ProvenanceStatus>(`/api/v1/provenance/key`),
  provenanceVerify: (detection_id: number) =>
    json<ProvenanceVerify>(`/api/v1/provenance/verify/${detection_id}`),
  anchorStatus: () =>
    json<{
      enabled: boolean;
      anchor_file: string;
      interval: number;
      total: number;
      last: { ts: string; count: number; tip: string; backend: string } | null;
    }>(`/api/v1/anchor/status`),
  anchorNow: () =>
    json<{ ok: boolean; reason?: string; anchor?: { ts: string; count: number; tip: string; backend: string } }>(
      `/api/v1/anchor/now`, { method: "POST" },
    ),
  anchorVerify: () =>
    json<{
      ok: boolean;
      total: number;
      mismatches: { count: number; ts: string; reason: string; anchored_tip?: string; live_tip?: string }[];
      last: { ts: string; count: number; tip: string; backend: string } | null;
    }>(`/api/v1/anchor/verify`),
  latencyMetrics: () => json<LatencyMetrics>(`/api/v1/benchmarks/latency`),
  adversarialMetrics: () => json<AdversarialMetrics>(`/api/v1/benchmarks/adversarial`),
  listMissions: (limit = 50) => json<Mission[]>(`/api/v1/ingest?limit=${limit}`),
  listDetections: (params?: { mission_id?: number; class_id?: number; limit?: number }) => {
    const q = new URLSearchParams();
    if (params?.mission_id != null) q.set("mission_id", String(params.mission_id));
    if (params?.class_id != null) q.set("class_id", String(params.class_id));
    if (params?.limit != null) q.set("limit", String(params.limit));
    return json<Detection[]>(`/api/v1/detections?${q}`);
  },
  listTracks: (mission_id: number) =>
    json<Track[]>(`/api/v1/tracks?mission_id=${mission_id}`),
  listAlerts: (params?: { mission_id?: number; status?: AlertStatus; min_score?: number }) => {
    const q = new URLSearchParams();
    if (params?.mission_id != null) q.set("mission_id", String(params.mission_id));
    if (params?.status) q.set("status", params.status);
    if (params?.min_score != null) q.set("min_score", String(params.min_score));
    return json<Alert[]>(`/api/v1/alerts?${q}`);
  },
  actOnAlert: (id: number, body: {
    action: "confirm" | "reject" | "reclassify" | "escalate" | "engage";
    operator_id: string;
    new_class_id?: number;
    reason?: string;
  }) => json<Alert>(`/api/v1/alerts/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  listAudit: (params?: {
    event_types?: string[];
    operator_id?: string;
    alert_id?: number;
    mission_id?: number;
    since?: string;
    until?: string;
    limit?: number;
  }) => {
    const q = new URLSearchParams();
    if (params?.event_types?.length) q.set("event_types", params.event_types.join(","));
    if (params?.operator_id) q.set("operator_id", params.operator_id);
    if (params?.alert_id != null) q.set("alert_id", String(params.alert_id));
    if (params?.mission_id != null) q.set("mission_id", String(params.mission_id));
    if (params?.since) q.set("since", params.since);
    if (params?.until) q.set("until", params.until);
    if (params?.limit) q.set("limit", String(params.limit));
    const qs = q.toString();
    return json<AuditEvent[]>(`/api/v1/audit${qs ? `?${qs}` : ""}`);
  },
  // v3.0/D5.7b — batch latest-row-id lookup per alert (pre-fetch helper)
  auditLatestByAlert: (alert_ids: number[]) =>
    json<{ by_alert: Record<string, number | null> }>(
      `/api/v1/audit/latest-by-alert?alert_ids=${alert_ids.join(",")}`,
    ),
  // v3.0/D3.2 — chain operations
  verifyAuditRow: (row_id: number) =>
    json<{
      ok: boolean;
      checked: number;
      broken_at_id: number | null;
      reason: string | null;
      row_hash: string | null;
      prev_hash: string | null;
    }>(`/api/v1/audit/verify-row/${row_id}`),
  operatorActivity: (params?: { since?: string; until?: string }) => {
    const q = new URLSearchParams();
    if (params?.since) q.set("since", params.since);
    if (params?.until) q.set("until", params.until);
    const qs = q.toString();
    return json<{
      since: string | null;
      until: string | null;
      operators: Array<{
        operator_id: string;
        total: number;
        by_event_type: Record<string, number>;
      }>;
      system_events: number;
      total: number;
    }>(`/api/v1/audit/operator-activity${qs ? `?${qs}` : ""}`);
  },
  /** Returns the URL for the range-cert PDF — caller passes it to <a download>. */
  auditRangeCertUrl: (params: { since?: string; until?: string }) => {
    const q = new URLSearchParams();
    if (params.since) q.set("since", params.since);
    if (params.until) q.set("until", params.until);
    return `${BASE}/api/v1/audit/range-cert${q.toString() ? `?${q}` : ""}`;
  },
  // ── Counter-Drone Sentinel (D3.3) ────────────────────────────────
  sentinelScenarios: () =>
    json<{
      scenarios: Array<{
        id: string; label: string; description: string;
        n_drones: number; n_friendlies: number;
      }>;
    }>(`/api/v1/sentinel/scenarios`),
  sentinelStatus: () =>
    json<{
      running: boolean;
      run_id?: string;
      scenario?: string;
      started_at?: string;
      n_drones?: number;
      n_commands_signed?: number;
      latency_p50_ms?: number | null;
    }>(`/api/v1/sentinel/status`),
  sentinelStart: (body: { scenario: string; n_drones?: number }) =>
    json<{ run_id: string; scenario: string; n_drones: number; n_friendlies: number }>(
      `/api/v1/sentinel/start`, { method: "POST", body: JSON.stringify(body) }
    ),
  sentinelStop: () =>
    json<{ stopped: boolean; had_run: boolean }>(`/api/v1/sentinel/stop`, { method: "POST" }),
  sentinelVerify: (drone_id: string) =>
    json<{ ok: boolean; role?: string; drone_id?: string; reason?: string }>(
      `/api/v1/sentinel/verify/${drone_id}`, { method: "POST" }
    ),
  sentinelEngage: (body: { drone_id: string; action: "soft_kill" | "hard_kill"; operator_id: string }) =>
    json<{ ok: boolean; drone_id: string; action: string; latency_ms: number; new_state: string }>(
      `/api/v1/sentinel/engage`, { method: "POST", body: JSON.stringify(body) }
    ),
  // ── Mesh (D3.4) ──────────────────────────────────────────────────
  meshPeers: () =>
    json<{ peers: MeshPeer[]; peers_dir: string; n_peers: number; peer_ids: string[] }>(
      `/api/v1/mesh/peers`,
    ),
  meshFeed: (params?: { since_id?: number; limit?: number }) => {
    const q = new URLSearchParams();
    if (params?.since_id != null) q.set("since_id", String(params.since_id));
    if (params?.limit != null) q.set("limit", String(params.limit));
    const qs = q.toString();
    return json<{
      since_id: number;
      count: number;
      events: Array<{
        id: number;
        event_type: string;
        operator_id: string | null;
        mission_id: number | null;
        alert_id: number | null;
        payload: Record<string, unknown> | null;
        prev_hash: string | null;
        row_hash: string | null;
        created_at: string | null;
      }>;
    }>(`/api/v1/mesh/feed${qs ? `?${qs}` : ""}`);
  },
  meshWitnesses: (audit_row_ids: number[]) => {
    const ids = audit_row_ids.join(",");
    return json<{
      by_row: Record<string, MeshWitness[]>;
      n_peers: number;
    }>(`/api/v1/mesh/witnesses?audit_row_ids=${encodeURIComponent(ids)}`);
  },
  meshSyncDemo: (limit?: number) =>
    json<{
      ok: boolean;
      rows_seen: number;
      peers: string[];
      witnesses_added: number;
      skipped: number;
      refused_due_to_tampering: number;
      last_sync_ts: string;
    }>(
      `/api/v1/mesh/sync-demo${limit ? `?limit=${limit}` : ""}`,
      { method: "POST" },
    ),
  // ── Public reports (D3.5) ────────────────────────────────────────
  publicSubmit: async (file: File, reporter_id: string, caption?: string) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("reporter_id", reporter_id);
    if (caption) fd.append("caption", caption);
    const res = await fetch(`${BASE}/api/v1/public/submit`, { method: "POST", body: fd });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json() as Promise<PublicSubmitResult>;
  },
  publicPin: (mission_id: number, body: { lat: number; lon: number; operator_id: string }) =>
    json<Mission>(`/api/v1/public/${mission_id}/pin`, {
      method: "POST", body: JSON.stringify(body),
    }),
  publicTriage: (limit = 50) =>
    json<TriageRow[]>(`/api/v1/public/triage?limit=${limit}`),
  publicRecent: (limit = 20) =>
    json<RecentPublicRow[]>(`/api/v1/public/recent?limit=${limit}`),
  publicThumbnailUrl: (mission_id: number) =>
    `${BASE}/api/v1/public/thumbnail/${mission_id}`,
  // ── Mission report PDF (D6.0 surface coverage) ───────────────────
  missionReportUrl: (mission_id: number) =>
    `${BASE}/api/v1/reports/mission/${mission_id}.pdf`,
  // ── OOD calibration (T1.3) ───────────────────────────────────────
  oodCalibration: () =>
    json<{
      backend: string;
      heuristic_threshold: number;
      available: boolean;
      weights_path?: string;
      captured_at?: string;
      classes?: string[];
      n_samples_per_class?: Record<string, number>;
      thresholds?: Record<string, number>;
      hint?: string;
    }>(`/api/v1/ood/calibration`),
  // ── Health dashboard (D3.6) ──────────────────────────────────────
  healthDashboard: () => json<HealthDashboard>(`/api/v1/health/dashboard`),
  // ── Mission audit snapshot (D4.2) ────────────────────────────────
  auditSnapshot: (mission_id: number, until_ts?: string) => {
    const q = new URLSearchParams({ mission_id: String(mission_id) });
    if (until_ts) q.set("until_ts", until_ts);
    return json<AuditSnapshot>(`/api/v1/audit/snapshot?${q}`);
  },
  ingest: async (file: File, name: string, aoi: AoiCorners) => {
    const fd = new FormData();
    fd.append("name", name);
    fd.append("file", file);
    fd.append("aoi_corners", JSON.stringify(aoi));
    const res = await fetch(`${BASE}/api/v1/ingest`, { method: "POST", body: fd });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json() as Promise<Mission>;
  },
  // Upload without explicit AOI — backend will try EXIF-GPS extraction and
  // fall back to a default AOI only if no GPS is found.
  ingestAuto: async (file: File, name: string) => {
    const fd = new FormData();
    fd.append("name", name);
    fd.append("file", file);
    const res = await fetch(`${BASE}/api/v1/ingest`, { method: "POST", body: fd });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json() as Promise<Mission>;
  },
  ingestUrl: async (
    url: string,
    name: string,
    aoi: AoiCorners,
    opts?: { max_frames?: number; duration_s?: number },
  ) => {
    const fd = new FormData();
    fd.append("name", name);
    fd.append("url", url);
    fd.append("aoi_corners", JSON.stringify(aoi));
    if (opts?.max_frames != null) fd.append("max_frames", String(opts.max_frames));
    if (opts?.duration_s != null) fd.append("duration_s", String(opts.duration_s));
    const res = await fetch(`${BASE}/api/v1/ingest/url`, { method: "POST", body: fd });
    if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
    return res.json() as Promise<Mission>;
  },
};

// Default demo AOI — same as friendly_assets range in backend config.py.
// Small ~1.2 km² box over Bengaluru centered near FOB Delta (12.9716, 77.5946).
export const DEFAULT_AOI: AoiCorners = {
  top_left:     [12.9750, 77.5900],
  top_right:    [12.9750, 77.6000],
  bottom_right: [12.9650, 77.6000],
  bottom_left:  [12.9650, 77.5900],
};

export function openLiveSocket(onMessage: (data: unknown) => void): WebSocket {
  const url = import.meta.env.VITE_WS_URL ?? `ws://${location.host}/ws/live`;
  const ws = new WebSocket(url);
  ws.onmessage = (ev) => {
    try { onMessage(JSON.parse(ev.data)); } catch { /* ignore */ }
  };
  return ws;
}

/** Sentinel command-and-control feed (D3.3). 5 Hz `sentinel_tick` events
 *  + on-demand `sentinel_ack` events. Falls back to a host-derived URL
 *  when VITE_WS_URL is not set. */
export function openC2Socket(onMessage: (data: unknown) => void): WebSocket {
  // Compute the c2 URL from the configured live URL by replacing /ws/live
  // → /ws/c2 if applicable, otherwise host-derived.
  const liveUrl: string | undefined = import.meta.env.VITE_WS_URL;
  const url = liveUrl
    ? liveUrl.replace(/\/ws\/live$/, "/ws/c2")
    : `ws://${location.host}/ws/c2`;
  const ws = new WebSocket(url);
  ws.onmessage = (ev) => {
    try { onMessage(JSON.parse(ev.data)); } catch { /* ignore */ }
  };
  return ws;
}

export function threatColor(score: number): string {
  if (score >= 0.75) return "text-threat-crit";
  if (score >= 0.55) return "text-threat-high";
  if (score >= 0.35) return "text-threat-med";
  return "text-threat-low";
}
