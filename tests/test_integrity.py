"""Integrity layer tests. Real crypto, nothing mocked.

v3 lesson: a chain test that recomputes hashes with the same function that
wrote them passes even if that function is broken (e.g. stops folding in
prev_hash). So the preimage is pinned here independently with hashlib.
"""

import copy
import hashlib
import json

import pytest

from astra.integrity.canonical import canonical_bytes
from astra.integrity.ledger import GENESIS, Ledger, row_hash
from astra.integrity.signing import Signer, verify


# ── canonical JSON ──────────────────────────────────────────────────────

def test_canonical_is_order_independent_and_compact():
    assert canonical_bytes({"b": 1, "a": [1, 2]}) == b'{"a":[1,2],"b":1}'
    assert canonical_bytes({"a": 1, "b": 2}) == canonical_bytes({"b": 2, "a": 1})


def test_canonical_rejects_nan():
    with pytest.raises(ValueError):
        canonical_bytes({"x": float("nan")})


# ── signed envelopes ────────────────────────────────────────────────────

BODY = {"scenario": "drag-0.5", "seed": 3, "passed": False, "max_err_m": 41.25,
        "inputs": {"firmware_sha256": "a" * 64, "params_sha256": "b" * 64}}


def test_sign_verify_round_trip_with_trusted_key():
    s = Signer.generate()
    env = s.sign("run-report", BODY)
    r = verify(env, [s.fingerprint])
    assert r.valid and r.trusted and r.ok


def test_valid_signature_from_untrusted_key_is_not_ok():
    """Anyone can mint a key: validity without trust must not pass."""
    s = Signer.generate()
    r = verify(s.sign("run-report", BODY), trusted_fingerprints=[])
    assert r.valid and not r.trusted and not r.ok


@pytest.mark.parametrize("path, value", [
    (("body", "passed"), True),
    (("body", "max_err_m"), 1.0),
    (("body", "seed"), 4),
    (("body", "inputs", "params_sha256"), "c" * 64),
    (("kind",), "other"),
])
def test_any_tamper_breaks_signature(path, value):
    s = Signer.generate()
    env = copy.deepcopy(s.sign("run-report", BODY))
    target = env
    for k in path[:-1]:
        target = target[k]
    target[path[-1]] = value
    r = verify(env, [s.fingerprint])
    assert not r.valid and r.reason == "signature mismatch"


def test_swapping_in_attacker_key_is_caught_by_trust_check():
    victim, attacker = Signer.generate(), Signer.generate()
    forged = attacker.sign("run-report", {**BODY, "passed": True})
    r = verify(forged, [victim.fingerprint])
    assert r.valid and not r.trusted


def test_fingerprint_must_match_embedded_key():
    a, b = Signer.generate(), Signer.generate()
    env = a.sign("run-report", BODY)
    env["signer"]["fingerprint"] = b.fingerprint
    assert verify(env, [b.fingerprint]).reason == "fingerprint does not match public key"


def test_key_persists_across_reload(tmp_path):
    kf = tmp_path / "keys" / "astra.ed25519"
    s1 = Signer.load_or_create(kf)
    s2 = Signer.load_or_create(kf)
    assert kf.read_bytes() and len(kf.read_bytes()) == 32
    assert s1.fingerprint == s2.fingerprint
    assert verify(s1.sign("k", BODY), [s2.fingerprint]).ok


# ── ledger ──────────────────────────────────────────────────────────────

def test_row_hash_preimage_is_pinned_independently():
    data = {"x": 1}
    expected = hashlib.sha256(
        GENESIS.encode() + b'{"data":{"x":1},"event":"e","seq":0}'
    ).hexdigest()
    assert row_hash(GENESIS, 0, "e", data) == expected
    # and prev_hash really is part of the preimage
    assert row_hash("f" * 64, 0, "e", data) != expected


def _ledger(tmp_path, n=5):
    lg = Ledger(tmp_path / "ledger.jsonl")
    for i in range(n):
        lg.append("run", {"i": i})
    return lg


def test_clean_chain_verifies(tmp_path):
    lg = _ledger(tmp_path)
    c = lg.verify()
    assert c.ok and c.rows == 5 and c.tip == lg.tip()[1]


def _rewrite(lg, fn):
    rows = [json.loads(x) for x in lg.path.read_text().splitlines()]
    rows = fn(rows)
    lg.path.write_text("".join(json.dumps(r) + "\n" for r in rows))


def test_editing_a_row_breaks_chain(tmp_path):
    lg = _ledger(tmp_path)
    _rewrite(lg, lambda rs: [*rs[:2], {**rs[2], "data": {"i": 99}}, *rs[3:]])
    c = lg.verify()
    assert not c.ok and c.broken_at == 2 and c.reason == "row_hash mismatch"


def test_deleting_a_row_breaks_chain(tmp_path):
    lg = _ledger(tmp_path)
    _rewrite(lg, lambda rs: rs[:2] + rs[3:])
    assert not lg.verify().ok


def test_reordering_rows_breaks_chain(tmp_path):
    lg = _ledger(tmp_path)
    _rewrite(lg, lambda rs: [rs[1], rs[0], *rs[2:]])
    assert not lg.verify().ok


def test_rehashing_an_edited_row_still_breaks_the_next_row(tmp_path):
    """An editor who recomputes the edited row's own hash is still caught by the next link."""
    lg = _ledger(tmp_path)

    def edit(rs):
        r = rs[2]
        r["data"] = {"i": 99}
        r["hash"] = row_hash(r["prev"], r["seq"], r["event"], r["data"])
        return rs

    _rewrite(lg, edit)
    c = lg.verify()
    assert not c.ok and c.broken_at == 3


def test_full_rewrite_from_genesis_changes_tip(tmp_path):
    """Documents the known limit: a full rewrite verifies locally, so the tip must be anchored externally."""
    lg = _ledger(tmp_path)
    original_tip = lg.tip()[1]
    lg.path.unlink()
    for i in range(5):
        lg.append("run", {"i": i if i != 2 else 99})
    assert lg.verify().ok
    assert lg.tip()[1] != original_tip
