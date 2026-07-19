import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from mail_manager.config import settings

logger = logging.getLogger(__name__)

_CONTAINER_CLIENT = None
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _get_container_client():
    global _CONTAINER_CLIENT
    if _CONTAINER_CLIENT is not None:
        return _CONTAINER_CLIENT
    if not settings.azure_storage_connection_string:
        raise RuntimeError("AZURE_STORAGE_CONNECTION_STRING manquant dans le fichier .env.")

    from azure.storage.blob import BlobServiceClient

    service = BlobServiceClient.from_connection_string(settings.azure_storage_connection_string)
    container = service.get_container_client(settings.azure_storage_container)
    try:
        container.create_container()
        logger.info("Azure container '%s' cree.", settings.azure_storage_container)
    except Exception:
        pass

    _CONTAINER_CLIENT = container
    return container


def _get_container_or_none():
    if not settings.azure_storage_enabled:
        return None
    try:
        return _get_container_client()
    except Exception:
        logger.exception("Azure indisponible, le cache est desactive.")
        return None


def _user_slug(user_email: str) -> str:
    slug = _SLUG_RE.sub("_", (user_email or "").lower()).strip("_")
    return slug or "anonymous"


def _hash_message_id(message_id: str) -> str:
    return hashlib.sha1((message_id or "").encode("utf-8")).hexdigest()


def _mail_date_folder(raw_date: str) -> str:
    """Convertit la date RFC 822 du mail en YYYY-MM-DD.

    Fallback sur la date UTC du jour si le header est manquant / illisible :
    cela garantit que le blob reste dans la fenetre de retention.
    """
    if raw_date:
        try:
            dt = parsedate_to_datetime(raw_date)
            if dt is not None:
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc).strftime("%Y-%m-%d")
        except (TypeError, ValueError):
            pass
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _blob_name(user_email: str, message_id: str, mail_date: str) -> str:
    return f"users/{_user_slug(user_email)}/{_mail_date_folder(mail_date)}/{_hash_message_id(message_id)}.json"


def _to_anonymized_record(enriched_mail: dict) -> dict:
    """Ne garde QUE la version anonymisee + l'analyse IA (RGPD-friendly)."""
    return {
        "stored_at": datetime.now(timezone.utc).isoformat(),
        "message_id": enriched_mail.get("message_id", ""),
        "date": enriched_mail.get("date", ""),
        "anonymized": {
            "sender": enriched_mail.get("anon_sender", ""),
            "subject": enriched_mail.get("anon_subject", ""),
            "snippet": enriched_mail.get("anon_snippet", ""),
        },
        "analysis": {
            "is_promo": enriched_mail.get("is_promo", False),
            "company": enriched_mail.get("company", ""),
            "category": enriched_mail.get("category", ""),
            "summary": enriched_mail.get("summary", ""),
            "promo_code": enriched_mail.get("promo_code", ""),
            "expiry_date": enriched_mail.get("expiry_date", ""),
            "discount": enriched_mail.get("discount", ""),
            "is_fake_promo": enriched_mail.get("is_fake_promo", False),
        },
    }


def list_cached_hashes(user_email: str) -> dict:
    """Retourne {sha1(message_id): blob_name_complet} pour tous les mails
    deja stockes de cet utilisateur (toutes dates confondues).

    Cle = hash du message_id (present dans le nom du blob).
    Valeur = chemin complet pour telechargement direct.
    """
    container = _get_container_or_none()
    if not container:
        return {}
    prefix = f"users/{_user_slug(user_email)}/"
    result = {}
    try:
        for blob in container.list_blobs(name_starts_with=prefix):
            leaf = blob.name.rsplit("/", 1)[-1]
            if leaf.endswith(".json"):
                result[leaf[:-5]] = blob.name
    except Exception:
        logger.exception("Impossible de lister les blobs pour %s.", user_email)
    return result


def fetch_cached_record(blob_name: str) -> dict:
    """Telecharge un enregistrement cache. Retourne {} en cas d'erreur."""
    container = _get_container_or_none()
    if not container or not blob_name:
        return {}
    try:
        stream = container.download_blob(blob_name)
        return json.loads(stream.readall())
    except Exception:
        logger.exception("Echec telechargement Azure pour %s.", blob_name)
        return {}


def store_anonymized_mails(enriched_mails: list, user_email: str) -> list:
    """Uploade la version anonymisee de chaque mail vers Azure Blob Storage.

    Chemin : users/<slug>/<YYYY-MM-DD>/<sha1(message_id)>.json.
    Le dossier date permet la purge quotidienne cote Azure Function.
    """
    if not enriched_mails:
        return []

    container = _get_container_or_none()
    if not container:
        return []

    uploaded = []
    for mail in enriched_mails:
        message_id = mail.get("message_id", "")
        if not message_id:
            logger.warning("Mail sans message_id ignore pour le stockage Azure.")
            continue
        record = _to_anonymized_record(mail)
        name = _blob_name(user_email, message_id, mail.get("date", ""))
        payload = json.dumps(record, ensure_ascii=False, indent=2).encode("utf-8")
        try:
            container.upload_blob(
                name=name,
                data=payload,
                overwrite=True,
                content_type="application/json",
            )
            uploaded.append(name)
        except Exception:
            logger.exception("Echec upload Azure pour %s.", name)

    logger.info("Uploaded %s/%s mails anonymises vers Azure.", len(uploaded), len(enriched_mails))
    return uploaded
