import re

from mail_manager.config import settings


EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(r"(?:(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?){2,5}\d{2,4})")
URL_RE = re.compile(r"(https?://\S+|www\.\S+)")
WHITESPACE_RE = re.compile(r"\s+")


def clean_text(value: str) -> str:
    return WHITESPACE_RE.sub(" ", value or "").strip()


def anonymize_text(value: str, max_length: int) -> str:
    text = clean_text(value)
    text = EMAIL_RE.sub("[email masque]", text)
    text = PHONE_RE.sub("[telephone masque]", text)
    text = URL_RE.sub("[lien masque]", text)
    if len(text) > max_length:
        text = text[: max_length - 3].rstrip() + "..."
    return text


def anonymize_mail(subject: str, snippet: str, sender: str = "", body: str = "") -> dict[str, str]:
    return {
        "sender": anonymize_text(sender, max_length=120),
        "subject": anonymize_text(subject, max_length=160),
        "snippet": anonymize_text(snippet, max_length=settings.mail_preview_length),
        "body": anonymize_text(body, max_length=settings.mail_body_max_chars),
    }
