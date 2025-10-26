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
    fetch_responsables
)


DOSSIER_DATA = "data"


def render_statistiques_page():
    """Affiche la page des statistiques"""

    # Vérifier que l'utilisateur est connecté
    if not st.session_state.get('logged_in', False):
        st.error("❌ Vous devez être connecté pour accéder à cette page")
        return

    userFolder=f'{DOSSIER_DATA}_{st.session_state.username}'

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


def render_branche_content(branche: str, df_functions_filtered: pd.DataFrame,
                          df_chefs_filtered: pd.DataFrame, inclure_preinscrits: bool):
    """Affiche le contenu complet d'une branche"""

    # Filtrer les données pour cette branche
    df_branche = df_functions_filtered[df_functions_filtered['Branche'] == branche].copy()
    df_chefs_branche = df_chefs_filtered[df_chefs_filtered['Branche'] == branche]

    if df_branche.empty:
        st.info(f"Aucune donnée disponible pour la branche {branche}")
        return

    # === TABLEAU DES FONCTIONS ===
    st.markdown("### 📋 Effectifs par groupe")

    # Créer un dictionnaire pour stocker les données formatées par fonction
    data_formatted_fonctions = {}
    totaux_par_structure = {}

    for _, row in df_branche.iterrows():
        nom_structure = row['Nom Structure'].strip()
        fonction = row['Fonction'].strip()
        adherent = row['Nombre Adherent']
        preinscrit = row['Nombre Preinscrit']

        if nom_structure not in data_formatted_fonctions:
            data_formatted_fonctions[nom_structure] = {}
            totaux_par_structure[nom_structure] = 0

        if inclure_preinscrits:
            total = adherent + preinscrit
            data_formatted_fonctions[nom_structure][fonction] = str(total)
            totaux_par_structure[nom_structure] += total
        else:
            data_formatted_fonctions[nom_structure][fonction] = str(adherent)
            totaux_par_structure[nom_structure] += adherent

    # Convertir en DataFrame
    df_pivot_branche = pd.DataFrame.from_dict(data_formatted_fonctions, orient='index').fillna("0")

    # Ajouter les colonnes de diplômes
    diplomes_par_structure = df_branche.groupby('Nom Structure')[
        ['Directeur', 'Appro', 'Tech', 'APF', 'Sans diplôme']].sum()

    # Combiner les DataFrames
    df_final = pd.concat([df_pivot_branche, diplomes_par_structure], axis=1)

    # Ajouter la colonne TOTAL
    df_final['TOTAL'] = df_final.index.map(lambda nom: str(totaux_par_structure[nom]))

    # Obtenir les colonnes de fonctions
    cols_fonctions = df_pivot_branche.columns.tolist()

    # Appliquer le style avec mise en surbrillance et collecter les alertes
    all_alerts = set()

    def apply_highlight_with_alerts(row):
        styles, alerts = highlight_row(row, cols_fonctions)
        all_alerts.update(alerts)
        return styles

    styled_df = df_final.style.apply(apply_highlight_with_alerts, axis=1)

    # Afficher le tableau
    st.dataframe(styled_df, use_container_width=True)

    # Afficher les légendes uniquement pour les alertes présentes
    if all_alerts:
        st.markdown("**Alertes détectées :**")
        if 'ratio_chefs' in all_alerts:
            st.markdown("🟥 <span style='background-color: #ffcccc; padding: 2px 8px;'>Rouge clair</span> : Moins de 1 chef/cheftaine pour 12 jeunes", unsafe_allow_html=True)
        if 'ratio_farfadet' in all_alerts:
            st.markdown("🟥 <span style='background-color: #ffcccc; padding: 2px 8px;'>Rouge clair</span> : Moins de 1 responsable farfadet pour 12 jeunes", unsafe_allow_html=True)
        if 'ratio_compagnon' in all_alerts:
            st.markdown("🟥 <span style='background-color: #ffcccc; padding: 2px 8px;'>Rouge clair</span> : Moins de 1 accompagnateur compagnon pour 8 jeunes", unsafe_allow_html=True)
        if 'plus_35_jeunes' in all_alerts:
            st.markdown("🟧 <span style='background-color: #ffe6cc; padding: 2px 8px;'>Orange clair</span> : Plus de 35 jeunes", unsafe_allow_html=True)
        if 'aucun_directeur' in all_alerts:
            st.markdown("🟨 <span style='background-color: #ffffcc; padding: 2px 8px;'>Jaune clair</span> : Aucun directeur", unsafe_allow_html=True)

    st.markdown("---")

    # === LISTE DES RESPONSABLES ===
    st.markdown("### 👨‍💼 Liste des Responsables")

    if not df_chefs_branche.empty:
        df_chefs_display = df_chefs_branche[['Nom Structure', 'Nom Groupe', 'Fonction', 'Prénom', 'Diplôme JS', 'Statut']].copy()

        styled_chefs = df_chefs_display.style.apply(highlight_chef_sans_diplome, axis=1)
        st.dataframe(styled_chefs, use_container_width=True, hide_index=True)

        nb_sans_diplome = len(df_chefs_branche[df_chefs_branche['Diplôme JS'] == '-'])
        if nb_sans_diplome > 0:
            st.markdown("🟥 <span style='background-color: #ffcccc; padding: 2px 8px;'>Rouge clair</span> : Responsable sans diplôme", unsafe_allow_html=True)

        st.markdown("---")

        # === RÉPARTITION DES FORMATIONS ===
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

def highlight_row(row, cols_fonctions) -> Tuple[List[str], List[str]]:
    """
    Fonction pour mettre en surbrillance les lignes selon les critères.
    Retourne (styles, alerts) où alerts est une liste des alertes déclenchées.
    """
    styles = [''] * len(row)
    alerts = []

    # Déterminer le type de structure en fonction des colonnes présentes
    has_farfadet = 'FARFADET' in cols_fonctions
    has_compagnon = 'COMPAGNON' in cols_fonctions
    has_regular_jeunes = any(func in cols_fonctions for func in ['SCOUT/MOUSSE', 'PIONNIER/MARIN', 'LOUVETEAU/MOUSSAILLON'])

    # Calculer le nombre de jeunes et de chefs selon le type de structure
    nb_jeunes = 0
    nb_chefs = 0
    ratio_requis = 12  # Par défaut
    alert_type = 'ratio_chefs'  # Par défaut

    if has_farfadet:
        # Structure Farfadet
        if 'FARFADET' in cols_fonctions:
            try:
                val = str(row['FARFADET'])
                nb_jeunes = int(val) if val.isdigit() else 0
            except:
                pass

        # Compter les responsables farfadet (Chef/Cheftaine pour les farfadets)
        if 'RESPONSABLE FARFADET' in cols_fonctions:
            try:
                val = str(row['RESPONSABLE FARFADET'])
                nb_chefs = int(val) if val.isdigit() else 0
            except:
                pass
        ratio_requis = 12
        alert_type = 'ratio_farfadet'

    elif has_compagnon:
        # Structure Compagnon
        if 'COMPAGNON' in cols_fonctions:
            try:
                val = str(row['COMPAGNON'])
                nb_jeunes = int(val) if val.isdigit() else 0
            except:
                pass

        # Compter les accompagnateurs compagnons (Chef/Cheftaine pour les compagnons)
        if 'ACCOMPAGNATEUR COMPAGNON' in cols_fonctions:
            try:
                val = str(row['ACCOMPAGNATEUR COMPAGNON'])
                nb_chefs = int(val) if val.isdigit() else 0
            except:
                pass
        ratio_requis = 8
        alert_type = 'ratio_compagnon'

    else:
        # Structure classique (Louveteaux, Scouts, Pionniers)
        fonctions_jeunes = ['SCOUT/MOUSSE', 'PIONNIER/MARIN', 'LOUVETEAU/MOUSSAILLON']
        for func in fonctions_jeunes:
            if func in cols_fonctions:
                try:
                    val = str(row[func])
                    nb_jeunes += int(val) if val.isdigit() else 0
                except:
                    pass

        # Calculer le nombre de chefs
        if 'Chef/Cheftaine' in cols_fonctions:
            try:
                val = str(row['Chef/Cheftaine'])
                nb_chefs = int(val) if val.isdigit() else 0
            except:
                pass
        ratio_requis = 12
        alert_type = 'ratio_chefs'

    # Vérifier les diplômes
    nb_directeurs = 0

    if 'Directeur' in row.index:
        try:
            nb_directeurs = int(row['Directeur'])
        except:
            pass

    # Déterminer la couleur et les alertes
    color = None

    # Priorité 1 : Ratio chef/jeunes insuffisant
    if nb_jeunes > 0 and nb_chefs < (nb_jeunes / ratio_requis):
        color = 'background-color: #ffcccc'
        alerts.append(alert_type)

    # Priorité 2 : Plus de 35 jeunes
    if nb_jeunes > 35:
        color = 'background-color: #ffe6cc'
        alerts.append('plus_35_jeunes')

    # Priorité 3 : Aucun directeur
    if nb_chefs > 0 and nb_directeurs == 0:
        color = 'background-color: #ffffcc'
        alerts.append('aucun_directeur')

    if color:
        styles = [color] * len(row)

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