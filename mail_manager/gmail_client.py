from typing import Any
from uuid import uuid4
import logging

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from mail_manager.config import settings

logger = logging.getLogger(__name__)


def _get_header(headers: list[dict[str, str]], name: str, default: str = "") -> str:
    wanted = name.lower()
    for header in headers:
        if header.get("name", "").lower() == wanted:
            return header.get("value", default)
    return default


class GmailClient:
    def __init__(self) -> None:
        self.provider_label = "Gmail"
        self.scopes = [settings.gmail_scope]
        self._credentials_store: dict[str, Credentials] = {}

    def is_configured(self) -> bool:
        return settings.gmail_credentials_file.exists()

    def get_configuration_error(self) -> str | None:
        if self.is_configured():
            return None
        return "Le fichier credentials.json est manquant a la racine du projet."

    def create_session_id(self) -> str:
        return uuid4().hex

    def load_credentials(self, session_id: str | None) -> Credentials | None:
        if not session_id:
            return None

        creds = self._credentials_store.get(session_id)
        if not creds:
            return None

        if creds.expired and creds.refresh_token:
            logger.info("Refreshing Gmail credentials for session %s", session_id)
            creds.refresh(Request())
            self._credentials_store[session_id] = creds
        return creds

    def serialize_credentials(self, session_id: str | None) -> dict[str, Any] | None:
        creds = self.load_credentials(session_id)
        if not creds:
            return None
        return {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": creds.scopes,
        }

    def restore_credentials(self, session_id: str | None, raw_credentials: dict[str, Any] | None) -> None:
        if not session_id or not raw_credentials:
            return
        self._credentials_store[session_id] = Credentials.from_authorized_user_info(raw_credentials, self.scopes)

    def is_connected(self, session_id: str | None) -> bool:
        creds = self.load_credentials(session_id)
        return bool(creds and creds.valid)

    def build_auth_url(self, redirect_uri: str | None = None) -> tuple[str, str]:
        final_redirect_uri = redirect_uri or settings.google_redirect_uri
        logger.info("Building Gmail OAuth URL with redirect_uri=%s", final_redirect_uri)
        flow = Flow.from_client_secrets_file(
            str(settings.gmail_credentials_file),
            scopes=self.scopes,
            redirect_uri=final_redirect_uri,
        )
        auth_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        return auth_url, state

    def fetch_token_from_callback(
        self,
        state: str,
        full_callback_url: str,
        session_id: str,
        redirect_uri: str | None = None,
    ) -> None:
        final_redirect_uri = redirect_uri or settings.google_redirect_uri
        logger.info("Fetching Gmail OAuth token with redirect_uri=%s", final_redirect_uri)
        flow = Flow.from_client_secrets_file(
            str(settings.gmail_credentials_file),
            scopes=self.scopes,
            state=state,
            redirect_uri=final_redirect_uri,
        )
        flow.fetch_token(authorization_response=full_callback_url)
        self._credentials_store[session_id] = flow.credentials

    def get_recent_emails(self, session_id: str | None, max_results: int = 10) -> list[dict[str, Any]]:
        creds = self.load_credentials(session_id)
        if not creds:
            logger.warning("No Gmail credentials found for session %s", session_id)
            return []

        logger.info("Fetching up to %s recent Gmail messages for session %s", max_results, session_id)
        service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        results = service.users().messages().list(userId="me", maxResults=max_results).execute()
        messages = results.get("messages", [])
        logger.info("Gmail API returned %s message ids", len(messages))

        items: list[dict[str, Any]] = []
        for message in messages:
            details = service.users().messages().get(
                userId="me",
                id=message["id"],
                format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            ).execute()

            payload = details.get("payload", {})
            headers = payload.get("headers", [])
            items.append(
                {
                    "id": details.get("id"),
                    "from": _get_header(headers, "From", "Inconnu"),
                    "subject": _get_header(headers, "Subject", "(sans sujet)"),
                    "date": _get_header(headers, "Date", ""),
                    "snippet": details.get("snippet", ""),
                }
            )
        logger.info("Built %s Gmail message payloads", len(items))
        return items

    def clear_session(self, session_id: str | None) -> None:
        if session_id:
            logger.info("Clearing Gmail session %s", session_id)
            self._credentials_store.pop(session_id, None)
