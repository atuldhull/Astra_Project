"""
Provenance signatures — Ed25519 per-detection signatures.

Every Detection row is cryptographically signed by ASTRA's server key
at commit time. The signature covers a canonical serialization of:

    model_hash || image_sha256 || mission_id || class_id ||
    confidence || (x1, y1, x2, y2) || created_at

Downstream consumers (chain anchor, exported PDF reports, federation
peers) verify against the published public key, proving:
  1. The detection came from the genuine ASTRA model + pipeline.
  2. The values haven't been tampered with after the fact.

Key lifecycle:
  * Generated on first call to `get_signing_key()` if absent.
  * Persisted at SECRETS_DIR/astra.ed25519 (gitignored).
  * 32-byte raw Ed25519 private key. Public key derived on demand.

The signing path is async-friendly (pure-Python crypto, no GIL contention)
but deliberately NOT inside the ingest critical path — pipeline.py calls
`sign_detection()` after the DB commit, so a signing error never blocks
ingest. Failures fall through with a logged warning; downstream verify
will simply return `signed: false`.

Feature flag: ASTRA_PROVENANCE_ENABLED (default on). When off:
  - new detections written with signature_b64=NULL
  - verify endpoint returns {available: false, reason: "disabled"}
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import threading
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey,
)
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

from app.config import SECRETS_DIR as _DEFAULT_SECRETS_DIR
from app.config import settings

log = logging.getLogger("astra.provenance")


# ── Configuration ──────────────────────────────────────────────────────

SECRETS_DIR = Path(os.environ.get("ASTRA_SECRETS_DIR") or _DEFAULT_SECRETS_DIR)
KEY_FILE = SECRETS_DIR / "astra.ed25519"
ENABLED = os.environ.get("ASTRA_PROVENANCE_ENABLED", "true").lower() != "false"

_lock = threading.Lock()
_signing_key: Ed25519PrivateKey | None = None
_public_key_pem: str | None = None
_fingerprint: str | None = None


# ── Key management ─────────────────────────────────────────────────────

def get_signing_key() -> Ed25519PrivateKey:
    """Load (or first-boot generate) the server's Ed25519 signing key."""
    global _signing_key
    if _signing_key is not None:
        return _signing_key
    with _lock:
        if _signing_key is not None:
            return _signing_key
        SECRETS_DIR.mkdir(parents=True, exist_ok=True)
        if KEY_FILE.exists():
            raw = KEY_FILE.read_bytes()
            if len(raw) != 32:
                raise RuntimeError(
                    f"key file {KEY_FILE} is not a 32-byte raw Ed25519 key "
                    f"(got {len(raw)} bytes). Refusing to overwrite — investigate manually."
                )
            _signing_key = Ed25519PrivateKey.from_private_bytes(raw)
            log.info("provenance: loaded signing key from %s", KEY_FILE)
        else:
            _signing_key = Ed25519PrivateKey.generate()
            raw = _signing_key.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption(),
            )
            # Write atomically: tmp file + rename
            tmp = KEY_FILE.with_suffix(".ed25519.tmp")
            tmp.write_bytes(raw)
            tmp.replace(KEY_FILE)
            log.info("provenance: generated new signing key at %s", KEY_FILE)
        return _signing_key


def public_key_pem() -> str:
    """Return the public key in PEM format (cached)."""
    global _public_key_pem
    if _public_key_pem is not None:
        return _public_key_pem
    pub: Ed25519PublicKey = get_signing_key().public_key()
    pem = pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    _public_key_pem = pem
    return pem


def public_key_fingerprint() -> str:
    """SHA-256 fingerprint of the public key, hex-encoded.

    Stable across restarts (key is persisted), short enough to display
    in the UI footer for visual identity verification.
    """
    global _fingerprint
    if _fingerprint is not None:
        return _fingerprint
    pub: Ed25519PublicKey = get_signing_key().public_key()
    raw = pub.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    _fingerprint = hashlib.sha256(raw).hexdigest()
    return _fingerprint


# ── Canonical payload ──────────────────────────────────────────────────

@dataclass(frozen=True)
class DetectionFields:
    """Subset of Detection fields covered by the signature."""
    mission_id: int
    class_id: int
    class_name: str
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float
    image_sha256: str
    model_hash: str
    created_at_iso: str


def _canonical_bytes(d: DetectionFields) -> bytes:
    """Stable serialization. JSON with sorted keys + no whitespace.

    Includes a version tag so future field additions can be migrated
    without breaking historical signatures.
    """
    payload = {
        "v": 1,
        "mission_id": d.mission_id,
        "class_id": d.class_id,
        "class_name": d.class_name,
        "confidence": round(float(d.confidence), 6),
        "bbox": [
            round(float(d.x1), 4), round(float(d.y1), 4),
            round(float(d.x2), 4), round(float(d.y2), 4),
        ],
        "image_sha256": d.image_sha256,
        "model_hash": d.model_hash,
        "created_at": d.created_at_iso,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


# ── Signing + verifying ────────────────────────────────────────────────

def sign_detection(d: DetectionFields) -> str | None:
    """Return base64-encoded Ed25519 signature, or None if provenance is
    disabled or signing fails. Never raises."""
    if not ENABLED:
        return None
    try:
        key = get_signing_key()
        sig = key.sign(_canonical_bytes(d))
        return base64.b64encode(sig).decode("ascii")
    except Exception as exc:  # noqa: BLE001 — never break ingest
        log.warning("provenance: sign failed: %s", exc)
        return None


def verify_detection(d: DetectionFields, signature_b64: str) -> dict:
    """Verify a detection's signature. Returns {ok, reason?, fingerprint}."""
    if not ENABLED:
        return {"ok": False, "reason": "provenance disabled"}
    try:
        sig = base64.b64decode(signature_b64.encode("ascii"))
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"signature decode: {exc}"}
    pub: Ed25519PublicKey = get_signing_key().public_key()
    try:
        pub.verify(sig, _canonical_bytes(d))
        return {"ok": True, "fingerprint": public_key_fingerprint()}
    except InvalidSignature:
        return {"ok": False, "reason": "signature mismatch"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"verify error: {exc}"}


# ── Hash helpers ───────────────────────────────────────────────────────

def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def model_hash() -> str:
    """SHA-256 of the production detector weights file. Cached.

    Pinning the model identity into every signature means a detection
    signed under v1 weights cannot be silently re-attributed to v1-hardened
    weights — they have different model_hash values.
    """
    global _model_hash_cache
    try:
        return _model_hash_cache  # type: ignore[name-defined]
    except NameError:
        pass
    weights_path = Path(os.environ.get("ASTRA_DETECTOR_WEIGHTS") or settings.model_path)
    if not weights_path.exists():
        digest = "weights-missing"
    else:
        h = hashlib.sha256()
        with weights_path.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        digest = h.hexdigest()
    _model_hash_cache = digest  # noqa: F841
    return digest


_model_hash_cache: str  # for the typing-aware cache hack above


# ── Public status ──────────────────────────────────────────────────────

def status() -> dict:
    """Used by /api/v1/provenance/key to render the UI badge."""
    return {
        "enabled": ENABLED,
        "key_file": str(KEY_FILE),
        "key_present": KEY_FILE.exists(),
        "fingerprint": public_key_fingerprint() if ENABLED and KEY_FILE.exists() else None,
        "public_key_pem": public_key_pem() if ENABLED and KEY_FILE.exists() else None,
        "model_hash": model_hash() if ENABLED else None,
    }
