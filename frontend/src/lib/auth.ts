/**
 * Auth client — JWT token storage + lightweight login/me wrappers.
 *
 * Token lives in localStorage under astra:jwt:v1. All api.ts calls add
 * the Bearer header automatically (see api.ts).
 *
 * Master switch: backend's ASTRA_AUTH_ENABLED. Frontend treats that as the
 * auth_enabled flag returned by /auth/me — when false, login is OPTIONAL
 * (the demo runs without it) but still works if you do it.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";
const KEY = "astra:jwt:v1";

export type LoginResponse = {
  access_token: string;
  token_type: string;
  expires_at: number;
  operator_id: string;
  role: "operator" | "commander" | "admin";
};

export type Me = {
  operator_id: string;
  role: "operator" | "commander" | "admin";
  auth_enabled: boolean;
};

export type OperatorListEntry = { operator_id: string; role: string };

let _token: string | null = (() => {
  try { return localStorage.getItem(KEY); } catch { return null; }
})();

const subscribers = new Set<(t: string | null) => void>();
function emit() { for (const fn of subscribers) fn(_token); }

export function getToken(): string | null { return _token; }

export function subscribeAuth(fn: (t: string | null) => void): () => void {
  subscribers.add(fn);
  return () => { subscribers.delete(fn); };
}

export function setToken(token: string | null) {
  _token = token;
  try {
    if (token) localStorage.setItem(KEY, token);
    else localStorage.removeItem(KEY);
  } catch { /* noop */ }
  emit();
}

export async function login(operator_id: string, password: string): Promise<LoginResponse> {
  const r = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ operator_id, password }),
  });
  if (!r.ok) {
    const msg = await r.text().catch(() => `${r.status}`);
    throw new Error(msg || `${r.status} ${r.statusText}`);
  }
  const data = (await r.json()) as LoginResponse;
  setToken(data.access_token);
  return data;
}

export function logout() { setToken(null); }

export async function fetchMe(): Promise<Me | null> {
  if (!_token) return null;
  const r = await fetch(`${API_BASE}/api/v1/auth/me`, {
    headers: { Authorization: `Bearer ${_token}` },
  });
  if (r.status === 401) {
    setToken(null);
    return null;
  }
  if (!r.ok) return null;
  return r.json();
}

export async function fetchOperators(): Promise<{ operators: OperatorListEntry[]; auth_enabled: boolean }> {
  const r = await fetch(`${API_BASE}/api/v1/auth/operators`);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

/** Decorate any fetch init with the Bearer header if we have a token. */
export function authHeaders(extra?: HeadersInit): HeadersInit {
  if (!_token) return extra ?? {};
  return { ...(extra ?? {}), Authorization: `Bearer ${_token}` };
}
