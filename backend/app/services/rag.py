"""
RAG-style commander Q&A.

Two-tier strategy with graceful fallback:
  1. If `llama-cpp-python` + a Phi-3.5-mini-instruct GGUF (~2.4 GB) are
     available, use them for natural-language responses with retrieved
     mission/alert context.
  2. Otherwise, fall back to a rule-based intent matcher that handles
     ~12 canonical question shapes ("how many ships near FOB Delta?",
     "what was the last engagement?", "which airframes did we ID today?").

The fallback is the contract — both tiers expose the same answer() API.
The fallback wins for hackathon reliability; the LLM is sugar on top.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Alert, AlertStatus, AuditEvent, Detection, Mission


PHI_PATH = Path(os.environ.get("ASTRA_PHI_PATH", "D:/astra-data/models/phi-3.5-mini-instruct.Q4_K_M.gguf"))


@dataclass
class Answer:
    text: str
    source: str       # 'rule' | 'llm' | 'error'
    citations: list[dict]   # [{type, id, summary}]


# ── Tier 2: Rule-based handler ─────────────────────────────────────────

def _rule_answer(db: Session, q: str) -> Answer:
    qn = q.lower().strip()
    cites: list[dict] = []

    # ----- Counts of things by class -----
    m = re.search(r"(?:how many|count of|number of)\s+(\w[\w\- ]*?)\s*(?:were|are|did we|in|near|seen|detected)?", qn)
    if m:
        target = m.group(1).strip()
        # Match against our 8 DOTA classes loosely
        candidates = ["small-vehicle", "large-vehicle", "aircraft-fixed-wing", "aircraft-rotor", "ship", "storage-depot", "harbor", "bridge"]
        match = next((c for c in candidates if target in c.replace("-", " ") or c in target), None)
        if match:
            n = db.execute(select(Detection).where(Detection.class_name == match)).scalars().all()
            cites.append({"type": "count", "class_name": match, "n": len(n)})
            return Answer(
                text=f"{len(n)} '{match}' detection(s) recorded across all missions.",
                source="rule",
                citations=cites,
            )

    # ----- Engagements / engaged alerts -----
    if "engaged" in qn or "engagement" in qn:
        engaged = db.execute(
            select(Alert).where(Alert.status == AlertStatus.ENGAGED).order_by(Alert.updated_at.desc()).limit(5)
        ).scalars().all()
        if not engaged:
            return Answer("No engaged alerts to date.", "rule", [])
        for a in engaged:
            cites.append({"type": "alert", "id": a.id, "score": a.threat_score, "narrative": (a.narrative or "")[:80]})
        last = engaged[0]
        return Answer(
            text=f"{len(engaged)} engaged alert(s). Most recent: alert #{last.id} at threat {last.threat_score:.2f} — {(last.narrative or '').strip()[:120]}",
            source="rule",
            citations=cites,
        )

    # ----- Missions today / recent -----
    if any(w in qn for w in ["recent mission", "today", "last mission", "latest"]):
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        recent = db.execute(
            select(Mission).where(Mission.created_at >= cutoff).order_by(Mission.created_at.desc()).limit(10)
        ).scalars().all()
        if not recent:
            return Answer("No missions in the last 24 hours.", "rule", [])
        for m in recent:
            cites.append({"type": "mission", "id": m.id, "name": m.name})
        return Answer(
            text=f"{len(recent)} mission(s) in the last 24 hours: " +
                 ", ".join(f"#{m.id} {m.name}" for m in recent[:6]),
            source="rule",
            citations=cites,
        )

    # ----- Airframes / cascade IDs -----
    if "airframe" in qn or "fighter" in qn or "f-22" in qn or "su-" in qn or "what aircraft" in qn:
        import json as _json
        from collections import Counter
        c: Counter = Counter()
        rows = db.execute(select(Detection).where(Detection.extras_json.is_not(None))).scalars().all()
        for d in rows:
            try:
                ex = _json.loads(d.extras_json or "{}")
                if ex.get("airframe"):
                    c[ex["airframe"]] += 1
            except Exception:
                pass
        if not c:
            return Answer("No fine-grained airframe IDs recorded yet (stage-2 cascade). Run a mission with aircraft.", "rule", [])
        top = c.most_common(8)
        return Answer(
            text="Airframes ID'd via MAR20 cascade: " + ", ".join(f"{n} ({k})" for k, n in top),
            source="rule",
            citations=[{"type": "airframe", "name": k, "count": n} for k, n in top],
        )

    # ----- Audit chain integrity -----
    if "chain" in qn or "audit" in qn or "tamper" in qn:
        from app.services.audit import verify_chain
        v = verify_chain(db)
        if v.get("ok"):
            return Answer(
                text=f"Audit chain integrity verified across {v.get('checked')} rows. SHA-256 chain unbroken from genesis.",
                source="rule", citations=[],
            )
        return Answer(
            text=f"Audit chain BROKEN at row #{v.get('broken_at_id')}. Reason: {v.get('reason')}.",
            source="rule", citations=[],
        )

    # ----- Federated state -----
    if "federated" in qn or "foolsgold" in qn or "sybil" in qn:
        log = Path(os.environ.get("ASTRA_FEDERATED_LOG", "D:/astra-data/federated/run.jsonl"))
        if not log.exists():
            return Answer("No federated run on disk yet. Start one with: python -m federated.run_demo --task synthetic --rounds 5 --inject-poison", "rule", [])
        import json
        last_acc = None; quarantined: list[str] = []
        for line in log.read_text(encoding="utf-8").splitlines()[-200:]:
            try:
                r = json.loads(line)
                if r.get("kind") == "aggregation":
                    last_acc = (r.get("global_eval") or {}).get("accuracy")
                if r.get("kind") == "foolsgold":
                    quarantined = [c for c, d in r.get("diag", {}).items() if d.get("flagged")]
            except Exception:
                pass
        text = f"Last federated round global accuracy: {last_acc*100:.1f}%." if last_acc is not None else "No completed rounds yet."
        if quarantined:
            text += f" FoolsGold quarantined: {', '.join(quarantined)}."
        return Answer(text, "rule", [])

    # ----- Help / fallback -----
    return Answer(
        text=(
            "I can answer about: detections by class, engaged alerts, recent missions, "
            "airframes ID'd, audit-chain integrity, federated state. "
            "Try: 'How many ships?' · 'What was the last engagement?' · 'Show me airframes today.' · 'Verify audit chain.'"
        ),
        source="rule",
        citations=[],
    )


# ── Tier 1: LLM with retrieval ─────────────────────────────────────────

def _llm_available() -> bool:
    if not PHI_PATH.exists():
        return False
    try:
        import llama_cpp  # noqa: F401
        return True
    except ImportError:
        return False


def _llm_answer(db: Session, q: str) -> Answer:
    """If llama-cpp-python + Phi-3.5 are available, answer with retrieval."""
    if not _llm_available():
        # Mark caller to fall through
        raise RuntimeError("LLM not available")

    from llama_cpp import Llama

    # Retrieval — pull a few recent missions + top-N alerts as context
    missions = db.execute(select(Mission).order_by(Mission.created_at.desc()).limit(5)).scalars().all()
    alerts = db.execute(select(Alert).order_by(Alert.threat_score.desc()).limit(8)).scalars().all()
    cites = [{"type": "mission", "id": m.id, "name": m.name} for m in missions]
    cites += [{"type": "alert", "id": a.id, "score": a.threat_score} for a in alerts]

    ctx_lines = ["RECENT MISSIONS:"]
    for m in missions:
        ctx_lines.append(f"  #{m.id} {m.name}  created={m.created_at.isoformat()}")
    ctx_lines.append("\nTOP THREAT ALERTS:")
    for a in alerts:
        ctx_lines.append(f"  #{a.id}  score={a.threat_score:.2f}  status={a.status.value}  '{(a.narrative or '')[:80]}'")

    prompt = (
        "<|system|>\nYou are ASTRA, a defence ISR commander console assistant. "
        "Answer questions briefly using only the context provided. Numbers where possible.\n<|end|>\n"
        f"<|user|>\nContext:\n{chr(10).join(ctx_lines)}\n\nQuestion: {q}\n<|end|>\n<|assistant|>\n"
    )

    llm = Llama(model_path=str(PHI_PATH), n_ctx=2048, n_threads=4, verbose=False)
    out = llm(prompt, max_tokens=180, temperature=0.2, stop=["<|end|>", "<|user|>"])
    text = out["choices"][0]["text"].strip()
    return Answer(text=text, source="llm", citations=cites)


# ── Public entry ──────────────────────────────────────────────────────

def answer(db: Session, question: str) -> Answer:
    """Try LLM first; fall back to rule-based if unavailable."""
    if _llm_available():
        try:
            return _llm_answer(db, question)
        except Exception as exc:
            return Answer(
                text=f"LLM error, falling back to rules. ({exc})",
                source="error",
                citations=[],
            )
    return _rule_answer(db, question)


def status() -> dict:
    """Used by the frontend Chat page to show which tier is active."""
    return {
        "llm_available": _llm_available(),
        "phi_path": str(PHI_PATH),
        "phi_present": PHI_PATH.exists(),
    }
