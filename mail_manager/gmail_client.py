import base64
import re
from typing import Any
from uuid import uuid4
import logging

from bs4 import BeautifulSoup
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from mail_manager.config import settings

logger = logging.getLogger(__name__)

UNSUBSCRIBE_HTTP_RE = re.compile(r"<(https?://[^>]+)>")


def _get_header(headers: list[dict[str, str]], name: str, default: str = "") -> str:
    wanted = name.lower()
    for header in headers:
        if header.get("name", "").lower() == wanted:
            return header.get("value", default)
    return default


def _decode_body_data(data: str) -> str:
    padded = data + "=" * (-len(data) % 4)
    try:
        return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")
    except Exception:
        logger.warning("Failed to decode a mail body part.")
        return ""


def _walk_parts(payload: dict[str, Any]) -> tuple[str, str]:
    """Retourne (text_plain, text_html) en parcourant recursivement les parts MIME."""
    plain, html = "", ""
    mime = payload.get("mimeType", "")
    data = payload.get("body", {}).get("data")

    if data:
        if mime == "text/plain":
            plain += _decode_body_data(data)
        elif mime == "text/html":
            html += _decode_body_data(data)

    for part in payload.get("parts", []) or []:
        sub_plain, sub_html = _walk_parts(part)
        plain += sub_plain
        html += sub_html
    return plain, html


def _extract_body_text(payload: dict[str, Any], max_chars: int) -> str:
    plain, html = _walk_parts(payload)
    text = plain.strip()
    if not text and html:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()
        text = soup.get_text(separator=" ")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def _extract_unsubscribe_link(headers: list[dict[str, str]]) -> str:
    """Extrait un lien http(s) du header List-Unsubscribe (ignore les mailto:)."""
    raw = _get_header(headers, "List-Unsubscribe", "")
    if not raw:
        return ""
    match = UNSUBSCRIBE_HTTP_RE.search(raw)
    return match.group(1) if match else ""


class GmailClient:
    def __init__(self) -> None:
        self.provider_label = "Gmail"
        self.scopes = [settings.gmail_scope]
        self._credentials_store: dict[str, Credentials] = {}
        self.last_fetch_strategy = ""

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

    def get_promo_emails(self, session_id: str | None, max_results: int = 10) -> list[dict[str, Any]]:
        """Lit les mails de l'onglet Promotions avec leur corps complet (tronque)."""
        creds = self.load_credentials(session_id)
        if not creds:
            logger.warning("No Gmail credentials found for session %s", session_id)
            return []

        logger.info("Fetching up to %s promo messages for session %s", max_results, session_id)
        service = build("gmail", "v1", credentials=creds, cache_discovery=False)

        # Cascade de strategies : certains comptes (Workspace, onglets desactives)
        # n'ont pas de categorie Promotions. On tente du plus precis au plus large.
        strategies: list[tuple[str, dict[str, Any]]] = [
            ("label CATEGORY_PROMOTIONS", {"labelIds": ["CATEGORY_PROMOTIONS"]}),
            ("requete category:promotions", {"q": "category:promotions"}),
            ("heuristique unsubscribe", {"q": "unsubscribe -in:sent -in:chat"}),
        ]

        messages: list[dict[str, Any]] = []
        self.last_fetch_strategy = ""
        for strategy_name, params in strategies:
            results = (
                service.users()
                .messages()
                .list(userId="me", maxResults=max_results, **params)
                .execute()
            )
            messages = results.get("messages", [])
            logger.info("Strategy '%s' returned %s message ids", strategy_name, len(messages))
            if messages:
                self.last_fetch_strategy = strategy_name
                break

        items: list[dict[str, Any] | None] = [None] * len(messages)

        def _on_message(request_id: str, response: Any, exception: Any) -> None:
            if exception:
                logger.error("Failed to fetch message %s: %s", request_id, exception)
                return
            idx = int(request_id)
            payload = response.get("payload", {})
            headers = payload.get("headers", [])
            message_id = response.get("id", "")
            items[idx] = {
                "id": message_id,
                "from": _get_header(headers, "From", "Inconnu"),
                "subject": _get_header(headers, "Subject", "(sans sujet)"),
                "date": _get_header(headers, "Date", ""),
                "snippet": response.get("snippet", ""),
                "body_text": _extract_body_text(payload, settings.mail_body_max_chars),
                "unsubscribe_link": _extract_unsubscribe_link(headers),
                "gmail_link": f"https://mail.google.com/mail/u/0/#all/{message_id}",
            }

        batch = service.new_batch_http_request(callback=_on_message)
        for i, message in enumerate(messages):
            batch.add(
                service.users().messages().get(userId="me", id=message["id"], format="full"),
                request_id=str(i),
            )
        batch.execute()

        result = [item for item in items if item is not None]
        logger.info("Built %s promo message payloads", len(result))
        return result

    def clear_session(self, session_id: str | None) -> None:
        if session_id:
            logger.info("Clearing Gmail session %s", session_id)
            self._credentials_store.pop(session_id, None)
