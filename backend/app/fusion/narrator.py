"""
Commander-friendly alert narrator.

Generates a 1-sentence natural-language summary of why an alert matters.
Uses deterministic templates (no LLM dependency) for guaranteed-to-ship
behaviour. A future Phi-3.5-mini upgrade path is stubbed at the bottom
for when it's safe to swap in.

Example outputs:
  "CRITICAL THREAT: 41 large-vehicle units 0.12km from FOB Delta (confidence 73%). Dense cluster formation."
  "Elevated threat: single aircraft-fixed-wing 2.40km from FOB Delta (confidence 91%)."
  "Routine detection: single ship 8.10km from Outpost Bravo (confidence 54%)."
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NarratorContext:
    class_name: str
    confidence: float           # 0..1
    threat_score: float         # 0..1
    distance_km: float | None
    nearest_asset: str | None
    same_class_count: int       # how many of this class in the mission


# Friendlier class name display (aircraft-fixed-wing → "fixed-wing aircraft" etc.)
_CLASS_DISPLAY: dict[str, str] = {
    "small-vehicle":       "light vehicle",
    "large-vehicle":       "heavy vehicle",
    "aircraft-fixed-wing": "fixed-wing aircraft",
    "aircraft-rotor":      "rotary-wing aircraft",
    "ship":                "maritime vessel",
    "storage-depot":       "storage installation",
    "harbor":              "harbor facility",
    "bridge":              "bridge structure",
}


def _urgency_label(threat_score: float) -> str:
    if threat_score >= 0.75:
        return "CRITICAL THREAT"
    if threat_score >= 0.55:
        return "High-priority alert"
    if threat_score >= 0.35:
        return "Elevated threat"
    return "Routine detection"


def _pluralize(cls: str, n: int) -> str:
    display = _CLASS_DISPLAY.get(cls, cls)
    if n <= 1:
        return f"single {display}"
    return f"{n} {display} units"


def _formation_hint(class_name: str, n: int) -> str | None:
    """Contextual insight based on class + count."""
    if n >= 15:
        return "dense cluster formation"
    if n >= 6:
        return "grouped formation"
    if n >= 3 and class_name in ("large-vehicle",):
        return "possible convoy formation"
    if n >= 2 and class_name in ("aircraft-fixed-wing", "aircraft-rotor"):
        return "multi-aircraft operation"
    return None


def _location_clause(distance_km: float | None, nearest_asset: str | None) -> str:
    if distance_km is None or nearest_asset is None:
        return ""
    if distance_km < 0.5:
        return f" within 500m of {nearest_asset}"
    return f" {distance_km:.2f}km from {nearest_asset}"


def narrate(ctx: NarratorContext) -> str:
    """Return a 1-sentence summary. Deterministic, template-based."""
    urgency = _urgency_label(ctx.threat_score)
    descriptor = _pluralize(ctx.class_name, ctx.same_class_count)
    location = _location_clause(ctx.distance_km, ctx.nearest_asset)
    conf_pct = int(round(max(0.0, min(1.0, ctx.confidence)) * 100))
    confidence_clause = f" (confidence {conf_pct}%)"

    base = f"{urgency}: {descriptor}{location}{confidence_clause}"

    hint = _formation_hint(ctx.class_name, ctx.same_class_count)
    if hint:
        base += f". {hint.capitalize()}."
    else:
        base += "."

    return base


# ── Future LLM upgrade hook ────────────────────────────────────────────────
# When llama-cpp-python is reliably installed and Phi-3.5-mini-instruct
# GGUF is downloaded to D:/astra-data/models/, uncomment the code below
# to generate richer narratives. Template path always remains as fallback.
#
# _llm = None
#
# def _try_llm(ctx: NarratorContext) -> str | None:
#     global _llm
#     try:
#         if _llm is None:
#             from llama_cpp import Llama
#             _llm = Llama(
#                 model_path="D:/astra-data/models/Phi-3.5-mini-instruct-Q4_K_M.gguf",
#                 n_ctx=2048, verbose=False,
#             )
#         prompt = (
#             f"You are a military intelligence analyst. Write exactly ONE sentence "
#             f"describing this alert for a commander:\n"
#             f"Class: {ctx.class_name}\nCount: {ctx.same_class_count}\n"
#             f"Distance: {ctx.distance_km}km from {ctx.nearest_asset}\n"
#             f"Confidence: {ctx.confidence}\nThreat score: {ctx.threat_score}\n"
#             f"Sentence:"
#         )
#         resp = _llm(prompt, max_tokens=60, temperature=0.2, stop=["\n"])
#         text = resp["choices"][0]["text"].strip()
#         return text if 15 <= len(text) <= 200 else None
#     except Exception:
#         return None
