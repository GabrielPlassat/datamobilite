"""Observatoire des données transport — application Streamlit.

Lit les fichiers du dossier data/ (produits par collecte/collecte.py) et montre :
les données transport disponibles sur data.gouv.fr, leurs réutilisations,
les schémas de données, et les données de mobilité de l'INSEE.

Lancement en local :  streamlit run app.py
"""
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

DATA = Path(__file__).parent / "data"
ACCENT = "#2f6f8f"
MUTED = "#b8c4cc"
FAMILLES_COULEURS = ["#2f6f8f", "#d08c3a", "#5b8f4e", "#8a5fa8", "#c4504f", "#4a9ba8", "#8c7a5b"]

st.set_page_config(page_title="Observatoire des données transport", layout="wide")


@st.cache_data
def load(name: str) -> pd.DataFrame:
    rows = json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))
    if isinstance(rows, dict):  # format {rows, meta}
        rows = rows.get("rows", [])
    return pd.DataFrame(rows)


def fmt(n) -> str:
    try:
        return f"{int(n):,}".replace(",", " ")
    except (TypeError, ValueError):
        return "—"


def hbar(df, x, y, color=None, color_map=None, height=None):
    fig = px.bar(df, x=x, y=y, orientation="h", color=color, color_discrete_map=color_map,
                 color_discrete_sequence=FAMILLES_COULEURS if color and not color_map else [ACCENT], text=x)
    fig.update_traces(texttemplate="%{text:,}", textposition="outside", cliponaxis=False)
    fig.update_layout(yaxis={"categoryorder": "total ascending", "title": None}, xaxis={"title": None},
                      margin={"l": 0, "r": 40, "t": 10, "b": 0}, height=height or max(260, 28 * len(df)),
                      legend={"title": None, "orientation": "h", "y": -0.08}, separators=", ")
    return fig


themes = load("themes")
topics = load("reuses_topics")
types = load("reuses_types")
top = load("reuses_top")
years = load("reuses_years")
schemas = load("schemas")
insee = load("insee")
try:
    date_collecte = json.loads((DATA / "collecte.json").read_text())["date"]
except Exception:  # noqa: BLE001
    date_collecte = "inconnue"

# ------------------------------------------------------------------ en-tête
st.caption(f"data.gouv.fr · INSEE · transport et logistique · relevé du {date_collecte}")
st.title("Observatoire des données transport")

n_transport = themes.loc[themes.mot_cle == "transport", "jeux_de_donnees"].sum()
n_mobilite = themes.loc[themes.mot_cle == "mobilite", "jeux_de_donnees"].sum()
n_logistique = themes.loc[themes.mot_cle == "logistique", "jeux_de_donnees"].sum()
reu_transport = topics.loc[topics.transport, "reutilisations"].sum()
reu_total = topics.reutilisations.sum()
part = 100 * reu_transport / reu_total if reu_total else 0
nommees = topics[topics.thematique != "Autres"].sort_values("reutilisations", ascending=False).reset_index(drop=True)
rang = int(nommees.index[nommees.transport].tolist()[0]) + 1 if nommees.transport.any() else None
sch_log = (schemas.famille == "Logistique & marchandises").sum()

part_txt = f"{part:.1f}".replace(".", ",")
st.markdown(
    f"Sur data.gouv.fr, **{fmt(n_transport)}** jeux de données portent le mot-clé « transport » et la thématique "
    f"transport compte **{fmt(reu_transport)}** réutilisations, soit **{part_txt} %** de toutes celles de la plateforme. "
    f"La logistique reste le parent pauvre : **{fmt(n_logistique)}** jeux tagués « logistique » et "
    f"**{sch_log}** schémas de données dédiés."
)

y = years.set_index("annee")["reutilisations"]
y.index = y.index.astype(str)
n26, n25 = y.get("2026"), y.get("2025")
sans_jeu = int((schemas.jeux_conformes.fillna(0) == 0).sum())

c1, c2, c3, c4 = st.columns(4)
c1.metric("Jeux tagués « transport »", fmt(n_transport), help=f"et {fmt(n_mobilite)} tagués « mobilité » (les deux se recoupent)")
c2.metric("Réutilisations transport et mobilité", fmt(reu_transport), help=f"{rang}e thématique, hors « Autres »")
last_year = years.annee.astype(str).max()
c3.metric(f"Réutilisations transport créées en {last_year}", fmt(y.get(last_year)),
          delta=f"× {y.get(last_year) / y.iloc[-2]:.1f} vs {y.index[-2]}".replace(".", ",") if len(y) > 1 and y.iloc[-2] else None)
c4.metric("Schémas transport et logistique", fmt(len(schemas)), help=f"{sans_jeu} sans aucun jeu de données conforme")

tab1, tab2, tab3, tab4 = st.tabs(["Données disponibles", "Réutilisations", "Schémas de données", "Mobilités à l'INSEE"])

# ------------------------------------------------------------------ données
with tab1:
    st.caption("Nombre de jeux de données et d'API publiés sous chaque mot-clé. "
               "Un même jeu peut porter plusieurs mots-clés : les chiffres ne s'additionnent pas.")
    col_a, col_b = st.columns(2)
    mesure = col_a.radio("Afficher", ["Jeux de données", "API"], horizontal=True)
    familles = ["Toutes"] + list(dict.fromkeys(themes.famille))
    fam = col_b.selectbox("Famille", familles)
    champ = "jeux_de_donnees" if mesure == "Jeux de données" else "apis"
    d = themes if fam == "Toutes" else themes[themes.famille == fam]
    cmap = {f: FAMILLES_COULEURS[i % len(FAMILLES_COULEURS)] for i, f in enumerate(dict.fromkeys(themes.famille))}
    st.plotly_chart(hbar(d, champ, "theme", color="famille", color_map=cmap), width="stretch")

    st.subheader("Le jeu le plus réutilisé de chaque thème")
    st.dataframe(
        d.sort_values("jeux_de_donnees", ascending=False)[
            ["theme", "famille", "jeux_de_donnees", "apis", "top1_titre", "top1_lien", "top1_reutilisations", "top1_producteur"]],
        hide_index=True, width="stretch",
        column_config={
            "theme": "Thème", "famille": "Famille", "jeux_de_donnees": "Jeux", "apis": "API",
            "top1_titre": "Jeu le plus réutilisé",
            "top1_lien": st.column_config.LinkColumn("Lien", display_text="ouvrir"),
            "top1_reutilisations": "Réutil.", "top1_producteur": "Producteur",
        })

# ------------------------------------------------------------------ réutilisations
with tab2:
    st.caption("Une réutilisation est une application, une carte, un article ou une API construite à partir des données, "
               "et déclarée sur data.gouv.fr par son auteur.")
    a, b = st.columns(2)
    with a:
        st.markdown("**Réutilisations par thématique**")
        t = topics.assign(groupe=topics.transport.map({True: "Transport", False: "Autres thématiques"}))
        st.plotly_chart(hbar(t, "reutilisations", "thematique", color="groupe",
                             color_map={"Transport": ACCENT, "Autres thématiques": MUTED}), width="stretch")
    with b:
        st.markdown("**Ce que l'on construit avec les données transport**")
        st.plotly_chart(hbar(types.dropna(), "reutilisations", "type"), width="stretch")

    st.markdown(f"**Réutilisations transport créées chaque année** (la dernière année s'arrête au {date_collecte})")
    yy = years.assign(annee=years.annee.astype(str))
    fig = px.bar(yy, x="annee", y="reutilisations", text="reutilisations", color_discrete_sequence=[ACCENT])
    fig.update_layout(xaxis={"title": None, "type": "category"}, yaxis={"title": None}, height=300,
                      margin={"l": 0, "r": 0, "t": 10, "b": 0})
    st.plotly_chart(fig, width="stretch")

    st.subheader("Les 25 réutilisations transport les plus vues")
    st.dataframe(
        top[["titre", "lien", "type", "auteur", "vues", "donnees", "creee_le"]],
        hide_index=True, width="stretch",
        column_config={
            "titre": "Réutilisation", "lien": st.column_config.LinkColumn("Lien", display_text="ouvrir"),
            "type": "Type", "auteur": "Auteur", "vues": st.column_config.NumberColumn("Vues", format="%d"),
            "donnees": "Données utilisées", "creee_le": "Créée le",
        })

# ------------------------------------------------------------------ schémas
with tab3:
    st.caption("Un schéma est un modèle commun (noms de colonnes, formats, valeurs autorisées) que les producteurs suivent "
               "pour publier la même donnée de la même façon. C'est ce qui permet de fusionner les fichiers de centaines "
               "de producteurs en une base nationale, comme pour les bornes de recharge.")
    par_fam = (schemas.assign(sans=schemas.jeux_conformes.fillna(0) == 0)
               .groupby("famille").agg(schemas=("schema", "count"), jeux_conformes=("jeux_conformes", "sum"),
                                       sans_jeu=("sans", "sum"))
               .sort_values("jeux_conformes", ascending=False).reset_index())
    cols = st.columns(min(4, len(par_fam)))
    for i, r in par_fam.iterrows():
        cols[i % len(cols)].metric(r.famille, f"{fmt(r.jeux_conformes)} jeux",
                                    help=f"{r.schemas} schéma(s), dont {r.sans_jeu} sans jeu conforme")
    fam_s = st.selectbox("Famille de schémas", ["Toutes"] + par_fam.famille.tolist())
    s = schemas if fam_s == "Toutes" else schemas[schemas.famille == fam_s]
    st.dataframe(
        s[["titre", "lien", "famille", "format", "version", "jeux_conformes", "nb_champs", "champs_cles"]],
        hide_index=True, width="stretch",
        column_config={
            "titre": "Schéma", "lien": st.column_config.LinkColumn("Lien", display_text="ouvrir"),
            "famille": "Famille", "format": "Format", "version": "Version",
            "jeux_conformes": st.column_config.ProgressColumn("Jeux conformes", format="%d", min_value=0,
                                                              max_value=int(schemas.jeux_conformes.max() or 1)),
            "nb_champs": "Champs", "champs_cles": "Premiers champs",
        })

# ------------------------------------------------------------------ INSEE
with tab4:
    st.caption("L'INSEE décrit surtout les déplacements des personnes à partir du recensement : où l'on travaille, comment "
               "on s'y rend, où l'on étudie, où l'on a déménagé. La plupart de ces données sont sur insee.fr et dans son "
               "catalogue Melodi, pas sur data.gouv.fr. Le fret, le trafic et le parc de véhicules relèvent du service "
               "statistique du ministère des Transports (SDES).")
    k1, k2, k3 = st.columns(3)
    k1.metric("Produits de données sur la mobilité", fmt(len(insee)))
    k2.metric("Interrogeables par l'API Melodi", fmt(int(insee.api_melodi.sum())), help="Sans clé, en CSV ou JSON")
    k3.metric("Séries les plus anciennes depuis", str(int(insee.depuis.min())) if insee.depuis.notna().any() else "—",
              help=f"{int((insee.editions.fillna(0) >= 10).sum())} produits ont au moins 10 éditions annuelles")

    fam_i = st.selectbox("Famille", ["Toutes"] + list(dict.fromkeys(insee.famille)))
    di = insee if fam_i == "Toutes" else insee[insee.famille == fam_i]

    dated = di.dropna(subset=["depuis", "dernier_millesime"]).copy()
    if len(dated):
        st.markdown("**Années couvertes par chaque série**")
        dated["debut"] = pd.to_datetime(dated.depuis.astype(int).astype(str) + "-01-01")
        dated["fin"] = pd.to_datetime(dated.dernier_millesime.astype(int).astype(str) + "-12-31")
        dated = dated.sort_values("depuis", ascending=False)
        fig = px.timeline(dated, x_start="debut", x_end="fin", y="produit", color="famille",
                          color_discrete_sequence=FAMILLES_COULEURS, hover_data={"editions": True, "echelle": True})
        fig.update_layout(yaxis={"title": None}, xaxis={"title": None}, height=max(260, 30 * len(dated)),
                          margin={"l": 0, "r": 0, "t": 10, "b": 0}, legend={"title": None, "orientation": "h", "y": -0.15})
        st.plotly_chart(fig, width="stretch")

    di = di.assign(periode=di.apply(
        lambda r: (f"{int(r.depuis)} → {int(r.dernier_millesime)}" if r.depuis != r.dernier_millesime else str(int(r.dernier_millesime)))
        if pd.notna(r.depuis) and pd.notna(r.dernier_millesime) else (f"mis à jour le {r.mise_a_jour}" if r.mise_a_jour else "—"), axis=1))
    st.dataframe(
        di[["produit", "lien", "famille", "type_produit", "acces", "periode", "echelle", "contenu"]],
        hide_index=True, width="stretch",
        column_config={
            "produit": "Produit", "lien": st.column_config.LinkColumn("Lien", display_text="ouvrir"),
            "famille": "Famille", "type_produit": "Type", "acces": "Accès", "periode": "Période",
            "echelle": "Échelle", "contenu": "Contenu",
        })

# ------------------------------------------------------------------ notes
with st.expander("Comment lire ces chiffres"):
    st.markdown(f"""
- **Relevé figé.** Les chiffres viennent des API publiques de data.gouv.fr et de l'INSEE, interrogées le {date_collecte}.
  Ils sont actualisés en relançant `collecte/collecte.py` (automatiquement chaque mois via GitHub Actions).
- **Mots-clés.** Chaque producteur choisit ses mots-clés. Un jeu mal tagué n'apparaît pas, et un jeu peut apparaître sous plusieurs thèmes.
- **Thématique des réutilisations.** C'est l'auteur qui range sa réutilisation dans « Transport et mobilité ». Certaines sont classées ailleurs, notamment dans « Autres ».
- **Vues.** Les vues comptent les visites de la fiche sur data.gouv.fr, pas l'usage réel de l'application.
- **Jeux conformes.** Ce sont les jeux qui déclarent suivre un schéma. Les bases nationales consolidées (IRVE, covoiturage, ZFE…) en regroupent beaucoup d'autres.
- **INSEE.** La liste vient du catalogue Melodi, du moteur de recherche d'insee.fr et des jeux de l'INSEE sur data.gouv.fr. Chaque série n'y figure qu'une fois, avec son dernier millésime.
- **Standards hors data.gouv.fr.** Les horaires de transport en commun suivent des standards internationaux (GTFS, NeTEx, SIRI, GBFS) gérés sur transport.data.gouv.fr.
""")
