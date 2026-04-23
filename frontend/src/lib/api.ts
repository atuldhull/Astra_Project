const BASE = import.meta.env.VITE_API_BASE_URL ?? "";

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

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
  created_at: string;
};

export type AlertStatus = "pending" | "confirmed" | "rejected" | "escalated";

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

export const api = {
  health: () => json<{ status: string; device: string; model_loaded: boolean }>("/health"),
  listDetections: (params?: { mission_id?: number; class_id?: number }) => {
    const q = new URLSearchParams();
    if (params?.mission_id != null) q.set("mission_id", String(params.mission_id));
    if (params?.class_id != null) q.set("class_id", String(params.class_id));
    return json<Detection[]>(`/api/v1/detections?${q}`);
  },
  listAlerts: (params?: { mission_id?: number; status?: AlertStatus; min_score?: number }) => {
    const q = new URLSearchParams();
    if (params?.mission_id != null) q.set("mission_id", String(params.mission_id));
    if (params?.status) q.set("status", params.status);
    if (params?.min_score != null) q.set("min_score", String(params.min_score));
    return json<Alert[]>(`/api/v1/alerts?${q}`);
  },
  actOnAlert: (id: number, body: {
    action: "confirm" | "reject" | "reclassify" | "escalate";
    operator_id: string;
    new_class_id?: number;
    reason?: string;
  }) => json<Alert>(`/api/v1/alerts/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  listAudit: () => json<AuditEvent[]>("/api/v1/audit"),
};

export function openLiveSocket(onMessage: (data: unknown) => void): WebSocket {
  const url = import.meta.env.VITE_WS_URL ?? `ws://${location.host}/ws/live`;
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
