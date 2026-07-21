from __future__ import annotations

import logging

from mail_manager.azure_storage import (
    _hash_message_id,
    fetch_cached_record,
    list_cached_hashes,
    store_anonymized_mails,
)
from mail_manager.config import settings
from mail_manager.privacy import anonymize_mail
from mail_manager.processors import analyze_mails_batch

logger = logging.getLogger(__name__)


class Workflow:
    def __init__(self, preferences: str = "", user_email: str = ""):
        self.preferences = preferences
        self.user_email = user_email or settings.gmail_email

    def _merge(self, email: dict, anon: dict, analysis: dict) -> dict:
        return {
            **email,
            "anon_sender": anon.get("sender", ""),
            "anon_subject": anon.get("subject", ""),
            "anon_snippet": anon.get("snippet", ""),
            "is_promo": analysis.get("is_promo", False),
            "company": analysis.get("company", ""),
            "category": analysis.get("category", ""),
            "summary": analysis.get("summary", ""),
            "promo_code": analysis.get("promo_code", ""),
            "expiry_date": analysis.get("expiry_date", ""),
            "discount": analysis.get("discount", ""),
            "is_fake_promo": analysis.get("is_fake_promo", False),
        }

    def run_for_batch(self, emails: list, cached_index: dict | None = None) -> list:
        if cached_index is None:
            cached_index = (
                list_cached_hashes(self.user_email) if settings.azure_storage_enabled else {}
            )

        result: list = [None] * len(emails)
        to_analyze_positions = []
        to_analyze_payload = []
        to_analyze_anon = []

        for idx, email in enumerate(emails):
            message_id = email.get("message_id", "")
            blob_name = cached_index.get(_hash_message_id(message_id)) if message_id else None

            if blob_name:
                record = fetch_cached_record(blob_name)
                if record:
                    result[idx] = self._merge(
                        email,
                        record.get("anonymized", {}),
                        record.get("analysis", {}),
                    )
                    continue

            anon = anonymize_mail(
                email.get("subject", ""),
                email.get("snippet", ""),
                email.get("from", ""),
            )
            to_analyze_positions.append(idx)
            to_analyze_anon.append(anon)
            to_analyze_payload.append(
                {
                    "sender": anon["sender"],
                    "subject": anon["subject"],
                    "snippet": anon["snippet"],
                    "body": "",
                }
            )

        newly_enriched = []
        if to_analyze_payload:
            analyses = analyze_mails_batch(to_analyze_payload, self.preferences)
            for idx, anon, analysis in zip(to_analyze_positions, to_analyze_anon, analyses):
                enriched = self._merge(emails[idx], anon, analysis)
                result[idx] = enriched
                newly_enriched.append(enriched)

        cached_count = len(emails) - len(to_analyze_positions)
        logger.info(
            "Analyse: %s mails depuis le cache Azure, %s ré-analysés.",
            cached_count,
            len(to_analyze_positions),
        )

        if settings.azure_storage_enabled and newly_enriched:
            try:
                store_anonymized_mails(newly_enriched, self.user_email)
            except Exception:
                logger.exception("Stockage Azure echoue.")

        return result
