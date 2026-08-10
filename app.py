import streamlit as st
from planner import Reseau, options_prochaine_etape, label_arret, _min_to_hhmm, _hhmm_to_min

st.set_page_config(page_title="Navettes Île d'Oléron — Itinéraire interactif", page_icon="🚌")

@st.cache_resource
def charger_reseau():
    return Reseau(".")

reseau = charger_reseau()

arrets = reseau.liste_arrets()
labels_arrets = [f"{s.commune} — {s.arret}" for _, s in arrets]
norms_arrets = [n for n, _ in arrets]

pi = reseau.liste_points_interet()

st.title("🚌 Navettes de l'Île d'Oléron")
st.caption("Construisez votre itinéraire étape par étape : à chaque arrêt, choisissez la pause qui vous convient "
           "tout en garantissant votre retour le jour même.")

# ----------------------------------------------------------------------
# Paramètres de départ
# ----------------------------------------------------------------------
if "voyage" not in st.session_state:
    st.session_state.voyage = None
if "options_affichees" not in st.session_state:
    st.session_state.options_affichees = None

with st.form("parametres"):
    col1, col2 = st.columns(2)
    with col1:
        idx_dep = st.selectbox("Arrêt de départ", range(len(labels_arrets)), format_func=lambda i: labels_arrets[i])
    with col2:
        idx_arr = st.selectbox("Arrêt d'arrivée finale", range(len(labels_arrets)), format_func=lambda i: labels_arrets[i])
    heure_min = st.time_input("Heure de départ minimum")
    lance = st.form_submit_button("Démarrer / recommencer le calcul interactif", type="primary")

if lance:
    st.session_state.voyage = {
        "position": norms_arrets[idx_dep],
        "heure": heure_min.strftime("%H:%M"),
        "arrivee": norms_arrets[idx_arr],
        "legs": [],          # liste de Segment-lists (un élément par tronçon confirmé)
        "termine": False,
    }
    st.session_state.options_affichees = None

voyage = st.session_state.voyage


def afficher_leg(leg):
    for seg in leg:
        a = reseau.stops[seg.arret_depart_norm]
        b = reseau.stops[seg.arret_arrivee_norm]
        st.write(
            f"🚏 Navette **{seg.couleur.capitalize()}** (ligne {seg.ligne_num}, "
            f"course {seg.course_num}) : {a.arret} ({_min_to_hhmm(seg.heure_depart)}) "
            f"→ {b.arret} ({_min_to_hhmm(seg.heure_arrivee)})"
        )


# ----------------------------------------------------------------------
# Récapitulatif du voyage déjà construit
# ----------------------------------------------------------------------
if voyage:
    if voyage["legs"]:
        st.subheader("Itinéraire construit jusqu'ici")
        for i, leg in enumerate(voyage["legs"]):
            heure_min_dispo = (
                voyage["legs"][i - 1][-1].heure_arrivee if i > 0 else _hhmm_to_min(voyage["heure_depart_initiale"])
            )
            attente = leg[0].heure_depart - heure_min_dispo
            if attente > 0:
                st.info(f"⏸️ Pause / attente de {attente} min à cet arrêt")
            afficher_leg(leg)

    st.write(f"**Position actuelle :** {label_arret(reseau, voyage['position'])} — "
             f"disponible à partir de {voyage['heure']}")

    if voyage["termine"]:
        st.success("🎉 Itinéraire terminé — vous arrivez à destination le jour même.")
    else:
        etapes_deja_utilisees = {voyage["position"]} | {leg[-1].arret_arrivee_norm for leg in voyage["legs"]}
        pi_restants = [(n, s) for n, s in pi if n not in etapes_deja_utilisees and n != voyage["arrivee"]]

        st.subheader("Et ensuite ?")
        choix = st.radio(
            "Que voulez-vous faire ?",
            ["Ajouter une étape (Point d'Intérêt)", "Rejoindre directement l'arrêt d'arrivée finale"],
            key="choix_action",
        )

        cible_norm = None
        if choix == "Ajouter une étape (Point d'Intérêt)":
            if not pi_restants:
                st.warning("Il ne reste plus de Point d'Intérêt disponible.")
            else:
                labels_pi_restants = [f"{s.commune} — {s.arret}" for _, s in pi_restants]
                idx_etape = st.selectbox("Choisir la prochaine étape", range(len(pi_restants)),
                                          format_func=lambda i: labels_pi_restants[i])
                if st.button("Voir les trajets possibles vers cette étape"):
                    cible_norm = pi_restants[idx_etape][0]
        else:
            if st.button("Voir les trajets possibles vers l'arrivée finale"):
                cible_norm = voyage["arrivee"]

        if cible_norm:
            options = options_prochaine_etape(reseau, voyage["position"], voyage["heure"],
                                                cible_norm, voyage["arrivee"])
            st.session_state.options_affichees = {
                "cible": cible_norm, "options": options,
                "type": "arrivee" if cible_norm == voyage["arrivee"] else "etape",
            }

        # -------------------- Affichage des options + sélection --------------------
        aff = st.session_state.options_affichees
        if aff:
            options = aff["options"]
            if not options:
                st.error("Aucun trajet ne permet d'atteindre cet arrêt tout en revenant "
                         "à l'arrivée finale le jour même.")
            else:
                st.write(
                    f"**{len(options)} option(s)** vers {label_arret(reseau, aff['cible'])} "
                    + ("(triées par pause possible décroissante) :" if aff["type"] == "etape"
                       else "(triées par heure d'arrivée) :")
                )
                for i, opt in enumerate(options):
                    leg = opt["leg"]
                    if opt["pause_max"] is not None:
                        titre = (f"Arrivée {_min_to_hhmm(opt['heure_arrivee'])} — "
                                 f"pause possible : jusqu'à {opt['pause_max']} min "
                                 f"(départ au plus tard à {_min_to_hhmm(opt['heure_limite_depart'])})")
                    else:
                        titre = f"Arrivée {_min_to_hhmm(opt['heure_arrivee'])}"
                    with st.expander(titre):
                        afficher_leg(leg)
                        if st.button("✅ Choisir ce trajet", key=f"choix_{aff['cible']}_{i}"):
                            if not voyage["legs"]:
                                voyage["heure_depart_initiale"] = voyage["heure"]
                            voyage["legs"].append(leg)
                            voyage["position"] = leg[-1].arret_arrivee_norm
                            voyage["heure"] = _min_to_hhmm(leg[-1].heure_arrivee)
                            if aff["type"] == "arrivee":
                                voyage["termine"] = True
                            st.session_state.options_affichees = None
                            st.rerun()

st.divider()
st.caption(
    "⚠️ Prototype pédagogique : vérifiez toujours les horaires réels avant de partir "
    "(aléas de circulation, restrictions certains jours, arrêts déplacés). "
    "Données issues des fiches horaires officielles."
)
