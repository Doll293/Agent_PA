import logging
import sys
from datetime import date, datetime
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


def _expiry_info(expiry_date: str) -> tuple[str, str] | None:
    """Retourne (texte, couleur streamlit) pour la date d'expiration, ou None."""
    if not expiry_date:
        return None
    try:
        expiry = datetime.strptime(expiry_date, "%Y-%m-%d").date()
    except ValueError:
        return None

    days = (expiry - date.today()).days
    if days < 0:
        return ("Offre expiree", "gray")
    if days == 0:
        return ("Expire aujourd'hui", "red")
    if days <= 3:
        return (f"Expire dans {days} jour(s)", "red")
    if days <= 7:
        return (f"Expire dans {days} jours", "orange")
    return (f"Expire le {expiry.strftime('%d/%m/%Y')}", "green")


def _render_email_card(email: dict) -> None:
    with st.container(border=True):
        header_col, score_col = st.columns([4, 1])
        with header_col:
            st.markdown(f"**{email['from']}**")
            st.caption(email["date"])
        with score_col:
            st.metric("Pertinence", f"{email['relevance_score']}/10")

        st.subheader(email["subject"])
        st.write(email["summary"])

        badges = [f":blue-badge[{email['category']}]"]
        expiry = _expiry_info(email.get("expiry_date", ""))
        if expiry:
            text, color = expiry
            badges.append(f":{color}-badge[{text}]")
        if email.get("is_fake_promo"):
            badges.append(":violet-badge[Promo permanente suspecte]")
        st.markdown(" ".join(badges))

        if email.get("promo_code"):
            st.caption("Code promo")
            st.code(email["promo_code"], language=None)

        link_col, unsub_col = st.columns(2)
        with link_col:
            st.link_button("Ouvrir dans Gmail", email["gmail_link"], use_container_width=True)
        with unsub_col:
            if email.get("unsubscribe_link"):
                st.link_button("Se desabonner", email["unsubscribe_link"], use_container_width=True)

        with st.expander("Donnees envoyees au LLM (anonymisees)"):
            st.write(f"Expediteur : {email['anonymized_sender']}")
            st.write(f"Sujet : {email['anonymized_subject']}")
            st.write(email["anonymized_snippet"])


def _filter_emails(emails: list[dict], selected_categories: list[str], search_text: str) -> list[dict]:
    filtered = emails

    if selected_categories:
        filtered = [email for email in filtered if email["category"] in selected_categories]

    normalized_search = search_text.strip().lower()
    if normalized_search:
        filtered = [
            email
            for email in filtered
            if normalized_search in email["from"].lower()
            or normalized_search in email["subject"].lower()
            or normalized_search in email["summary"].lower()
            or normalized_search in email["category"].lower()
        ]

    return sorted(filtered, key=lambda e: e["relevance_score"], reverse=True)


def _run_analysis(session_id: str, preferences: str, mail_limit: int) -> None:
    with st.status("Analyse des promotions...", expanded=False) as status:
        try:
            status.update(label="Lecture des mails Promotions...")
            emails = gmail_client.get_promo_emails(session_id, max_results=mail_limit)
        except Exception as exc:
            logger.exception("Gmail promo retrieval failed.")
            status.update(label="Erreur lors de la lecture Gmail.", state="error")
            st.error(str(exc))
            return

        if not emails:
            status.update(label="Aucun mail trouve.", state="complete")
            st.session_state["processed_emails"] = []
            st.info("Aucun mail dans l'onglet Promotions.")
            return

        status.update(label=f"Analyse LLM de {len(emails)} mails (un seul appel)...")
        try:
            processed = workflow.run_for_batch(emails, preferences=preferences)
        except Exception as exc:
            logger.exception("LLM analysis failed.")
            status.update(label="Erreur d'analyse LLM.", state="error")
            st.error(str(exc))
            return

        st.session_state["processed_emails"] = processed
        st.session_state["analyzed_count"] = len(emails)
        status.update(label=f"{len(processed)} promotions analysees.", state="complete")


def main() -> None:
    st.set_page_config(page_title="Mail Manager", layout="centered")
    st.title("Mail Manager - Promotions")
    st.write(
        "Lit vos mails de promotion Gmail en lecture seule, les anonymise, "
        "puis les resume et les classe selon vos envies avec un LLM (Groq)."
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
        st.info("Connexion Gmail requise pour lire vos mails de promotion.")
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
            for key in ("gmail_credentials", "gmail_oauth_state", "processed_emails", "analyzed_count"):
                st.session_state.pop(key, None)
            st.rerun()

    if error_message:
        logger.error("Stored UI error after login: %s", error_message)
        st.error(error_message)

    # --- Preferences utilisateur ---
    st.subheader("Vos envies")
    preferences = st.text_area(
        "Decrivez ce qui vous interesse en ce moment",
        placeholder="Ex : je cherche des promos tech (ecouteurs, SSD), des billets de train et des offres de restaurants.",
        key="preferences",
    )

    mail_limit = st.session_state.get("mail_limit", settings.mail_max_results)
    if st.button("Analyser mes promotions", type="primary", use_container_width=True):
        _run_analysis(session_id, preferences, mail_limit)

    processed_emails = st.session_state.get("processed_emails")
    if processed_emails is None:
        st.caption(f"Modele LLM : {settings.groq_model} - {mail_limit} mails analyses au maximum")
        return
    if not processed_emails:
        return

    # --- Filtres ---
    st.subheader("Filtres")
    available_categories = sorted({email["category"] for email in processed_emails})
    filter_col1, filter_col2 = st.columns([1, 1])
    with filter_col1:
        selected_categories = st.multiselect("Categories", available_categories, default=[])
    with filter_col2:
        search_text = st.text_input("Recherche", placeholder="expediteur, sujet, resume...")

    filtered_emails = _filter_emails(processed_emails, selected_categories, search_text)
    st.caption(f"{len(filtered_emails)} promo(s) affichee(s) sur {len(processed_emails)}, triees par pertinence")

    if not filtered_emails:
        st.info("Aucune promo ne correspond au filtre actuel.")
        return

    for email in filtered_emails:
        _render_email_card(email)

    if st.session_state.get("analyzed_count", 0) == mail_limit:
        if st.button("Analyser plus de mails", use_container_width=True):
            st.session_state["mail_limit"] = mail_limit + settings.mail_max_results
            _run_analysis(session_id, preferences, mail_limit + settings.mail_max_results)
            st.rerun()


if __name__ == "__main__":
    main()
