"""Dashboard analytique des promos."""
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mail_manager.ui_theme import PALETTE, hero_header, inject_global_css, plotly_layout

st.set_page_config(page_title="Statistiques — Mail Manager", layout="wide", page_icon="📊")
inject_global_css()

hero_header(
    "Tableau de bord",
    "Vue analytique de vos promotions détectées par l'IA",
    icon="📊",
)


def _collect_emails() -> list:
    """Récupère tous les emails traités depuis la session Streamlit."""
    all_emails = []
    for key, value in st.session_state.items():
        if key.startswith("emails_") and isinstance(value, list):
            all_emails.extend(value)
    return all_emails


emails = _collect_emails()

if not emails:
    st.warning("Aucun email chargé. Retournez à la page principale pour charger vos mails.")
    st.page_link("streamlit_app.py", label="← Retour à la page principale", icon="📧")
    st.stop()

promos = [e for e in emails if e.get("is_promo")]
non_promos = [e for e in emails if not e.get("is_promo")]

# ================= KPIs =================
st.markdown("### Indicateurs clés")

kpi_cols = st.columns(4)
with kpi_cols[0]:
    st.metric("Emails analysés", len(emails))
with kpi_cols[1]:
    promo_rate = (len(promos) / len(emails) * 100) if emails else 0
    st.metric("Promos détectées", len(promos), f"{promo_rate:.0f}% du total")
with kpi_cols[2]:
    unique_companies = len({p.get("company") for p in promos if p.get("company")})
    st.metric("Marques uniques", unique_companies)
with kpi_cols[3]:
    fake_count = sum(1 for p in promos if p.get("is_fake_promo"))
    st.metric("Promos trompeuses", fake_count, f"-{fake_count}" if fake_count else None,
              delta_color="inverse")

st.markdown("")

if not promos:
    st.info("Aucune promo détectée pour afficher des visualisations.")
    st.stop()

# ================= Préparation des données =================
df_rows = []
for p in promos:
    df_rows.append({
        "company": p.get("company") or "Inconnu",
        "category": p.get("category") or "autre",
        "date": p.get("received_date", ""),
        "discount": p.get("discount", ""),
        "is_fake": bool(p.get("is_fake_promo")),
        "has_code": bool(p.get("promo_code")),
        "has_expiry": bool(p.get("expiry_date")),
    })
df = pd.DataFrame(df_rows)

# ================= Ligne 1 : Camembert catégories + Top marques =================
st.markdown("### Répartition par catégorie & marques")

col_left, col_right = st.columns(2)

with col_left:
    cat_counts = df["category"].value_counts()
    fig_cat = go.Figure(data=[go.Pie(
        labels=cat_counts.index.tolist(),
        values=cat_counts.values.tolist(),
        hole=0.55,
        marker=dict(colors=PALETTE, line=dict(color="#0F172A", width=2)),
        textinfo="percent",
        textfont=dict(size=13, color="white", family="Inter"),
        hovertemplate="<b>%{label}</b><br>%{value} promos<br>%{percent}<extra></extra>",
    )])
    layout = plotly_layout("Distribution par catégorie", height=400)
    layout["annotations"] = [dict(
        text=f"<b>{len(promos)}</b><br><span style='font-size:11px;color:#94A3B8'>promos</span>",
        x=0.5, y=0.5, font=dict(size=22, color="#F1F5F9", family="Inter"),
        showarrow=False,
    )]
    fig_cat.update_layout(**layout)
    st.plotly_chart(fig_cat, use_container_width=True)

with col_right:
    top_companies = df["company"].value_counts().head(10).sort_values(ascending=True)
    fig_comp = go.Figure(data=[go.Bar(
        x=top_companies.values,
        y=top_companies.index,
        orientation="h",
        marker=dict(
            color=top_companies.values,
            colorscale=[[0, "#6366F1"], [1, "#EC4899"]],
            line=dict(width=0),
        ),
        text=top_companies.values,
        textposition="outside",
        textfont=dict(color="#F1F5F9"),
        hovertemplate="<b>%{y}</b><br>%{x} promos<extra></extra>",
    )])
    fig_comp.update_layout(**plotly_layout("Top 10 des marques", height=400))
    st.plotly_chart(fig_comp, use_container_width=True)

# ================= Ligne 2 : Évolution temporelle =================
st.markdown("### Évolution dans le temps")

df_time = df[df["date"] != ""].copy()
if not df_time.empty:
    df_time["date_parsed"] = pd.to_datetime(df_time["date"], errors="coerce")
    df_time = df_time.dropna(subset=["date_parsed"])

if not df_time.empty:
    daily = df_time.groupby(df_time["date_parsed"].dt.date).size().reset_index()
    daily.columns = ["date", "count"]

    fig_time = go.Figure()
    fig_time.add_trace(go.Scatter(
        x=daily["date"],
        y=daily["count"],
        mode="lines+markers",
        line=dict(color="#6366F1", width=3, shape="spline"),
        marker=dict(size=9, color="#EC4899", line=dict(color="#F1F5F9", width=2)),
        fill="tozeroy",
        fillcolor="rgba(99, 102, 241, 0.15)",
        hovertemplate="<b>%{x}</b><br>%{y} promos<extra></extra>",
        name="Promos reçues",
    ))
    fig_time.update_layout(**plotly_layout("Promos reçues par jour", height=350))
    st.plotly_chart(fig_time, use_container_width=True)
else:
    st.info("Pas de données temporelles disponibles.")

# ================= Ligne 3 : Qualité des promos =================
st.markdown("### Qualité des promotions")

col_a, col_b, col_c = st.columns(3)

with col_a:
    fake_data = {
        "Fiables": len(df) - df["is_fake"].sum(),
        "Trompeuses": int(df["is_fake"].sum()),
    }
    fig_fake = go.Figure(data=[go.Pie(
        labels=list(fake_data.keys()),
        values=list(fake_data.values()),
        hole=0.6,
        marker=dict(colors=["#10B981", "#EF4444"], line=dict(color="#0F172A", width=2)),
        textinfo="percent",
        textfont=dict(size=14, color="white"),
    )])
    fig_fake.update_layout(**plotly_layout("Fiabilité", height=320))
    st.plotly_chart(fig_fake, use_container_width=True)

with col_b:
    code_data = {
        "Avec code": int(df["has_code"].sum()),
        "Sans code": len(df) - int(df["has_code"].sum()),
    }
    fig_code = go.Figure(data=[go.Pie(
        labels=list(code_data.keys()),
        values=list(code_data.values()),
        hole=0.6,
        marker=dict(colors=["#8B5CF6", "#64748B"], line=dict(color="#0F172A", width=2)),
        textinfo="percent",
        textfont=dict(size=14, color="white"),
    )])
    fig_code.update_layout(**plotly_layout("Codes promo", height=320))
    st.plotly_chart(fig_code, use_container_width=True)

with col_c:
    exp_data = {
        "Avec expiration": int(df["has_expiry"].sum()),
        "Sans expiration": len(df) - int(df["has_expiry"].sum()),
    }
    fig_exp = go.Figure(data=[go.Pie(
        labels=list(exp_data.keys()),
        values=list(exp_data.values()),
        hole=0.6,
        marker=dict(colors=["#F59E0B", "#334155"], line=dict(color="#0F172A", width=2)),
        textinfo="percent",
        textfont=dict(size=14, color="white"),
    )])
    fig_exp.update_layout(**plotly_layout("Dates limites", height=320))
    st.plotly_chart(fig_exp, use_container_width=True)

# ================= Ligne 4 : Heatmap catégories × marques =================
st.markdown("### Croisement catégories × marques")

top_5_comp = df["company"].value_counts().head(8).index.tolist()
df_top = df[df["company"].isin(top_5_comp)]

if not df_top.empty and df_top["category"].nunique() > 1:
    pivot = df_top.pivot_table(
        index="company",
        columns="category",
        aggfunc="size",
        fill_value=0,
    )

    fig_heat = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=pivot.columns.tolist(),
        y=pivot.index.tolist(),
        colorscale=[[0, "#1E293B"], [0.5, "#6366F1"], [1, "#EC4899"]],
        text=pivot.values,
        texttemplate="%{text}",
        textfont=dict(color="white", size=13),
        hovertemplate="<b>%{y}</b> — %{x}<br>%{z} promos<extra></extra>",
        colorbar=dict(title="Nombre", tickfont=dict(color="#CBD5E1")),
    ))
    fig_heat.update_layout(**plotly_layout("Volume par marque et catégorie", height=380))
    st.plotly_chart(fig_heat, use_container_width=True)
else:
    st.info("Pas assez de données pour construire le croisement.")

# ================= Navigation =================
st.markdown("---")
nav_cols = st.columns(3)
with nav_cols[0]:
    st.page_link("streamlit_app.py", label="Retour aux promos", icon="📧",
                 use_container_width=True)
with nav_cols[1]:
    st.page_link("pages/1_Chat_Promos.py", label="Ouvrir le chat", icon="💬",
                 use_container_width=True)
with nav_cols[2]:
    if st.button("Actualiser", use_container_width=True):
        st.rerun()
