"""
ASTRA Mesh — cross-agency audit witnessing (T D3.4).

Architecture:
  * We expose a read-only audit feed (auth-gated).
  * Peer agencies pull our chain, locally re-walk SHA-256 from genesis
    using the SAME _row_hash primitive we use, and post Ed25519
    signatures over (peer_id || audit_row_id || row_hash).
  * Tampering on our side breaks the local re-walk — peers refuse to
    witness a row whose hash they can't reproduce, so a tampered row
    stays at "0/2" while the rest fill up to "2/2".

For the demo we stand up two synthetic peers in-process ("peer-IB" and
"peer-NIA") with their own Ed25519 keypairs persisted in
PEER_KEYS_DIR. In production each peer BYOs a key and the synthetic
loop becomes the peer's own cron job hitting the same endpoints.

PEER_KEYS_DIR layout ($ASTRA_DATA_DIR/secrets/mesh_peers/):
      peer-IB.ed25519       (32-byte raw private key)
      peer-IB.pub.pem       (PEM-encoded public key, optional)
      peer-NIA.ed25519
      peer-NIA.pub.pem

Honest framing: this is mathematically equivalent to anchoring the
chain tip externally — but at every row, not just every N. No
consensus, no token, no chain fork — just append-only co-witnessing.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey,
)
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

from app.config import SECRETS_DIR


PEER_KEYS_DIR = Path(os.environ.get("ASTRA_MESH_PEERS_DIR") or SECRETS_DIR / "mesh_peers")

# The two synthetic demo peers. Each gets a real Ed25519 keypair on
# first boot — these are not mocked.
DEMO_PEERS = ("peer-IB", "peer-NIA")

_lock = threading.Lock()
_priv_cache: dict[str, Ed25519PrivateKey] = {}
_pub_cache: dict[str, Ed25519PublicKey] = {}


# ── Key management ────────────────────────────────────────────────────

def _priv_path(peer_id: str) -> Path:
    return PEER_KEYS_DIR / f"{peer_id}.ed25519"


def _pub_path(peer_id: str) -> Path:
    return PEER_KEYS_DIR / f"{peer_id}.pub.pem"


def _ensure_peer(peer_id: str) -> Ed25519PrivateKey:
    """Load (or first-boot generate) a peer's keypair. Persists the public
    PEM alongside for easy export."""
    with _lock:
        if peer_id in _priv_cache:
            return _priv_cache[peer_id]
        PEER_KEYS_DIR.mkdir(parents=True, exist_ok=True)
        priv_p = _priv_path(peer_id)
        if priv_p.exists():
            raw = priv_p.read_bytes()
            if len(raw) != 32:
                raise RuntimeError(f"peer {peer_id} key file is not 32 bytes")
            priv = Ed25519PrivateKey.from_private_bytes(raw)
        else:
            priv = Ed25519PrivateKey.generate()
            tmp = priv_p.with_suffix(".ed25519.tmp")
            tmp.write_bytes(priv.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption(),
            ))
            tmp.replace(priv_p)
            # Also write the public PEM for convenience.
            pub_pem = priv.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            _pub_path(peer_id).write_bytes(pub_pem)
        _priv_cache[peer_id] = priv
        _pub_cache[peer_id] = priv.public_key()
        return priv


def public_pem(peer_id: str) -> str:
    """Return the peer's public key in PEM. Lazy-creates the keypair."""
    _ensure_peer(peer_id)
    pub = _pub_cache[peer_id]
    return pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")


def list_peers() -> list[dict]:
    """Returns metadata for every demo peer (lazy-creates keys)."""
    out = []
    for pid in DEMO_PEERS:
        _ensure_peer(pid)
        out.append({
            "peer_id": pid,
            "key_present": _priv_path(pid).exists(),
            "public_key_pem": public_pem(pid),
        })
    return out


# ── Witness payload canonicalization ─────────────────────────────────

def _witness_payload_bytes(peer_id: str, audit_row_id: int, row_hash: str) -> bytes:
    """Stable encoding for what each peer signs over.

    Format: peer_id || ":" || audit_row_id || ":" || row_hash, UTF-8.
    Simple, append-resistant, and trivial for an external client to
    reproduce in any language.
    """
    return f"{peer_id}:{audit_row_id}:{row_hash}".encode("utf-8")


def sign_as_peer(peer_id: str, audit_row_id: int, row_hash: str) -> str:
    """Return a base64 Ed25519 signature for the witness payload."""
    import base64
    priv = _ensure_peer(peer_id)
    sig = priv.sign(_witness_payload_bytes(peer_id, audit_row_id, row_hash))
    return base64.b64encode(sig).decode("ascii")


def verify_peer_signature(peer_id: str, audit_row_id: int, row_hash: str, sig_b64: str) -> bool:
    """Verify a witness signature posted by a peer. False on any error."""
    import base64
    _ensure_peer(peer_id)
    try:
        sig = base64.b64decode(sig_b64.encode("ascii"))
        _pub_cache[peer_id].verify(sig, _witness_payload_bytes(peer_id, audit_row_id, row_hash))
        return True
    except InvalidSignature:
        return False
    except Exception:
        return False


# ── Peer-side chain re-walk (the demo client) ────────────────────────

@dataclass
class PeerVerifyResult:
    audit_row_id: int
    row_hash: str
    chain_ok: bool   # did our local re-walk reproduce this row's hash?
    reason: str | None = None


def peer_walk_and_verify(rows: list) -> list[PeerVerifyResult]:
    """Simulates a peer agency pulling the feed and re-walking the chain
    locally. Each peer reproduces the same _row_hash() primitive — so a
    server-side tampered row will fail to reproduce and the peer refuses
    to witness it.

    Input `rows` is the ordered list of AuditEvent ORM rows (ascending id).
    Returns one PeerVerifyResult per row.
    """
    from app.services.audit import GENESIS_HASH, _row_hash
    out: list[PeerVerifyResult] = []
    prev = GENESIS_HASH
    for r in rows:
        fields = {
            "event_type": r.event_type.value if hasattr(r.event_type, "value") else str(r.event_type),
            "operator_id": r.operator_id,
            "mission_id": r.mission_id,
            "alert_id": r.alert_id,
            "payload": r.payload_json,
        }
        expected = _row_hash(prev, fields)
        if r.row_hash and r.row_hash != expected:
            out.append(PeerVerifyResult(
                audit_row_id=r.id,
                row_hash=r.row_hash,
                chain_ok=False,
                reason="row_hash_mismatch",
            ))
            # Continue but use the row's stored hash so subsequent rows
            # still chain — peers don't refuse to witness GOOD rows just
            # because there was a bad one earlier; they refuse the bad
            # one specifically.
            prev = r.row_hash
            continue
        if r.prev_hash and r.prev_hash != prev:
            out.append(PeerVerifyResult(
                audit_row_id=r.id,
                row_hash=r.row_hash or expected,
                chain_ok=False,
                reason="prev_hash_mismatch",
            ))
            prev = r.row_hash or expected
            continue
        out.append(PeerVerifyResult(
            audit_row_id=r.id,
            row_hash=r.row_hash or expected,
            chain_ok=True,
        ))
        prev = r.row_hash or expected
    return out


# ── Status ───────────────────────────────────────────────────────────

def status() -> dict:
    return {
        "peers_dir": str(PEER_KEYS_DIR),
        "n_peers": len(DEMO_PEERS),
        "peer_ids": list(DEMO_PEERS),
    }
