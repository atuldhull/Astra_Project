"""
Telegram notifier for high-threat alerts.

Pitch demo: a phone in the operator's hand buzzes the moment an ENGAGED or
high-threat-score alert lands. Visual: ASTRA detects a vehicle convoy near
FOB Delta, narrator fires, phone vibrates with the threat narrative.

Config (via .env):
    TELEGRAM_BOT_TOKEN      # from @BotFather
    TELEGRAM_CHAT_ID        # the chat where alerts go (DM, group, or channel)
    TELEGRAM_ALERT_THRESHOLD=0.85   # threat_score above which we DM

If either token/chat_id is missing, all calls become no-ops — the rest of
the pipeline doesn't care, the demo still completes, just nothing buzzes.

Pure HTTP — no python-telegram-bot dep, just httpx.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

log = logging.getLogger("astra.notifier")


@dataclass
class TelegramConfig:
    bot_token: str
    chat_id: str
    threshold: float


def _config() -> TelegramConfig | None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        return None
    try:
        threshold = float(os.environ.get("TELEGRAM_ALERT_THRESHOLD", "0.85"))
    except ValueError:
        threshold = 0.85
    return TelegramConfig(bot_token=token, chat_id=chat, threshold=threshold)


def is_configured() -> bool:
    return _config() is not None


def threshold() -> float:
    cfg = _config()
    return cfg.threshold if cfg else 1.1   # > any possible score


def send_alert(
    text: str,
    *,
    image_path: str | None = None,
    threat_score: float | None = None,
) -> bool:
    """Best-effort Telegram send. Returns True iff the API confirmed delivery.

    Never raises — pipeline must continue even if Telegram is down. Any error
    is logged for the operator to inspect.
    """
    cfg = _config()
    if cfg is None:
        return False

    # Threshold gate: only DM the commander when the score warrants it.
    if threat_score is not None and threat_score < cfg.threshold:
        return False

    try:
        import httpx
    except ImportError:
        log.warning("httpx not installed — cannot send telegram")
        return False

    base = f"https://api.telegram.org/bot{cfg.bot_token}"
    try:
        with httpx.Client(timeout=8.0) as client:
            if image_path:
                with open(image_path, "rb") as f:
                    files = {"photo": (os.path.basename(image_path), f, "image/jpeg")}
                    data = {"chat_id": cfg.chat_id, "caption": text}
                    r = client.post(f"{base}/sendPhoto", data=data, files=files)
            else:
                r = client.post(
                    f"{base}/sendMessage",
                    json={"chat_id": cfg.chat_id, "text": text, "parse_mode": "Markdown"},
                )
        if r.status_code != 200:
            log.warning("telegram send failed (%d): %s", r.status_code, r.text[:200])
            return False
        body = r.json()
        return bool(body.get("ok"))
    except Exception as exc:
        log.warning("telegram exception: %s", exc)
        return False


def format_alert_text(
    *,
    mission_name: str,
    class_name: str,
    threat_score: float,
    narrative: str | None,
    nearest_asset: str | None = None,
    distance_km: float | None = None,
    airframe: str | None = None,
) -> str:
    """Build a human-readable Telegram message body."""
    score_pct = int(round(threat_score * 100))
    icon = "🔴" if threat_score >= 0.85 else "🟠" if threat_score >= 0.55 else "🟡"
    lines = [f"{icon} *ASTRA Alert* — {score_pct}% threat", ""]
    label = airframe or class_name
    if airframe:
        lines.append(f"*Object:* {airframe} ({class_name})")
    else:
        lines.append(f"*Object:* {label}")
    if nearest_asset and distance_km is not None:
        lines.append(f"*Distance:* {distance_km:.2f} km from {nearest_asset}")
    lines.append(f"*Mission:* `{mission_name}`")
    if narrative:
        lines.append("")
        lines.append(narrative)
    return "\n".join(lines)
