import logging
from concurrent.futures import ThreadPoolExecutor

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
        self._cache_index: dict | None = None

    def load_cache_index(self, force: bool = False) -> dict:
        """Charge une seule fois l'index Azure {hash(message_id): blob_name}.

        Appeler une fois avant la boucle de batchs pour eviter N appels
        `list_cached_hashes` (un par batch).
        """
        if self._cache_index is not None and not force:
            return self._cache_index
        self._cache_index = (
            list_cached_hashes(self.user_email) if settings.azure_storage_enabled else {}
        )
        return self._cache_index

    def invalidate_cache_index(self) -> None:
        self._cache_index = None

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

    def run_for_batch(self, emails: list) -> list:
        cached_index = self.load_cache_index()

        result: list = [None] * len(emails)
        to_analyze_positions = []
        to_analyze_payload = []
        to_analyze_anon = []

        # 1. Repérer les mails en cache et les nouveaux
        cached_lookups: list[tuple[int, str]] = []  # (idx, blob_name)
        for idx, email in enumerate(emails):
            message_id = email.get("message_id", "")
            blob_name = cached_index.get(_hash_message_id(message_id)) if message_id else None

            if blob_name:
                cached_lookups.append((idx, blob_name))
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

        # 2. Télécharger les blobs en parallèle
        if cached_lookups:
            with ThreadPoolExecutor(max_workers=8) as pool:
                records = list(pool.map(fetch_cached_record, [b for _, b in cached_lookups]))
            for (idx, _), record in zip(cached_lookups, records):
                if record:
                    result[idx] = self._merge(
                        emails[idx],
                        record.get("anonymized", {}),
                        record.get("analysis", {}),
                    )
                else:
                    # blob manquant : re-analyser
                    anon = anonymize_mail(
                        emails[idx].get("subject", ""),
                        emails[idx].get("snippet", ""),
                        emails[idx].get("from", ""),
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
                uploaded = store_anonymized_mails(newly_enriched, self.user_email)
                # Mettre à jour l'index local pour eviter un re-list Azure
                for name in uploaded:
                    leaf = name.rsplit("/", 1)[-1]
                    if leaf.endswith(".json"):
                        cached_index[leaf[:-5]] = name
            except Exception:
                logger.exception("Stockage Azure echoue.")

        return result
