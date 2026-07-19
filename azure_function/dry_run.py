"""Dry-run local : simule ce que la Function ferait, sans rien supprimer.

Usage :
    cd /Users/ilhameouhaddou/Desktop/Agent_PA-1
    python3 azure_function/dry_run.py

Lit la connection string depuis local.settings.json (pratique en dev).
Aucune ecriture ni suppression cote Azure : juste des logs.
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from azure.storage.blob import BlobServiceClient


def load_local_settings() -> dict:
    settings_path = Path(__file__).resolve().parent / "local.settings.json"
    with open(settings_path) as f:
        return json.load(f)["Values"]


def main() -> None:
    values = load_local_settings()
    conn = values["MAILS_CONN_STR"]
    container_name = values.get("MAILS_CONTAINER", "mails-anonymized")
    days = int(values.get("RETENTION_DAYS", "30"))

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    print(f"Container : {container_name}")
    print(f"Retention : {days} jours -> cutoff = {cutoff}")
    print("-" * 60)

    container = BlobServiceClient.from_connection_string(conn).get_container_client(container_name)

    inspected = 0
    kept = 0
    would_delete = 0
    malformed = 0
    for blob in container.list_blobs(name_starts_with="users/"):
        inspected += 1
        parts = blob.name.split("/")
        if len(parts) != 4:
            malformed += 1
            print(f"  [MALFORME]  {blob.name}")
            continue
        blob_date = parts[2]
        if blob_date < cutoff:
            would_delete += 1
            print(f"  [DELETE]    {blob.name}")
        else:
            kept += 1

    print("-" * 60)
    print(f"Total inspectes : {inspected}")
    print(f"Garderaient (>= cutoff) : {kept}")
    print(f"Seraient supprimes (< cutoff) : {would_delete}")
    print(f"Malformes (ignores) : {malformed}")

    if inspected == 0:
        print()
        print("Aucun blob trouve. Verifiez que :")
        print("  1. Streamlit a bien uploade des mails (AZURE_STORAGE_ENABLED=true dans .env)")
        print("  2. Le container 'mails-anonymized' existe et contient bien des blobs sous 'users/'")


if __name__ == "__main__":
    sys.exit(main())
