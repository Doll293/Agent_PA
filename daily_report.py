#!/usr/bin/env python3
"""Récap quotidien des promos par WhatsApp via CallMeBot.

Usage: python daily_report.py

Ce script :
1. Se connecte à Gmail via IMAP
2. Récupère les mails de l'onglet Promotions reçus aujourd'hui
3. Les analyse via Groq (batch)
4. Envoie un résumé WhatsApp via CallMeBot
"""
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote_plus

import requests

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from mail_manager.config import settings
from mail_manager.gmail_client import GmailClient
from mail_manager.workflow import Workflow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(PROJECT_ROOT / "daily_report.log"),
    ],
)
logger = logging.getLogger(__name__)


def _parse_email_date(raw: str) -> datetime:
    for fmt in ["%a, %d %b %Y %H:%M:%S %z", "%d %b %Y %H:%M:%S %z"]:
        try:
            return datetime.strptime(raw[:31].strip(), fmt).replace(tzinfo=None)
        except Exception:
            continue
    return datetime.now()


def _fetch_today_promos() -> list:
    if not settings.gmail_email or not settings.gmail_app_password:
        raise RuntimeError("GMAIL_EMAIL et GMAIL_APP_PASSWORD requis dans .env")

    client = GmailClient()
    session_id = client.connect(settings.gmail_email, settings.gmail_app_password)
    if not session_id:
        raise RuntimeError("Connexion IMAP Gmail échouée")

    try:
        emails = client.get_promo_emails(session_id, days=2)
        logger.info("Fetched %s emails from Promotions", len(emails))

        # Filtre : aujourd'hui uniquement
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        today_emails = [
            e for e in emails
            if _parse_email_date(e.get("date", "")).date() in (today, yesterday)
        ]
        # Garder juste ceux d'aujourd'hui si il y en a assez
        strict_today = [e for e in today_emails if _parse_email_date(e.get("date", "")).date() == today]
        selected = strict_today if strict_today else today_emails

        logger.info("Kept %s emails for today (%s)", len(selected), today)

        if not selected:
            return []

        workflow = Workflow()
        BATCH_SIZE = 8
        analyzed = []
        for i in range(0, len(selected), BATCH_SIZE):
            batch = selected[i:i + BATCH_SIZE]
            analyzed.extend(workflow.run_for_batch(batch))
            logger.info("Analyzed batch %s/%s", (i // BATCH_SIZE) + 1, (len(selected) + BATCH_SIZE - 1) // BATCH_SIZE)

        promos = [e for e in analyzed if e.get("is_promo")]
        logger.info("Detected %s promos out of %s emails", len(promos), len(analyzed))
        return promos
    finally:
        client.clear_session(session_id)


def _build_whatsapp_message(promos: list) -> str:
    today_str = datetime.now().strftime("%d/%m/%Y")

    if not promos:
        return f"📧 Récap promos du {today_str}\n\nAucune promo aujourd'hui."

    lines = [f"📧 Récap promos du {today_str}", ""]

    # Groupe par catégorie pour meilleure lisibilité
    by_cat = {}
    for p in promos:
        cat = p.get("category", "autre")
        by_cat.setdefault(cat, []).append(p)

    for cat, items in sorted(by_cat.items()):
        lines.append(f"*{cat.upper()}*")
        for p in items:
            company = (p.get("company") or p.get("from", "").split("<")[0].strip())[:30]
            summary = (p.get("summary", "") or p.get("subject", ""))[:80]
            discount = p.get("discount", "")
            parts = [f"• {company}"]
            if discount:
                parts.append(f"({discount})")
            parts.append(f": {summary}")
            lines.append(" ".join(parts))
        lines.append("")

    lines.append(f"Total : {len(promos)} promo(s)")

    # WhatsApp limite ~1500 chars pour être safe
    msg = "\n".join(lines)
    if len(msg) > 1500:
        msg = msg[:1497] + "..."
    return msg


def _send_whatsapp(message: str) -> None:
    if not settings.whatsapp_phone or not settings.callmebot_api_key:
        raise RuntimeError("WHATSAPP_PHONE et CALLMEBOT_API_KEY requis dans .env")

    url = "https://api.callmebot.com/whatsapp.php"
    params = {
        "phone": settings.whatsapp_phone,
        "text": message,
        "apikey": settings.callmebot_api_key,
    }
    logger.info("Sending WhatsApp message (%s chars) to %s", len(message), settings.whatsapp_phone)
    response = requests.get(url, params=params, timeout=30)
    logger.info("CallMeBot response: %s - %s", response.status_code, response.text[:200])
    response.raise_for_status()


def main() -> None:
    logger.info("=== Daily Report Started ===")
    try:
        promos = _fetch_today_promos()
        message = _build_whatsapp_message(promos)
        logger.info("Message preview:\n%s", message)
        _send_whatsapp(message)
        logger.info("=== Daily Report Sent Successfully ===")
    except Exception as exc:
        logger.exception("Daily report failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
