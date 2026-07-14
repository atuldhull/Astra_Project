"""Tests for the two crypto primitives the product's claims rest on:

  * app.services.provenance — Ed25519 per-detection signatures
  * app.services.audit      — SHA-256 audit hash chain

Both are exercised for real: a real keypair is generated into tmp_path, a real
signature is produced and verified, and the chain is built and re-walked
against a real (in-memory SQLite) database. Nothing here is mocked — a test
that mocks the signature would pass with the crypto ripped out.
"""

import dataclasses
import hashlib
import json

import pytest
from cryptography.exceptions import InvalidSignature
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, AuditEventType, Base
from app.services import provenance as prov
from app.services.audit import (
    GENESIS_HASH, _row_hash, latest_hash, log_event, verify_chain, verify_row,
)


# ── Fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def signer(tmp_path, monkeypatch):
    """Point provenance at a throwaway key directory and clear its caches, so
    each test generates and persists its own real Ed25519 key."""
    secrets = tmp_path / "secrets"
    monkeypatch.setattr(prov, "SECRETS_DIR", secrets)
    monkeypatch.setattr(prov, "KEY_FILE", secrets / "astra.ed25519")
    monkeypatch.setattr(prov, "ENABLED", True)
    monkeypatch.setattr(prov, "_signing_key", None)
    monkeypatch.setattr(prov, "_public_key_pem", None)
    monkeypatch.setattr(prov, "_fingerprint", None)
    return prov


@pytest.fixture
def db():
    """In-memory SQLite with the real ORM metadata."""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def _detection(**overrides) -> prov.DetectionFields:
    fields = {
        "mission_id": 7,
        "class_id": 2,
        "class_name": "aircraft-fixed-wing",
        "confidence": 0.8734,
        "x1": 100.5,
        "y1": 220.25,
        "x2": 340.0,
        "y2": 410.75,
        "image_sha256": "a" * 64,
        "model_hash": "b" * 64,
        "created_at_iso": "2026-04-28T11:04:57.143624+00:00",
    }
    fields.update(overrides)
    return prov.DetectionFields(**fields)


# ── Provenance: Ed25519 sign → verify ───────────────────────────────────

def test_sign_then_verify_round_trip(signer):
    d = _detection()

    sig = signer.sign_detection(d)
    assert sig, "signing produced no signature"

    result = signer.verify_detection(d, sig)
    assert result["ok"] is True
    assert result["fingerprint"] == signer.public_key_fingerprint()


def test_key_is_persisted_and_stable_across_reloads(signer, tmp_path):
    d = _detection()
    sig = signer.sign_detection(d)
    assert signer.KEY_FILE.exists()
    assert len(signer.KEY_FILE.read_bytes()) == 32

    fingerprint_before = signer.public_key_fingerprint()

    # Simulate a process restart: drop the cached key, reload from disk.
    signer._signing_key = None
    signer._fingerprint = None
    signer._public_key_pem = None

    assert signer.public_key_fingerprint() == fingerprint_before
    # A signature made before the "restart" still verifies under the reloaded key.
    assert signer.verify_detection(d, sig)["ok"] is True


@pytest.mark.parametrize(
    "field, tampered_value",
    [
        ("confidence", 0.99),                 # inflate the score
        ("class_id", 4),                      # aircraft -> ship
        ("class_name", "ship"),
        ("mission_id", 8),                    # re-attribute to another mission
        ("x1", 101.5),                        # nudge the box
        ("image_sha256", "c" * 64),           # swap the source image
        ("model_hash", "d" * 64),             # re-attribute to other weights
        ("created_at_iso", "2026-04-28T11:04:58.143624+00:00"),
    ],
)
def test_verify_fails_when_record_is_tampered_with(signer, field, tampered_value):
    original = _detection()
    sig = signer.sign_detection(original)
    assert signer.verify_detection(original, sig)["ok"] is True

    tampered = dataclasses.replace(original, **{field: tampered_value})

    result = signer.verify_detection(tampered, sig)
    assert result["ok"] is False
    assert result["reason"] == "signature mismatch"


def test_tampered_payload_raises_invalid_signature_at_the_primitive(signer):
    """The dict-returning wrapper swallows the exception — assert the underlying
    cryptography primitive really does reject the modified payload."""
    import base64

    original = _detection()
    sig = base64.b64decode(signer.sign_detection(original))
    tampered = dataclasses.replace(original, confidence=0.99)

    pub = signer.get_signing_key().public_key()
    pub.verify(sig, signer._canonical_bytes(original))  # the genuine payload verifies

    with pytest.raises(InvalidSignature):
        pub.verify(sig, signer._canonical_bytes(tampered))


def test_verify_rejects_a_signature_from_a_different_key(signer):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    d = _detection()
    attacker_sig = Ed25519PrivateKey.generate().sign(signer._canonical_bytes(d))

    import base64
    result = signer.verify_detection(d, base64.b64encode(attacker_sig).decode("ascii"))
    assert result["ok"] is False
    assert result["reason"] == "signature mismatch"


def test_garbage_signature_is_rejected_not_raised(signer):
    result = signer.verify_detection(_detection(), "!!!not-base64!!!")
    assert result["ok"] is False
    assert "decode" in result["reason"]


# ── Audit: hash chain ───────────────────────────────────────────────────

def test_genesis_hash_is_64_zeroes():
    assert GENESIS_HASH == "0" * 64
    assert len(GENESIS_HASH) == 64


def test_row_hash_is_sha256_of_prev_hash_then_canonical_fields():
    """Pin the preimage. verify_chain() recomputes hashes with the same function
    it signs them with, so a bug in _row_hash would verify happily against
    itself — only an independent recomputation catches that."""
    fields = {"event_type": "alert_confirmed", "operator_id": "op-1",
              "mission_id": 1, "alert_id": 2, "payload": {"seq": 0}}
    canonical = json.dumps(fields, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=True, default=str)

    expected = hashlib.sha256(
        GENESIS_HASH.encode("utf-8") + canonical.encode("utf-8")
    ).hexdigest()

    assert _row_hash(GENESIS_HASH, fields) == expected


def test_row_hash_depends_on_the_predecessor():
    """The property that makes this a *chain*: identical fields under a
    different predecessor must hash differently. Without it, editing one row
    would not invalidate any of its successors."""
    fields = {"event_type": "alert_confirmed", "operator_id": "op-1",
              "mission_id": 1, "alert_id": 2, "payload": {"seq": 0}}

    from_genesis = _row_hash(GENESIS_HASH, fields)
    from_other = _row_hash("f" * 64, fields)

    assert from_genesis != from_other
    assert _row_hash(GENESIS_HASH, fields) == from_genesis  # deterministic


def test_editing_an_early_row_invalidates_every_successor(db):
    """The whole point of chaining: a retroactive edit at row 1 must break the
    hash of every row after it, not just its own."""
    events = _append(db, 5)
    recomputed_before = [
        _row_hash(e.prev_hash, {
            "event_type": e.event_type.value, "operator_id": e.operator_id,
            "mission_id": e.mission_id, "alert_id": e.alert_id,
            "payload": e.payload_json,
        })
        for e in events
    ]
    assert recomputed_before == [e.row_hash for e in events]

    events[1].payload_json = {"seq": 1, "note": "edited"}
    db.commit()

    # Row 1's own hash no longer matches its stored value...
    tampered_hash = _row_hash(events[1].prev_hash, {
        "event_type": events[1].event_type.value,
        "operator_id": events[1].operator_id,
        "mission_id": events[1].mission_id,
        "alert_id": events[1].alert_id,
        "payload": events[1].payload_json,
    })
    assert tampered_hash != events[1].row_hash

    # ...and because each row folds in its predecessor, every later row's
    # recomputed hash diverges too once the chain is re-walked from the edit.
    prev = tampered_hash
    for e in events[2:]:
        recomputed = _row_hash(prev, {
            "event_type": e.event_type.value, "operator_id": e.operator_id,
            "mission_id": e.mission_id, "alert_id": e.alert_id,
            "payload": e.payload_json,
        })
        assert recomputed != e.row_hash, "successor hash must not survive an ancestor edit"
        prev = recomputed


def test_empty_chain_tip_is_genesis(db):
    assert latest_hash(db) == GENESIS_HASH
    assert verify_chain(db) == {
        "ok": True, "checked": 0, "broken_at_id": None,
        "genesis": GENESIS_HASH, "tip": GENESIS_HASH,
    }


def _append(db: Session, n: int) -> list[AuditEvent]:
    events = []
    for i in range(n):
        events.append(
            log_event(
                db,
                AuditEventType.ALERT_CONFIRMED,
                operator_id=f"op-{i % 3}",
                mission_id=1,
                alert_id=i + 1,
                payload={"seq": i, "note": f"confirm {i}"},
            )
        )
    db.commit()
    return events


def test_chain_of_n_entries_verifies_from_genesis(db):
    events = _append(db, 12)

    assert events[0].prev_hash == GENESIS_HASH
    for prev, cur in zip(events, events[1:]):
        assert cur.prev_hash == prev.row_hash, "each row must link to its predecessor"

    result = verify_chain(db)
    assert result["ok"] is True
    assert result["checked"] == 12
    assert result["broken_at_id"] is None
    assert result["genesis"] == GENESIS_HASH
    assert result["tip"] == events[-1].row_hash
    assert latest_hash(db) == events[-1].row_hash


def test_mutating_an_entry_in_the_middle_breaks_the_chain(db):
    events = _append(db, 9)
    assert verify_chain(db)["ok"] is True

    victim = events[4]           # middle of the chain
    victim_id = victim.id

    # Retroactively rewrite the payload, exactly what an insider would do —
    # leaving prev_hash/row_hash untouched so the row still *looks* linked.
    victim.payload_json = {"seq": 4, "note": "confirm 4", "reclassified": "false positive"}
    db.commit()

    result = verify_chain(db)
    assert result["ok"] is False
    assert result["broken_at_id"] == victim_id
    assert result["reason"] == "row_hash_mismatch"


def test_rewriting_a_row_hash_breaks_the_next_link(db):
    events = _append(db, 6)
    victim = events[2]

    # Recompute nothing — just forge the stored hash. The row itself now fails
    # its own hash check before we even reach the successor's prev_hash.
    victim.row_hash = "f" * 64
    db.commit()

    result = verify_chain(db)
    assert result["ok"] is False
    assert result["broken_at_id"] == victim.id


def test_deleting_a_row_breaks_the_chain(db):
    events = _append(db, 6)
    db.delete(events[3])
    db.commit()

    result = verify_chain(db)
    assert result["ok"] is False
    # The row after the hole still carries the deleted row's hash as its prev.
    assert result["broken_at_id"] == events[4].id
    assert result["reason"] == "prev_hash_mismatch"


def test_verify_row_walks_up_to_the_target(db):
    events = _append(db, 5)

    result = verify_row(db, events[2].id)
    assert result["ok"] is True
    assert result["row_hash"] == events[2].row_hash
    assert result["prev_hash"] == events[1].row_hash


def test_verify_row_reports_a_tampered_ancestor(db):
    events = _append(db, 5)
    events[1].payload_json = {"seq": 1, "note": "edited"}
    db.commit()

    result = verify_row(db, events[4].id)
    assert result["ok"] is False
    assert result["broken_at_id"] == events[1].id


def test_appending_after_verification_keeps_the_chain_intact(db):
    _append(db, 3)
    assert verify_chain(db)["checked"] == 3

    more = _append(db, 2)
    result = verify_chain(db)
    assert result["ok"] is True
    assert result["checked"] == 5
    assert result["tip"] == more[-1].row_hash
