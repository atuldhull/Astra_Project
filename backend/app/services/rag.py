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

Round-3 add-ons:
  * Mission-scoped briefing intent: "details of mission #N", "brief me on
    mission 14", "tell me about MISSION-…" → renders a multi-section
    professional briefing pulling Mission + Detections + airframes +
    Alerts + ChatMessages + audit chain.
  * Note intent: "note: …", "save: …", "remember: …" — when a mission_id
    is in scope, persists the note as a ChatMessage so the next briefing
    surfaces it.
"""

from __future__ import annotations

import json as _json
import os
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.models import (
    Alert, AlertStatus, AuditEvent, ChatMessage, Detection, Mission,
)


PHI_PATH = Path(os.environ.get("ASTRA_PHI_PATH", "D:/astra-data/models/phi-3.5-mini-instruct.Q4_K_M.gguf"))


@dataclass
class Answer:
    text: str
    source: str       # 'rule' | 'llm' | 'error' | 'note' | 'briefing'
    citations: list[dict]   # [{type, id, summary}]


# ── Mission detail extraction ───────────────────────────────────────────

_MISSION_DETAIL_PATTERNS = [
    re.compile(r"(?:details?|brief(?:ing)?|tell me about|info(?:rmation)? on|summary of|what about|recap of)\s+(?:mission\s+)?#?(\d+)", re.I),
    re.compile(r"mission\s+#?(\d+)\s+(?:details?|brief(?:ing)?|summary|info|recap)", re.I),
    re.compile(r"all\s+(?:the\s+)?(?:details?|info|data)\s+(?:of|for|about)\s+(?:mission\s+)?#?(\d+)", re.I),
    re.compile(r"(?:show|give)\s+me\s+(?:everything|all)\s+(?:on|about|for)\s+(?:mission\s+)?#?(\d+)", re.I),
]


def _detect_mission_id(q: str, fallback: int | None) -> int | None:
    for pat in _MISSION_DETAIL_PATTERNS:
        m = pat.search(q)
        if m:
            return int(m.group(1))
    # If question mentions "this mission" / "current mission" / standalone
    # "mission #N", trust the explicit ID first then the fallback.
    m = re.search(r"mission\s+#?(\d+)", q, re.I)
    if m:
        return int(m.group(1))
    if re.search(r"\b(this|current|active)\s+mission\b", q, re.I):
        return fallback
    return None


def _is_briefing_request(q: str) -> bool:
    qn = q.lower()
    triggers = [
        "details", "detail", "briefing", "brief me", "tell me about",
        "summary of", "recap", "everything about", "everything on",
        "all info", "all the info", "all data", "all the data",
        "all details", "all the details", "what about mission",
    ]
    return any(t in qn for t in triggers)


# ── Mission briefing renderer ───────────────────────────────────────────

def _fmt_dt(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def _render_briefing(db: Session, mission_id: int) -> Answer:
    m: Mission | None = db.get(Mission, mission_id)
    if m is None:
        return Answer(
            text=f"No mission #{mission_id} on record. Use 'recent missions' to list available IDs.",
            source="briefing",
            citations=[],
        )

    dets = db.execute(
        select(Detection).where(Detection.mission_id == mission_id)
    ).scalars().all()
    alerts = db.execute(
        select(Alert).where(Alert.mission_id == mission_id).order_by(Alert.threat_score.desc())
    ).scalars().all()
    notes = db.execute(
        select(ChatMessage)
        .where(ChatMessage.mission_id == mission_id, ChatMessage.source == "note")
        .order_by(ChatMessage.created_at.asc())
    ).scalars().all()
    audit_rows = db.execute(
        select(AuditEvent).where(AuditEvent.mission_id == mission_id).order_by(AuditEvent.id.asc())
    ).scalars().all()

    # ── OVERVIEW ────────────────────────────────────────────────────────
    aoi_corners = m.aoi_corners_json or "—"
    src_path = m.source_path or "—"
    if len(src_path) > 64:
        src_path = "…" + src_path[-60:]

    # ── DETECTIONS aggregate ───────────────────────────────────────────
    by_class: dict[str, list[float]] = {}
    airframes: Counter[str] = Counter()
    airframe_conf: dict[str, list[float]] = {}
    track_ids = set()
    ood_count = 0
    for d in dets:
        by_class.setdefault(d.class_name, []).append(d.confidence)
        if d.track_id is not None:
            track_ids.add(d.track_id)
        try:
            ex = _json.loads(d.extras_json or "{}")
        except Exception:
            ex = {}
        if ex.get("airframe"):
            airframes[ex["airframe"]] += 1
            airframe_conf.setdefault(ex["airframe"], []).append(
                float(ex.get("airframe_confidence") or 0.0)
            )
        if ex.get("ood_flag"):
            ood_count += 1

    # ── ALERTS aggregate ───────────────────────────────────────────────
    status_counts: Counter[str] = Counter(a.status.value for a in alerts)

    # ── AUDIT chain (mission-local) ────────────────────────────────────
    audit_summary = "no events"
    if audit_rows:
        last = audit_rows[-1]
        last_hash = (last.row_hash or "")[:8] + "…" + (last.row_hash or "")[-4:] if last.row_hash else "—"
        audit_summary = f"{len(audit_rows)} events · last hash {last_hash}"

    # ── Render ─────────────────────────────────────────────────────────
    lines: list[str] = []
    sep = "═" * 60
    thin = "─" * 60
    lines.append(sep)
    lines.append(f"  MISSION #{m.id} — {m.name}")
    lines.append(sep)
    lines.append("")
    lines.append("OVERVIEW")
    lines.append(f"  Created    : {_fmt_dt(m.created_at)}")
    lines.append(f"  Source     : {src_path}")
    lines.append(f"  AOI        : {'set' if m.aoi_corners_json else 'none / GPS-anchored'}")
    lines.append("")

    lines.append(f"DETECTIONS ({len(dets)} total · {len(track_ids)} tracks · {ood_count} OOD-flagged)")
    if by_class:
        lines.append(thin)
        lines.append(f"  {'Class':<24}{'Count':>8}{'Avg conf':>12}")
        lines.append(thin)
        for cls, confs in sorted(by_class.items(), key=lambda kv: -len(kv[1])):
            avg = sum(confs) / len(confs)
            lines.append(f"  {cls:<24}{len(confs):>8}{avg:>12.2f}")
        lines.append(thin)
    else:
        lines.append("  (none)")
    lines.append("")

    if airframes:
        lines.append("AIRFRAMES IDENTIFIED  (MAR20 cascade)")
        for name, n in airframes.most_common(10):
            confs = airframe_conf.get(name, [])
            avg = (sum(confs) / len(confs)) if confs else 0.0
            lines.append(f"  • {name:<16} × {n:<3}  (avg {avg:.2f})")
        lines.append("")

    lines.append(f"ALERTS  ({len(alerts)} raised · " +
                 ", ".join(f"{n} {s}" for s, n in status_counts.items()) + ")")
    if alerts:
        for a in alerts[:8]:
            narr = (a.narrative or "").strip().replace("\n", " ")
            if len(narr) > 60:
                narr = narr[:57] + "…"
            lines.append(f"  #{a.id:<4} threat {a.threat_score:.2f}  {a.status.value:<10} \"{narr}\"")
        if len(alerts) > 8:
            lines.append(f"  … + {len(alerts) - 8} more")
    else:
        lines.append("  (none)")
    lines.append("")

    lines.append(f"OPERATOR NOTES ({len(notes)})")
    if notes:
        for n in notes[-12:]:
            ts = n.created_at.strftime("%H:%M") if n.created_at else "--:--"
            who = n.operator_id or "operator"
            txt = n.text.strip().replace("\n", " ")
            if len(txt) > 80:
                txt = txt[:77] + "…"
            lines.append(f"  [{ts}] {who}: {txt}")
        if len(notes) > 12:
            lines.append(f"  … + {len(notes) - 12} earlier")
    else:
        lines.append("  (no notes — say 'note: <text>' while this mission is active to add one)")
    lines.append("")

    lines.append("AUDIT")
    lines.append(f"  {audit_summary}")
    lines.append(sep)

    cites: list[dict] = (
        [{"type": "mission", "id": m.id, "name": m.name}]
        + [{"type": "alert", "id": a.id, "score": a.threat_score} for a in alerts[:5]]
        + [{"type": "note", "id": n.id} for n in notes[-5:]]
    )
    return Answer(text="\n".join(lines), source="briefing", citations=cites)


# ── Note saver ─────────────────────────────────────────────────────────

_NOTE_PREFIXES = re.compile(r"^\s*(?:note|save|remember|log|jot)\s*[:\-]\s*", re.I)


def _try_save_note(db: Session, q: str, mission_id: int | None, operator_id: str | None) -> Answer | None:
    m = _NOTE_PREFIXES.match(q)
    if not m:
        return None
    body = q[m.end():].strip()
    if not body:
        return Answer("Empty note — say 'note: <something>' to save text against this mission.", "note", [])
    if mission_id is None:
        return Answer(
            "No active mission selected. Open a Mission first (or pass mission_id) so the note has somewhere to land.",
            "note", [],
        )
    msg = ChatMessage(
        mission_id=mission_id, role="user", text=body, source="note",
        operator_id=operator_id,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return Answer(
        text=f"Note saved to mission #{mission_id} (note #{msg.id}). It will appear in the next briefing.",
        source="note",
        citations=[{"type": "note", "id": msg.id, "mission_id": mission_id}],
    )


# ── Tier 2: Rule-based handler ─────────────────────────────────────────

def _rule_answer(db: Session, q: str, mission_id: int | None = None) -> Answer:
    qn = q.lower().strip()
    cites: list[dict] = []

    # ----- Mission briefing (highest priority) -----
    if _is_briefing_request(qn):
        mid = _detect_mission_id(q, mission_id)
        if mid is not None:
            return _render_briefing(db, mid)
        # Briefing words but no mission ID — guide
        return Answer(
            "Tell me which mission. Try: 'details of mission #14' or 'brief me on mission 14'.",
            "rule", [],
        )

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
    if any(w in qn for w in ["recent mission", "today", "last mission", "latest", "list missions"]):
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        recent = db.execute(
            select(Mission).where(Mission.created_at >= cutoff).order_by(Mission.created_at.desc()).limit(10)
        ).scalars().all()
        if not recent:
            return Answer("No missions in the last 24 hours.", "rule", [])
        for mm in recent:
            cites.append({"type": "mission", "id": mm.id, "name": mm.name})
        return Answer(
            text=f"{len(recent)} mission(s) in the last 24 hours: " +
                 ", ".join(f"#{mm.id} {mm.name}" for mm in recent[:6]),
            source="rule",
            citations=cites,
        )

    # ----- Airframes / cascade IDs -----
    if "airframe" in qn or "fighter" in qn or "f-22" in qn or "su-" in qn or "what aircraft" in qn:
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
        last_acc = None; quarantined: list[str] = []
        for line in log.read_text(encoding="utf-8").splitlines()[-200:]:
            try:
                r = _json.loads(line)
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
            "airframes ID'd, audit-chain integrity, federated state, and full mission "
            "briefings. Try: 'details of mission #14' · 'How many ships?' · "
            "'note: <text to save against this mission>'."
        ),
        source="rule",
        citations=[],
    )


# ── Tier 1: LLM with retrieval ─────────────────────────────────────────

_LLM = None  # Singleton Llama instance — populated on first call OR by warmup hook.


def _llm_available() -> bool:
    if not PHI_PATH.exists():
        return False
    try:
        import llama_cpp  # noqa: F401
        return True
    except ImportError:
        return False


def _get_llm():
    """Return the cached Llama instance, instantiating it on first call.
    Called explicitly from the FastAPI startup warmup hook and lazily by
    _llm_answer() to keep cold-start cost out of the request path."""
    global _LLM
    if _LLM is not None:
        return _LLM
    from llama_cpp import Llama
    _LLM = Llama(model_path=str(PHI_PATH), n_ctx=2048, n_threads=4, verbose=False)
    return _LLM


def _llm_answer(db: Session, q: str, mission_id: int | None = None) -> Answer:
    """If llama-cpp-python + Phi-3.5 are available, answer with retrieval."""
    if not _llm_available():
        # Mark caller to fall through
        raise RuntimeError("LLM not available")

    # Mission-scoped retrieval if we have a mission_id, else global.
    if mission_id is not None and db.get(Mission, mission_id) is not None:
        m = db.get(Mission, mission_id)
        dets_n = db.execute(
            select(func.count()).select_from(Detection).where(Detection.mission_id == mission_id)
        ).scalar_one()
        alerts = db.execute(
            select(Alert).where(Alert.mission_id == mission_id).order_by(Alert.threat_score.desc()).limit(8)
        ).scalars().all()
        notes = db.execute(
            select(ChatMessage)
            .where(ChatMessage.mission_id == mission_id, ChatMessage.source == "note")
            .order_by(ChatMessage.created_at.desc()).limit(8)
        ).scalars().all()
        cites = (
            [{"type": "mission", "id": m.id, "name": m.name}]
            + [{"type": "alert", "id": a.id, "score": a.threat_score} for a in alerts]
            + [{"type": "note", "id": n.id} for n in notes]
        )
        ctx_lines = [f"ACTIVE MISSION #{m.id} {m.name}  detections={dets_n}"]
        ctx_lines.append("\nALERTS:")
        for a in alerts:
            ctx_lines.append(f"  #{a.id} score={a.threat_score:.2f} status={a.status.value} '{(a.narrative or '')[:80]}'")
        if notes:
            ctx_lines.append("\nOPERATOR NOTES:")
            for n in notes:
                ctx_lines.append(f"  [{n.created_at:%H:%M}] {(n.operator_id or 'op')}: {n.text[:120]}")
    else:
        missions = db.execute(select(Mission).order_by(Mission.created_at.desc()).limit(5)).scalars().all()
        alerts = db.execute(select(Alert).order_by(Alert.threat_score.desc()).limit(8)).scalars().all()
        cites = [{"type": "mission", "id": mm.id, "name": mm.name} for mm in missions]
        cites += [{"type": "alert", "id": a.id, "score": a.threat_score} for a in alerts]
        ctx_lines = ["RECENT MISSIONS:"]
        for mm in missions:
            ctx_lines.append(f"  #{mm.id} {mm.name}  created={mm.created_at.isoformat()}")
        ctx_lines.append("\nTOP THREAT ALERTS:")
        for a in alerts:
            ctx_lines.append(f"  #{a.id}  score={a.threat_score:.2f}  status={a.status.value}  '{(a.narrative or '')[:80]}'")

    prompt = (
        "<|system|>\nYou are ASTRA, a defence ISR commander console assistant. "
        "Answer questions briefly using only the context provided. Numbers where possible. "
        "Be professional and concise.\n<|end|>\n"
        f"<|user|>\nContext:\n{chr(10).join(ctx_lines)}\n\nQuestion: {q}\n<|end|>\n<|assistant|>\n"
    )

    llm = _get_llm()
    out = llm(prompt, max_tokens=220, temperature=0.2, stop=["<|end|>", "<|user|>"])
    text = out["choices"][0]["text"].strip()
    return Answer(text=text, source="llm", citations=cites)


# ── Public entry ──────────────────────────────────────────────────────

def answer(
    db: Session,
    question: str,
    mission_id: int | None = None,
    operator_id: str | None = None,
    persist: bool = True,
) -> Answer:
    """Try note-save first, then briefing if requested, then LLM, then rules.

    If `persist` is True, both the user turn and the response get written
    to the chat_messages table tied to mission_id (nullable).
    """
    # 1. Try note-save shortcut (writes its own chat_message internally)
    note = _try_save_note(db, question, mission_id, operator_id)
    if note is not None:
        if persist:
            _persist_turn(db, mission_id, question, note, operator_id, skip_user=True)
        return note

    # 2. Briefing intent — handled by rule path even if LLM is up, because
    #    the structured briefing is more useful than free text here.
    if _is_briefing_request(question):
        a = _rule_answer(db, question, mission_id=mission_id)
        if persist:
            _persist_turn(db, mission_id, question, a, operator_id)
        return a

    # 3. LLM if available
    if _llm_available():
        try:
            a = _llm_answer(db, question, mission_id=mission_id)
        except Exception as exc:
            a = Answer(
                text=f"LLM error, falling back to rules. ({exc})",
                source="error",
                citations=[],
            )
            # Fall through to rules below
            a_fallback = _rule_answer(db, question, mission_id=mission_id)
            if persist:
                _persist_turn(db, mission_id, question, a_fallback, operator_id)
            return a_fallback
        if persist:
            _persist_turn(db, mission_id, question, a, operator_id)
        return a

    # 4. Rule-based fallback
    a = _rule_answer(db, question, mission_id=mission_id)
    if persist:
        _persist_turn(db, mission_id, question, a, operator_id)
    return a


def _persist_turn(
    db: Session,
    mission_id: int | None,
    question: str,
    answer: Answer,
    operator_id: str | None,
    skip_user: bool = False,
) -> None:
    if not skip_user:
        db.add(ChatMessage(
            mission_id=mission_id, role="user", text=question,
            source=None, operator_id=operator_id,
        ))
    db.add(ChatMessage(
        mission_id=mission_id, role="astra", text=answer.text,
        source=answer.source,
        citations_json=_json.dumps(answer.citations) if answer.citations else None,
        operator_id=operator_id,
    ))
    db.commit()


def status() -> dict:
    """Used by the frontend Chat page to show which tier is active."""
    return {
        "llm_available": _llm_available(),
        "phi_path": str(PHI_PATH),
        "phi_present": PHI_PATH.exists(),
    }
