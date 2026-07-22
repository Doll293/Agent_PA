"""Mail Manager — application NiceGUI (remplacement de la stack Streamlit)."""
from __future__ import annotations

import logging
import re
import secrets
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from nicegui import app, run, ui

from mail_manager.config import settings
from mail_manager.gmail_client import GmailClient
from mail_manager.workflow import Workflow

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ============================================================
# État partagé (module-level singletons)
# ============================================================

_gmail_client = GmailClient()
_user_workflows: dict[str, Workflow] = {}
_user_emails: dict[str, list[dict]] = {}  # {gmail_email: [enriched_mails]}


def _html(content: str):
    """Wrapper ui.html avec sanitize=False (NiceGUI 3.x requiert le kwarg)."""
    return ui.html(content, sanitize=False)


def _get_workflow(user_email: str) -> Workflow:
    if user_email not in _user_workflows:
        _user_workflows[user_email] = Workflow(user_email=user_email)
    return _user_workflows[user_email]


# ============================================================
# Palette et styles globaux
# ============================================================

PRIMARY = "#F97316"           # orange chaud
PRIMARY_DARK = "#EA580C"
ACCENT = "#EC4899"            # rose
SUCCESS = "#059669"
WARNING = "#D97706"
DANGER = "#DC2626"
BG_DARK = "#FFFFFF"           # (nom historique, valeur = fond crème pour bordures graphiques)
BG_CARD = "#FFFFFF"
BORDER = "rgba(0, 0, 0, 0.08)"
TEXT_MUTED = "#78716C"        # warm gray
TEXT_MAIN = "#1F2937"         # charcoal

PALETTE = [
    "#F97316", "#EC4899", "#F59E0B", "#8B5CF6",
    "#EF4444", "#10B981", "#3B82F6", "#14B8A6",
    "#D97706", "#DB2777", "#A855F7", "#84CC16",
]


GLOBAL_CSS = f"""
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, .q-page, .nicegui-content {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    background: linear-gradient(135deg, #FFF7ED 0%, #FEF3E2 50%, #FCE7F3 100%) !important;
    color: {TEXT_MAIN};
    min-height: 100vh;
}}
.nicegui-content {{
    padding: 0 !important;
}}

/* Cartes */
.mm-card {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 18px;
    padding: 1.4rem 1.6rem;
    box-shadow: 0 4px 16px rgba(249, 115, 22, 0.06);
    transition: all 0.3s ease;
}}
.mm-card:hover {{
    border-color: rgba(249, 115, 22, 0.3);
    transform: translateY(-2px);
    box-shadow: 0 12px 32px rgba(249, 115, 22, 0.12);
}}
.mm-card--flat {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 18px;
    padding: 1.4rem 1.6rem;
    box-shadow: 0 4px 16px rgba(249, 115, 22, 0.06);
}}

/* Titres */
.mm-title {{
    font-weight: 800;
    font-size: 2.2rem;
    letter-spacing: -0.02em;
    background: linear-gradient(90deg, {PRIMARY} 0%, {ACCENT} 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0;
}}
.mm-subtitle {{
    color: {TEXT_MUTED};
    font-size: 1rem;
    margin-top: 0.2rem;
}}

/* Header sticky */
.mm-header {{
    background: rgba(255, 255, 255, 0.85);
    backdrop-filter: blur(14px);
    border-bottom: 1px solid {BORDER};
    padding: 0.9rem 2rem;
    position: sticky;
    top: 0;
    z-index: 50;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.03);
}}
.mm-nav-link {{
    color: {TEXT_MUTED};
    font-weight: 500;
    padding: 0.4rem 0.9rem;
    border-radius: 10px;
    cursor: pointer;
    transition: all 0.2s;
    text-decoration: none;
}}
.mm-nav-link:hover {{
    background: rgba(249, 115, 22, 0.08);
    color: {PRIMARY_DARK};
}}
.mm-nav-link--active {{
    background: linear-gradient(135deg, rgba(249, 115, 22, 0.15), rgba(236, 72, 153, 0.10));
    color: {PRIMARY_DARK};
    border: 1px solid rgba(249, 115, 22, 0.30);
}}

/* Boutons primaires */
.mm-btn-primary {{
    background: linear-gradient(135deg, {PRIMARY} 0%, {ACCENT} 100%) !important;
    color: white !important;
    border-radius: 12px !important;
    font-weight: 600 !important;
    padding: 0.55rem 1.4rem !important;
    box-shadow: 0 4px 14px rgba(249, 115, 22, 0.35);
    transition: all 0.25s ease;
    text-transform: none !important;
}}
.mm-btn-primary:hover {{
    transform: translateY(-2px);
    box-shadow: 0 8px 22px rgba(249, 115, 22, 0.5);
    filter: brightness(1.05);
}}
.mm-btn-ghost {{
    background: rgba(255, 255, 255, 0.6) !important;
    color: {TEXT_MAIN} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 10px !important;
    font-weight: 500 !important;
    text-transform: none !important;
}}
.mm-btn-ghost:hover {{
    background: rgba(249, 115, 22, 0.08) !important;
    border-color: rgba(249, 115, 22, 0.3) !important;
    color: {PRIMARY_DARK} !important;
}}

/* Inputs */
.mm-input .q-field__control {{
    background: rgba(255, 255, 255, 0.9) !important;
    border-radius: 12px !important;
    color: {TEXT_MAIN} !important;
}}
.mm-input .q-field__native, .mm-input input, .mm-input textarea {{
    color: {TEXT_MAIN} !important;
}}
.mm-input .q-field__label {{
    color: {TEXT_MUTED} !important;
}}
.mm-input input[type="date"] {{
    color: {TEXT_MAIN} !important;
    color-scheme: light !important;
}}

/* KPI metric */
.mm-kpi {{
    background: linear-gradient(135deg, #FFFFFF 0%, #FEF3E2 100%);
    border: 1px solid rgba(249, 115, 22, 0.15);
    border-radius: 18px;
    padding: 1.2rem 1.4rem;
    box-shadow: 0 4px 14px rgba(249, 115, 22, 0.08);
    transition: all 0.3s;
}}
.mm-kpi:hover {{
    transform: translateY(-3px);
    border-color: rgba(249, 115, 22, 0.4);
    box-shadow: 0 12px 30px rgba(249, 115, 22, 0.18);
}}
.mm-kpi-label {{
    color: {TEXT_MUTED};
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}}
.mm-kpi-value {{
    color: {TEXT_MAIN};
    font-weight: 800;
    font-size: 2rem;
    margin-top: 0.2rem;
}}
.mm-kpi-delta {{
    color: {TEXT_MUTED};
    font-size: 0.85rem;
    margin-top: 0.15rem;
}}

/* Badges */
.mm-badge {{
    display: inline-block;
    padding: 0.2rem 0.65rem;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
}}
.mm-badge--success {{ background: rgba(5, 150, 105, 0.12); color: {SUCCESS}; }}
.mm-badge--warning {{ background: rgba(217, 119, 6, 0.12); color: {WARNING}; }}
.mm-badge--danger {{ background: rgba(220, 38, 38, 0.12); color: {DANGER}; }}
.mm-badge--info {{ background: rgba(249, 115, 22, 0.12); color: {PRIMARY_DARK}; }}

/* Chat */
.mm-chat-user {{
    background: linear-gradient(135deg, rgba(249, 115, 22, 0.12), rgba(236, 72, 153, 0.08));
    border: 1px solid rgba(249, 115, 22, 0.25);
    border-radius: 16px 16px 4px 16px;
    padding: 0.9rem 1.1rem;
    margin-bottom: 0.8rem;
    max-width: 80%;
    margin-left: auto;
    color: {TEXT_MAIN};
}}
.mm-chat-assistant {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 16px 16px 16px 4px;
    padding: 0.9rem 1.1rem;
    margin-bottom: 0.8rem;
    max-width: 80%;
    color: {TEXT_MAIN};
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}}
.mm-chat-assistant a {{ color: {PRIMARY_DARK}; text-decoration: underline; }}
.mm-chat-assistant code {{
    background: rgba(249, 115, 22, 0.10);
    color: {PRIMARY_DARK};
    padding: 0.15rem 0.4rem;
    border-radius: 6px;
    font-family: 'SF Mono', Menlo, monospace;
    font-size: 0.9em;
}}

/* Tabs Quasar en clair */
.q-tab {{
    color: {TEXT_MUTED} !important;
}}
.q-tab--active {{
    color: {PRIMARY_DARK} !important;
}}
.q-tabs__content {{
    color: {TEXT_MAIN};
}}

/* Table Quasar en clair */
.q-table__container, .q-table {{
    background: transparent !important;
    color: {TEXT_MAIN} !important;
}}
.q-table thead tr th {{
    color: {TEXT_MUTED} !important;
    font-weight: 600 !important;
    background: rgba(249, 115, 22, 0.05) !important;
    border-bottom: 1px solid {BORDER} !important;
}}
.q-table tbody tr {{
    border-bottom: 1px solid rgba(0, 0, 0, 0.04) !important;
}}
.q-table tbody tr:hover {{
    background: rgba(249, 115, 22, 0.06) !important;
}}

/* Scrollbar */
::-webkit-scrollbar {{ width: 10px; height: 10px; }}
::-webkit-scrollbar-track {{ background: rgba(0, 0, 0, 0.03); }}
::-webkit-scrollbar-thumb {{ background: rgba(249, 115, 22, 0.3); border-radius: 5px; }}
::-webkit-scrollbar-thumb:hover {{ background: rgba(249, 115, 22, 0.5); }}
"""


# ============================================================
# Layout partagé
# ============================================================

def _plotly_layout(title: str = "", height: int = 380) -> dict:
    return dict(
        title=dict(text=title, font=dict(size=15, color=TEXT_MAIN, family="Inter")),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT_MUTED, family="Inter", size=12),
        margin=dict(l=20, r=20, t=50, b=20),
        height=height,
        xaxis=dict(gridcolor="rgba(0,0,0,0.06)", zerolinecolor="rgba(0,0,0,0.06)"),
        yaxis=dict(gridcolor="rgba(0,0,0,0.06)", zerolinecolor="rgba(0,0,0,0.06)"),
        legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor="rgba(0,0,0,0.06)"),
    )


def _setup_page() -> None:
    """Injecte le CSS et configure la page. À appeler au début de chaque route."""
    ui.dark_mode().disable()
    ui.add_head_html(f"<style>{GLOBAL_CSS}</style>")


def _current_route() -> str:
    try:
        return ui.context.client.request.url.path
    except Exception:
        return "/"


def render_header(active: str) -> None:
    """En-tête sticky avec navigation."""
    email = app.storage.user.get("gmail_email", "")
    with ui.element("div").classes("mm-header w-full"):
        with ui.row().classes("items-center justify-between w-full max-w-7xl mx-auto"):
            with ui.row().classes("items-center gap-3"):
                _html('<span style="font-size:1.6rem;">📬</span>')
                _html(f'<span style="font-weight:800;font-size:1.15rem;color:{TEXT_MAIN};">Mail Manager</span>')

            with ui.row().classes("items-center gap-2"):
                for label, target in [("Promos", "/"), ("Chat IA", "/chat"), ("Statistiques", "/stats")]:
                    cls = "mm-nav-link mm-nav-link--active" if active == target else "mm-nav-link"
                    ui.link(label, target).classes(cls)

            with ui.row().classes("items-center gap-3"):
                if email:
                    _html(f'<span style="color:{TEXT_MUTED};font-size:0.85rem;">{email}</span>')
                    ui.button("Déconnexion", on_click=logout).props("flat dense").classes("mm-btn-ghost")


def logout() -> None:
    session_id = app.storage.user.get("session_id")
    if session_id:
        _gmail_client.clear_session(session_id)
    app.storage.user.clear()
    ui.navigate.to("/")


def _ensure_connection() -> str | None:
    session_id = app.storage.user.get("session_id")
    if session_id and _gmail_client.is_connected(session_id):
        return session_id

    email = app.storage.user.get("gmail_email")
    password = app.storage.user.get("gmail_password")
    if email and password:
        new_session = _gmail_client.connect(email, password)
        if new_session:
            app.storage.user["session_id"] = new_session
            return new_session
    return None


# ============================================================
# Page principale (login OU liste promos)
# ============================================================

@ui.page("/")
def page_home() -> None:
    _setup_page()
    session_id = _ensure_connection()
    if not session_id:
        _render_login()
    else:
        render_header(active="/")
        _render_promos(session_id)


def _render_login() -> None:
    with ui.column().classes("items-center justify-center w-full").style("min-height:100vh;padding:2rem;"):
        with ui.element("div").classes("mm-card").style("max-width:480px;width:100%;"):
            _html('<div style="text-align:center;font-size:3.5rem;">📬</div>')
            _html('<h1 class="mm-title" style="text-align:center;font-size:2rem;margin-top:0.5rem;">Bienvenue</h1>')
            _html(f'<p style="text-align:center;color:{TEXT_MUTED};margin:0.5rem 0 1.5rem;">Connectez votre boîte Gmail pour laisser l\'IA trier vos promos</p>')

            with ui.expansion("Comment obtenir un mot de passe d'application ?", icon="help_outline").classes("w-full").style(f"color:{TEXT_MAIN};"):
                ui.markdown("""
1. Allez sur [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Activez la **validation en 2 étapes** si ce n'est pas fait
3. Créez un mot de passe → nom : `Mail Manager`
4. Copiez le code à **16 caractères**
                """).style(f"color:{TEXT_MAIN};")

            email_input = ui.input("Adresse Gmail", placeholder="exemple@gmail.com").classes("mm-input w-full").props("outlined")
            password_input = ui.input("Mot de passe d'application", placeholder="xxxx xxxx xxxx xxxx",
                                       password=True, password_toggle_button=True).classes("mm-input w-full").props("outlined")
            error_label = ui.label("").style(f"color:{DANGER};font-size:0.9rem;min-height:1.2rem;")

            async def do_login() -> None:
                if not email_input.value or not password_input.value:
                    error_label.text = "Veuillez remplir les deux champs."
                    return
                error_label.text = ""
                clean_pw = password_input.value.replace(" ", "")
                connect_btn.props("loading")
                try:
                    session_id = await run.io_bound(_gmail_client.connect, email_input.value, clean_pw)
                finally:
                    connect_btn.props(remove="loading")
                if session_id:
                    app.storage.user["session_id"] = session_id
                    app.storage.user["gmail_email"] = email_input.value
                    app.storage.user["gmail_password"] = clean_pw
                    ui.navigate.to("/")
                else:
                    error_label.text = "Connexion échouée. Vérifiez votre email et votre mot de passe d'application."

            connect_btn = ui.button("Se connecter", on_click=do_login).classes("mm-btn-primary w-full").style("margin-top:1rem;")
            password_input.on("keydown.enter", do_login)
            email_input.on("keydown.enter", do_login)


def _render_promos(session_id: str) -> None:
    user_email = app.storage.user.get("gmail_email", "")
    with ui.column().classes("w-full max-w-7xl mx-auto").style("padding:2rem;"):
        _html('<h1 class="mm-title">Vos promotions</h1>')
        _html(f'<p class="mm-subtitle">Détection intelligente par IA · fenêtre {settings.mail_retention_days} jours</p>')

        # État de connexion
        with ui.element("div").classes("mm-card--flat").style("margin-top:1rem;"):
            with ui.row().classes("items-center justify-between w-full"):
                with ui.row().classes("items-center gap-2"):
                    _html(f'<span class="mm-badge mm-badge--success">● Connecté</span>')
                    _html(f'<span style="color:{TEXT_MAIN};">{user_email}</span>')

        # Préférences
        pref_input = ui.input(
            "Vos centres d'intérêt (facultatif)",
            placeholder="ex: tech, voyages, mode femme...",
            value=app.storage.user.get("preferences", ""),
        ).classes("mm-input w-full").style("margin-top:1rem;").props("outlined")

        # Bouton charger (avant le container pour que la zone de resultats apparaisse dessous)
        content_container = ui.column().classes("w-full")

        async def load_and_render() -> None:
            app.storage.user["preferences"] = pref_input.value
            await _load_promos_flow(user_email, pref_input.value, content_container)

        with ui.row().classes("w-full").style("margin-top:1rem;"):
            ui.button(
                f"Charger / Actualiser les {settings.mail_retention_days} derniers jours",
                icon="refresh",
                on_click=load_and_render,
            ).classes("mm-btn-primary w-full")

        # La zone de resultats doit venir apres le bouton visuellement
        content_container.move()  # deplace le container juste apres le bouton dans le DOM
        _render_cached_promos(content_container, user_email)


async def _load_promos_flow(user_email: str, preferences: str, container: ui.column) -> None:
    session_id = app.storage.user.get("session_id")
    if not session_id:
        ui.notify("Session expirée, reconnectez-vous.", type="negative")
        return

    workflow = _get_workflow(user_email)
    workflow.preferences = preferences

    container.clear()
    with container:
        with ui.element("div").classes("mm-card--flat").style("margin-top:1rem;"):
            status_label = ui.label(f"Lecture des {settings.mail_retention_days} derniers jours...")
            progress = ui.linear_progress(value=0, show_value=False).style("margin-top:0.6rem;")

    try:
        emails = await run.io_bound(
            _gmail_client.get_promo_emails, session_id, settings.mail_retention_days
        )
    except Exception as exc:
        logger.exception("Erreur lecture IMAP")
        status_label.text = f"Erreur : {exc}"
        return

    if not emails:
        status_label.text = "Aucun email trouvé dans l'onglet Promotions."
        return

    total = len(emails)
    status_label.text = f"{total} mails à traiter (déduplication via Azure)..."

    # Charger index Azure une seule fois
    await run.io_bound(workflow.load_cache_index, True)

    processed: list[dict] = []
    BATCH_SIZE = 4
    for batch_start in range(0, total, BATCH_SIZE):
        batch = emails[batch_start:batch_start + BATCH_SIZE]
        batch_result = await run.io_bound(workflow.run_for_batch, batch)
        processed.extend(batch_result)
        done = min(batch_start + BATCH_SIZE, total)
        progress.value = done / total
        status_label.text = f"Traitement {done} / {total}..."

    status_label.text = f"{len(processed)} mails traités."
    _user_emails[user_email] = processed
    _render_cached_promos(container, user_email)


def _render_cached_promos(container: ui.column, user_email: str) -> None:
    processed = _user_emails.get(user_email, [])
    container.clear()

    if not processed:
        with container:
            with ui.element("div").classes("mm-card--flat").style("margin-top:1rem;text-align:center;"):
                _html(f'<p style="color:{TEXT_MUTED};">Cliquez sur "Charger / Actualiser" pour démarrer.</p>')
        return

    all_promos = [e for e in processed if e.get("is_promo")]
    other_mails = [e for e in processed if not e.get("is_promo")]

    # Determine la plage de dates disponible
    known_dates = sorted({p.get("received_date", "") for p in all_promos if p.get("received_date")})
    if known_dates:
        min_date = known_dates[0]
        max_date = known_dates[-1]
    else:
        today = datetime.now().strftime("%Y-%m-%d")
        min_date = max_date = today

    date_state = {"start": min_date, "end": max_date}

    with container:
        # Barre de haut : titre + filtre de date a droite
        with ui.row().classes("w-full items-center justify-between").style("margin-top:1.5rem;flex-wrap:wrap;gap:1rem;"):
            _html(f'<div style="color:{TEXT_MUTED};font-size:0.9rem;">{len(processed)} mails analyses · {len(all_promos)} promos</div>')
            with ui.row().classes("items-center gap-2"):
                _html(f'<span style="color:{TEXT_MUTED};font-size:0.9rem;">Du</span>')
                start_input = ui.input(value=date_state["start"]).props("type=date outlined dense").classes("mm-input")
                _html(f'<span style="color:{TEXT_MUTED};font-size:0.9rem;">au</span>')
                end_input = ui.input(value=date_state["end"]).props("type=date outlined dense").classes("mm-input")

                def reset_range() -> None:
                    date_state["start"] = min_date
                    date_state["end"] = max_date
                    start_input.value = min_date
                    end_input.value = max_date
                    rebuild()

                ui.button("Toute la plage", on_click=reset_range).classes("mm-btn-ghost")

        # KPIs (recalculés selon le filtre)
        kpi_row = ui.row().classes("w-full gap-3").style("margin-top:1rem;")

        # Tabs container (re-rendu au changement de date)
        tabs_container = ui.column().classes("w-full")

        def rebuild() -> None:
            start = date_state["start"] or min_date
            end = date_state["end"] or max_date
            if start > end:
                start, end = end, start

            def in_range(e: dict) -> bool:
                d = e.get("received_date", "")
                return bool(d) and start <= d <= end

            filtered = [p for p in all_promos if in_range(p)]
            filtered_others = [e for e in other_mails if in_range(e)]

            # KPIs
            kpi_row.clear()
            with kpi_row:
                _kpi("Promos affichées", str(len(filtered)))
                _kpi("Marques", str(len({p.get("company") for p in filtered if p.get("company")})))
                _kpi("Avec code promo", str(sum(1 for p in filtered if p.get("promo_code"))))
                _kpi("Autres mails", str(len(filtered_others)))

            # Tabs
            tabs_container.clear()
            with tabs_container:
                with ui.element("div").classes("mm-card--flat").style("margin-top:1.5rem;"):
                    with ui.tabs().classes("w-full").props(f"indicator-color=primary") as tabs:
                        tab_fiche = ui.tab("Fiche promos", icon="receipt_long")
                        tab_cat = ui.tab("Par catégorie", icon="category")
                        tab_other = ui.tab(f"Autres mails ({len(filtered_others)})", icon="inbox")
                    with ui.tab_panels(tabs, value=tab_fiche).classes("w-full").style("background:transparent;"):
                        with ui.tab_panel(tab_fiche):
                            if not filtered:
                                _html(f'<p style="color:{TEXT_MUTED};">Aucune promo dans cette plage.</p>')
                            for e in filtered:
                                _render_promo_card(e)
                        with ui.tab_panel(tab_cat):
                            if not filtered:
                                _html(f'<p style="color:{TEXT_MUTED};">Aucune promo dans cette plage.</p>')
                            else:
                                _render_by_category(filtered)
                        with ui.tab_panel(tab_other):
                            _render_other_mails(filtered_others)

        # Wire changes
        start_input.on("update:model-value", lambda e: (date_state.update(start=start_input.value), rebuild()))
        end_input.on("update:model-value", lambda e: (date_state.update(end=end_input.value), rebuild()))

        rebuild()


def _kpi(label: str, value: str, delta: str = "") -> None:
    with ui.element("div").classes("mm-kpi").style("flex:1;"):
        _html(f'<div class="mm-kpi-label">{label}</div>')
        _html(f'<div class="mm-kpi-value">{value}</div>')
        if delta:
            _html(f'<div class="mm-kpi-delta">{delta}</div>')


def _render_other_mails(mails: list) -> None:
    """Affichage compact des mails non-promo (newsletters, notifications, confirmations...)."""
    if not mails:
        _html(f'<p style="color:{TEXT_MUTED};margin-top:1rem;">Aucun autre mail dans cette plage de dates.</p>')
        return

    _html(
        f'<p style="color:{TEXT_MUTED};margin:0.5rem 0 1rem;">'
        f'{len(mails)} mail(s) que l\'IA n\'a pas classé(s) comme promo '
        f'(newsletters, confirmations de commande, notifications...)</p>'
    )
    for m in mails:
        company = m.get("company") or m.get("from", "Inconnu")
        subject = m.get("subject", "") or m.get("summary", "")
        date_str = m.get("date", "")[:16]
        category = m.get("category", "")
        message_id = m.get("message_id", "")
        unsubscribe_url = m.get("unsubscribe_url", "")

        with ui.element("div").classes("mm-card").style("margin-bottom:0.7rem;padding:1rem 1.2rem;"):
            with ui.row().classes("items-start justify-between w-full").style("gap:1rem;"):
                with ui.column().classes("gap-1").style("flex:1;min-width:0;"):
                    _html(f'<div style="font-weight:600;color:{TEXT_MAIN};">{company}</div>')
                    _html(f'<div style="color:{TEXT_MUTED};font-size:0.85rem;">{subject}</div>')
                    _html(f'<div style="color:{TEXT_MUTED};font-size:0.75rem;">{category} · {date_str}</div>')
                with ui.row().classes("items-center gap-2"):
                    if message_id:
                        url = f"https://mail.google.com/mail/u/0/#search/rfc822msgid:{message_id}"
                        ui.link("Voir", url, new_tab=True).classes("mm-btn-ghost").style("padding:0.3rem 0.7rem;text-decoration:none;font-size:0.85rem;")
                    if unsubscribe_url:
                        ui.link("Stop", unsubscribe_url, new_tab=True).classes("mm-btn-ghost").style("padding:0.3rem 0.7rem;text-decoration:none;font-size:0.85rem;")


def _render_by_category(promos: list) -> None:
    cats = sorted({e.get("category", "autre") for e in promos})
    selected = {"value": cats[0] if cats else ""}
    content = ui.column().classes("w-full").style("margin-top:1rem;")

    def refresh() -> None:
        content.clear()
        cat_promos = [e for e in promos if e.get("category") == selected["value"]]
        with content:
            _html(f'<p style="color:{TEXT_MUTED};">{len(cat_promos)} promo(s) dans "{selected["value"]}"</p>')
            for e in cat_promos:
                _render_promo_card(e)

    ui.select(cats, value=selected["value"], on_change=lambda e: (selected.update(value=e.value), refresh())) \
        .classes("mm-input w-full").props("outlined").style("max-width:400px;")

    refresh()


def _render_promo_card(email: dict) -> None:
    company = email.get("company") or email.get("from", "Inconnu")
    summary = email.get("summary", "") or email.get("subject", "")
    promo_code = email.get("promo_code", "")
    expiry = email.get("expiry_date", "")
    discount = email.get("discount", "")
    category = email.get("category", "")
    unsubscribe_url = email.get("unsubscribe_url", "")
    message_id = email.get("message_id", "")
    date_str = email.get("date", "")[:16]

    with ui.element("div").classes("mm-card").style("margin-bottom:1rem;"):
        with ui.row().classes("items-start justify-between w-full"):
            with ui.column().classes("gap-1").style("flex:1;"):
                _html(f'<div style="font-weight:700;font-size:1.1rem;color:{TEXT_MAIN};">{company}</div>')
                _html(f'<div style="color:{TEXT_MUTED};font-size:0.85rem;">{category} · {date_str}</div>')
            if discount:
                _html(f'<div style="font-weight:800;font-size:1.4rem;color:{ACCENT};">{discount}</div>')

        _html(f'<p style="color:{TEXT_MAIN};margin-top:0.7rem;">{summary}</p>')

        badges = []
        if promo_code:
            badges.append(f'<span class="mm-badge mm-badge--success">Code : <code style="font-family:SF Mono,Menlo,monospace;">{promo_code}</code></span>')
        if expiry:
            badges.append(f'<span class="mm-badge mm-badge--info">Expire : {expiry}</span>')
        if badges:
            _html(f'<div style="display:flex;gap:0.5rem;flex-wrap:wrap;margin-top:0.6rem;">{"".join(badges)}</div>')

        with ui.row().classes("gap-2 w-full").style("margin-top:0.9rem;"):
            if message_id:
                gmail_url = f"https://mail.google.com/mail/u/0/#search/rfc822msgid:{message_id}"
                ui.link("Voir dans Gmail", gmail_url, new_tab=True).classes("mm-btn-ghost").style("padding:0.4rem 0.8rem;text-decoration:none;")
            if unsubscribe_url:
                ui.link("Se désabonner", unsubscribe_url, new_tab=True).classes("mm-btn-ghost").style("padding:0.4rem 0.8rem;text-decoration:none;")


# ============================================================
# Page Chat
# ============================================================

MAX_PROMOS_IN_CONTEXT = 25


def _build_promos_context(promos: list) -> tuple[str, dict]:
    if not promos:
        return "Aucune promo n'a encore été chargée.", {}
    limited = promos[:MAX_PROMOS_IN_CONTEXT]
    lines = []
    links_map: dict[int, dict] = {}
    for i, p in enumerate(limited, 1):
        company = (p.get("company") or p.get("from", ""))[:60]
        summary = (p.get("summary") or p.get("subject", ""))[:120]
        parts = [f"#{i}", company]
        if p.get("discount"):
            parts.append(f"réduc:{p['discount']}")
        if p.get("promo_code"):
            parts.append(f"code:{p['promo_code']}")
        if p.get("expiry_date"):
            parts.append(f"exp:{p['expiry_date']}")
        if p.get("category"):
            parts.append(f"cat:{p['category']}")
        lines.append(" | ".join(parts) + f" — {summary}")
        gmail_link = ""
        if p.get("message_id"):
            gmail_link = f"https://mail.google.com/mail/u/0/#search/rfc822msgid:{p['message_id']}"
        links_map[i] = {"gmail": gmail_link, "unsubscribe": p.get("unsubscribe_url", "")}

    context = "\n".join(lines)
    if len(promos) > MAX_PROMOS_IN_CONTEXT:
        context += f"\n\n(Note: {len(promos) - MAX_PROMOS_IN_CONTEXT} promos plus anciennes non affichées)"
    return context, links_map


def _inject_links(response: str, links_map: dict) -> str:
    def repl(match: re.Match) -> str:
        num = int(match.group(1))
        if num in links_map and links_map[num]["gmail"]:
            return f"[#{num}]({links_map[num]['gmail']})"
        return match.group(0)
    return re.sub(r"#(\d+)", repl, response)


def _ask_groq(messages: list, promos_context: str) -> str:
    if not settings.groq_api_key:
        return "Erreur : GROQ_API_KEY manquant dans le .env"
    from groq import Groq
    client = Groq(api_key=settings.groq_api_key)

    system_prompt = f"""Tu es un assistant shopping. Voici les promos de l'utilisateur.

Format de chaque ligne :
#id | ENTREPRISE | réduc:XX | code:XXX | exp:DATE | cat:XXX — DESCRIPTION DE LA PROMO

Promos disponibles :
{promos_context}

REGLES OBLIGATOIRES pour chaque promo citee :
1. Format : **NOM_ENTREPRISE** (#id) : description courte + reduction + code + expiration
2. Exemple correct : "**Amazon** (#3) : -30% sur les ecouteurs sans fil, code `PROMO30`, expire le 2026-07-15"
3. Exemple INCORRECT : "La promo #3 propose une reduction de -30%" (manque le nom de la marque et le detail)

Autres regles :
- Reponds en francais, sois concis
- Utilise des listes a puces groupees par categorie si pertinent
- Mets les codes promo en `backticks`
- Si aucune promo ne correspond, dis-le clairement
- Vise l'action : quoi acheter, quoi ignorer, quoi expire bientot"""

    trimmed = messages[-4:] if len(messages) > 4 else messages
    try:
        response = client.chat.completions.create(
            model=settings.groq_model,
            temperature=0.5,
            max_tokens=1024,
            messages=[{"role": "system", "content": system_prompt}] + trimmed,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        logger.exception("Groq chat call failed")
        return f"Erreur lors de l'appel à Groq : {e}"


@ui.page("/chat")
def page_chat() -> None:
    _setup_page()
    session_id = _ensure_connection()
    if not session_id:
        ui.navigate.to("/")
        return

    render_header(active="/chat")

    user_email = app.storage.user.get("gmail_email", "")
    promos = [e for e in _user_emails.get(user_email, []) if e.get("is_promo")]

    with ui.column().classes("w-full max-w-5xl mx-auto").style("padding:2rem;"):
        _html('<h1 class="mm-title">Assistant IA</h1>')
        _html('<p class="mm-subtitle">Discutez avec l\'IA pour explorer vos promos</p>')

        if not promos:
            with ui.element("div").classes("mm-card--flat").style("margin-top:1.5rem;text-align:center;"):
                _html(f'<p style="color:{TEXT_MUTED};">Aucune promo chargée. Retournez à la page principale et cliquez sur "Charger les mails promos".</p>')
                ui.button("Retour aux promos", on_click=lambda: ui.navigate.to("/")).classes("mm-btn-primary").style("margin-top:1rem;")
            return

        with ui.element("div").classes("mm-card--flat").style("margin-top:1rem;"):
            _html(f'<span class="mm-badge mm-badge--info">🤖 IA prête</span> <span style="color:{TEXT_MAIN};margin-left:0.5rem;">{len(promos)} promo(s) chargée(s)</span>')
            with ui.expansion(f"Voir les {len(promos)} promos analysées par l'IA").classes("w-full").style("margin-top:0.6rem;"):
                for p in promos[:30]:
                    c = p.get("company") or p.get("from", "Inconnu")
                    s = p.get("summary") or p.get("subject", "")
                    _html(f'<div style="padding:0.3rem 0;color:{TEXT_MAIN};">• <b>{c}</b> — <span style="color:{TEXT_MUTED};">{s}</span></div>')
                if len(promos) > 30:
                    _html(f'<div style="color:{TEXT_MUTED};font-size:0.85rem;">... et {len(promos) - 30} autres</div>')

        # Suggestions
        _html(f'<h4 style="color:{TEXT_MAIN};margin:1.5rem 0 0.5rem;">💡 Suggestions</h4>')
        suggestions = [
            ("✨", "Résume-moi les meilleures promos"),
            ("⏰", "Quelles promos expirent bientôt ?"),
            ("📮", "Quelles marques envoient trop d'emails ?"),
            ("💻", "Y a-t-il des promos tech ?"),
        ]
        with ui.row().classes("gap-2 w-full flex-wrap"):
            for icon, txt in suggestions:
                def make_handler(t: str):
                    async def h() -> None:
                        await send_message(t)
                    return h
                ui.button(f"{icon}  {txt}", on_click=make_handler(txt)).classes("mm-btn-ghost")

        # Historique chat
        chat_history = app.storage.user.get("chat_messages", [])
        chat_container = ui.column().classes("w-full").style("margin-top:1.5rem;min-height:200px;")

        def render_history() -> None:
            chat_container.clear()
            with chat_container:
                for msg in app.storage.user.get("chat_messages", []):
                    cls = "mm-chat-user" if msg["role"] == "user" else "mm-chat-assistant"
                    with ui.element("div").classes(cls):
                        ui.markdown(msg["content"])

        render_history()

        # Input + envoi
        input_row = ui.row().classes("w-full items-end gap-2").style("margin-top:1rem;")
        with input_row:
            user_input = ui.textarea(placeholder="Posez votre question sur vos promos...").classes("mm-input").props("outlined autogrow rows=1").style("flex:1;")

            async def on_send() -> None:
                text = (user_input.value or "").strip()
                if not text:
                    return
                user_input.value = ""
                await send_message(text)

            send_btn = ui.button(icon="send", on_click=on_send).classes("mm-btn-primary")
            user_input.on("keydown.enter", on_send)

        # Bouton reset
        if chat_history:
            def reset_chat() -> None:
                app.storage.user["chat_messages"] = []
                render_history()
            ui.button("🗑 Nouvelle conversation", on_click=reset_chat).classes("mm-btn-ghost").style("margin-top:0.6rem;align-self:flex-end;")

        async def send_message(text: str) -> None:
            messages = app.storage.user.get("chat_messages", [])
            messages.append({"role": "user", "content": text})
            app.storage.user["chat_messages"] = messages
            render_history()

            with chat_container:
                thinking = ui.element("div").classes("mm-chat-assistant")
                with thinking:
                    _html(f'<span style="color:{TEXT_MUTED};">🤖 L\'assistant réfléchit...</span>')

            promos_context, links_map = _build_promos_context(promos)
            raw = await run.io_bound(_ask_groq, messages, promos_context)
            response = _inject_links(raw, links_map)

            messages.append({"role": "assistant", "content": response})
            app.storage.user["chat_messages"] = messages
            render_history()


# ============================================================
# Page Statistiques
# ============================================================

@ui.page("/stats")
def page_stats() -> None:
    _setup_page()
    session_id = _ensure_connection()
    if not session_id:
        ui.navigate.to("/")
        return

    render_header(active="/stats")

    user_email = app.storage.user.get("gmail_email", "")
    emails = _user_emails.get(user_email, [])
    promos = [e for e in emails if e.get("is_promo")]

    with ui.column().classes("w-full max-w-7xl mx-auto").style("padding:2rem;"):
        _html('<h1 class="mm-title">Tableau de bord</h1>')
        _html('<p class="mm-subtitle">Vue analytique de vos promotions</p>')

        if not emails:
            with ui.element("div").classes("mm-card--flat").style("margin-top:1.5rem;text-align:center;"):
                _html(f'<p style="color:{TEXT_MUTED};">Aucun email chargé. Retournez à la page principale.</p>')
                ui.button("Retour", on_click=lambda: ui.navigate.to("/")).classes("mm-btn-primary").style("margin-top:1rem;")
            return

        # KPIs
        promo_rate = (len(promos) / len(emails) * 100) if emails else 0
        unique_companies = len({p.get("company") for p in promos if p.get("company")})
        with_code = sum(1 for p in promos if p.get("promo_code"))
        with ui.row().classes("w-full gap-3").style("margin-top:1.5rem;"):
            _kpi("Emails analysés", str(len(emails)))
            _kpi("Promos détectées", str(len(promos)), f"{promo_rate:.0f}% du total")
            _kpi("Marques uniques", str(unique_companies))
            _kpi("Avec code promo", str(with_code))

        if not promos:
            with ui.element("div").classes("mm-card--flat").style("margin-top:1.5rem;"):
                _html(f'<p style="color:{TEXT_MUTED};">Aucune promo détectée pour afficher des visualisations.</p>')
            return

        df = pd.DataFrame([{
            "company": p.get("company") or "Inconnu",
            "category": p.get("category") or "autre",
            "date": p.get("received_date", ""),
            "has_code": bool(p.get("promo_code")),
            "has_expiry": bool(p.get("expiry_date")),
        } for p in promos])

        # Ligne 1 : Camembert + Top marques
        _html(f'<h3 style="color:{TEXT_MAIN};margin:1.5rem 0 0.5rem;">Répartition par catégorie & marques</h3>')
        with ui.row().classes("w-full gap-4"):
            with ui.element("div").classes("mm-card--flat").style("flex:1;"):
                cat_counts = df["category"].value_counts()
                fig_cat = go.Figure(data=[go.Pie(
                    labels=cat_counts.index.tolist(),
                    values=cat_counts.values.tolist(),
                    hole=0.55,
                    marker=dict(colors=PALETTE, line=dict(color=BG_DARK, width=2)),
                    textinfo="percent",
                    textfont=dict(size=13, color="white", family="Inter"),
                )])
                layout = _plotly_layout("Distribution par catégorie", height=380)
                layout["annotations"] = [dict(
                    text=f"<b>{len(promos)}</b><br><span style='font-size:11px;color:{TEXT_MUTED}'>promos</span>",
                    x=0.5, y=0.5, font=dict(size=22, color=TEXT_MAIN, family="Inter"),
                    showarrow=False,
                )]
                fig_cat.update_layout(**layout)
                ui.plotly(fig_cat).classes("w-full")

            with ui.element("div").classes("mm-card--flat").style("flex:1;"):
                top_companies = df["company"].value_counts().head(10).sort_values(ascending=True)
                fig_comp = go.Figure(data=[go.Bar(
                    x=top_companies.values,
                    y=top_companies.index,
                    orientation="h",
                    marker=dict(
                        color=top_companies.values,
                        colorscale=[[0, PRIMARY], [1, ACCENT]],
                        line=dict(width=0),
                    ),
                    text=top_companies.values,
                    textposition="outside",
                    textfont=dict(color=TEXT_MAIN),
                )])
                fig_comp.update_layout(**_plotly_layout("Top 10 des marques", height=380))
                ui.plotly(fig_comp).classes("w-full")

        # Ligne 2 : Évolution temporelle
        _html(f'<h3 style="color:{TEXT_MAIN};margin:1.5rem 0 0.5rem;">Évolution dans le temps</h3>')
        df_time = df[df["date"] != ""].copy()
        if not df_time.empty:
            df_time["date_parsed"] = pd.to_datetime(df_time["date"], errors="coerce")
            df_time = df_time.dropna(subset=["date_parsed"])

        with ui.element("div").classes("mm-card--flat"):
            if not df_time.empty:
                daily = df_time.groupby(df_time["date_parsed"].dt.date).size().reset_index()
                daily.columns = ["date", "count"]
                fig_time = go.Figure()
                fig_time.add_trace(go.Scatter(
                    x=daily["date"], y=daily["count"], mode="lines+markers",
                    line=dict(color=PRIMARY, width=3, shape="spline"),
                    marker=dict(size=9, color=ACCENT, line=dict(color=TEXT_MAIN, width=2)),
                    fill="tozeroy", fillcolor="rgba(249, 115, 22, 0.15)",
                ))
                fig_time.update_layout(**_plotly_layout("Promos reçues par jour", height=340))
                ui.plotly(fig_time).classes("w-full")
            else:
                _html(f'<p style="color:{TEXT_MUTED};">Pas de données temporelles disponibles.</p>')



# ============================================================
# Lancement
# ============================================================

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        title="Mail Manager",
        port=8080,
        storage_secret=settings.session_secret if settings.session_secret != "change-me" else secrets.token_urlsafe(32),
        favicon="📬",
        dark=True,
        reload=False,
        show=False,
    )
