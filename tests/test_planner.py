"""
Tests unitaires pour planner.py.

Le réseau de test est un petit jeu de données synthétique (écrit dans des
CSV temporaires par la fixture `reseau`), volontairement indépendant des
vraies données d'Oléron (arrets.csv / horaires_long.csv) : les vraies
fiches horaires changent avec le temps, alors que ces tests doivent rester
stables et vérifier des mécanismes précis (correspondance automatique,
pause maximale, etc.).

Lancer avec : pytest
"""
import csv
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from planner import (
    Reseau,
    _hhmm_to_min,
    _min_to_hhmm,
    _rechercher_leg,
    calculer_itineraires,
    est_jours_validite_standard,
    formater_itineraire,
    heure_limite_depart,
    label_arret,
    options_prochaine_etape,
)

ARRETS_FIELDS = ["commune", "arret", "arret_norm", "point_interet", "correspondance"]
HORAIRES_FIELDS = [
    "ligne_num", "couleur", "origine", "destination", "jours_validite", "course_num",
    "heure_ref_depart_ligne", "commune", "arret", "arret_norm", "heure_passage", "remarque",
]

JOURS_STANDARD = "Du lundi au dimanche et jours fériés"


def _ecrire_reseau(data_dir, arrets, passages):
    with open(data_dir / "arrets.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=ARRETS_FIELDS)
        w.writeheader()
        w.writerows(arrets)
    with open(data_dir / "horaires_long.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=HORAIRES_FIELDS)
        w.writeheader()
        w.writerows(passages)


def _arret(commune, arret, norm, pi=0, correspondance=""):
    return {"commune": commune, "arret": arret, "arret_norm": norm,
            "point_interet": str(pi), "correspondance": correspondance}


def _passage(ligne_num, couleur, course_num, arret_norm, heure_passage,
             commune="X", arret="X", jours_validite=JOURS_STANDARD, remarque=""):
    return {
        "ligne_num": ligne_num, "couleur": couleur, "origine": "O", "destination": "D",
        "jours_validite": jours_validite, "course_num": course_num,
        "heure_ref_depart_ligne": heure_passage, "commune": commune, "arret": arret,
        "arret_norm": arret_norm, "heure_passage": heure_passage, "remarque": remarque,
    }


@pytest.fixture
def reseau(tmp_path):
    """
    Petit réseau synthétique :

    - "depart", "arrivee" : arrêts simples.
    - "correspondance1"   : marqué Correspondance -> verte (permet un
      changement automatique en cours de route depuis n'importe quelle
      couleur vers la ligne verte).
    - "sans_correspondance" : même configuration géométrique que
      correspondance1, mais SANS la colonne Correspondance renseignée :
      sert de témoin pour vérifier qu'aucun changement automatique n'y
      est autorisé.
    - "pi" : Point d'Intérêt (point_interet=1), non marqué Correspondance.

    Lignes :
    - bleue course 1 : depart(08:00) -> correspondance1(08:10) -> pi(08:20) -> arrivee(08:30)
    - bleue course 2 : depart(09:00) -> sans_correspondance(09:10)  [s'arrête là]
    - verte  course 1 : correspondance1(08:15) -> destination_verte(08:35)
    - orange course 1 : sans_correspondance(09:15) -> destination_verte(09:35)
    - rouge  course 1 : pi(11:00) -> arrivee(11:20)   (permet de repartir du PI plus tard)
    """
    arrets = [
        _arret("X", "Depart", "depart"),
        _arret("X", "Correspondance1", "correspondance1", correspondance="verte"),
        _arret("X", "SansCorrespondance", "sans_correspondance"),
        _arret("X", "PointInteret", "pi", pi=1),
        _arret("X", "Arrivee", "arrivee"),
        _arret("X", "DestinationVerte", "destination_verte"),
    ]
    passages = [
        _passage(1, "bleue", 1, "depart", "08:00"),
        _passage(1, "bleue", 1, "correspondance1", "08:10"),
        _passage(1, "bleue", 1, "pi", "08:20"),
        _passage(1, "bleue", 1, "arrivee", "08:30"),

        _passage(1, "bleue", 2, "depart", "09:00"),
        _passage(1, "bleue", 2, "sans_correspondance", "09:10"),

        _passage(2, "verte", 1, "correspondance1", "08:15"),
        _passage(2, "verte", 1, "destination_verte", "08:35"),

        _passage(3, "orange", 1, "sans_correspondance", "09:15"),
        _passage(3, "orange", 1, "destination_verte", "09:35"),

        _passage(4, "rouge", 1, "pi", "11:00"),
        _passage(4, "rouge", 1, "arrivee", "11:20"),
    ]
    _ecrire_reseau(tmp_path, arrets, passages)
    return Reseau(str(tmp_path))


# ----------------------------------------------------------------------
# Fonctions utilitaires
# ----------------------------------------------------------------------

def test_conversion_heure_minute_aller_retour():
    for hhmm in ["00:00", "08:05", "13:45", "23:59"]:
        assert _min_to_hhmm(_hhmm_to_min(hhmm)) == hhmm


def test_label_arret(reseau):
    assert label_arret(reseau, "depart") == "X — Depart"


# ----------------------------------------------------------------------
# Chargement du réseau
# ----------------------------------------------------------------------

def test_reseau_charge_bien_tous_les_arrets(reseau):
    assert set(n for n, _ in reseau.liste_arrets()) == {
        "depart", "correspondance1", "sans_correspondance", "pi", "arrivee", "destination_verte",
    }


def test_liste_points_interet_ne_contient_que_les_pi(reseau):
    pi = reseau.liste_points_interet()
    assert [n for n, _ in pi] == ["pi"]


# ----------------------------------------------------------------------
# Trajet direct (aucune correspondance nécessaire)
# ----------------------------------------------------------------------

def test_trajet_direct_sans_correspondance(reseau):
    legs = _rechercher_leg(reseau, "depart", "pi", 8 * 60)
    assert len(legs) == 1
    leg = legs[0]
    assert len(leg) == 1  # un seul segment, pas de changement de navette
    assert leg[0].heure_depart == _hhmm_to_min("08:00")
    assert leg[0].heure_arrivee == _hhmm_to_min("08:20")
    assert leg[0].couleur == "bleue"


# ----------------------------------------------------------------------
# Correspondance automatique
# ----------------------------------------------------------------------

def test_correspondance_automatique_autorisee_a_un_arret_marque(reseau):
    """depart -> destination_verte n'est atteignable qu'en changeant de
    navette (bleue -> verte) à correspondance1, qui est marqué comme
    autorisant la correspondance vers 'verte'."""
    legs = _rechercher_leg(reseau, "depart", "destination_verte", _hhmm_to_min("08:00"))
    assert len(legs) == 1
    leg = legs[0]
    assert [seg.couleur for seg in leg] == ["bleue", "verte"]
    assert leg[0].arret_arrivee_norm == "correspondance1"
    assert leg[1].arret_depart_norm == "correspondance1"
    assert leg[-1].heure_arrivee == _hhmm_to_min("08:35")


def test_pas_de_correspondance_automatique_a_un_arret_non_marque(reseau):
    """Même géométrie (bleue s'arrête, orange repart peu après vers la
    même destination) mais sans la colonne Correspondance renseignée :
    aucun trajet automatique ne doit être trouvé."""
    legs = _rechercher_leg(reseau, "depart", "destination_verte", _hhmm_to_min("09:00"))
    assert legs == []


def test_trajet_tardif_avec_correspondance_pas_ecarte_par_un_direct_matinal(tmp_path):
    """Un trajet direct très tôt le matin ne doit PAS faire disparaître un
    trajet avec correspondance beaucoup plus tard dans la journée vers la
    même destination : ce sont deux propositions différentes pour deux
    moments de la journée, pas des alternatives l'une de l'autre (bug
    précédent : le filtrage comparait l'heure d'arrivée d'un trajet
    complexe à la MEILLEURE heure d'arrivée jamais vue pour un trajet plus
    simple, sans tenir compte de l'heure de départ)."""
    arrets = [
        _arret("X", "Depart", "depart"),
        _arret("X", "Correspondance1", "correspondance1", correspondance="verte"),
        _arret("X", "Destination", "destination"),
    ]
    passages = [
        _passage(1, "bleue", 1, "depart", "07:00"),
        _passage(1, "bleue", 1, "destination", "07:10"),
        _passage(2, "bleue", 2, "depart", "16:00"),
        _passage(2, "bleue", 2, "correspondance1", "16:10"),
        _passage(3, "verte", 1, "correspondance1", "16:15"),
        _passage(3, "verte", 1, "destination", "16:30"),
    ]
    _ecrire_reseau(tmp_path, arrets, passages)
    r = Reseau(str(tmp_path))
    legs = _rechercher_leg(r, "depart", "destination", _hhmm_to_min("06:00"), max_resultats=50)
    heures_arrivee = sorted(leg[-1].heure_arrivee for leg in legs)
    assert heures_arrivee == [_hhmm_to_min("07:10"), _hhmm_to_min("16:30")]


def test_detour_inutile_a_la_meme_fenetre_horaire_reste_ecarte(tmp_path):
    """En revanche, un détour par correspondance qui part à la même heure
    qu'un trajet direct mais arrive plus tard doit toujours être écarté :
    le trajet direct est alors une alternative strictement au moins aussi
    bonne, sans qu'il soit besoin de partir plus tôt."""
    arrets = [
        _arret("X", "Depart", "depart"),
        _arret("X", "Correspondance1", "correspondance1", correspondance="verte"),
        _arret("X", "Destination", "destination"),
    ]
    passages = [
        _passage(1, "bleue", 1, "depart", "08:00"),
        _passage(1, "bleue", 1, "destination", "08:10"),
        _passage(2, "bleue", 2, "depart", "08:00"),
        _passage(2, "bleue", 2, "correspondance1", "08:12"),
        _passage(3, "verte", 1, "correspondance1", "08:15"),
        _passage(3, "verte", 1, "destination", "08:30"),
    ]
    _ecrire_reseau(tmp_path, arrets, passages)
    r = Reseau(str(tmp_path))
    legs = _rechercher_leg(r, "depart", "destination", _hhmm_to_min("06:00"), max_resultats=50)
    assert len(legs) == 1
    assert [seg.couleur for seg in legs[0]] == ["bleue"]
    assert legs[0][-1].heure_arrivee == _hhmm_to_min("08:10")


def test_un_depart_tres_ramifie_ne_masque_pas_un_depart_ulterieur_meilleur(tmp_path):
    """Le premier départ trouvé par la recherche (08:00) se ramifie en 5
    correspondances possibles (couleurs c1 à c5), toutes arrivant après
    09:00. Un second départ, plus tard (08:30), permet lui d'arriver dès
    08:50 via une correspondance différente (c6) -- objectivement la
    meilleure option.

    Bug précédent : le budget de résultats passé par l'appelant
    (`max_resultats`) bornait directement la recherche brute en profondeur
    (DFS). Comme le premier départ, à lui seul, produisait déjà 5 chemins
    bruts, la recherche s'arrêtait après avoir exploré uniquement SA
    ramification, sans jamais essayer le second départ -- alors même que
    ce dernier menait à une meilleure arrivée. Avec max_resultats=3, seuls
    les 3 premiers chemins du départ ramifié (arrivées 09:00/09:05/09:10)
    étaient renvoyés, jamais celui à 08:50.
    """
    arrets = [
        _arret("X", "Depart", "depart"),
        _arret("X", "Correspondance1", "correspondance1", correspondance="c1 c2 c3 c4 c5 c6"),
        _arret("X", "Arrivee", "arrivee"),
    ]
    passages = [
        _passage(1, "bleue", 1, "depart", "08:00"),
        _passage(1, "bleue", 1, "correspondance1", "08:10"),
        _passage(2, "c1", 1, "correspondance1", "08:12"),
        _passage(2, "c1", 1, "arrivee", "09:00"),
        _passage(3, "c2", 1, "correspondance1", "08:12"),
        _passage(3, "c2", 1, "arrivee", "09:05"),
        _passage(4, "c3", 1, "correspondance1", "08:12"),
        _passage(4, "c3", 1, "arrivee", "09:10"),
        _passage(5, "c4", 1, "correspondance1", "08:12"),
        _passage(5, "c4", 1, "arrivee", "09:15"),
        _passage(6, "c5", 1, "correspondance1", "08:12"),
        _passage(6, "c5", 1, "arrivee", "09:20"),
        _passage(7, "bleue", 2, "depart", "08:30"),
        _passage(7, "bleue", 2, "correspondance1", "08:40"),
        _passage(8, "c6", 1, "correspondance1", "08:42"),
        _passage(8, "c6", 1, "arrivee", "08:50"),
    ]
    _ecrire_reseau(tmp_path, arrets, passages)
    r = Reseau(str(tmp_path))
    legs = _rechercher_leg(r, "depart", "arrivee", _hhmm_to_min("06:00"), max_resultats=3)
    assert len(legs) == 3
    # La meilleure arrivée (08:50, via le second départ) doit être trouvée
    # et remonter en tête, pas être masquée par les 5 branches du premier
    # départ à elle seule.
    assert legs[0][-1].heure_arrivee == _hhmm_to_min("08:50")
    assert legs[0][-1].couleur == "c6"


def test_pi_seul_ne_suffit_pas_a_activer_la_correspondance_automatique(reseau):
    """Être un Point d'Intérêt ne suffit pas : sans la colonne
    Correspondance renseignée, 'pi' ne permet pas non plus de changement
    automatique en cours de route (bleue -> rouge)."""
    legs = _rechercher_leg(reseau, "depart", "arrivee", _hhmm_to_min("08:00"))
    # Le seul trajet trouvé est le trajet direct en bleue (08:00 -> 08:30) ;
    # la correspondance bleue -> rouge au PI n'est PAS proposée automatiquement.
    assert len(legs) == 1
    assert [seg.couleur for seg in legs[0]] == ["bleue"]


def test_etape_choisie_explicitement_permet_de_repartir_apres(reseau):
    """Si l'utilisateur choisit explicitement 'pi' comme étape (deux appels
    distincts, comme le fait calculer_itineraires), il peut reprendre
    N'IMPORTE QUELLE navette qui dessert 'pi' par la suite : soit rester
    dans la bleue qui continue jusqu'à 'arrivee', soit une tout autre
    couleur (ici la rouge) -- sans la restriction "même couleur ou couleurs
    listées en Correspondance" qui s'applique, elle, aux transferts
    automatiques en cours de route."""
    leg_vers_pi = _rechercher_leg(reseau, "depart", "pi", _hhmm_to_min("08:00"))
    assert leg_vers_pi and leg_vers_pi[0][-1].heure_arrivee == _hhmm_to_min("08:20")

    leg_depuis_pi = _rechercher_leg(reseau, "pi", "arrivee", _hhmm_to_min("08:20"))
    couleurs_par_chemin = {tuple(seg.couleur for seg in leg) for leg in leg_depuis_pi}
    assert ("bleue",) in couleurs_par_chemin
    assert ("rouge",) in couleurs_par_chemin


# ----------------------------------------------------------------------
# calculer_itineraires (bout en bout, avec étape)
# ----------------------------------------------------------------------

def test_calculer_itineraires_avec_etape(reseau):
    # Deux itinéraires : rester dans la bleue qui continue jusqu'à
    # 'arrivee' (08:30), ou repartir plus tard en rouge (11:20).
    itins = calculer_itineraires(reseau, "depart", "08:00", ["pi"], "arrivee")
    assert len(itins) == 2
    assert [it["heure_arrivee"] for it in itins] == sorted(it["heure_arrivee"] for it in itins)

    plus_rapide = itins[0]
    assert plus_rapide["heure_depart"] == _hhmm_to_min("08:00")
    assert plus_rapide["heure_arrivee"] == _hhmm_to_min("08:30")
    assert plus_rapide["pauses"] == [0]

    plus_tardif = itins[1]
    assert plus_tardif["heure_arrivee"] == _hhmm_to_min("11:20")
    assert plus_tardif["pauses"] == [_hhmm_to_min("11:00") - _hhmm_to_min("08:20")]


def test_calculer_itineraires_sans_solution(reseau):
    """Aucune navette ne part assez tôt pour permettre le trajet : liste vide."""
    assert calculer_itineraires(reseau, "depart", "10:00", [], "pi") == []


# ----------------------------------------------------------------------
# heure_limite_depart / options_prochaine_etape (mode interactif)
# ----------------------------------------------------------------------

def test_heure_limite_depart(reseau):
    # Depuis 'pi', la seule navette du jour vers 'arrivee' part à 11:00.
    assert heure_limite_depart(reseau, "pi", "arrivee") == _hhmm_to_min("11:00")


def test_heure_limite_depart_aucune_solution(reseau):
    # 'destination_verte' n'a aucune navette vers 'arrivee'.
    assert heure_limite_depart(reseau, "destination_verte", "arrivee") is None


def test_options_prochaine_etape_calcule_la_pause_max(reseau):
    options = options_prochaine_etape(reseau, "depart", "08:00", "pi", "arrivee")
    assert len(options) == 1
    opt = options[0]
    assert opt["heure_arrivee"] == _hhmm_to_min("08:20")
    # Limite de départ depuis 'pi' = 11:00 -> pause max = 11:00 - 08:20 = 160 min
    assert opt["pause_max"] == _hhmm_to_min("11:00") - _hhmm_to_min("08:20")


def test_options_prochaine_etape_exclut_les_pauses_nulles_ou_negatives(reseau):
    # Depuis 'depart', la seule façon d'atteindre 'correspondance1' est la
    # bleue (arrivée 08:10) ; or c'est aussi la toute dernière navette de la
    # journée permettant de repartir de 'correspondance1' vers 'arrivee'
    # (heure_limite_depart == 08:10) : la pause serait nulle, l'option doit
    # donc être exclue plutôt que proposée avec 0 minute de battement.
    assert heure_limite_depart(reseau, "correspondance1", "arrivee") == _hhmm_to_min("08:10")
    options = options_prochaine_etape(reseau, "depart", "08:00", "correspondance1", "arrivee")
    assert options == []


def test_options_prochaine_etape_vers_larrivee_finale(reseau):
    # Deux façons d'atteindre l'arrivée depuis 'pi' (bleue directe ou
    # rouge plus tard), triées par heure d'arrivée croissante.
    options = options_prochaine_etape(reseau, "pi", "08:20", "arrivee", "arrivee")
    assert len(options) == 2
    assert all(o["pause_max"] is None for o in options)
    assert [o["heure_arrivee"] for o in options] == [_hhmm_to_min("08:30"), _hhmm_to_min("11:20")]


# ----------------------------------------------------------------------
# jours_validite
# ----------------------------------------------------------------------

def test_jours_validite_defaut_est_la_valeur_majoritaire(reseau):
    assert reseau.jours_validite_defaut == JOURS_STANDARD


def test_est_jours_validite_standard_detecte_les_exceptions(tmp_path):
    arrets = [_arret("X", "Depart", "depart"), _arret("X", "Arrivee", "arrivee")]
    passages = [
        _passage(1, "bleue", 1, "depart", "08:00", jours_validite=JOURS_STANDARD),
        _passage(1, "bleue", 1, "arrivee", "08:10", jours_validite=JOURS_STANDARD),
        _passage(1, "bleue", 2, "depart", "09:00", jours_validite=JOURS_STANDARD),
        _passage(1, "bleue", 2, "arrivee", "09:10", jours_validite=JOURS_STANDARD),
        _passage(2, "rouge", 1, "depart", "10:00", jours_validite="Le dimanche uniquement"),
        _passage(2, "rouge", 1, "arrivee", "10:10", jours_validite="Le dimanche uniquement"),
    ]
    _ecrire_reseau(tmp_path, arrets, passages)
    r = Reseau(str(tmp_path))
    assert r.jours_validite_defaut == JOURS_STANDARD
    assert est_jours_validite_standard(r, JOURS_STANDARD) is True
    assert est_jours_validite_standard(r, "Le dimanche uniquement") is False

    legs = _rechercher_leg(r, "depart", "arrivee", _hhmm_to_min("10:00"))
    assert legs and legs[0][0].jours_validite == "Le dimanche uniquement"


def test_remarque_propagee_sur_le_segment(tmp_path):
    arrets = [_arret("X", "Depart", "depart"), _arret("X", "Arrivee", "arrivee")]
    passages = [
        _passage(1, "bleue", 1, "depart", "08:00", remarque="Départ info"),
        _passage(1, "bleue", 1, "arrivee", "08:10", remarque="Correspondance navette verte"),
    ]
    _ecrire_reseau(tmp_path, arrets, passages)
    r = Reseau(str(tmp_path))
    legs = _rechercher_leg(r, "depart", "arrivee", _hhmm_to_min("08:00"))
    seg = legs[0][0]
    assert seg.remarque_depart == "Départ info"
    assert seg.remarque_arrivee == "Correspondance navette verte"


# ----------------------------------------------------------------------
# formater_itineraire
# ----------------------------------------------------------------------

def test_formater_itineraire(reseau):
    # On choisit volontairement l'itinéraire qui repart en rouge après une
    # vraie pause, pour couvrir à la fois le formatage de deux navettes de
    # couleurs différentes et celui d'une ligne de pause non nulle.
    itins = calculer_itineraires(reseau, "depart", "08:00", ["pi"], "arrivee")
    itin_rouge = next(it for it in itins if it["legs"][-1][0].couleur == "rouge")
    texte = formater_itineraire(reseau, itin_rouge)
    assert "Départ 08:00" in texte
    assert "Arrivée 11:20" in texte
    assert "Navette Bleue" in texte
    assert "Navette Rouge" in texte
    assert f"pause de {_hhmm_to_min('11:00') - _hhmm_to_min('08:20')} min" in texte
