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
| `tests/` | Tests unitaires du moteur (`pytest`), sur un jeu de données synthétique |
| `requirements.txt` | Bibliothèques Python nécessaires pour faire tourner l'application |
| `requirements-dev.txt` | + les outils nécessaires pour développer/tester (`pytest`) |

## Données horaires

`arrets.csv` et `horaires_long.csv` sont générés par `extract.py` à partir
des fiches horaires officielles (fichiers Excel `Arrêts.xlsx` et
`Fiches_Horaires.xlsx`), pour **une saison/édition donnée** — ces fichiers
Excel ne sont pas versionnés dans ce dépôt et les CSV eux-mêmes ne portent
aucune information de saison ou de date de validité. Il faut donc suivre
"à la main" la fraîcheur des données (par ex. via la date/le message du
dernier commit qui a touché ces deux CSV) et relancer `extract.py` avec les
fichiers Excel à jour dès que de nouvelles fiches horaires officielles sont
publiées.

Concrètement aujourd'hui, toutes les courses du jeu de données ont la même
valeur de validité (« Du lundi au dimanche et jours fériés ») : le moteur
ne filtre donc pas les trajets par jour de la semaine. Si une future mise à
jour introduit des navettes à jours de circulation restreints (ex. « sauf
le dimanche »), l'application les signalera par un avertissement dans
l'itinéraire proposé plutôt que de les filtrer elle-même — vérifiez
toujours l'horaire réel avant de partir, comme le rappelle l'avertissement
affiché en bas de l'application.

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

## Tests

```
pip install -r requirements-dev.txt
pytest
```

Les tests (`tests/test_planner.py`) utilisent un petit réseau de navettes
synthétique généré à la volée, indépendant des vraies données d'Oléron, pour
vérifier précisément les règles ci-dessus (correspondance automatique
uniquement aux arrêts marqués, pause maximale, absence de solution le jour
même, etc.). Ils ne dépendent donc pas du contenu de `arrets.csv` /
`horaires_long.csv` et continuent de fonctionner même quand les horaires
officiels changent.

## Obtenir un .exe Windows (application de bureau)

En plus de la version web (Streamlit Community Cloud), le dépôt contient
tout le nécessaire pour obtenir un fichier `.exe` autonome, construit
gratuitement par GitHub (pas d'installation locale nécessaire pour le
construire) :

- `launcher.py` : démarre le serveur Streamlit et ouvre le navigateur
  automatiquement sur `http://localhost:8501`.
- `.github/workflows/build-exe.yml` : demande à GitHub Actions de
  construire l'exécutable Windows avec PyInstaller à chaque envoi de code,
  ou à la demande.

### Récupérer le .exe

1. Sur la page du dépôt GitHub, cliquez sur l'onglet **Actions**.
2. Cliquez sur le workflow **« Construire l'exécutable Windows »**.
3. Cliquez sur **« Run workflow »** (bouton à droite) puis confirmez.
   Patientez 3 à 5 minutes pendant que GitHub construit l'exécutable sur
   une machine Windows dans le cloud.
4. Une fois le run terminé (coche verte), cliquez dessus, puis en bas de
   la page téléchargez l'archive **« OleronNavettes-Windows »**.
5. Décompressez l'archive sur un PC Windows : le fichier
   `OleronNavettes.exe` s'y trouve, à côté d'un dossier `_internal`
   (à garder dans le même dossier, ne pas déplacer l'exe seul).
   Double-clic dessus : l'application s'ouvre dans le navigateur par
   défaut.

Remarques :
- L'exécutable est assez volumineux (~150-200 Mo) car il embarque Python
  et Streamlit ; c'est normal pour ce type d'empaquetage.
- Windows Defender / SmartScreen peut afficher un avertissement la
  première fois (exécutable non signé numériquement) : cliquer sur
  « Informations complémentaires » puis « Exécuter quand même ».
- Ce `.exe` n'a besoin d'aucune connexion internet pour fonctionner (les
  données horaires sont incluses dedans) ; il faudra reconstruire un
  nouvel exe après une mise à jour de `horaires_long.csv`.

## Licence

Ce projet est distribué sous licence [GNU AGPL v3.0](LICENSE). En résumé :
vous pouvez librement utiliser, modifier et redistribuer ce code, y compris
à des fins commerciales, à condition que toute version modifiée — y compris
si elle n'est mise à disposition que via un service en ligne — reste
disponible sous la même licence avec son code source complet.
