"""
Page des statistiques - Interface utilisateur
"""

import streamlit as st
import pandas as pd
from typing import List, Set, Tuple
from data_service import (
    load_data,
    prepare_dataframes,
    filter_dataframes,
    get_available_groupes,
    sort_branches,
    fetch_responsables, clearAndReload
)


DOSSIER_DATA = "data"


def render_statistiques_page():
    """Affiche la page des statistiques"""

    # Vérifier que l'utilisateur est connecté
    if not st.session_state.get('logged_in', False):
        st.error("❌ Vous devez être connecté pour accéder à cette page")
        return

    userFolder = getUserFolder()

    # Charger les données
    with st.spinner("Chargement des données en cours..."):
        data, fichiers_traites, adherents_traites, adherents_ignores, structure_mapping, fichiers_erreur = load_data(userFolder)

    # Afficher les fichiers en erreur si présents
    if fichiers_erreur:
        with st.expander(f"⚠️ {len(fichiers_erreur)} fichier(s) non traité(s) - Cliquez pour voir les détails"):
            for erreur in fichiers_erreur:
                st.warning(f"• {erreur}")

    # Préparer les DataFrames
    df_functions, df_chefs = prepare_dataframes(data, structure_mapping)

    # Vérification si des données ont été chargées
    if df_functions.empty:
        st.error("❌ Aucune donnée n'a pu être chargée. Vérifiez que :")
        st.markdown("""
                - Le chemin du dossier est correct
                - Les fichiers JSON contiennent des adhérents
                - Les adhérents ont bien les champs `branche`, `fonction` et `codeStructure`
                """)
        st.stop()

    # --- Interface utilisateur Streamlit - SIDEBAR ---
    if st.sidebar.button("🚪 Déconnexion", use_container_width=True):
        handle_logout()

    if st.sidebar.button("🔄 Recharger tout", use_container_width=True):
        st.cache_data.clear()
        clearAndReload(getUserFolder())

    # === OPTION POUR INCLURE LES PRÉINSCRITS ===
    st.sidebar.subheader("⚙️ Options d'affichage")
    inclure_preinscrits = st.sidebar.checkbox(
        "Inclure les préinscrits dans les calculs",
        value=False,
        key="inclure_preinscrits",
        help="Si coché, les préinscrits sont inclus dans les totaux. Sinon, ils sont exclus complètement."
    )

    st.sidebar.markdown("---")

    # === FILTRE PAR CODE GROUPE (Cases à cocher) ===
    st.sidebar.subheader("🏢 Groupes")

    # Récupérer les groupes disponibles
    available_groupes = get_available_groupes(df_chefs, structure_mapping)

    if available_groupes:
        if 'group_selections' not in st.session_state:
            st.session_state.group_selections = {code: True for code, _ in available_groupes}

        col_g1, col_g2 = st.sidebar.columns(2)
        with col_g1:
            if st.button("Tout sélectionner", key="btn_select_all_groupes", use_container_width=True):
                for code_groupe, _ in available_groupes:
                    st.session_state.group_selections[code_groupe] = True
                st.rerun()
        with col_g2:
            if st.button("Tout désélectionner", key="btn_deselect_all_groupes", use_container_width=True):
                for code_groupe, _ in available_groupes:
                    st.session_state.group_selections[code_groupe] = False
                st.rerun()

        groupe_selected = []
        for code_groupe, nom_groupe in available_groupes:
            label = f"{code_groupe} - {nom_groupe}"
            checked = st.sidebar.checkbox(
                label,
                value=st.session_state.group_selections.get(code_groupe, True),
                key=f"groupe_{code_groupe}"
            )
            st.session_state.group_selections[code_groupe] = checked
            if checked:
                groupe_selected.append(code_groupe)
    else:
        groupe_selected = []

    # Filtrer les DataFrames
    df_functions_filtered, df_chefs_filtered = filter_dataframes(
        df_functions, df_chefs, groupe_selected, inclure_preinscrits
    )

    # --- Affichage des résultats ---


    # === ONGLETS PAR BRANCHE ===
    if not df_functions_filtered.empty:
        branches_filtrees = sort_branches(list(df_functions_filtered['Branche'].unique()))

        # Créer les noms d'onglets avec émojis
        tab_names = []
        emoji_map = {
            'farfadet': '🧚',
            'louveteau_jeannette': '🐺',
            'scout_guide': '⚜️',
            'pionnier_caravelle': '🏔️',
            'compagnon': '🎒',
            'audace': '🚀',
            'adulte': '👨‍👩‍👧‍👦',
        }

        for branche in branches_filtrees:
            emoji = emoji_map.get(branche.lower(), '📊')
            tab_names.append(f"{emoji} {branche.replace('_', ' ').title()}")

        tab_names.append('📊 Statistiques Globales')

        # Créer les onglets
        tabs = st.tabs(tab_names)

        # Remplir chaque onglet avec les données de la branche correspondante
        for idx, branche in enumerate(branches_filtrees):
            with tabs[idx]:
                render_branche_content(
                    branche,
                    df_functions_filtered,
                    df_chefs_filtered,
                    inclure_preinscrits
                )
        with tabs[len(branches_filtrees)]:
            render_global_stats(df_functions_filtered, df_chefs_filtered, inclure_preinscrits)

    else:
        st.info("Aucune donnée disponible pour les filtres sélectionnés.")

    # Options de téléchargement
    st.sidebar.markdown("---")
    st.sidebar.header("📥 Téléchargement")
    st.sidebar.download_button(
        label="Télécharger les fonctions (CSV)",
        data=df_functions_filtered.to_csv(index=False).encode('utf-8') if not df_functions_filtered.empty else "".encode('utf-8'),
        file_name='fonctions_filtrees.csv',
        mime='text/csv',
        disabled=df_functions_filtered.empty
    )

    st.sidebar.download_button(
        label="Télécharger les responsables (CSV)",
        data=df_chefs_filtered.to_csv(index=False).encode('utf-8') if not df_chefs_filtered.empty else "".encode('utf-8'),
        file_name='responsables_filtres.csv',
        mime='text/csv',
        disabled=df_chefs_filtered.empty
    )

    st.sidebar.markdown("---")
    st.sidebar.info("Application Streamlit v4.0 🚀")


def getUserFolder():
    userFolder = f'{DOSSIER_DATA}_{st.session_state.username}'
    return userFolder


def verifier_quotas_camp_sgdf(nb_jeunes: int, nb_dir: int, nb_qual: int, nb_stag: int, nb_autres: int) -> Tuple[bool, str, dict]:
    """
    Vérifie la conformité selon le tableau SGDF.
    Les directeurs sont ici considérés comme 'qualifiés' pour le calcul des quotas.
    """
    if nb_jeunes < 7:
        return True, "", {}

    # Définition des paliers [Total requis, Dir requis, Qualifiés requis]
    paliers = {
        (7, 12): {'total': 2, 'dir': 1, 'qual': 1},
        (13, 24): {'total': 3, 'dir': 1, 'qual': 1},
        (25, 36): {'total': 4, 'dir': 1, 'qual': 2},
        (37, 48): {'total': 5, 'dir': 1, 'qual': 2},
        (49, 60): {'total': 6, 'dir': 1, 'qual': 3},
        (61, 72): {'total': 7, 'dir': 1, 'qual': 3},
        (73, 84): {'total': 8, 'dir': 1, 'qual': 4},
    }

    config = next((v for (mini, maxi), v in paliers.items() if mini <= nb_jeunes <= maxi), None)

    if not config:
        return False, "Effectif hors tableau (>84)", {}

    manquants = {}

    # 1. Vérification du poste de Directeur (il en faut au moins un)
    if nb_dir < config['dir']:
        manquants['Directeur'] = config['dir'] - nb_dir

    # 2. Vérification des Qualifiés (Le directeur est aussi qualifié)
    # Somme de tous ceux qui ont un diplôme (Dir + Appro + Tech)
    total_diplomes_disponibles = nb_dir + nb_qual
    if total_diplomes_disponibles < config['qual']:
        manquants['Qualifié (BAFA/Appro/Tech)'] = config['qual'] - total_diplomes_disponibles

    # 3. Vérification du nombre total d'adultes
    total_actuel = nb_dir + nb_qual + nb_stag + nb_autres
    if total_actuel < config['total']:
        diff_total = config['total'] - total_actuel
        besoins_fixes = sum(manquants.values())
        if diff_total > besoins_fixes:
            manquants['Encadrant supplémentaire'] = diff_total - besoins_fixes

    return len(manquants) == 0, "" if not manquants else "Manque d'encadrement", manquants
details_alertes_camp = {}


def render_branche_content(branche: str, df_functions_filtered: pd.DataFrame,
                           df_chefs_filtered: pd.DataFrame, inclure_preinscrits: bool):
    """Affiche le contenu complet d'une branche avec détails des manques pour le camp"""

    # --- 1. Préparation des données ---
    df_branche = df_functions_filtered[df_functions_filtered['Branche'] == branche].copy()
    df_branche['Nom Structure'] = df_branche['Nom Structure'].str.strip()

    df_chefs_branche = df_chefs_filtered[df_chefs_filtered['Branche'] == branche].copy()
    if not df_chefs_branche.empty:
        df_chefs_branche['Nom Structure'] = df_chefs_branche['Nom Structure'].str.strip()

    if df_branche.empty:
        st.info(f"Aucune donnée disponible pour la branche {branche}")
        return

    # --- 2. Construction du tableau pivot des effectifs ---
    st.markdown("### 📋 Effectifs par groupe")

    data_formatted_fonctions = {}
    totaux_par_structure = {}

    for _, row in df_branche.iterrows():
        nom_structure = row['Nom Structure']
        fonction = row['Fonction'].strip()
        adherent = row['Nombre Adherent']
        preinscrit = row['Nombre Preinscrit']

        if nom_structure not in data_formatted_fonctions:
            data_formatted_fonctions[nom_structure] = {}
            totaux_par_structure[nom_structure] = 0

        total = (adherent + preinscrit) if inclure_preinscrits else adherent
        data_formatted_fonctions[nom_structure][fonction] = str(total)
        totaux_par_structure[nom_structure] += total

    # DataFrame pivot
    df_pivot_branche = pd.DataFrame.from_dict(data_formatted_fonctions, orient='index').fillna("0")

    # *** CORRECTION : Calcul des diplômes depuis df_chefs_branche ***
    if not df_chefs_branche.empty:
        diplomes_counts = {}
        for nom_structure in df_pivot_branche.index:
            df_structure_chefs = df_chefs_branche[df_chefs_branche['Nom Structure'] == nom_structure]

            diplomes_counts[nom_structure] = {
                'Directeur (Qualifié)': len(df_structure_chefs[df_structure_chefs['Diplôme JS'] == 'Directeur']),
                'Appro (Qualifié)': len(df_structure_chefs[df_structure_chefs['Diplôme JS'] == 'Appro']),
                'Tech (Qualifié)': len(df_structure_chefs[df_structure_chefs['Diplôme JS'] == 'Tech']),
                'APF (Stagiaire)': len(df_structure_chefs[df_structure_chefs['Diplôme JS'] == 'APF']),
                'Sans diplôme (Non qualifié)': len(df_structure_chefs[df_structure_chefs['Diplôme JS'] == '-'])
            }

        df_diplomes = pd.DataFrame.from_dict(diplomes_counts, orient='index')
    else:
        # Si pas de responsables, créer un DataFrame vide avec les bonnes colonnes
        df_diplomes = pd.DataFrame(
            0,
            index=df_pivot_branche.index,
            columns=['Directeur (Qualifié)', 'Appro (Qualifié)', 'Tech (Qualifié)',
                     'APF (Stagiaire)', 'Sans diplôme (Non qualifié)']
        )

    # Fusion finale pour affichage
    df_final = pd.concat([df_pivot_branche, df_diplomes], axis=1)
    df_final['TOTAL'] = df_final.index.map(totaux_par_structure).fillna(0).astype(int).astype(str)

    cols_fonctions = df_pivot_branche.columns.tolist()

    # --- 3. Stylage et calcul des manques ---
    details_alertes_camp = {}
    all_alerts = set()

    def apply_style_and_collect(row, cols_f, details_dict):
        styles, alerts = highlight_row(row, cols_f, details_dict)
        for a in alerts:
            all_alerts.add(a)
        return styles

    # On applique le style en passant les arguments requis
    styled_df = df_final.style.apply(
        apply_style_and_collect,
        axis=1,
        args=(cols_fonctions, details_alertes_camp)
    )

    # Affichage du tableau principal
    st.dataframe(styled_df, use_container_width=True)

    # --- 4. Affichage des alertes et détails des manques ---
    if all_alerts:
        st.markdown("### ⚠️ Alertes de vigilance")

        if 'quota_camp_insuffisant' in all_alerts:
            with st.expander("🚨 **Alerte Camp :** L'encadrement actuel est insuffisant pour valider un départ en camp.", expanded=True):
                if details_alertes_camp:
                    for structure, besoins in details_alertes_camp.items():
                        txt_besoins = ", ".join([f"{n} {k}" for k, n in besoins.items()])
                        st.write(f"• **{structure}** : Manque {txt_besoins}")
                else:
                    st.info("Analysez les colonnes de diplômes pour identifier les manques.")

        if 'plus_35_jeunes' in all_alerts:
            st.warning("**🔸 Taille du groupe :** Plus de 35 jeunes. Envisagez une scission d'unité ou un renfort.")

    st.markdown("---")

    # --- 5. Liste des Responsables ---
    st.markdown("### 👨‍💼 Liste des Responsables")

    if not df_chefs_branche.empty:
        df_chefs_display = df_chefs_branche[['Nom Structure', 'Nom Groupe', 'Fonction', 'Prénom', 'Diplôme JS', 'Statut']].copy()
        styled_chefs = df_chefs_display.style.apply(highlight_chef_sans_diplome, axis=1)
        st.dataframe(styled_chefs, use_container_width=True, hide_index=True)

        if len(df_chefs_branche[df_chefs_branche['Diplôme JS'] == '-']) > 0:
            st.markdown("🟥 <span style='background-color: #ffcccc; padding: 2px 8px;'>Rouge clair</span> : Responsable sans diplôme", unsafe_allow_html=True)

        st.markdown("---")

        # --- 6. Niveaux de formation (Tableau coloré) ---
        st.markdown("### 📊 Répartition des formations par structure")

        structures_diplomes = []

        for nom_structure in df_chefs_branche['Nom Structure'].unique():
            df_structure = df_chefs_branche[df_chefs_branche['Nom Structure'] == nom_structure]
            total = len(df_structure)

            directeur = len(df_structure[df_structure['Diplôme JS'] == 'Directeur'])
            appro = len(df_structure[df_structure['Diplôme JS'] == 'Appro'])
            tech = len(df_structure[df_structure['Diplôme JS'] == 'Tech'])
            apf = len(df_structure[df_structure['Diplôme JS'] == 'APF'])
            sans_diplome = len(df_structure[df_structure['Diplôme JS'] == '-'])

            structures_diplomes.append({
                'Structure': nom_structure,
                'Total': total,
                'Directeur (%)': f"{(directeur / total * 100):.1f}%" if total > 0 else "0%",
                'Appro (%)': f"{(appro / total * 100):.1f}%" if total > 0 else "0%",
                'Tech (%)': f"{(tech / total * 100):.1f}%" if total > 0 else "0%",
                'APF (%)': f"{(apf / total * 100):.1f}%" if total > 0 else "0%",
                'Sans diplôme (%)': f"{(sans_diplome / total * 100):.1f}%" if total > 0 else "0%",
                'Directeur': directeur,
                'Appro': appro,
                'Tech': tech,
                'APF': apf,
                'Sans diplôme': sans_diplome
            })

        df_structures_diplomes = pd.DataFrame(structures_diplomes)

        # Calculer le niveau de formation
        for idx, row in df_structures_diplomes.iterrows():
            directeur = row['Directeur']
            appro = row['Appro']
            tech = row['Tech']
            sans_diplome = row['Sans diplôme']
            total = row['Total']

            pct_diplomes = ((directeur + appro + tech) / total * 100) if total > 0 else 0
            pct_sans_diplome = (sans_diplome / total * 100) if total > 0 else 0

            if pct_diplomes >= 70:
                niveau = '🟩 Excellent'
            elif pct_sans_diplome > 55:
                niveau = '🟥 Insuffisant'
            elif pct_diplomes < 40:
                niveau = '🟧 À améliorer'
            else:
                niveau = '🟨 Acceptable'

            df_structures_diplomes.at[idx, 'Niveau'] = niveau

        def color_row(row):
            niveau = row['Niveau']
            if '🟩' in str(niveau):
                return ['background-color: #ccffcc'] * len(row)
            elif '🟥' in str(niveau):
                return ['background-color: #ffcccc'] * len(row)
            elif '🟧' in str(niveau):
                return ['background-color: #ffe6cc'] * len(row)
            elif '🟨' in str(niveau):
                return ['background-color: #ffffcc'] * len(row)
            return [''] * len(row)

        styled_structures = df_structures_diplomes[
            ['Structure', 'Total', 'Niveau', 'Directeur (%)', 'Appro (%)', 'Tech (%)', 'APF (%)', 'Sans diplôme (%)']
        ].style.apply(color_row, axis=1)

        st.dataframe(styled_structures, use_container_width=True, hide_index=True)

        st.markdown("""
        **📖 Légende des niveaux de formation :**

        | Couleur | Niveau | Critères |
        |---------|--------|----------|
        | 🟩 <span style='background-color: #ccffcc; padding: 2px 8px; border-radius: 3px;'>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span> | **Excellent** | ≥ 70% des responsables ont un diplôme (Tech, Appro ou Directeur) |
        | 🟨 <span style='background-color: #ffffcc; padding: 2px 8px; border-radius: 3px;'>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span> | **Acceptable** | Entre 40% et 70% de diplômés |
        | 🟧 <span style='background-color: #ffe6cc; padding: 2px 8px; border-radius: 3px;'>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span> | **À améliorer** | < 40% de diplômés |
        | 🟥 <span style='background-color: #ffcccc; padding: 2px 8px; border-radius: 3px;'>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span> | **Insuffisant** | > 55% de responsables sans diplôme |

        *Note : Les diplômes pris en compte sont Tech, Appro et Directeur (le diplôme APF n'est pas comptabilisé dans le calcul du niveau).*
        """, unsafe_allow_html=True)

    else:
        st.info(f"Aucun responsable trouvé pour la branche {branche}.")

def render_global_stats(df_functions_filtered: pd.DataFrame, df_chefs_filtered: pd.DataFrame, inclure_preinscrits: bool):
    """Affiche les statistiques globales toutes branches confondues"""

    if df_functions_filtered.empty:
        st.info("Aucune donnée disponible")
        return

    col1, col2, col3 = st.columns(3)

    with col1:
        st.write("**Résumé par fonction**")
        if inclure_preinscrits:
            fonction_summary = df_functions_filtered.groupby('Fonction')['Nombre Total'].sum().sort_values(ascending=False)
        else:
            fonction_summary = df_functions_filtered.groupby('Fonction')['Nombre Adherent'].sum().sort_values(ascending=False)
        st.dataframe(fonction_summary, use_container_width=True)

    with col2:
        st.write("**Répartition des diplômes**")
        if not df_chefs_filtered.empty:
            diplomes_count = df_chefs_filtered['Diplôme JS'].value_counts()
            st.dataframe(diplomes_count, use_container_width=True)

    with col3:
        st.write("**Répartition des branches**")
        if inclure_preinscrits:
            branche_summary = df_functions_filtered.groupby('Branche')['Nombre Total'].sum().sort_values(ascending=False)
        else:
            branche_summary = df_functions_filtered.groupby('Branche')['Nombre Adherent'].sum().sort_values(ascending=False)
        st.dataframe(branche_summary, use_container_width=True)

    # Métriques globales
    if inclure_preinscrits:
        total_adherents = int(df_functions_filtered['Nombre Total'].sum()) if not df_functions_filtered.empty else 0
    else:
        total_adherents = int(df_functions_filtered['Nombre Adherent'].sum()) if not df_functions_filtered.empty else 0

    st.metric("Total Adhérents", total_adherents)
    st.metric("Total Responsables", len(df_chefs_filtered))




# === FONCTIONS DE MISE EN FORME ===
def highlight_row(row, cols_fonctions, details_alertes_camp):
    """
    Applique le style aux lignes et calcule les besoins manquants pour le camp.
    Prend en compte que les Directeurs remplissent aussi le quota de 'Qualifiés'.
    """
    styles = [''] * len(row)
    alerts = []

    try:
        # 1. Extraction des effectifs jeunes (ajustez les noms selon vos données exactes)
        # On cible toutes les fonctions qui correspondent à des 'mineurs'
        FONCTIONS_JEUNES = [
            'SCOUT/MOUSSE', 'PIONNIER/MARIN', 'LOUVETEAU/MOUSSAILLON',
            'JEANNETTE', 'GUIDE', 'CARAVELLE'
        ]

        nb_jeunes = 0
        for f in FONCTIONS_JEUNES:
            val = row.get(f, 0)
            # Conversion sécurisée en entier
            try:
                nb_jeunes += int(float(val))
            except (ValueError, TypeError):
                continue

        # Si moins de 7 jeunes, la règle du tableau SGDF ne s'applique pas (micro-camps)
        if nb_jeunes < 7:
            return styles, alerts

        # 2. Extraction des diplômes depuis les colonnes du DataFrame pivot
        # 'nb_dir' : compte pour la colonne 'Directeur'
        # 'nb_qual' : compte pour la colonne 'Qualifié' (somme de Appro et Tech)
        nb_dir = int(float(row.get('Directeur (Qualifié)', 0)))
        nb_qual = int(float(row.get('Appro (Qualifié)', 0))) + int(float(row.get('Tech (Qualifié)', 0)))
        nb_stag = int(float(row.get('APF (Stagiaire)', 0)))
        nb_autres = int(float(row.get('Sans diplôme (Non qualifié)', 0)))

        # 3. Vérification via la fonction des quotas (avec la nouvelle logique cumulative)
        camp_ok, msg_erreur, manquants = verifier_quotas_camp_sgdf(
            nb_jeunes, nb_dir, nb_qual, nb_stag, nb_autres
        )

        # 4. Application des styles visuels
        # Cas : Alerte Rouge (Manque d'encadrement critique)
        if not camp_ok:
            # Fond rouge, texte blanc pour une visibilité maximale
            color = 'background-color: #ffe6cc; color: black;'
            styles = [color] * len(row)
            alerts.append('quota_camp_insuffisant')
            # On stocke les détails pour l'affichage des expanders sous le tableau
            details_alertes_camp[row.name] = manquants

        # Cas : Alerte Orange (Taille d'unité importante, conseil de scission)
        elif nb_jeunes > 35:
            color = 'background-color: #ffe6cc; color: black;'
            styles = [color] * len(row)
            alerts.append('plus_35_jeunes')

    except Exception as e:
        # En cas d'erreur imprévue, on ne bloque pas l'affichage Streamlit
        return [''] * len(row), []

    return styles, alerts

def highlight_chef_sans_diplome(row):
    """
    Met en surbrillance les responsables sans diplôme.
    """
    if row['Diplôme JS'] == '-':
        return ['background-color: #ffcccc'] * len(row)
    return [''] * len(row)


def handle_logout():
    """Gère la déconnexion"""
    if 'api_instance' in st.session_state:
        st.session_state.api_instance.logout()

    st.session_state.logged_in = False
    st.session_state.api_instance = None
    st.session_state.username = None

    st.success("✅ Déconnexion réussie")
    st.rerun()


# Point d'entrée de la page
if __name__ == "__main__":
    render_statistiques_page()