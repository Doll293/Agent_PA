import imaplib
import email
import re
from email.header import decode_header
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def _decode_str(value: str) -> str:
    parts = decode_header(value or "")
    result = []
    for part, enc in parts:
        if isinstance(part, bytes):
            result.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            result.append(part)
    return "".join(result)


def _extract_unsubscribe(header_value: str) -> tuple:
    """Retourne (unsubscribe_url, unsubscribe_email) depuis le header List-Unsubscribe."""
    if not header_value:
        return "", ""
    url = ""
    mailto = ""
    matches = re.findall(r"<([^>]+)>", header_value)
    for m in matches:
        if m.startswith("mailto:") and not mailto:
            mailto = m.replace("mailto:", "")
        elif m.startswith("http") and not url:
            url = m
    return url, mailto


class GmailClient:
    IMAP_HOST = "imap.gmail.com"
    IMAP_PORT = 993

    def __init__(self) -> None:
        self._sessions: dict = {}

    def is_configured(self) -> bool:
        return True

    def get_configuration_error(self) -> Optional[str]:
        return None

    def connect(self, email_address: str, app_password: str) -> Optional[str]:
        try:
            mail = imaplib.IMAP4_SSL(self.IMAP_HOST, self.IMAP_PORT)
            mail.login(email_address, app_password)
            session_id = email_address
            self._sessions[session_id] = mail
            logger.info("IMAP connection successful for %s", email_address)
            return session_id
        except imaplib.IMAP4.error as e:
            logger.error("IMAP login failed: %s", e)
            return None

    def is_connected(self, session_id: Optional[str]) -> bool:
        if not session_id or session_id not in self._sessions:
            return False
        try:
            self._sessions[session_id].noop()
            return True
        except Exception:
            return False

    def clear_session(self, session_id: Optional[str]) -> None:
        if session_id and session_id in self._sessions:
            try:
                self._sessions[session_id].logout()
            except Exception:
                pass
            del self._sessions[session_id]

    def get_promo_emails(self, session_id: Optional[str], max_results: int = 30) -> list:
        """Recupere uniquement les mails de l'onglet Promotions de Gmail via X-GM-RAW."""
        if not session_id or session_id not in self._sessions:
            return []

        mail = self._sessions[session_id]
        try:
            mail.select("INBOX")
            typ, data = mail.search(None, 'X-GM-RAW', '"category:promotions"')
            if typ != "OK":
                logger.warning("X-GM-RAW search failed, fallback to ALL")
                _, data = mail.search(None, "ALL")

            ids = data[0].split()
            recent_ids = ids[-max_results:][::-1]
            logger.info("Found %s promotion emails (fetching last %s)", len(ids), len(recent_ids))

            return self._fetch_emails(mail, recent_ids)
        except Exception as e:
            logger.error("Failed to fetch promo emails: %s", e)
            return []

    def get_recent_emails(self, session_id: Optional[str], max_results: int = 10) -> list:
        if not session_id or session_id not in self._sessions:
            return []

        mail = self._sessions[session_id]
        try:
            mail.select("INBOX")
            _, data = mail.search(None, "ALL")
            ids = data[0].split()
            recent_ids = ids[-max_results:][::-1]
            return self._fetch_emails(mail, recent_ids)
        except Exception as e:
            logger.error("Failed to fetch emails: %s", e)
            return []

    def _fetch_emails(self, mail, msg_ids: list) -> list:
        emails = []
        for msg_id in msg_ids:
            try:
                _, msg_data = mail.fetch(msg_id, "(RFC822)")
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)

                subject = _decode_str(msg.get("Subject", "(sans sujet)"))
                sender = _decode_str(msg.get("From", "Inconnu"))
                date = msg.get("Date", "")
                snippet = self._get_snippet(msg)
                unsubscribe_url, unsubscribe_email = _extract_unsubscribe(
                    msg.get("List-Unsubscribe", "")
                )
                message_id = msg.get("Message-ID", "").strip("<>")

                emails.append({
                    "id": msg_id.decode() if isinstance(msg_id, bytes) else str(msg_id),
                    "from": sender,
                    "subject": subject,
                    "date": date,
                    "snippet": snippet,
                    "unsubscribe_url": unsubscribe_url,
                    "unsubscribe_email": unsubscribe_email,
                    "message_id": message_id,
                })
            except Exception as e:
                logger.error("Failed to parse message %s: %s", msg_id, e)
        return emails

    def _get_snippet(self, msg) -> str:
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                if ctype == "text/plain" and not part.get("Content-Disposition"):
                    payload = part.get_payload(decode=True)
                    if payload:
                        body = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
                        break
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                body = payload.decode(msg.get_content_charset() or "utf-8", errors="replace")
        return body[:500].replace("\n", " ").replace("\r", "").strip()
