"""Collecte des données de l'Observatoire des données transport.

Interroge les API publiques de data.gouv.fr, schema.data.gouv.fr et de l'INSEE,
puis écrit les fichiers JSON du dossier data/ utilisés par l'application Streamlit.

Lancement :  python collecte/collecte.py
Aucune clé d'API n'est nécessaire.
"""
import datetime
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
API = "https://www.data.gouv.fr/api/1/"
INSEE_ORG = "534fff81a3a7292c64a77e5c"  # organisation INSEE sur data.gouv.fr


def get_json(url, data=None, headers=None, tries=8):
    """Appel HTTP avec nouvelles tentatives (les API publiques coupent parfois la connexion)."""
    err = None
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers=headers or {})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            err = e
            time.sleep(4)
    print(f"ÉCHEC {url} : {err}", file=sys.stderr)
    return None


def dg(path, **params):
    return get_json(API + path + ("?" + urllib.parse.urlencode(params) if params else ""))


def fr(value):
    """Texte français d'un champ multilingue Melodi."""
    if isinstance(value, list):
        for e in value:
            if isinstance(e, dict) and e.get("lang") == "fr":
                return e.get("content") or ""
    return value or ""


# ---------------------------------------------------------------- mots-clés
THEMES = {
    "transport": ("Transport", "Mobilité (général)"),
    "mobilite": ("Mobilité", "Mobilité (général)"),
    "gtfs": ("Horaires GTFS", "Transports collectifs"),
    "transports-en-commun": ("Transports en commun", "Transports collectifs"),
    "ferroviaire": ("Ferroviaire", "Transports collectifs"),
    "maritime": ("Maritime", "Transports collectifs"),
    "trafic": ("Trafic routier", "Route"),
    "securite-routiere": ("Sécurité routière", "Route"),
    "accidents": ("Accidents", "Route"),
    "poids-lourds": ("Poids lourds", "Route"),
    "velo": ("Vélo", "Vélo et partage"),
    "covoiturage": ("Covoiturage", "Vélo et partage"),
    "stationnement": ("Stationnement", "Vélo et partage"),
    "irve": ("Bornes de recharge (IRVE)", "Énergie et véhicules"),
    "zfe": ("Zones à faibles émissions", "Énergie et véhicules"),
    "vehicules": ("Véhicules", "Énergie et véhicules"),
    "logistique": ("Logistique", "Logistique et fret"),
    "fret": ("Fret", "Logistique et fret"),
    "marchandises": ("Marchandises", "Logistique et fret"),
    "livraison": ("Livraison", "Logistique et fret"),
}


def collect_themes():
    rows = []
    for tag, (label, famille) in THEMES.items():
        d = dg("datasets/", tag=tag, page_size=3, sort="-reuses")
        a = dg("dataservices/", tag=tag, page_size=1)
        r = {"mot_cle": tag, "theme": label, "famille": famille,
             "jeux_de_donnees": d["total"] if d else None, "apis": a["total"] if a else None,
             "lien": "https://www.data.gouv.fr/datasets/?tag=" + tag}
        for i in range(3):
            x = (d or {}).get("data", [])[i] if d and len(d.get("data", [])) > i else {}
            r[f"top{i+1}_titre"] = x.get("title")
            r[f"top{i+1}_lien"] = x.get("page")
            r[f"top{i+1}_reutilisations"] = (x.get("metrics") or {}).get("reuses")
            r[f"top{i+1}_producteur"] = (x.get("organization") or {}).get("name")
        rows.append(r)
        print("thème", tag, r["jeux_de_donnees"])
    return rows


# ---------------------------------------------------------------- réutilisations
TOPICS = {
    "transport_and_mobility": "Transport et mobilité", "health": "Santé",
    "housing_and_development": "Logement et aménagement", "food_and_agriculture": "Alimentation et agriculture",
    "culture_and_recreation": "Culture et loisirs", "economy_and_business": "Économie et entreprises",
    "environment_and_energy": "Environnement et énergie", "work_and_training": "Travail et formation",
    "politics_and_public_life": "Vie publique", "safety_and_security": "Sécurité",
    "education_and_research": "Éducation et recherche", "society_and_demography": "Société et démographie",
    "law_and_justice": "Droit et justice", "open_data_tools": "Outils open data", "others": "Autres",
}
T = "transport_and_mobility"


def collect_reuses():
    topics = []
    for t, label in TOPICS.items():
        d = dg("reuses/", topic=t, page_size=1)
        topics.append({"thematique": label, "reutilisations": d["total"] if d else None, "transport": t == T})
    topics.sort(key=lambda r: -(r["reutilisations"] or 0))

    types_ref = dg("reuses/types/") or []
    labels = {x["id"]: x["label"] for x in types_ref}
    types = []
    for ty in types_ref:
        d = dg("reuses/", topic=T, type=ty["id"], page_size=1)
        types.append({"type": ty["label"], "reutilisations": d["total"] if d else None})
    types.sort(key=lambda r: -(r["reutilisations"] or 0))

    top = []
    for r in (dg("reuses/", topic=T, sort="-views", page_size=25) or {}).get("data", []):
        org = (r.get("organization") or {}).get("name")
        owner = " ".join(filter(None, [(r.get("owner") or {}).get("first_name"), (r.get("owner") or {}).get("last_name")]))
        top.append({"titre": r["title"], "type": labels.get(r["type"], r["type"]), "auteur": org or owner,
                    "vues": r["metrics"].get("views"), "jeux_utilises": len(r.get("datasets") or []),
                    "apis_utilisees": len(r.get("dataservices") or []), "creee_le": r["created_at"][:10],
                    "donnees": " · ".join(x.get("title") for x in (r.get("datasets") or [])[:5] if x.get("title")),
                    "lien": r.get("page")})

    years = defaultdict(int)
    page = 1
    while True:
        d = dg("reuses/", topic=T, sort="created", page_size=100, page=page)
        if not d or not d["data"]:
            break
        for r in d["data"]:
            years[r["created_at"][:4]] += 1
        if page * 100 >= d["total"]:
            break
        page += 1
    years = [{"annee": y, "reutilisations": n} for y, n in sorted(years.items())]
    print("réutilisations", sum(r["reutilisations"] or 0 for r in topics))
    return topics, types, top, years


# ---------------------------------------------------------------- schémas
SCHEMAS = {
    "etalab/schema-irve-statique": "Recharge électrique", "etalab/schema-irve-dynamique": "Recharge électrique",
    "etalab/schema-sdirve": "Recharge électrique",
    "etalab/schema-amenagements-cyclables": "Vélo", "etalab/schema-stationnement-cyclable": "Vélo",
    "etalab/schema-stationnement": "Stationnement", "macaron-ai/onstreet-parking-schema": "Stationnement",
    "cnigfr/aire_stationnement": "Stationnement",
    "CEREMA/schema-aire-livraison": "Logistique & marchandises",
    "CEREMA/schema-arrete-circulation-marchandises": "Logistique & marchandises",
    "cnigfr/schema-desserte-transport-bois": "Logistique & marchandises",
    "etalab/schema-zfe": "Réglementation & voirie", "etalab/schema-passage-a-niveau": "Réglementation & voirie",
    "cnigfr/schema-accessibilite-voirie": "Réglementation & voirie", "cnigfr/arret_tc": "Réglementation & voirie",
    "etalab/schema-lieux-covoiturage": "Covoiturage & taxi", "openmaraude/schema-stationstaxi": "Covoiturage & taxi",
    "etalab/schema-comptage-mobilites-site": "Comptage & flottes",
    "etalab/schema-comptage-mobilites-channel": "Comptage & flottes",
    "etalab/schema-comptage-mobilites-measure": "Comptage & flottes",
    "etalab/schema-vehicules-faibles-emissions-renouvellement-parc": "Comptage & flottes",
    "etalab/schema-vehicules-faibles-emissions-renouvellement-parc-synthese": "Comptage & flottes",
}
FORMATS = {"tableschema": "Tableau (CSV)", "jsonschema": "JSON / GeoJSON", "other": "Standard SIG"}


def collect_schemas():
    rows = []
    for s in dg("datasets/schemas/") or []:
        name = s["name"]
        if name not in SCHEMAS:
            continue
        d = dg("datasets/", schema=name, page_size=1)
        nf, keys = None, []
        if (s.get("schema_url") or "").endswith(".json"):
            j = get_json(s["schema_url"])
            if j and s.get("schema_type") == "tableschema" and "fields" in j:
                nf, keys = len(j["fields"]), [f["name"] for f in j["fields"]][:8]
            elif j and s.get("schema_type") == "jsonschema" and len(j.get("properties") or {}) > 2:
                nf, keys = len(j["properties"]), list(j["properties"])[:8]
        kf = ", ".join(keys)
        if s.get("schema_type") == "jsonschema" and not nf:
            kf = "Structure GeoJSON (voir la documentation)"
        if s.get("schema_type") == "other" and not kf:
            kf = "Standard géographique CNIG (voir la documentation)"
        versions = [v["version_name"] for v in s.get("versions") or []]
        rows.append({"schema": name, "titre": s["title"].strip(), "famille": SCHEMAS[name],
                     "format": FORMATS.get(s.get("schema_type"), s.get("schema_type")),
                     "version": versions[-1] if versions else None, "nb_versions": len(versions),
                     "jeux_conformes": d["total"] if d else None, "nb_champs": nf, "champs_cles": kf or None,
                     "description": (s.get("description") or "").strip().replace("\n", " ")[:220],
                     "base_consolidee": bool(s.get("consolidation_dataset_id")),
                     "lien": f"https://schema.data.gouv.fr/{name}/"})
        print("schéma", name, rows[-1]["jeux_conformes"])
    rows.sort(key=lambda r: -(r["jeux_conformes"] or 0))
    return rows


# ---------------------------------------------------------------- INSEE
RES = {"COM": "commune", "IRIS": "IRIS", "EPCI": "EPCI", "ZE2020": "zone d'emploi", "AAV2020": "aire d'attraction",
       "DEP": "département", "REG": "région", "FRANCE": "France", "UU2020": "unité urbaine", "BV2022": "bassin de vie",
       "ARR": "arrondissement", "ARM": "arrondissement municipal"}
SOLR_QUERIES = ["mobilités professionnelles", "mobilités scolaires", "déplacements domicile travail", "base flux de mobilité",
                "fichiers détail mobilités", "migrations résidentielles", "mode de transport", "navettes"]


def insee_search(text):
    body = json.dumps({"q": text, "start": 0, "rows": 100, "sortFields": [{"field": "score", "order": "desc"}],
                       "filters": [{"field": "rubrique", "tag": "tagCategorie", "values": ["statistiques"]}],
                       "facetsField": []}).encode()
    d = get_json("https://www.insee.fr/fr/solr/consultation", data=body,
                 headers={"Content-Type": "application/json; charset=utf-8", "Accept": "application/json"})
    return (d or {}).get("documents", [])


def collect_insee():
    mel = {x["identifier"]: x for x in get_json("https://api.insee.fr/melodi/catalog/all") or []}
    dgi = {}
    page = 1
    while True:
        d = dg("datasets/", organization=INSEE_ORG, page_size=100, page=page)
        if not d:
            break
        dgi.update({x["id"]: x for x in d["data"]})
        if page * 100 >= d["total"]:
            break
        page += 1
    solr = {}
    for q in SOLR_QUERIES:
        for x in insee_search(q):
            solr[x["id"]] = {"id": x["id"], "titre": x["titre"], "sousTitre": x.get("sousTitre"),
                             "date": x.get("dateDiffusion") or x.get("datePublication")}
    solr = list(solr.values())
    rows = []

    def add(**r):
        base = dict.fromkeys(["produit", "famille", "type_produit", "acces", "depuis", "dernier_millesime", "editions",
                              "echelle", "contenu", "lien", "vues_datagouv", "reutilisations_datagouv", "mise_a_jour"])
        base["api_melodi"] = False
        base.update(r)
        rows.append(base)

    def melodi(ident, famille, contenu, dgid=None):
        x = mel.get(ident)
        if not x:
            print("Melodi : absent", ident, file=sys.stderr)
            return
        t = x.get("temporal") or {}
        r = dict(produit=fr(x["title"]), famille=famille, type_produit="Indicateurs et tableaux détaillés",
                 acces="API Melodi + fichier CSV",
                 depuis=int(t["startPeriod"][:4]) if t.get("startPeriod") else None,
                 dernier_millesime=int(t["endPeriod"][:4]) if t.get("endPeriod") else None,
                 echelle=", ".join(dict.fromkeys(RES.get(z["id"], z["id"]) for z in x.get("spatialResolution", []))),
                 contenu=contenu, lien="https://catalogue-donnees.insee.fr/fr/catalogue/recherche/" + ident,
                 api_melodi=True, mise_a_jour=(x.get("modified") or "")[:10] or None)
        if dgid in dgi:
            r["vues_datagouv"] = dgi[dgid]["metrics"].get("views")
            r["reutilisations_datagouv"] = dgi[dgid]["metrics"].get("reuses")
        add(**r)

    melodi("DS_RP_NAVETTES_PRINC", "Domicile-travail", "Lieu de travail des actifs (même commune ou non) et mode de transport principal, par commune et zonages.", "685d96280b33ade4e2634260")
    melodi("DS_RP_NAVETTES_PRINC_IRIS", "Domicile-travail", "Mêmes indicateurs domicile-travail à l'échelle de l'IRIS (quartier).", "6ad16a7406eea90157a47a33")
    melodi("DS_RP_TD_NAVETTES_SEXTRANSPORT_COMP", "Domicile-travail", "Actifs selon le sexe, le lieu de travail et le moyen de transport (voiture, transports en commun, vélo, marche…).", "6a430a7d994f73a50d54d38d")
    melodi("DS_RP_TD_NAVETTES_SEXAGE_COMP", "Domicile-travail", "Actifs selon le sexe, l'âge et le lieu de travail.", "6a430a7c994f73a50d54d38c")
    melodi("DS_RP_TD_NAVETTES_PCSACTIVITY_COMP", "Domicile-travail", "Actifs selon la catégorie socioprofessionnelle, le secteur d'activité et le lieu de travail.", "6a430a7c994f73a50d54d38b")
    melodi("DS_RP_LOGEMENT_PRINC", "Équipement automobile", "Caractéristiques des logements, dont le nombre de voitures du ménage.")

    series = [
        (r"^Mobilités professionnelles\s+en\s+(?:19|20)\d\d\s*:\s*déplacements domicile", "Base flux", "Mobilités professionnelles : déplacements domicile - lieu de travail", "Domicile-travail", "Base flux de mobilité", "Nombre d'actifs pour chaque couple commune de résidence → commune de travail.", "commune → commune"),
        (r"^Mobilités scolaires\s+en\s+(?:19|20)\d\d\s*:\s*déplacements domicile", "Base flux", "Mobilités scolaires : déplacements domicile - lieu d'études", "Domicile-études", "Base flux de mobilité", "Nombre d'élèves et d'étudiants pour chaque couple commune de résidence → commune d'études.", "commune → commune"),
        (r"^Migrations résidentielles\s+en\s+(?:19|20)\d\d\s*:\s*lieu de résidence", "Base flux", "Migrations résidentielles : résidence actuelle - résidence antérieure", "Mobilité résidentielle", "Base flux de mobilité", "Nombre de personnes ayant déménagé, par commune de résidence actuelle et commune de résidence un an avant.", "commune → commune"),
        (r"^Mobilités professionnelles des individus : déplacements commune", "ichier", "Mobilités professionnelles des individus (fichier détail MOBPRO)", "Domicile-travail", "Fichier détail", "Une ligne par actif (anonymisé) : communes de résidence et de travail, mode de transport, âge, catégorie, équipement automobile…", "individu (commune)"),
        (r"^Mobilités scolaires des individus : déplacements commune", "ichier", "Mobilités scolaires des individus (fichier détail MOBSCO)", "Domicile-études", "Fichier détail", "Une ligne par élève ou étudiant (anonymisé) : communes de résidence et d'études, âge, caractéristiques du ménage.", "individu (commune)"),
        (r"^Migrations résidentielles : localisation à la commune de résidence et à la commune", "ichier", "Migrations résidentielles des individus (fichier détail)", "Mobilité résidentielle", "Fichier détail", "Une ligne par personne ayant déménagé : commune actuelle et commune antérieure, caractéristiques.", "individu (commune)"),
        (r"^Activité professionnelle des individus : lieu de travail localisé", "ichier", "Activité professionnelle des individus : lieu de travail à la zone d'emploi", "Domicile-travail", "Fichier détail", "Une ligne par actif : zone d'emploi de résidence et de travail, emploi, mode de transport.", "individu (zone d'emploi)"),
    ]
    for pat, key, nom, fam, typ, contenu, ech in series:
        found = [v for v in solr if re.search(pat, v["titre"]) and key in (v.get("sousTitre") or "")]
        if not found:
            print("INSEE : série introuvable", nom, file=sys.stderr)
            continue
        yrs = sorted(int(y) for v in found for y in re.findall(r"\b(?:19|20)\d\d\b", v["titre"]))
        last = max(found, key=lambda v: v["date"] or "")
        add(produit=nom, famille=fam, type_produit=typ, acces="Fichier à télécharger (insee.fr)", echelle=ech,
            contenu=contenu, depuis=yrs[0] if yrs else None, dernier_millesime=yrs[-1] if yrs else None,
            editions=len(found), mise_a_jour=(last["date"] or "")[:10] or None,
            lien=f"https://www.insee.fr/fr/statistiques/{last['id']}")

    pages = [
        (5430829, "Mode de transport pour aller travailler selon la catégorie socioprofessionnelle", "Domicile-travail", "Tableau national", "Répartition des actifs par mode de transport, selon la catégorie socioprofessionnelle.", "France"),
        (5430864, "Mode de transport pour aller travailler selon les aires d'attraction des villes", "Domicile-travail", "Tableau national", "Répartition des actifs par mode de transport, des grands pôles urbains au rural.", "France"),
        (3575648, "Indicateurs en cartes : mobilités et déplacements", "Synthèses", "Cartes interactives", "Moyens de transport, équipement automobile et flux domicile-travail en cartes.", "commune à région"),
        (5435508, "Mobilités et déplacements : tableau de bord de l'économie française", "Synthèses", "Tableau de bord", "Principaux indicateurs nationaux de mobilité, mis à jour chaque année.", "France"),
    ]
    by_id = {v["id"]: v for v in solr}
    for i, nom, fam, typ, contenu, ech in pages:
        v = by_id.get(i) or {}
        add(produit=nom, famille=fam, type_produit=typ, acces="Tableaux et cartes (insee.fr)", echelle=ech,
            contenu=contenu, mise_a_jour=(v.get("date") or "")[:10] or None,
            lien=f"https://www.insee.fr/fr/statistiques/{i}")

    for i, nom, fam, typ, contenu, ech in [
        ("65c0e835c48bd8b0e5db9076", "Émissions de gaz à effet de serre des déplacements domicile-travail", "Émissions", "Estimation", "Émissions de CO2 estimées pour chaque trajet domicile-travail, selon la distance et le mode de transport.", "commune"),
        ("67fe0fe2423db9c4a05d8ced", "Localisation et accès de la population aux équipements", "Accès aux équipements", "Base permanente des équipements", "Équipements géolocalisés (dont gares, aéroports, taxis) et temps d'accès de la population.", "équipement, commune"),
        ("67edcfd916b9f5ccba6ca1da", "Dénombrement des équipements (commerce, sport, services, transports…)", "Accès aux équipements", "Base permanente des équipements", "Nombre d'équipements par commune, dont les équipements de transport.", "commune"),
    ]:
        x = dgi.get(i)
        if not x:
            continue
        add(produit=nom, famille=fam, type_produit=typ, acces="Fichier à télécharger (data.gouv.fr)", echelle=ech,
            contenu=contenu, mise_a_jour=x["last_update"][:10], lien=x["page"],
            vues_datagouv=x["metrics"].get("views"), reutilisations_datagouv=x["metrics"].get("reuses"))
    print("INSEE", len(rows), "produits")
    return rows


def save(name, rows):
    if not rows:
        print(f"{name} : aucune donnée, fichier conservé tel quel", file=sys.stderr)
        return
    (DATA / f"{name}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    DATA.mkdir(exist_ok=True)
    save("themes", collect_themes())
    topics, types, top, years = collect_reuses()
    save("reuses_topics", topics)
    save("reuses_types", types)
    save("reuses_top", top)
    save("reuses_years", years)
    save("schemas", collect_schemas())
    save("insee", collect_insee())
    (DATA / "collecte.json").write_text(json.dumps({"date": datetime.date.today().isoformat()}), encoding="utf-8")
    print("Terminé.")


if __name__ == "__main__":
    main()
