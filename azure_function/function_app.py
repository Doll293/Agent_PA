"""Azure Function : purge quotidienne des mails > 30 jours dans le Blob Storage.

Chemin des blobs (defini par mail_manager/azure_storage.py) :
    users/<user_slug>/<YYYY-MM-DD>/<sha1(message_id)>.json

La Function se contente de :
    1. calculer cutoff = today (UTC) - RETENTION_DAYS jours
    2. lister tous les blobs sous 'users/'
    3. supprimer ceux dont le segment date < cutoff

Elle ne lit JAMAIS le contenu des blobs (pas d'IA, pas de Gmail).
"""

import logging
import os
from datetime import datetime, timedelta, timezone

import azure.functions as func
from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import BlobServiceClient

app = func.FunctionApp()


RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "30"))
MAILS_CONTAINER = os.getenv("MAILS_CONTAINER", "mails-anonymized")


def _mails_container():
    conn = os.environ["MAILS_CONN_STR"]
    service = BlobServiceClient.from_connection_string(conn)
    return service.get_container_client(MAILS_CONTAINER)


@app.function_name(name="RetentionDaily")
@app.schedule(
    schedule="%RETENTION_CRON%",
    arg_name="mytimer",
    run_on_startup=False,
    use_monitor=True,
)
def retention_daily(mytimer: func.TimerRequest) -> None:
    cutoff = (
        datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
    ).strftime("%Y-%m-%d")
    logging.info("Purge des blobs dont la date < %s (retention = %s jours)",
                 cutoff, RETENTION_DAYS)

    container = _mails_container()

    inspected = 0
    deleted = 0
    for blob in container.list_blobs(name_starts_with="users/"):
        inspected += 1
        parts = blob.name.split("/")
        # attendu : users/<slug>/<YYYY-MM-DD>/<hash>.json
        if len(parts) != 4:
            continue
        blob_date = parts[2]
        if blob_date < cutoff:
            try:
                container.delete_blob(blob.name)
                deleted += 1
            except ResourceNotFoundError:
                # blob deja supprime par une execution concurrente, on ignore
                pass
            except Exception:
                logging.exception("Echec suppression pour %s.", blob.name)

    logging.info(
        "Retention terminee : %s blobs inspectes, %s supprimes.",
        inspected, deleted,
    )
