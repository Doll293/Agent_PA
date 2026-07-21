import json
import logging
import sys
from pathlib import Path

import streamlit as st

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mail_manager.config import settings
from mail_manager.ui_theme import hero_header, inject_global_css

logger = logging.getLogger(__name__)

st.set_page_config(page_title="Chat Promos", layout="wide", page_icon="💬")
inject_global_css()
hero_header(
    "Assistant IA",
    "Discutez avec l'IA pour explorer vos promos et obtenir des recommandations",
    icon="💬",
)


def _get_promos_from_session() -> list:
    promos = []
    for key, value in st.session_state.items():
        if key.startswith("emails_") and isinstance(value, list):
            promos.extend([e for e in value if e.get("is_promo")])
    return promos


MAX_PROMOS_IN_CONTEXT = 25


def _build_promos_context(promos: list) -> tuple:
    """Retourne (contexte_texte, mapping_id_vers_liens)."""
    if not promos:
        return "Aucune promo n'a encore été chargée.", {}

    # Garder les plus récentes seulement
    limited = promos[:MAX_PROMOS_IN_CONTEXT]

    # Format compact texte pour économiser des tokens
    lines = []
    links_map = {}
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

        # Stocke les liens séparément (pas envoyés à l'IA)
        gmail_link = ""
        if p.get("message_id"):
            gmail_link = f"https://mail.google.com/mail/u/0/#search/rfc822msgid:{p['message_id']}"
        links_map[i] = {
            "gmail": gmail_link,
            "unsubscribe": p.get("unsubscribe_url", ""),
        }

    context = "\n".join(lines)
    if len(promos) > MAX_PROMOS_IN_CONTEXT:
        context += f"\n\n(Note: {len(promos) - MAX_PROMOS_IN_CONTEXT} promos plus anciennes non affichées)"
    return context, links_map


def _inject_links(response: str, links_map: dict) -> str:
    """Remplace les #N par des liens Markdown réels."""
    import re
    def repl(match):
        num = int(match.group(1))
        if num in links_map and links_map[num]["gmail"]:
            return f"[#{num}]({links_map[num]['gmail']})"
        return match.group(0)
    return re.sub(r"#(\d+)", repl, response)


def _get_groq_client():
    if not settings.groq_api_key:
        return None
    from groq import Groq
    return Groq(api_key=settings.groq_api_key)


def _ask_groq(messages: list, promos_context: str) -> str:
    client = _get_groq_client()
    if not client:
        return "Erreur : GROQ_API_KEY manquant dans le .env"

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

    # Ne garder que les 4 derniers messages pour économiser des tokens
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


# Vérification : promos chargées ?
promos = _get_promos_from_session()

if not promos:
    st.warning("Aucune promo chargée. Allez d'abord sur la page principale et cliquez sur 'Charger les mails promos'.")
    st.page_link("streamlit_app.py", label="← Retour à la page principale", icon="📧")
    st.stop()

# Barre d'état + navigation
status_cols = st.columns([3, 1, 1])
with status_cols[0]:
    st.markdown(
        f"""
        <div style='background:linear-gradient(135deg, rgba(99,102,241,0.15), rgba(236,72,153,0.10));
                    border:1px solid rgba(99,102,241,0.3);
                    border-radius:12px;padding:0.7rem 1rem;'>
            <span style='color:#A5B4FC;font-weight:600;'>🤖 IA prête</span>
            <span style='color:#CBD5E1;margin-left:0.5rem;'>{len(promos)} promo(s) chargée(s)</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
with status_cols[1]:
    st.page_link("streamlit_app.py", label="📧 Promos", use_container_width=True)
with status_cols[2]:
    st.page_link("pages/2_Statistiques.py", label="📊 Stats", use_container_width=True)

with st.expander(f"📋 Voir les {len(promos)} promos analysées par l'IA"):
    for p in promos[:30]:
        company = p.get('company') or p.get('from', 'Inconnu')
        summary = p.get('summary') or p.get('subject', '')
        st.markdown(f"- **{company}** — {summary}")
    if len(promos) > 30:
        st.caption(f"... et {len(promos) - 30} autres")

# Historique de conversation
if "chat_messages" not in st.session_state:
    st.session_state["chat_messages"] = []

# Suggestions rapides
st.markdown("#### 💡 Suggestions")
sug_cols = st.columns(4)
suggestions = [
    ("✨", "Résume-moi les meilleures promos"),
    ("⏰", "Quelles promos expirent bientôt ?"),
    ("📮", "Quelles marques envoient trop d'emails ?"),
    ("💻", "Y a-t-il des promos tech ?"),
]
for i, (icon, sug) in enumerate(suggestions):
    with sug_cols[i]:
        if st.button(f"{icon}  {sug}", use_container_width=True, key=f"sug_{i}"):
            st.session_state["_pending_message"] = sug

# Bouton reset
if st.session_state["chat_messages"]:
    reset_cols = st.columns([3, 1])
    with reset_cols[1]:
        if st.button("🗑️ Nouvelle conversation", type="secondary", use_container_width=True):
            st.session_state["chat_messages"] = []
            st.rerun()

st.markdown("---")

# Affichage historique
for msg in st.session_state["chat_messages"]:
    avatar = "🧑" if msg["role"] == "user" else "🤖"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# Message en attente depuis une suggestion
pending = st.session_state.pop("_pending_message", None)

# Input utilisateur
user_input = st.chat_input("Posez votre question sur vos promos...")

message_to_send = pending or user_input

if message_to_send:
    st.session_state["chat_messages"].append({"role": "user", "content": message_to_send})
    with st.chat_message("user", avatar="🧑"):
        st.markdown(message_to_send)

    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("L'assistant réfléchit..."):
            promos_context, links_map = _build_promos_context(promos)
            raw_response = _ask_groq(st.session_state["chat_messages"], promos_context)
            response = _inject_links(raw_response, links_map)
        st.markdown(response)

    st.session_state["chat_messages"].append({"role": "assistant", "content": response})
    st.rerun()
