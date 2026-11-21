# datamobilite

Observatoire des données ouvertes sur le transport, la logistique et la mobilité en France.

L'application montre en un coup d'œil :

- **les données disponibles** sur data.gouv.fr, par thème (transports collectifs, route, vélo, recharge électrique, logistique…) ;
- **leurs réutilisations** : applications, cartes et articles construits à partir de ces données ;
- **les schémas de données** qui permettent de publier une même donnée de la même façon partout ;
- **les données de mobilité de l'INSEE** (déplacements domicile-travail, domicile-études, déménagements…).

## Contenu du dépôt

| Fichier | Rôle |
|---|---|
| `app.py` | L'application Streamlit |
| `data/` | Les données affichées (fichiers JSON) et la date du dernier relevé |
| `collecte/collecte.py` | Le script qui interroge les API publiques et met à jour `data/` |
| `.github/workflows/collecte.yml` | La mise à jour automatique, chaque mois |
| `requirements.txt` | Les bibliothèques Python nécessaires |

## Publier l'application (gratuit, sans rien installer)

1. Aller sur [share.streamlit.io](https://share.streamlit.io) et se connecter avec son compte GitHub.
2. Cliquer sur **Create app**, puis choisir ce dépôt, la branche `main` et le fichier `app.py`.
3. Cliquer sur **Deploy**. L'application est en ligne en quelques minutes, avec une adresse à partager.

## Mettre à jour les données

- **Automatiquement** : chaque mois, GitHub relance la collecte et enregistre les nouvelles données. L'application publiée se met à jour toute seule.
- **À la demande** : dans l'onglet **Actions** du dépôt, choisir « Collecte mensuelle des données » puis **Run workflow**.

La collecte prend environ 15 minutes. Elle n'a besoin d'aucune clé d'API.

## Sources

- [API de data.gouv.fr](https://www.data.gouv.fr/api/1/) : jeux de données, API, réutilisations, schémas
- [schema.data.gouv.fr](https://schema.data.gouv.fr) : détail des schémas
- [Catalogue Melodi de l'INSEE](https://catalogue-donnees.insee.fr) et [insee.fr](https://www.insee.fr) : données de mobilité

## Limites à connaître

- Les thèmes reposent sur les **mots-clés** choisis par les producteurs : un jeu mal tagué n'apparaît pas, un jeu peut apparaître sous plusieurs thèmes.
- La thématique d'une réutilisation est choisie par son auteur.
- Les **vues** comptent les visites de la fiche sur data.gouv.fr, pas l'usage réel.
- Le fret, le trafic et le parc de véhicules relèvent du SDES (ministère des Transports), pas encore couvert ici.
