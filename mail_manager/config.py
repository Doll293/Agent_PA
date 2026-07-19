import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _enable_local_oauth_http(redirect_uri: str) -> None:
    parsed = urlparse(redirect_uri)
    if parsed.scheme != "http":
        return
    if parsed.hostname not in {"localhost", "127.0.0.1"}:
        return
    os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")


class Settings:
    def __init__(self) -> None:
        self.gmail_credentials_file = BASE_DIR / os.getenv("GMAIL_CREDENTIALS_FILE", "credentials.json")
        self.google_redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8501")
        self.streamlit_redirect_uri = os.getenv("STREAMLIT_REDIRECT_URI", self.google_redirect_uri)
        _enable_local_oauth_http(self.google_redirect_uri)
        _enable_local_oauth_http(self.streamlit_redirect_uri)
        self.gmail_scope = "https://www.googleapis.com/auth/gmail.readonly"
        self.session_secret = os.getenv("SESSION_SECRET", "change-me")
        self.mail_preview_length = int(os.getenv("MAIL_PREVIEW_LENGTH", "220"))
        self.mail_max_results = int(os.getenv("MAIL_MAX_RESULTS", "10"))
        self.mail_retention_days = int(os.getenv("MAIL_RETENTION_DAYS", "30"))
        self.debug = os.getenv("DEBUG", "false").strip().lower() in {"1", "true", "yes", "on"}
        self.groq_api_key = os.getenv("GROQ_API_KEY", "")
        self.groq_model = os.getenv("GROQ_MODEL", "llama3-8b-8192")
        self.gmail_email = os.getenv("GMAIL_EMAIL", "")
        self.gmail_app_password = os.getenv("GMAIL_APP_PASSWORD", "")
        self.whatsapp_phone = os.getenv("WHATSAPP_PHONE", "")
        self.callmebot_api_key = os.getenv("CALLMEBOT_API_KEY", "")
        self.azure_storage_connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
        self.azure_storage_container = os.getenv("AZURE_STORAGE_CONTAINER", "mails-anonymized")
        self.azure_storage_enabled = os.getenv("AZURE_STORAGE_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


settings = Settings()
