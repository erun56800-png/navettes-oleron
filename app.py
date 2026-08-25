import datetime
import pandas as pd
import streamlit as st
from planner import (
    Reseau, calculer_itineraires, label_arret, _min_to_hhmm, _hhmm_to_min,
    est_jours_validite_standard,
)

st.set_page_config(page_title="Navettes Île d'Oléron — Itinéraire interactif", page_icon="🚌",
                    layout="wide")

MAX_PAR_SEGMENT = 30
MAX_ITINERAIRES = 150


@st.cache_resource
def charger_reseau():
    return Reseau(".")


reseau = charger_reseau()

arrets = reseau.liste_arrets()
labels_arrets = [f"{s.commune} — {s.arret}" for _, s in arrets]
norms_arrets = [n for n, _ in arrets]

pi = reseau.liste_points_interet()
labels_pi = {n: f"{s.commune} — {s.arret}" for n, s in pi}

st.title("🚌 Navettes de l'Île d'Oléron")
st.caption(
    "Indiquez votre arrêt de départ, votre heure minimum et votre arrêt d'arrivée "
    "(le retour — par défaut le même que le départ, pour un aller-retour dans la "
    "journée). Ajoutez des étapes si vous le souhaitez : le tableau liste alors, "
    "sans rien présélectionner, TOUS les itinéraires complets possibles, avec la "
    "durée d'attente avant le départ et la durée de pause à chaque étape, tout en "
    "garantissant le retour à l'arrivée le jour même."
)

# ----------------------------------------------------------------------
# Départ / arrivée / heure minimum
# ----------------------------------------------------------------------
if "idx_dep" not in st.session_state:
    st.session_state.idx_dep = 0
if "idx_arr" not in st.session_state:
    st.session_state.idx_arr = st.session_state.idx_dep  # par défaut : arrivée = départ

col1, col2, col3 = st.columns(3)
with col1:
    st.selectbox("Arrêt de départ", range(len(labels_arrets)),
                 format_func=lambda i: labels_arrets[i], key="idx_dep")
with col2:
    st.selectbox("Arrêt d'arrivée (retour)", range(len(labels_arrets)),
                 format_func=lambda i: labels_arrets[i], key="idx_arr")
with col3:
    heure_min_input = st.time_input("Heure de départ minimum", value=datetime.time(9, 0))

depart_norm = norms_arrets[st.session_state.idx_dep]
arrivee_norm = norms_arrets[st.session_state.idx_arr]
heure_min_str = heure_min_input.strftime("%H:%M")
heure_min_minutes = _hhmm_to_min(heure_min_str)

# ----------------------------------------------------------------------
# Étapes (Points d'Intérêt), dans l'ordre de visite
# ----------------------------------------------------------------------
if "etapes" not in st.session_state:
    st.session_state.etapes = []

# Retire du parcours toute étape devenue invalide (choisie entretemps comme
# départ ou arrivée).
st.session_state.etapes = [n for n in st.session_state.etapes if n not in (depart_norm, arrivee_norm)]

st.subheader("Étapes à visiter (facultatif, dans l'ordre)")

for i in range(len(st.session_state.etapes)):
    exclus = (set(st.session_state.etapes) | {depart_norm, arrivee_norm}) - {st.session_state.etapes[i]}
    dispo = [n for n, _ in pi if n not in exclus]
    colA, colB = st.columns([6, 1])
    with colA:
        choix = st.selectbox(
            f"Étape {i + 1}", dispo,
            index=dispo.index(st.session_state.etapes[i]),
            format_func=lambda n: labels_pi[n],
            key=f"etape_{i}",
        )
        st.session_state.etapes[i] = choix
    with colB:
        st.write("")
        if st.button("✕", key=f"etape_del_{i}", help="Retirer cette étape"):
            st.session_state.etapes.pop(i)
            st.rerun()

dispo_ajout = [n for n, _ in pi if n not in (set(st.session_state.etapes) | {depart_norm, arrivee_norm})]
if dispo_ajout:
    if st.button("➕ Ajouter une étape"):
        st.session_state.etapes.append(dispo_ajout[0])
        st.rerun()
else:
    st.caption("Tous les Points d'Intérêt disponibles sont déjà utilisés dans cet itinéraire.")

etapes_labels = [labels_pi[n] for n in st.session_state.etapes]

st.divider()


def afficher_leg(leg):
    for idx, seg in enumerate(leg):
        if idx > 0:
            # Attente à une correspondance AUTOMATIQUE (choisie par le moteur en
            # cours de route, pas par l'utilisateur) : à afficher explicitement,
            # sans quoi deux itinéraires peuvent sembler identiques ("même
            # départ, même nombre de navettes") alors qu'ils impliquent une
            # attente très différente à un arrêt de correspondance intermédiaire.
            attente_corr = seg.heure_depart - leg[idx - 1].heure_arrivee
            if attente_corr > 0:
                st.caption(f"⏸️ Correspondance : {attente_corr} min d'attente à "
                           f"{reseau.stops[seg.arret_depart_norm].arret}")
        a = reseau.stops[seg.arret_depart_norm]
        b = reseau.stops[seg.arret_arrivee_norm]
        st.write(
            f"🚏 Navette **{seg.couleur.capitalize()}** (ligne {seg.ligne_num}, "
            f"course {seg.course_num}) : {a.arret} ({_min_to_hhmm(seg.heure_depart)}) "
            f"→ {b.arret} ({_min_to_hhmm(seg.heure_arrivee)})"
        )
        if not est_jours_validite_standard(reseau, seg.jours_validite):
            st.warning(f"⚠️ Cette navette ne circule pas tous les jours : {seg.jours_validite}. "
                       "Vérifiez qu'elle circule bien le jour de votre trajet.")
        remarques = {r for r in (seg.remarque_depart, seg.remarque_arrivee) if r}
        for remarque in remarques:
            st.caption(f"ℹ️ {remarque}")


# ----------------------------------------------------------------------
# Calcul et tableau exhaustif des itinéraires possibles
# ----------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def _calculer_itineraires(depart_norm, heure_min_str, etapes_tuple, arrivee_norm):
    return calculer_itineraires(
        reseau, depart_norm, heure_min_str, list(etapes_tuple), arrivee_norm,
        max_par_segment=MAX_PAR_SEGMENT, max_itineraires=MAX_ITINERAIRES,
    )


if depart_norm == arrivee_norm and not st.session_state.etapes:
    st.info("Ajoutez au moins une étape pour construire un aller-retour "
            "(départ = arrivée pour l'instant).")
else:
    itineraires = _calculer_itineraires(depart_norm, heure_min_str, tuple(st.session_state.etapes), arrivee_norm)

    if not itineraires:
        st.error("Aucun itinéraire ne permet de rejoindre l'arrivée le jour même avec ces paramètres.")
    else:
        rows = []
        for itin in itineraires:
            row = {
                "⚠️": "",
                "Durée avant départ (min)": itin["heure_depart"] - heure_min_minutes,
                "Horaire de départ": _min_to_hhmm(itin["heure_depart"]),
            }
            for i, label in enumerate(etapes_labels):
                row[f"Horaire d'arrivée — {label}"] = _min_to_hhmm(itin["legs"][i][-1].heure_arrivee)
                row[f"Durée à l'étape (min) — {label}"] = itin["pauses"][i]
                row[f"Horaire de départ — {label}"] = _min_to_hhmm(itin["legs"][i + 1][0].heure_depart)
            row["Horaire d'arrivée à l'arrivée"] = _min_to_hhmm(itin["heure_arrivee"])

            tous_segments = [seg for leg in itin["legs"] for seg in leg]
            if any(not est_jours_validite_standard(reseau, seg.jours_validite) for seg in tous_segments):
                row["⚠️"] = "⚠️"
            rows.append(row)

        df = pd.DataFrame(rows)
        df.index = range(1, len(df) + 1)
        df.index.name = "N°"

        st.write(f"**{len(itineraires)} itinéraire(s) complet(s)** trouvé(s), "
                 "triés par heure d'arrivée croissante :")
        if len(itineraires) >= MAX_ITINERAIRES:
            st.caption(f"⚠️ Résultat limité aux {MAX_ITINERAIRES} premiers itinéraires "
                       "(triés par heure d'arrivée) ; affinez votre recherche (ajoutez une "
                       "étape, avancez l'heure minimum) si besoin.")
        hauteur_tableau = min(38 + 35 * len(df), 600)
        st.dataframe(df, use_container_width=True, height=hauteur_tableau)
        if etapes_labels:
            st.caption("↔️ Le tableau se parcourt horizontalement s'il ne tient pas entièrement "
                       "à l'écran (une colonne par étape).")
        st.caption("⚠️ dans la première colonne = au moins une navette de cet itinéraire "
                   "ne circule pas tous les jours (voir le détail ci-dessous).")

        st.subheader("Détail des navettes à prendre")
        numero = st.number_input(
            "Voir le détail de la ligne n°", min_value=1, max_value=len(itineraires),
            value=1, step=1,
        )
        itin_choisi = itineraires[int(numero) - 1]
        for leg in itin_choisi["legs"]:
            afficher_leg(leg)

st.divider()
st.caption(
    "⚠️ Prototype pédagogique : vérifiez toujours les horaires réels avant de partir "
    "(aléas de circulation, restrictions certains jours, arrêts déplacés). "
    "Données issues des fiches horaires officielles."
)
