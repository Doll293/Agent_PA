import logging
import sys
from pathlib import Path
from urllib.parse import urlencode

import streamlit as st

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mail_manager.config import settings
from mail_manager.gmail_client import GmailClient
from mail_manager.workflow import Workflow


logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

gmail_client = GmailClient()
workflow = Workflow()


def _sync_credentials_from_session(session_id: str) -> None:
    raw_credentials = st.session_state.get("gmail_credentials")
    gmail_client.restore_credentials(session_id, raw_credentials)


def _get_session_id() -> str:
    session_id = st.session_state.get("gmail_session_id")
    if not session_id:
        session_id = gmail_client.create_session_id()
        st.session_state["gmail_session_id"] = session_id
    return session_id


def _get_callback_url() -> str:
    params = st.query_params
    if not params:
        return settings.streamlit_redirect_uri

    raw_params = {}
    for key, value in params.items():
        if isinstance(value, list):
            raw_params[key] = value[-1]
        else:
            raw_params[key] = value
    return f"{settings.streamlit_redirect_uri}?{urlencode(raw_params)}"


def _clear_query_params() -> None:
    st.query_params.clear()


def _handle_oauth_callback(session_id: str) -> None:
    if "code" not in st.query_params or "state" not in st.query_params:
        return

    returned_state = st.query_params.get("state")
    if isinstance(returned_state, list):
        returned_state = returned_state[-1]
    if not returned_state:
        st.session_state["last_error"] = "Etat OAuth Gmail introuvable."
        logger.error("OAuth callback received without state parameter.")
        _clear_query_params()
        return

    # Streamlit peut recreer une session au retour de Google.
    # On reutilise donc le state OAuth comme identifiant de session stable.
    st.session_state["gmail_oauth_state"] = returned_state
    st.session_state["gmail_session_id"] = returned_state

    try:
        gmail_client.fetch_token_from_callback(
            state=returned_state,
            full_callback_url=_get_callback_url(),
            session_id=returned_state,
            redirect_uri=settings.streamlit_redirect_uri,
        )
        st.session_state["gmail_credentials"] = gmail_client.serialize_credentials(returned_state)
        logger.info("Gmail OAuth callback completed successfully.")
    except Exception as exc:
        logger.exception("Gmail OAuth callback failed.")
        st.session_state["last_error"] = str(exc)
    finally:
        st.session_state.pop("gmail_oauth_state", None)
        _clear_query_params()
        st.rerun()


def _render_email_card(email: dict[str, str]) -> None:
    with st.container(border=True):
        st.markdown(f"**{email['from']}**")
        st.caption(email["date"])
        st.subheader(email["subject"])
        st.write(email["snippet"])
        st.write(f"Categorie : **{email['category']}**")
        st.write(f"Suggestion : **{email['suggestion']}**")
        col1, col2 = st.columns(2)
        with col1:
            st.caption("Sujet envoye au traitement")
            st.write(email["anonymized_subject"])
        with col2:
            st.caption("Extrait envoye au traitement")
            st.write(email["anonymized_snippet"])


def _filter_emails(emails: list[dict[str, str]], selected_category: str, search_text: str) -> list[dict[str, str]]:
    filtered = emails

    if selected_category != "Toutes":
        filtered = [email for email in filtered if email["category"] == selected_category]

    normalized_search = search_text.strip().lower()
    if not normalized_search:
        return filtered

    return [
        email
        for email in filtered
        if normalized_search in email["from"].lower()
        or normalized_search in email["subject"].lower()
        or normalized_search in email["snippet"].lower()
        or normalized_search in email["category"].lower()
    ]


def main() -> None:
    st.set_page_config(page_title="Mail Manager", layout="centered")
    st.title("Mail Manager")
    st.write(
        "Prototype simple avec Gmail en lecture seule, anonymisation avant traitement "
        "et classification locale."
    )

    session_id = _get_session_id()
    _sync_credentials_from_session(session_id)
    _handle_oauth_callback(session_id)
    session_id = _get_session_id()
    _sync_credentials_from_session(session_id)

    error_message = st.session_state.pop("last_error", None)
    configuration_error = gmail_client.get_configuration_error()

    if configuration_error:
        logger.warning("Application misconfigured: %s", configuration_error)
        st.warning(configuration_error)
        return

    if not gmail_client.is_connected(session_id):
        st.info("Connexion Gmail requise pour lire les 10 derniers messages.")
        auth_url, state = gmail_client.build_auth_url(redirect_uri=settings.streamlit_redirect_uri)
        st.session_state["gmail_oauth_state"] = state
        st.session_state["gmail_session_id"] = state
        st.link_button("Se connecter avec Gmail", auth_url, use_container_width=True)
        with st.expander("Debug OAuth"):
            st.code(settings.streamlit_redirect_uri)
            st.caption("Cette valeur doit etre strictement identique dans Google Cloud > Authorized redirect URIs.")
        if error_message:
            logger.error("Stored UI error before login: %s", error_message)
            st.error(error_message)
        return

    col1, col2 = st.columns([3, 1])
    with col1:
        st.success("Connexion Gmail active pour cette session.")
    with col2:
        if st.button("Deconnecter", use_container_width=True):
            gmail_client.clear_session(session_id)
            st.session_state.pop("gmail_credentials", None)
            st.session_state.pop("gmail_oauth_state", None)
            st.rerun()

    action_col1, action_col2, action_col3 = st.columns([2, 2, 1])
    with action_col1:
        if st.button("Actualiser les mails", use_container_width=True):
            st.rerun()
    with action_col2:
        st.caption(f"{settings.mail_max_results} derniers mails lus au maximum")
    with action_col3:
        use_model = st.toggle("Modele IA", value=True, key="use_model")

    if error_message:
        logger.error("Stored UI error after login: %s", error_message)
        st.error(error_message)

    with st.status("Chargement des mails...", expanded=False) as status:
        try:
            status.update(label="Lecture Gmail en cours...")
            mail_limit = st.session_state.get("mail_limit", settings.mail_max_results)
            emails = gmail_client.get_recent_emails(session_id, max_results=mail_limit)
        except Exception as exc:
            logger.exception("Gmail mail retrieval failed.")
            status.update(label="Erreur lors de la lecture.", state="error")
            st.error(str(exc))
            return

        if not emails:
            logger.info("No emails returned from Gmail API.")
            status.update(label="Aucun mail trouve.", state="complete")
            st.info(f"Aucun email trouve dans les {settings.mail_max_results} derniers messages.")
            return

        logger.info("Retrieved %s emails from Gmail API.", len(emails))
        status.update(label=f"Classification de {len(emails)} mails...")
        processed_emails = []
        progress = st.progress(0, text="Classification en cours...")
        for i, email in enumerate(emails):
            processed_emails.extend(workflow.run_for_batch([email], use_model=use_model))
            progress.progress((i + 1) / len(emails), text=f"Mail {i + 1} / {len(emails)}")
        progress.empty()
        status.update(label=f"{len(emails)} mails charges.", state="complete")
    available_categories = ["Toutes"] + sorted({email["category"] for email in processed_emails})

    st.subheader("Filtres")
    filter_col1, filter_col2 = st.columns([1, 2])
    with filter_col1:
        selected_category = st.selectbox("Categorie", available_categories, index=0)
    with filter_col2:
        search_text = st.text_input("Recherche", placeholder="expediteur, sujet, extrait...")

    filtered_emails = _filter_emails(processed_emails, selected_category, search_text)
    st.caption(f"{len(filtered_emails)} mail(s) affiche(s) sur {len(processed_emails)}")

    if not filtered_emails:
        st.info("Aucun mail ne correspond au filtre actuel.")
        return

    for email in filtered_emails:
        _render_email_card(email)

    if len(emails) == mail_limit:
        if st.button("Voir plus", use_container_width=True):
            st.session_state["mail_limit"] = mail_limit + settings.mail_max_results
            st.rerun()


if __name__ == "__main__":
    main()
