# Navettes Île d'Oléron — Calculateur d'itinéraires

Application web (100 % gratuite, 100 % dans le navigateur) qui calcule les
trajets possibles entre un arrêt de départ et un arrêt d'arrivée, en passant
par une ou plusieurs étapes (Points d'Intérêt), avec calcul des temps de
pause à chaque étape et des correspondances entre navettes de couleurs
différentes.

## Contenu du dépôt

| Fichier | Rôle |
|---|---|
| `extract.py` | Transforme les fichiers Excel officiels en fichiers `arrets.csv` et `horaires_long.csv` (à relancer si les horaires changent) |
| `arrets.csv` / `horaires_long.csv` | Données nettoyées, prêtes à l'emploi |
| `planner.py` | Le moteur de calcul d'itinéraires (indépendant de l'interface) |
| `app.py` | L'interface web (Streamlit) |
| `requirements.txt` | Liste des bibliothèques Python nécessaires |

## Principe de fonctionnement du moteur (`planner.py`)

- Vous pouvez monter dans **n'importe quelle navette** à votre arrêt de
  départ, et à chaque **étape** que vous choisissez (car une étape est par
  définition un endroit où vous acceptez de descendre, visiter, puis
  reprendre une navette suivante — même ligne dans les deux sens).
- En cours de route, un changement de navette automatique n'est autorisé
  qu'aux arrêts marqués **« Correspondance »** dans `Arrêts.xlsx` (les
  navettes s'y attendent, indépendamment de l'horaire affiché).
- Comme les fiches horaires ne couvrent qu'une seule journée de service,
  tout trajet trouvé arrive nécessairement le jour même.

Vous pouvez ajuster ces règles directement dans `planner.py` si votre lecture
du terrain diffère (commentaires en tête de fichier).
