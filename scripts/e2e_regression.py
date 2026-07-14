"""
End-to-end smoke test for ASTRA Round 2.

Hits every backend endpoint that drives a demo moment, in sequence,
printing a per-feature PASS/FAIL line. Run this in a separate terminal
right before a demo to catch regressions.

Usage (with backend running on 127.0.0.1:8000 and a demo image at
$ASTRA_DATA_DIR/demo-samples/02-airfield-hero.jpg):

    python scripts/e2e_regression.py
    python scripts/e2e_regression.py --base http://127.0.0.1:8000 --image $ASTRA_DATA_DIR/demo-samples/02-airfield-hero.jpg

Exit code:  0 = all green, 1 = any failure.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from astra_paths import DEMO_SAMPLES_DIR  # noqa: E402


PASS = "[ ok ]"
FAIL = "[FAIL]"
SKIP = "[skip]"


def _rule(text: str = "") -> None:
    if text:
        print(f"\n=== {text} ===")
    else:
        print("-" * 60)


def _check(label: str, ok: bool, detail: str = "") -> bool:
    tag = PASS if ok else FAIL
    sep = "  " if detail else ""
    print(f"  {tag} {label}{sep}{detail}")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--image", type=Path, default=DEMO_SAMPLES_DIR / "02-airfield-hero.jpg")
    ap.add_argument("--mission-name", default="E2E-REGRESSION")
    args = ap.parse_args()

    if not args.image.exists():
        print(f"FATAL: demo image not found at {args.image}")
        return 2

    fails = 0
    client = httpx.Client(base_url=args.base, timeout=120.0)

    # ── 1. /health ──────────────────────────────────────────────────────
    _rule("1. backend health")
    try:
        r = client.get("/health"); r.raise_for_status()
        h = r.json()
        if not _check(f"GET /health  device={h.get('device')}  model_loaded={h.get('model_loaded')}", h.get("status") == "ok"):
            fails += 1
    except Exception as exc:
        _check("GET /health", False, str(exc)); fails += 1
        print("\nbackend appears down — bailing"); return 1

    # ── 2. Adversarial variants probe ───────────────────────────────────
    _rule("2. adversarial variants (A/B model picker)")
    try:
        v = client.get("/api/v1/adversarial/variants").json()
        loaded = {x["variant"]: x["loaded"] for x in v.get("variants", [])}
        _check(f"v1 weights loaded (loaded={loaded.get('v1')})", loaded.get("v1") is True) or (fails := fails + 1)
        if loaded.get("v1-hardened"):
            _check("v1-hardened weights loaded", True)
        else:
            print(f"  {SKIP} v1-hardened not on disk (run training/adversarial_augment.py + train.py + cp to enable)")
    except Exception as exc:
        _check("variants endpoint", False, str(exc)); fails += 1

    # ── 3. Ingest + cascade + OOD ───────────────────────────────────────
    _rule("3. ingest pipeline (cascade + OOD + WS broadcast)")
    mission_id = None
    try:
        with args.image.open("rb") as f:
            r = client.post(
                "/api/v1/ingest",
                data={"name": args.mission_name},
                files={"file": (args.image.name, f, "image/jpeg")},
            )
        r.raise_for_status()
        m = r.json()
        mission_id = m["id"]
        _check(f"ingest -> Mission #{mission_id}  aoi_source={m.get('aoi_source')}", True)
    except Exception as exc:
        _check("ingest", False, str(exc)); fails += 1; return 1

    # Poll detections.
    detections: list = []
    deadline = time.time() + 90
    while time.time() < deadline:
        d = client.get(f"/api/v1/detections", params={"mission_id": mission_id, "limit": 500}).json()
        if d:
            detections = d
            break
        time.sleep(1.5)
    if not _check(f"pipeline produced {len(detections)} detections", len(detections) > 0):
        fails += 1
    cascaded = [d for d in detections if d.get("extras", {}).get("airframe")]
    if not _check(f"MAR20 cascade fired on {len(cascaded)}/{len(detections)} aircraft",
                  any(d["class_name"] == "aircraft-fixed-wing" for d in detections) and len(cascaded) > 0):
        fails += 1
    if cascaded:
        ex = cascaded[0]["extras"]
        _check(f"sample airframe: {ex.get('airframe')} @ {ex.get('airframe_confidence')}", True)
    flagged = [d for d in detections if d.get("extras", {}).get("ood_flag")]
    _check(f"OOD gatekeeper assessed {len(detections)} dets, flagged {len(flagged)} as unknown", True)

    # ── 4. Tracks / alerts ──────────────────────────────────────────────
    _rule("4. alerts pipeline")
    alerts = client.get("/api/v1/alerts", params={"mission_id": mission_id, "limit": 200}).json()
    _check(f"alerts count = {len(alerts)}", len(alerts) > 0) or (fails := fails + 1)
    narrated = sum(1 for a in alerts if a.get("narrative"))
    _check(f"alerts with narrative: {narrated}/{len(alerts)}", narrated == len(alerts)) or (fails := fails + 1)

    # ── 5. Adversarial FGSM A/B ─────────────────────────────────────────
    _rule("5. adversarial FGSM A/B")
    for variant in ("v1", "v1-hardened"):
        # Skip if variant not loaded
        var_info = client.get("/api/v1/adversarial/variants").json()["variants"]
        if not next((v for v in var_info if v["variant"] == variant), {}).get("loaded"):
            print(f"  {SKIP} variant {variant} weights not on disk")
            continue
        with args.image.open("rb") as f:
            r = client.post(
                "/api/v1/adversarial",
                data={"epsilon": 0.05, "method": "fgsm", "model_variant": variant},
                files={"file": (args.image.name, f, "image/jpeg")},
            )
        if r.status_code != 200:
            _check(f"adversarial {variant}", False, r.text[:120]); fails += 1; continue
        d = r.json()
        meth = d.get("method_used")
        ret = d.get("retention", 0.0)
        orig = d.get("original", {}).get("detection_count")
        pert = d.get("perturbed", {}).get("detection_count")
        ok = (meth == "fgsm")
        _check(f"{variant:13s}  method={meth:14s}  dets {orig}->{pert}  retention={ret*100:.0f}%", ok) or (fails := fails + 1)

    # ── 6. Diff endpoint ────────────────────────────────────────────────
    _rule("6. mission diff")
    missions = client.get("/api/v1/ingest", params={"limit": 50}).json()
    if len(missions) < 2:
        print(f"  {SKIP} need 2+ missions to diff (have {len(missions)})")
    else:
        m_new, m_old = missions[0], missions[1]
        try:
            d = client.post("/api/v1/diff", json={
                "earlier_mission_id": m_old["id"],
                "later_mission_id": m_new["id"],
                "match_radius_m": 50,
                "move_threshold_m": 15,
            }).json()
            _check(f"diff #{m_old['id']} -> #{m_new['id']}: {d.get('summary_text')}", True)
        except Exception as exc:
            _check("diff", False, str(exc)); fails += 1

    # ── 7. Dual-control engage flow ─────────────────────────────────────
    _rule("7. dual-control engage workflow")
    pending = [a for a in alerts if a.get("status") == "pending"]
    if not pending:
        print(f"  {SKIP} no pending alerts to escalate (try a fresh ingest)")
    else:
        target = pending[0]["id"]
        # escalate
        r = client.patch(f"/api/v1/alerts/{target}", json={"action": "escalate", "operator_id": "e2e-cmdr-01"}).json()
        _check(f"escalate alert #{target} -> {r.get('status')}", r.get("status") == "escalated") or (fails := fails + 1)
        # first engage
        r = client.patch(f"/api/v1/alerts/{target}", json={"action": "engage", "operator_id": "e2e-cmdr-01", "reason": "e2e first"}).json()
        _check(f"first engage by cmdr-01 (still escalated, 1/2)", r.get("status") == "escalated" and len(r.get("confirmations", [])) == 1) or (fails := fails + 1)
        # duplicate (should 409)
        rsp = client.patch(f"/api/v1/alerts/{target}", json={"action": "engage", "operator_id": "e2e-cmdr-01"})
        _check(f"duplicate cmdr-01 attempt blocked (HTTP {rsp.status_code})", rsp.status_code == 409) or (fails := fails + 1)
        # second engage by different op -> ENGAGED
        r = client.patch(f"/api/v1/alerts/{target}", json={"action": "engage", "operator_id": "e2e-cmdr-02", "reason": "e2e second"}).json()
        _check(f"second engage by cmdr-02 -> {r.get('status')}", r.get("status") == "engaged") or (fails := fails + 1)

    # ── 8. Audit chain verification ─────────────────────────────────────
    _rule("8. tamper-evident audit chain")
    try:
        v = client.get("/api/v1/audit/verify").json()
        ok = v.get("ok", False)
        _check(f"chain integrity: {v.get('checked')} rows verified, ok={ok}", ok) or (fails := fails + 1)
        if not ok:
            print(f"      broken at row #{v.get('broken_at_id')}: {v.get('reason')}")
    except Exception as exc:
        _check("audit verify", False, str(exc)); fails += 1

    # ── 9. Federated state ──────────────────────────────────────────────
    _rule("9. federated dashboard state")
    try:
        f = client.get("/api/v1/federated").json()
        if not f.get("available"):
            print(f"  {SKIP} no federated run on disk yet — run `python -m federated.run_demo --task synthetic --rounds 5 --inject-poison`")
        else:
            cfg = f.get("config", {})
            _check(f"federated config: task={cfg.get('task')}  clients={len(cfg.get('client_ids',[]))}", True)
            _check(f"global curve has {len(f.get('global_curve',[]))} points", len(f.get('global_curve', [])) > 0) or (fails := fails + 1)
            _check(f"foolsgold rounds: {len(f.get('foolsgold',[]))}", len(f.get('foolsgold', [])) > 0) or (fails := fails + 1)
    except Exception as exc:
        _check("federated state", False, str(exc)); fails += 1

    # ── 10. Telegram notifier ───────────────────────────────────────────
    _rule("10. telegram notifier (optional)")
    # Telegram can't be tested via API since it's pipeline-internal. Probe
    # via env var presence — informational only.
    import os
    have_token = bool(os.environ.get("TELEGRAM_BOT_TOKEN"))
    have_chat = bool(os.environ.get("TELEGRAM_CHAT_ID"))
    if have_token and have_chat:
        print(f"  {PASS} TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID set — pipeline will notify above threshold")
    else:
        print(f"  {SKIP} TELEGRAM_BOT_TOKEN/CHAT_ID not set in env — notifier silently no-ops (this is fine)")

    # ── Summary ─────────────────────────────────────────────────────────
    _rule()
    if fails == 0:
        print(f"ALL GREEN — Round 2 features verified.")
        return 0
    print(f"{fails} FAILURE(S) — see above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
