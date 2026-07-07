import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

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

if "gmail_client" not in st.session_state:
    st.session_state["gmail_client"] = GmailClient()
if "workflow" not in st.session_state:
    st.session_state["workflow"] = Workflow()

gmail_client = st.session_state["gmail_client"]
workflow = st.session_state["workflow"]


def _render_login_form() -> None:
    st.markdown("### Connexion à votre boîte Gmail")
    st.info("Entrez votre adresse Gmail et un mot de passe d'application pour accéder à vos emails.")

    with st.expander("Comment obtenir un mot de passe d'application ?"):
        st.markdown("""
1. Allez sur [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Activez la **validation en 2 étapes** si ce n'est pas fait
3. Créez un mot de passe → nom : `Mail Manager`
4. Copiez le code à **16 caractères**
        """)

    with st.form("login_form"):
        email_input = st.text_input("Adresse Gmail", placeholder="exemple@gmail.com")
        password_input = st.text_input("Mot de passe d'application", type="password", placeholder="xxxx xxxx xxxx xxxx")
        submitted = st.form_submit_button("Se connecter", use_container_width=True)

    if submitted:
        if not email_input or not password_input:
            st.error("Veuillez remplir les deux champs.")
            return
        clean_password = password_input.replace(" ", "")
        with st.spinner("Connexion en cours..."):
            session_id = gmail_client.connect(email_input, clean_password)
        if session_id:
            st.session_state["session_id"] = session_id
            st.session_state["gmail_email"] = email_input
            st.session_state["gmail_password"] = clean_password
            st.rerun()
        else:
            st.error("Connexion échouée. Vérifiez votre email et votre mot de passe d'application.")


def _ensure_connection() -> Optional[str]:
    """Vérifie et rétablit la connexion IMAP si nécessaire."""
    session_id = st.session_state.get("session_id")
    if session_id and gmail_client.is_connected(session_id):
        return session_id

    email = st.session_state.get("gmail_email")
    password = st.session_state.get("gmail_password")
    if email and password:
        logger.info("Reconnecting IMAP for %s", email)
        new_session = gmail_client.connect(email, password)
        if new_session:
            st.session_state["session_id"] = new_session
            return new_session

    return None


def _load_emails(session_id: str, mail_limit: int) -> list:
    emails = gmail_client.get_recent_emails(session_id, max_results=mail_limit)
    processed = []
    progress = st.progress(0, text="Analyse IA en cours...")
    for i, em in enumerate(emails):
        processed.extend(workflow.run_for_batch([em]))
        progress.progress((i + 1) / len(emails), text=f"Analyse mail {i + 1} / {len(emails)}")
    progress.empty()
    return processed


def _parse_date(email: dict) -> datetime:
    raw = email.get("date", "")
    for fmt in ["%a, %d %b %Y %H:%M:%S %z", "%d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z"]:
        try:
            return datetime.strptime(raw[:31].strip(), fmt)
        except Exception:
            continue
    return datetime.now()


def _render_promo_card(email: dict) -> None:
    company = email.get("company") or email.get("from", "Inconnu")
    summary = email.get("summary", "")
    promo_code = email.get("promo_code", "")
    expiry = email.get("expiry_date", "")
    discount = email.get("discount", "")
    category = email.get("category", "")
    is_fake = email.get("is_fake_promo", False)
    unsubscribe_url = email.get("unsubscribe_url", "")
    message_id = email.get("message_id", "")

    with st.container(border=True):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"**{company}**")
            st.caption(f"{category}  •  {email.get('date', '')[:16]}")
        with col2:
            if discount:
                st.markdown(f"### {discount}")

        st.write(summary or email.get("subject", ""))

        info_cols = st.columns(2)
        with info_cols[0]:
            if promo_code:
                st.success(f"Code : `{promo_code}`")
        with info_cols[1]:
            if expiry:
                st.info(f"Expire : {expiry}")

        if is_fake:
            st.warning("Promo permanente ou trompeuse")

        # Boutons d'action
        action_cols = st.columns(2)
        with action_cols[0]:
            if message_id:
                gmail_url = f"https://mail.google.com/mail/u/0/#search/rfc822msgid:{message_id}"
                st.link_button("Voir dans Gmail", gmail_url, use_container_width=True)
        with action_cols[1]:
            if unsubscribe_url:
                st.link_button("Se désabonner", unsubscribe_url, use_container_width=True, type="secondary")


def _render_fiche(promos: list, period: str) -> None:
    now = datetime.now()

    if period == "Aujourd'hui":
        filtered = [e for e in promos if _parse_date(e).date() == now.date()]
        label = f"aujourd'hui ({now.strftime('%d/%m/%Y')})"
    elif period == "Cette semaine":
        start = now - timedelta(days=now.weekday())
        filtered = [e for e in promos if _parse_date(e).date() >= start.date()]
        label = f"cette semaine (depuis le {start.strftime('%d/%m/%Y')})"
    else:
        filtered = [e for e in promos if _parse_date(e).month == now.month and _parse_date(e).year == now.year]
        label = f"ce mois-ci ({now.strftime('%B %Y')})"

    st.markdown(f"### {len(filtered)} promo(s) reçue(s) {label}")

    if not filtered:
        st.info("Aucune promo sur cette période.")
        return

    # Tableau récapitulatif
    rows = []
    for e in filtered:
        message_id = e.get("message_id", "")
        gmail_url = f"https://mail.google.com/mail/u/0/#search/rfc822msgid:{message_id}" if message_id else ""
        rows.append({
            "Entreprise": e.get("company") or e.get("from", ""),
            "Promo": e.get("summary") or e.get("subject", ""),
            "Réduction": e.get("discount", ""),
            "Code promo": e.get("promo_code", ""),
            "Expire le": e.get("expiry_date", ""),
            "Catégorie": e.get("category", ""),
            "Ouvrir": gmail_url,
            "Se désabonner": e.get("unsubscribe_url", ""),
        })

    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Ouvrir": st.column_config.LinkColumn("Ouvrir", display_text="📧 Voir"),
            "Se désabonner": st.column_config.LinkColumn("Se désabonner", display_text="🚫 Stop"),
        }
    )

    st.markdown("---")
    st.markdown("#### Détail des promos")
    for e in filtered:
        _render_promo_card(e)


def main() -> None:
    st.set_page_config(page_title="Mail Manager — Promos", layout="wide")
    st.title("Mail Manager — Promos")

    session_id = _ensure_connection()

    if not session_id:
        _render_login_form()
        return

    # Barre du haut
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        st.success(f"Connecté : {session_id}")
    with col2:
        mail_limit = st.selectbox("Nb de mails", [20, 50, 100, 200], index=1, label_visibility="collapsed")
    with col3:
        if st.button("Déconnecter", use_container_width=True):
            gmail_client.clear_session(session_id)
            st.session_state.pop("session_id", None)
            st.session_state.pop("gmail_email", None)
            st.session_state.pop("gmail_password", None)
            st.session_state.pop("processed_emails", None)
            st.rerun()

    preferences = st.text_input(
        "Vos centres d'intérêt (facultatif)",
        placeholder="ex: tech, voyages, mode femme...",
        key="preferences"
    )
    workflow.preferences = preferences

    # Cache global d'analyses par message_id (persiste entre chargements)
    if "analysis_cache" not in st.session_state:
        st.session_state["analysis_cache"] = {}
    analysis_cache = st.session_state["analysis_cache"]

    # Chargement ou récupération depuis session
    cache_key = f"emails_{session_id}_{mail_limit}"
    force_reload = st.button("Charger / Actualiser les mails promos", use_container_width=True)

    if force_reload or cache_key not in st.session_state:
        with st.status("Chargement et analyse des mails promos...", expanded=True) as status:
            try:
                status.update(label="Lecture de l'onglet Promotions de Gmail...")
                emails = gmail_client.get_promo_emails(session_id, max_results=mail_limit)
                if not emails:
                    status.update(label="Aucun mail trouvé.", state="complete")
                    st.info("Aucun email trouvé dans l'onglet Promotions.")
                    return

                # Séparation cache / à analyser
                to_analyze = []
                processed = []
                for em in emails:
                    mid = em.get("message_id", "")
                    if mid and mid in analysis_cache:
                        processed.append({**em, **analysis_cache[mid]})
                    else:
                        to_analyze.append(em)

                cached_count = len(processed)
                if cached_count:
                    status.update(label=f"{cached_count} mails déjà en cache — analyse de {len(to_analyze)} nouveaux...")
                else:
                    status.update(label=f"{len(emails)} mails à analyser...")

                # Batch de 8 mails par appel API
                BATCH_SIZE = 8
                progress = st.progress(0, text="Analyse IA en cours...")
                total = len(to_analyze)
                for batch_start in range(0, total, BATCH_SIZE):
                    batch = to_analyze[batch_start:batch_start + BATCH_SIZE]
                    analyzed_batch = workflow.run_for_batch(batch)
                    for em, an in zip(batch, analyzed_batch):
                        mid = em.get("message_id", "")
                        if mid:
                            analysis_cache[mid] = {k: v for k, v in an.items() if k not in em}
                        processed.append(an)
                    done = min(batch_start + BATCH_SIZE, total)
                    progress.progress(done / total if total else 1.0,
                                      text=f"Analyse {done} / {total}")
                progress.empty()

                st.session_state[cache_key] = processed
                status.update(
                    label=f"{len(processed)} mails traités ({cached_count} depuis cache, {len(to_analyze)} analysés).",
                    state="complete"
                )
            except Exception as exc:
                logger.exception("Erreur chargement mails.")
                status.update(label="Erreur.", state="error")
                st.error(str(exc))
                return

    processed = st.session_state.get(cache_key, [])
    if not processed:
        st.info("Cliquez sur 'Charger / Actualiser les mails' pour démarrer.")
        return

    promos = [e for e in processed if e.get("is_promo")]

    top_cols = st.columns([2, 1, 1])
    with top_cols[0]:
        st.caption(f"{len(promos)} promo(s) sur {len(processed)} mails — cache : {len(analysis_cache)}")
    with top_cols[1]:
        if st.button("Vider cache IA", use_container_width=True):
            st.session_state["analysis_cache"] = {}
            for key in list(st.session_state.keys()):
                if key.startswith("emails_"):
                    del st.session_state[key]
            st.rerun()
    with top_cols[2]:
        st.page_link("pages/1_Chat_Promos.py", label="💬 Ouvrir le chat", use_container_width=True)

    if not promos:
        st.info("Aucune promo détectée parmi les mails chargés.")
        return

    tab1, tab2 = st.tabs(["Fiche Promos", "Par catégorie"])

    with tab1:
        period = st.radio("Période", ["Aujourd'hui", "Cette semaine", "Ce mois"], horizontal=True)
        _render_fiche(promos, period)

    with tab2:
        cats = sorted({e.get("category", "autre") for e in promos})
        selected = st.selectbox("Catégorie", cats)
        cat_promos = [e for e in promos if e.get("category") == selected]
        st.caption(f"{len(cat_promos)} promo(s) dans '{selected}'")
        for e in cat_promos:
            _render_promo_card(e)


if __name__ == "__main__":
    main()
