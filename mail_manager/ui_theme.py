"""Thème visuel partagé pour toutes les pages Streamlit."""
import streamlit as st

PRIMARY = "#6366F1"
PRIMARY_DARK = "#4F46E5"
ACCENT = "#EC4899"
SUCCESS = "#10B981"
WARNING = "#F59E0B"
DANGER = "#EF4444"
BG_GRADIENT_START = "#0F172A"
BG_GRADIENT_END = "#1E293B"
CARD_BG = "#FFFFFF"

PALETTE = [
    "#6366F1", "#EC4899", "#10B981", "#F59E0B",
    "#3B82F6", "#8B5CF6", "#EF4444", "#14B8A6",
    "#F97316", "#06B6D4", "#A855F7", "#84CC16",
]


def inject_global_css() -> None:
    """Injecte le CSS global (fonts, boutons, cartes) sur toutes les pages."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }

        /* Fond principal en dégradé */
        .stApp {
            background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
            color: #E2E8F0;
        }

        /* Titre principal */
        h1 {
            font-weight: 800 !important;
            background: linear-gradient(90deg, #6366F1 0%, #EC4899 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            letter-spacing: -0.02em;
        }

        h2, h3, h4 {
            color: #F1F5F9 !important;
            font-weight: 700 !important;
        }

        /* Cartes / containers (uniquement st.container(border=True)) */
        [data-testid="stVerticalBlockBorderWrapper"] {
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            border-radius: 16px !important;
            padding: 1.2rem 1.4rem !important;
            backdrop-filter: blur(10px);
            transition: all 0.3s ease;
        }

        [data-testid="stVerticalBlockBorderWrapper"]:hover {
            border-color: rgba(99, 102, 241, 0.4) !important;
            box-shadow: 0 10px 30px rgba(99, 102, 241, 0.15);
        }

        /* Éviter que les conteneurs imbriqués (colonnes) héritent du style carte */
        [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stVerticalBlockBorderWrapper"] {
            background: transparent !important;
            border: none !important;
            padding: 0 !important;
            box-shadow: none !important;
        }
        [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stVerticalBlockBorderWrapper"]:hover {
            box-shadow: none !important;
        }

        /* Header / toolbar Streamlit (bandeau blanc en haut) */
        [data-testid="stHeader"], header[data-testid="stHeader"] {
            background: transparent !important;
        }
        [data-testid="stToolbar"] {
            background: transparent !important;
        }
        [data-testid="stDecoration"] {
            display: none !important;
        }

        /* Zone bas de page (chat input) */
        [data-testid="stBottomBlockContainer"],
        [data-testid="stBottom"] {
            background: transparent !important;
        }

        /* Boutons principaux */
        .stButton > button {
            background: linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%);
            color: white !important;
            border: none !important;
            border-radius: 12px !important;
            padding: 0.55rem 1.2rem !important;
            font-weight: 600 !important;
            transition: all 0.25s ease !important;
            box-shadow: 0 4px 14px rgba(99, 102, 241, 0.35);
        }

        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(99, 102, 241, 0.5);
            filter: brightness(1.1);
        }

        .stButton > button:active {
            transform: translateY(0);
        }

        /* Bouton de soumission de formulaire (st.form_submit_button) */
        .stFormSubmitButton > button,
        [data-testid="stFormSubmitButton"] > button {
            background: linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%) !important;
            color: white !important;
            border: none !important;
            border-radius: 12px !important;
            padding: 0.55rem 1.2rem !important;
            font-weight: 600 !important;
            transition: all 0.25s ease !important;
            box-shadow: 0 4px 14px rgba(99, 102, 241, 0.35);
        }

        .stFormSubmitButton > button:hover,
        [data-testid="stFormSubmitButton"] > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(99, 102, 241, 0.5);
            filter: brightness(1.1);
        }

        /* Boutons secondaires */
        .stButton > button[kind="secondary"] {
            background: rgba(255, 255, 255, 0.08) !important;
            color: #E2E8F0 !important;
            border: 1px solid rgba(255, 255, 255, 0.15) !important;
            box-shadow: none;
        }

        .stButton > button[kind="secondary"]:hover {
            background: rgba(255, 255, 255, 0.14) !important;
            border-color: rgba(255, 255, 255, 0.25) !important;
        }

        /* Boutons link */
        .stLinkButton > a {
            background: rgba(99, 102, 241, 0.15) !important;
            color: #A5B4FC !important;
            border: 1px solid rgba(99, 102, 241, 0.3) !important;
            border-radius: 10px !important;
            font-weight: 500 !important;
            transition: all 0.25s ease !important;
        }

        .stLinkButton > a:hover {
            background: rgba(99, 102, 241, 0.25) !important;
            border-color: rgba(99, 102, 241, 0.6) !important;
        }

        /* Inputs — wrappers Streamlit */
        .stTextInput [data-baseweb="input"],
        .stTextInput [data-baseweb="base-input"] {
            background: #1E293B !important;
            border: 1px solid rgba(255, 255, 255, 0.12) !important;
            border-radius: 10px !important;
        }

        /* Inputs — champ natif */
        .stTextInput input,
        .stTextArea textarea {
            background: #1E293B !important;
            color: #F1F5F9 !important;
            -webkit-text-fill-color: #F1F5F9 !important;
            caret-color: #F1F5F9 !important;
            border: none !important;
        }

        .stSelectbox > div > div {
            background: #1E293B !important;
            border: 1px solid rgba(255, 255, 255, 0.12) !important;
            border-radius: 10px !important;
            color: #F1F5F9 !important;
        }

        .stTextInput [data-baseweb="input"]:focus-within {
            border-color: #6366F1 !important;
            box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2) !important;
        }

        .stTextInput input::placeholder, .stTextArea textarea::placeholder {
            color: rgba(226, 232, 240, 0.45) !important;
            -webkit-text-fill-color: rgba(226, 232, 240, 0.45) !important;
        }

        /* Neutraliser l'autofill navigateur */
        .stTextInput input:-webkit-autofill,
        .stTextInput input:-webkit-autofill:hover,
        .stTextInput input:-webkit-autofill:focus,
        .stTextInput input:-webkit-autofill:active,
        input:-webkit-autofill {
            -webkit-box-shadow: 0 0 0 1000px #1E293B inset !important;
            -webkit-text-fill-color: #F1F5F9 !important;
            caret-color: #F1F5F9 !important;
            background-color: #1E293B !important;
            background-image: none !important;
            transition: background-color 5000s ease-in-out 0s;
        }

        /* Alertes */
        .stAlert {
            border-radius: 12px !important;
            border: none !important;
            backdrop-filter: blur(10px);
        }

        /* Métriques (KPI) */
        [data-testid="stMetric"] {
            background: linear-gradient(135deg, rgba(99, 102, 241, 0.15) 0%, rgba(236, 72, 153, 0.10) 100%);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            padding: 1.2rem 1.4rem;
            transition: all 0.3s ease;
        }

        [data-testid="stMetric"]:hover {
            transform: translateY(-3px);
            border-color: rgba(99, 102, 241, 0.5);
            box-shadow: 0 12px 30px rgba(99, 102, 241, 0.2);
        }

        [data-testid="stMetricValue"] {
            font-size: 2.2rem !important;
            font-weight: 800 !important;
            color: #F1F5F9 !important;
        }

        [data-testid="stMetricLabel"] {
            color: #94A3B8 !important;
            font-weight: 500 !important;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            font-size: 0.75rem !important;
        }

        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            background: rgba(255, 255, 255, 0.03);
            border-radius: 12px;
            padding: 6px;
        }

        .stTabs [data-baseweb="tab"] {
            border-radius: 8px !important;
            padding: 8px 20px !important;
            color: #94A3B8 !important;
            font-weight: 600 !important;
        }

        .stTabs [aria-selected="true"] {
            background: linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%) !important;
            color: white !important;
        }

        /* Chat messages */
        [data-testid="stChatMessage"] {
            background: rgba(255, 255, 255, 0.04) !important;
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 16px !important;
            padding: 1rem 1.2rem !important;
            margin-bottom: 0.8rem;
        }

        [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
            background: linear-gradient(135deg, rgba(99, 102, 241, 0.12) 0%, rgba(139, 92, 246, 0.08) 100%) !important;
            border-color: rgba(99, 102, 241, 0.25);
        }

        /* Chat input */
        [data-testid="stChatInput"] {
            background: rgba(255, 255, 255, 0.06) !important;
            border: 1px solid rgba(255, 255, 255, 0.15) !important;
            border-radius: 14px !important;
        }

        /* Progress bar */
        .stProgress > div > div {
            background: linear-gradient(90deg, #6366F1 0%, #EC4899 100%) !important;
        }

        /* Dataframe */
        [data-testid="stDataFrame"] {
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid rgba(255, 255, 255, 0.08);
            background: rgba(15, 23, 42, 0.6) !important;
        }
        [data-testid="stDataFrame"] div[class*="glide"],
        [data-testid="stDataFrame"] canvas {
            background: transparent !important;
        }

        /* Chat input (barre du bas) */
        [data-testid="stChatInput"] textarea {
            background: transparent !important;
            color: #F1F5F9 !important;
            -webkit-text-fill-color: #F1F5F9 !important;
        }
        [data-testid="stChatInput"] textarea::placeholder {
            color: rgba(226, 232, 240, 0.5) !important;
        }

        /* Captions */
        [data-testid="stCaptionContainer"], .stCaption {
            color: #94A3B8 !important;
        }

        /* Expander */
        .streamlit-expanderHeader {
            background: rgba(255, 255, 255, 0.04) !important;
            border-radius: 10px !important;
        }

        /* Sidebar */
        [data-testid="stSidebar"] {
            background: rgba(15, 23, 42, 0.9) !important;
            border-right: 1px solid rgba(255, 255, 255, 0.08);
        }

        /* Cacher menu Streamlit */
        #MainMenu, footer {
            visibility: hidden;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def hero_header(title: str, subtitle: str = "", icon: str = "") -> None:
    """Affiche un en-tête de page stylisé."""
    icon_html = f"<span style='font-size:2.4rem;margin-right:0.6rem;'>{icon}</span>" if icon else ""
    subtitle_html = (
        f"<p style='color:#94A3B8;font-size:1.05rem;margin-top:0.3rem;font-weight:400;'>{subtitle}</p>"
        if subtitle else ""
    )
    st.markdown(
        f"""
        <div style="padding: 1rem 0 1.5rem 0;">
            <h1 style="margin-bottom:0;display:flex;align-items:center;">
                {icon_html}{title}
            </h1>
            {subtitle_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def plotly_layout(title: str = "", height: int = 380) -> dict:
    """Layout Plotly cohérent avec le thème sombre."""
    return dict(
        title=dict(text=title, font=dict(size=16, color="#F1F5F9", family="Inter")),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#CBD5E1", family="Inter", size=12),
        margin=dict(l=20, r=20, t=50, b=20),
        height=height,
        xaxis=dict(gridcolor="rgba(255,255,255,0.08)", zerolinecolor="rgba(255,255,255,0.08)"),
        yaxis=dict(gridcolor="rgba(255,255,255,0.08)", zerolinecolor="rgba(255,255,255,0.08)"),
        legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor="rgba(255,255,255,0.1)"),
    )
