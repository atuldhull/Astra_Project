"""Ed25519 signed envelopes.

Fixes the v3 design flaws:
  * Verification needs only the public key, never the private key, so an
    evaluator can verify offline on their own machine.
  * A valid signature alone proves nothing (anyone can mint a key). `verify`
    therefore reports whether the signing key is in the caller's trusted set.
  * The envelope binds the result to its inputs (firmware, params, scenario
    pack and seed hashes), so a result can't be re-attributed.

Envelope format (v1):
    {
      "astra_envelope": 1,
      "kind": "run-report" | ...,
      "body": {...},                        # what is attested
      "signer": {"alg": "ed25519", "public_key": <b64 raw 32B>, "fingerprint": <sha256 hex>},
      "signature": <b64>                    # over canonical({"astra_envelope","kind","body","signer"})
    }
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from astra.integrity.canonical import canonical_bytes, sha256_hex

ENVELOPE_VERSION = 1


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def _unb64(s: str) -> bytes:
    return base64.b64decode(s.encode("ascii"), validate=True)


def fingerprint_of(public_raw: bytes) -> str:
    return sha256_hex(public_raw)


@dataclass(frozen=True)
class Signer:
    key: Ed25519PrivateKey

    @property
    def public_raw(self) -> bytes:
        return self.key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )

    @property
    def fingerprint(self) -> str:
        return fingerprint_of(self.public_raw)

    @classmethod
    def generate(cls) -> "Signer":
        return cls(Ed25519PrivateKey.generate())

    @classmethod
    def load_or_create(cls, key_file: str | Path) -> "Signer":
        """Load a raw 32-byte key, or create one (0600 where the OS supports it)."""
        p = Path(key_file)
        if p.exists():
            raw = p.read_bytes()
            if len(raw) != 32:
                raise ValueError(f"{p} is not a raw 32-byte Ed25519 key ({len(raw)} bytes)")
            return cls(Ed25519PrivateKey.from_private_bytes(raw))
        p.parent.mkdir(parents=True, exist_ok=True)
        signer = cls.generate()
        raw = signer.key.private_bytes(
            serialization.Encoding.Raw,
            serialization.PrivateFormat.Raw,
            serialization.NoEncryption(),
        )
        tmp = p.with_suffix(p.suffix + ".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
        tmp.replace(p)
        return signer

    def sign(self, kind: str, body: dict[str, Any]) -> dict[str, Any]:
        unsigned = {
            "astra_envelope": ENVELOPE_VERSION,
            "kind": kind,
            "body": body,
            "signer": {
                "alg": "ed25519",
                "public_key": _b64(self.public_raw),
                "fingerprint": self.fingerprint,
            },
        }
        sig = self.key.sign(canonical_bytes(unsigned))
        return {**unsigned, "signature": _b64(sig)}


@dataclass(frozen=True)
class VerifyResult:
    valid: bool  # signature cryptographically valid for the embedded key
    trusted: bool  # embedded key is in the caller's trusted fingerprint set
    fingerprint: str | None
    reason: str

    @property
    def ok(self) -> bool:
        return self.valid and self.trusted


def verify(envelope: dict[str, Any], trusted_fingerprints: Iterable[str] = ()) -> VerifyResult:
    try:
        if envelope.get("astra_envelope") != ENVELOPE_VERSION:
            return VerifyResult(False, False, None, "unsupported envelope version")
        signer = envelope["signer"]
        if signer.get("alg") != "ed25519":
            return VerifyResult(False, False, None, "unsupported algorithm")
        public_raw = _unb64(signer["public_key"])
        fp = fingerprint_of(public_raw)
        if fp != signer.get("fingerprint"):
            return VerifyResult(False, False, fp, "fingerprint does not match public key")
        unsigned = {k: envelope[k] for k in ("astra_envelope", "kind", "body", "signer")}
        Ed25519PublicKey.from_public_bytes(public_raw).verify(
            _unb64(envelope["signature"]), canonical_bytes(unsigned)
        )
    except InvalidSignature:
        return VerifyResult(False, False, None, "signature mismatch")
    except (KeyError, TypeError, ValueError) as exc:
        return VerifyResult(False, False, None, f"malformed envelope: {exc}")
    trusted = fp in set(trusted_fingerprints)
    return VerifyResult(True, trusted, fp, "ok" if trusted else "valid signature from an untrusted key")
