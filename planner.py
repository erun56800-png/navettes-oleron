"""
Moteur de calcul d'itinéraires pour les navettes de l'Île d'Oléron.

Lit les fichiers arrets.csv et horaires_long.csv (générés depuis les
fichiers Excel officiels avec extract.py) et calcule les trajets
possibles entre un arrêt de départ, une ou plusieurs étapes (Points
d'Intérêt) et un arrêt d'arrivée.

Hypothèses de modélisation (à ajuster si besoin, voir README) :
  - On peut monter dans n'importe quelle navette à l'arrêt de départ
    choisi (pas besoin de "correspondance" pour l'arrêt de départ).
  - On ne peut changer de navette en cours de route QUE :
      * à un arrêt "Point d'Intérêt" (PI) : on peut reprendre une
        navette ultérieure de LA MÊME couleur, dans le même sens ou
        dans le sens inverse (retour) ;
      * à un arrêt "Correspondance" : on peut reprendre une navette
        d'une des couleurs listées dans la colonne Correspondance,
        sans contrainte stricte d'horaire (les navettes s'attendent).
  - Les fiches horaires ne couvrent qu'une seule journée de service
    (aucune course après minuit) : tout trajet trouvé par le moteur
    arrive donc nécessairement "le jour même".
"""
import csv
from dataclasses import dataclass
from collections import defaultdict


def _hhmm_to_min(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _min_to_hhmm(m):
    return f"{m // 60:02d}:{m % 60:02d}"


@dataclass
class Stop:
    commune: str
    arret: str
    point_interet: bool
    correspondance: list


@dataclass
class Passage:
    ligne_num: int
    couleur: str
    course_num: int
    arret_norm: str
    arret: str
    position: int
    heure_min: int
    remarque: str
    jours_validite: str


@dataclass
class Segment:
    ligne_num: int
    couleur: str
    course_num: int
    arret_depart_norm: str
    heure_depart: int
    arret_arrivee_norm: str
    heure_arrivee: int
    jours_validite: str = ""
    remarque_depart: str = ""
    remarque_arrivee: str = ""


class Reseau:
    def __init__(self, data_dir="."):
        self.stops = {}
        self.courses = defaultdict(list)             # (ligne_num,course_num) -> [Passage]
        self.passages_par_arret = defaultdict(list)   # arret_norm -> [Passage]
        self.jours_validite_defaut = None             # valeur la plus courante, voir _load
        self._load(data_dir)

    def _load(self, data_dir):
        with open(f"{data_dir}/arrets.csv", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                corr = [c.strip().lower() for c in row["correspondance"].split()] if row["correspondance"] else []
                self.stops[row["arret_norm"]] = Stop(
                    commune=row["commune"], arret=row["arret"],
                    point_interet=(row["point_interet"] == "1"),
                    correspondance=corr,
                )
        compte_jours_validite = defaultdict(int)
        with open(f"{data_dir}/horaires_long.csv", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                key = (int(row["ligne_num"]), int(row["course_num"]))
                p = Passage(
                    ligne_num=int(row["ligne_num"]), couleur=row["couleur"].lower(),
                    course_num=int(row["course_num"]), arret_norm=row["arret_norm"],
                    arret=row["arret"], position=len(self.courses[key]),
                    heure_min=_hhmm_to_min(row["heure_passage"]),
                    remarque=row["remarque"],
                    jours_validite=row["jours_validite"],
                )
                self.courses[key].append(p)
                self.passages_par_arret[row["arret_norm"]].append(p)
                if row["arret_norm"] not in self.stops:
                    self.stops[row["arret_norm"]] = Stop(row["commune"], row["arret"], False, [])
                if p.jours_validite:
                    compte_jours_validite[p.jours_validite] += 1
        for lst in self.passages_par_arret.values():
            lst.sort(key=lambda p: p.heure_min)
        # Valeur de jours_validite la plus répandue dans les données : sert de
        # référence pour repérer, à l'affichage, les navettes dont les jours
        # de circulation diffèrent de la norme (ex: service restreint) — voir
        # est_jours_validite_standard() ci-dessous. Le moteur ne filtre PAS
        # les trajets par jour (les fiches horaires actuelles ne couvrent
        # qu'un seul jour type) : ceci ne fait qu'éviter que des horaires à
        # validité particulière soient proposés sans avertissement.
        if compte_jours_validite:
            self.jours_validite_defaut = max(compte_jours_validite, key=compte_jours_validite.get)

    def liste_arrets(self):
        return sorted(self.stops.items(), key=lambda kv: (kv[1].commune, kv[1].arret))

    def liste_points_interet(self):
        return sorted([(n, s) for n, s in self.stops.items() if s.point_interet],
                       key=lambda kv: (kv[1].commune, kv[1].arret))


def est_jours_validite_standard(reseau: "Reseau", jours_validite: str) -> bool:
    """True si `jours_validite` correspond aux jours de circulation les plus
    courants du réseau (ou si on ne dispose d'aucune référence). Permet à
    l'interface de signaler les navettes à validité particulière plutôt que
    de les proposer sans distinction (voir Reseau.jours_validite_defaut)."""
    if not jours_validite or reseau.jours_validite_defaut is None:
        return True
    return jours_validite == reseau.jours_validite_defaut


def _couleurs_transfert_possibles(reseau: "Reseau", arret_norm: str, couleur_courante: str):
    """Correspondances AUTOMATIQUES en cours de route (sans que l'utilisateur
    ait choisi cet arrêt comme étape) : uniquement aux arrêts marqués
    "Correspondance" dans Arrêts.xlsx, vers les couleurs qui y sont listées.
    La possibilité de "descendre en Point d'Intérêt puis reprendre une
    navette suivante (même sens ou sens inverse)" est, elle, gérée au niveau
    des étapes explicitement choisies par l'utilisateur (voir
    calculer_itineraires) : à chaque étape, on autorise l'embarquement sur
    N'IMPORTE QUELLE navette qui dessert cet arrêt ensuite, exactement comme
    au départ initial du trajet.
    """
    stop = reseau.stops.get(arret_norm)
    if stop is None or not stop.correspondance:
        return set()
    return set(stop.correspondance) | {couleur_courante}


def _rechercher_leg(reseau: "Reseau", depart_norm, arrivee_norm, heure_min_depart,
                     max_transferts=3, max_resultats=50):
    """DFS bornée : renvoie une liste de trajets (liste de Segment) reliant
    depart_norm à arrivee_norm, partant au plus tôt à heure_min_depart."""
    resultats = []

    def dfs(arret_norm, heure_min, chemin, nb_transferts, couleur_prec, courses_utilisees):
        if len(resultats) >= max_resultats:
            return
        candidats = [p for p in reseau.passages_par_arret[arret_norm] if p.heure_min >= heure_min]
        if chemin:
            couleurs_ok = _couleurs_transfert_possibles(reseau, arret_norm, couleur_prec)
            candidats = [p for p in candidats if p.couleur in couleurs_ok]

        vues = set()
        for p in candidats:
            key = (p.ligne_num, p.course_num)
            if key in vues or key in courses_utilisees:
                continue
            vues.add(key)
            course = reseau.courses[key]
            for q in course[p.position + 1:]:
                if q.heure_min < p.heure_min:
                    continue
                seg = Segment(p.ligne_num, p.couleur, p.course_num,
                              arret_norm, p.heure_min, q.arret_norm, q.heure_min,
                              jours_validite=p.jours_validite,
                              remarque_depart=p.remarque, remarque_arrivee=q.remarque)
                nouveau_chemin = chemin + [seg]
                if q.arret_norm == arrivee_norm:
                    resultats.append(nouveau_chemin)
                    if len(resultats) >= max_resultats:
                        return
                if nb_transferts < max_transferts and q.arret_norm != arrivee_norm:
                    couleurs_ok2 = _couleurs_transfert_possibles(reseau, q.arret_norm, p.couleur)
                    if couleurs_ok2:
                        dfs(q.arret_norm, q.heure_min, nouveau_chemin, nb_transferts + 1,
                            p.couleur, courses_utilisees | {key})

    dfs(depart_norm, heure_min_depart, [], 0, None, frozenset())
    vus = set()
    uniques = []
    for chemin in resultats:
        sig = tuple((s.ligne_num, s.course_num, s.heure_depart, s.heure_arrivee) for s in chemin)
        if sig not in vus:
            vus.add(sig)
            uniques.append(chemin)
    # On écarte un trajet s'il existe, parmi ceux déjà retenus, un trajet
    # strictement plus simple (moins de correspondances "automatiques" en
    # route) qui part au moins aussi tard ET arrive au moins aussi tôt : ce
    # trajet plus simple est alors une alternative au moins aussi bonne,
    # sans qu'il soit besoin de partir plus tôt -- inutile de proposer un
    # détour de correspondance dans ce cas précis.
    #
    # Le départ compte ici volontairement : un trajet plus simple qui part
    # PLUS TÔT dans la journée n'est PAS une alternative, c'est une
    # proposition différente pour un autre moment de la journée, qui doit
    # rester proposée à côté des autres (ex: un bus direct à 7h ne rend pas
    # inutile un trajet avec correspondance à 16h vers la même destination).
    # De même, on ne compare jamais deux trajets de même taille entre eux
    # (deux départs différents d'une même ligne directe, par exemple,
    # restent tous deux proposés).
    uniques.sort(key=lambda c: (len(c), c[-1].heure_arrivee))
    retenus = []
    for chemin in uniques:
        taille = len(chemin)
        depart = chemin[0].heure_depart
        arrivee = chemin[-1].heure_arrivee
        domine = any(
            len(autre) < taille
            and autre[0].heure_depart >= depart
            and autre[-1].heure_arrivee <= arrivee
            for autre in retenus
        )
        if domine:
            continue
        retenus.append(chemin)
    retenus.sort(key=lambda c: c[-1].heure_arrivee)
    return retenus


def calculer_itineraires(reseau: "Reseau", depart_norm, heure_min_depart_hhmm,
                          etapes_norms, arrivee_norm, max_par_segment=15,
                          max_itineraires=25):
    """
    Calcule les itinéraires complets départ -> étape(s) -> arrivée.
    etapes_norms : liste ORDONNÉE des arrêts-étapes (Points d'Intérêt) choisis.
    Renvoie une liste de dicts triés par heure d'arrivée.
    """
    heure_min_depart = _hhmm_to_min(heure_min_depart_hhmm)
    etapes = [depart_norm] + list(etapes_norms) + [arrivee_norm]
    resultats = []

    def combiner(idx, heure_min, chemin_complet):
        if len(resultats) >= max_itineraires:
            return
        if idx == len(etapes) - 1:
            resultats.append(list(chemin_complet))
            return
        legs = _rechercher_leg(reseau, etapes[idx], etapes[idx + 1], heure_min,
                                max_resultats=max_par_segment)
        for leg in legs:
            combiner(idx + 1, leg[-1].heure_arrivee, chemin_complet + [leg])
            if len(resultats) >= max_itineraires:
                return

    combiner(0, heure_min_depart, [])

    itineraires = []
    for chemin in resultats:
        heure_depart = chemin[0][0].heure_depart
        heure_arrivee = chemin[-1][-1].heure_arrivee
        pauses = []
        for i in range(len(chemin) - 1):
            fin_leg = chemin[i][-1].heure_arrivee
            debut_leg_suivant = chemin[i + 1][0].heure_depart
            pauses.append(debut_leg_suivant - fin_leg)
        itineraires.append({
            "legs": chemin, "heure_depart": heure_depart,
            "heure_arrivee": heure_arrivee,
            "duree_totale": heure_arrivee - heure_depart,
            "pauses": pauses,
        })
    itineraires.sort(key=lambda it: it["heure_arrivee"])
    return itineraires


def label_arret(reseau: "Reseau", arret_norm):
    stop = reseau.stops[arret_norm]
    return f"{stop.commune} — {stop.arret}"


def heure_limite_depart(reseau: "Reseau", etape_norm, arrivee_norm):
    """Dernière heure à laquelle on peut encore partir de etape_norm en
    espérant atteindre arrivee_norm le jour même (None si aucune heure de
    la journée ne le permet)."""
    if etape_norm == arrivee_norm:
        return None
    departs = sorted({p.heure_min for p in reseau.passages_par_arret[etape_norm]}, reverse=True)
    for t in departs:
        if _rechercher_leg(reseau, etape_norm, arrivee_norm, t, max_resultats=1):
            return t
    return None


def options_prochaine_etape(reseau: "Reseau", position_norm, heure_min_hhmm, prochain_norm,
                             arrivee_norm, exclure_pause_nulle=True, max_options=40):
    """
    Mode interactif : liste toutes les façons d'atteindre `prochain_norm`
    (une étape PI, ou l'arrêt final) depuis `position_norm` en partant au
    plus tôt à `heure_min_hhmm`.

    - Si prochain_norm == arrivee_norm : simple liste d'arrivées possibles,
      triée par heure d'arrivée croissante (dernier tronçon du voyage).
    - Sinon : pour chaque arrivée possible à l'étape, calcule la pause
      maximale disponible avant qu'il ne devienne impossible de rejoindre
      arrivee_norm le jour même ; écarte les pauses nulles ; trie par
      pause décroissante (le but demandé : privilégier les plus longues
      pauses tout en garantissant le retour).
    """
    heure_min = _hhmm_to_min(heure_min_hhmm) if isinstance(heure_min_hhmm, str) else heure_min_hhmm
    legs = _rechercher_leg(reseau, position_norm, prochain_norm, heure_min, max_resultats=max_options)

    options = []
    if prochain_norm == arrivee_norm:
        for leg in legs:
            options.append({"leg": leg, "heure_arrivee": leg[-1].heure_arrivee, "pause_max": None})
        options.sort(key=lambda o: o["heure_arrivee"])
        return options

    limite = heure_limite_depart(reseau, prochain_norm, arrivee_norm)
    for leg in legs:
        arrivee = leg[-1].heure_arrivee
        if limite is None or limite <= arrivee:
            continue  # plus aucun moyen de repartir à temps vers l'arrivée finale
        pause = limite - arrivee
        if exclure_pause_nulle and pause <= 0:
            continue
        options.append({"leg": leg, "heure_arrivee": arrivee, "pause_max": pause,
                         "heure_limite_depart": limite})
    options.sort(key=lambda o: (-o["pause_max"], o["heure_arrivee"]))
    return options


def formater_itineraire(reseau: "Reseau", itin):
    """Représentation texte lisible d'un itinéraire complet (tel que renvoyé
    par calculer_itineraires), utile pour l'export, le log ou les tests."""
    lignes = [f"Départ {_min_to_hhmm(itin['heure_depart'])} -> "
              f"Arrivée {_min_to_hhmm(itin['heure_arrivee'])} "
              f"(durée totale {itin['duree_totale']} min)"]
    for i, leg in enumerate(itin["legs"]):
        for seg in leg:
            a = reseau.stops[seg.arret_depart_norm]
            b = reseau.stops[seg.arret_arrivee_norm]
            lignes.append(
                f"  Navette {seg.couleur.capitalize()} (ligne {seg.ligne_num}, "
                f"course {seg.course_num}) : {a.arret} ({_min_to_hhmm(seg.heure_depart)}) "
                f"-> {b.arret} ({_min_to_hhmm(seg.heure_arrivee)})"
            )
        if i < len(itin["pauses"]):
            lignes.append(f"  --- pause de {itin['pauses'][i]} min à cette étape ---")
    return "\n".join(lignes)
