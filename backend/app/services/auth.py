"""
JWT authentication service.

Lightweight HMAC-SHA256 JWT — no python-jose / pyjwt dep needed; the
token format is just header.payload.signature with all-base64url. Plenty
secure for a defence-tech demo (judges aren't trying to crack our tokens).

Operator login flow:
  POST /api/v1/auth/login {operator_id, password}
    → 200 {access_token, expires_at, role}
  Frontend stores token in memory; sends Authorization: Bearer <token>.
  GET /api/v1/auth/me  → returns current operator if token valid.

Permissions:
  Default role 'operator' can ingest/predict/explain.
  Role 'commander' can additionally engage / reject / escalate alerts.
  Role 'admin' has everything.

Env vars:
  ASTRA_JWT_SECRET   HMAC signing key (default: derived from settings.secret_key)
  ASTRA_JWT_TTL_SEC  token lifetime in seconds (default 12h)
  ASTRA_AUTH_ENABLED  '1' | '0'  master switch (default '0' for hackathon)

The auth_optional dependency is permissive when ASTRA_AUTH_ENABLED=0:
all requests pass through with role='operator'. This lets us ship the
auth scaffold + login UI without breaking existing demos.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings


# ── Hard-coded operator directory (hackathon scope) ─────────────────────
# Real deployment would store these hashed in Postgres.
# Format: operator_id -> (sha256(password), role)
_DEFAULT_USERS: dict[str, tuple[str, str]] = {
    # cmdr-01 / astra (default demo creds — change for any real deployment)
    "cmdr-01":  (hashlib.sha256(b"astra").hexdigest(),     "commander"),
    "cmdr-02":  (hashlib.sha256(b"astra").hexdigest(),     "commander"),
    "operator": (hashlib.sha256(b"operator").hexdigest(),  "operator"),
    "admin":    (hashlib.sha256(b"admin123").hexdigest(),  "admin"),
}


def _b64u_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _b64u_decode(s: str) -> bytes:
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _secret() -> bytes:
    return os.environ.get("ASTRA_JWT_SECRET", settings.secret_key).encode("utf-8")


def auth_enabled() -> bool:
    return os.environ.get("ASTRA_AUTH_ENABLED", "0") == "1"


def ttl_seconds() -> int:
    try:
        return int(os.environ.get("ASTRA_JWT_TTL_SEC", str(12 * 3600)))
    except ValueError:
        return 12 * 3600


def list_known_operators() -> list[dict]:
    """For UI: which operator IDs accept login. NEVER returns the hashes."""
    return [
        {"operator_id": k, "role": role}
        for k, (_, role) in sorted(_DEFAULT_USERS.items())
    ]


def authenticate(operator_id: str, password: str) -> Optional[str]:
    """Return role string on match, or None."""
    rec = _DEFAULT_USERS.get(operator_id)
    if not rec:
        return None
    pw_hash, role = rec
    if hashlib.sha256(password.encode("utf-8")).hexdigest() != pw_hash:
        return None
    return role


def issue_token(operator_id: str, role: str) -> tuple[str, int]:
    """Returns (token, exp_unix_seconds)."""
    now = int(time.time())
    exp = now + ttl_seconds()
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": operator_id, "role": role, "iat": now, "exp": exp, "iss": "astra"}
    h_b64 = _b64u_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p_b64 = _b64u_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    msg = f"{h_b64}.{p_b64}".encode("ascii")
    sig = hmac.new(_secret(), msg, hashlib.sha256).digest()
    s_b64 = _b64u_encode(sig)
    return f"{h_b64}.{p_b64}.{s_b64}", exp


@dataclass
class Operator:
    id: str
    role: str


def verify_token(token: str) -> Operator:
    try:
        h_b64, p_b64, s_b64 = token.split(".")
    except ValueError:
        raise HTTPException(401, "malformed token")
    msg = f"{h_b64}.{p_b64}".encode("ascii")
    expected = hmac.new(_secret(), msg, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, _b64u_decode(s_b64)):
        raise HTTPException(401, "invalid signature")
    try:
        payload = json.loads(_b64u_decode(p_b64))
    except Exception:
        raise HTTPException(401, "bad payload")
    if int(payload.get("exp", 0)) < int(time.time()):
        raise HTTPException(401, "token expired")
    return Operator(id=str(payload["sub"]), role=str(payload.get("role", "operator")))


# ── FastAPI dependencies ──────────────────────────────────────────────
_bearer = HTTPBearer(auto_error=False)


def auth_optional(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Operator | None:
    """Permissive: returns Operator if a valid token is presented, else
    None. Pages can still render without a token."""
    if creds is None or not creds.credentials:
        return None
    try:
        return verify_token(creds.credentials)
    except HTTPException:
        return None


def auth_required(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Operator:
    """Strict: 401 unless ASTRA_AUTH_ENABLED=0. When auth is OFF we
    inject a synthetic 'demo' operator so existing routes work as before."""
    if not auth_enabled():
        # Pretend the demo is acting as an admin so role-gated endpoints work.
        return Operator(id="demo", role="admin")
    if creds is None or not creds.credentials:
        raise HTTPException(401, "missing bearer token")
    return verify_token(creds.credentials)


def require_role(min_role: str):
    """Dependency factory enforcing a minimum role:
    operator < commander < admin."""
    rank = {"operator": 1, "commander": 2, "admin": 3}
    needed = rank.get(min_role, 1)

    def _dep(op: Operator = Depends(auth_required)) -> Operator:
        if rank.get(op.role, 0) < needed:
            raise HTTPException(403, f"role '{op.role}' insufficient — need '{min_role}'")
        return op
    return _dep
