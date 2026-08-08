import streamlit as st
from planner import Reseau, calculer_itineraires, _min_to_hhmm

st.set_page_config(page_title="Navettes Île d'Oléron — Calcul d'itinéraires", page_icon="🚌")

@st.cache_resource
def charger_reseau():
    return Reseau(".")

reseau = charger_reseau()

st.title("🚌 Navettes de l'Île d'Oléron")
st.caption("Calcul d'itinéraires avec étapes (Points d'Intérêt) et correspondances")

arrets = reseau.liste_arrets()
labels_arrets = [f"{s.commune} — {s.arret}" for _, s in arrets]
norms_arrets = [n for n, _ in arrets]

pi = reseau.liste_points_interet()
labels_pi = [f"{s.commune} — {s.arret}" for _, s in pi]
norms_pi = [n for n, _ in pi]

col1, col2 = st.columns(2)
with col1:
    idx_dep = st.selectbox("Arrêt de départ", range(len(labels_arrets)), format_func=lambda i: labels_arrets[i])
with col2:
    idx_arr = st.selectbox("Arrêt d'arrivée", range(len(labels_arrets)), format_func=lambda i: labels_arrets[i])

heure_min = st.time_input("Heure de départ minimum")

etapes_idx = st.multiselect(
    "Étapes (Points d'Intérêt) à visiter, dans l'ordre souhaité",
    range(len(labels_pi)), format_func=lambda i: labels_pi[i],
)

if st.button("Calculer les trajets possibles", type="primary"):
    depart_norm = norms_arrets[idx_dep]
    arrivee_norm = norms_arrets[idx_arr]
    etapes_norms = [norms_pi[i] for i in etapes_idx]
    heure_str = heure_min.strftime("%H:%M")

    itineraires = calculer_itineraires(reseau, depart_norm, heure_str, etapes_norms, arrivee_norm)

    if not itineraires:
        st.warning("Aucun trajet trouvé permettant d'arriver le jour même avec ces critères.")
    else:
        st.success(f"{len(itineraires)} trajet(s) trouvé(s)")
        for it in itineraires:
            titre = (f"{_min_to_hhmm(it['heure_depart'])} → {_min_to_hhmm(it['heure_arrivee'])} "
                     f"(durée totale : {it['duree_totale']} min)")
            with st.expander(titre):
                for i, leg in enumerate(it["legs"]):
                    for seg in leg:
                        a = reseau.stops[seg.arret_depart_norm]
                        b = reseau.stops[seg.arret_arrivee_norm]
                        st.write(
                            f"🚏 Navette **{seg.couleur.capitalize()}** (ligne {seg.ligne_num}, "
                            f"course {seg.course_num}) : {a.arret} ({_min_to_hhmm(seg.heure_depart)}) "
                            f"→ {b.arret} ({_min_to_hhmm(seg.heure_arrivee)})"
                        )
                    if i < len(it["pauses"]):
                        st.info(f"⏸️ Pause de {it['pauses'][i]} minutes à cette étape")

st.divider()
st.caption(
    "⚠️ Prototype pédagogique : vérifiez toujours les horaires réels avant de partir "
    "(aléas de circulation, restrictions certains jours, arrêts déplacés). "
    "Données issues des fiches horaires officielles 2026."
)
