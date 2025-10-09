import streamlit as st
import json
from collections import defaultdict
import glob
import os
import pandas as pd


# --- Fonctions auxiliaires pour les defaultdict (rendues pickleables) ---

def diplome_dict_factory():
    """Crée un defaultdict(int) pour les diplômes."""
    return defaultdict(int)


def status_dict_factory():
    """Crée un dictionnaire pour stocker les compteurs ADHERENT et PREINSCRIT."""
    return {'ADHERENT': 0, 'PREINSCRIT': 0}


def structure_data_factory():
    """
    Crée la structure de données pour une structure donnée:
    {'functions': defaultdict(status_dict_factory), 'chefs': [], 'diplomes': defaultdict(diplome_dict_factory)}
    """
    return {
        'functions': defaultdict(status_dict_factory),
        'chefs': [],
        'diplomes': defaultdict(diplome_dict_factory)
    }


def nested_defaultdict_factory():
    """
    Crée un defaultdict qui utilise structure_data_factory comme fabrique par défaut.
    Ceci représente les structures au sein d'une branche.
    """
    return defaultdict(structure_data_factory)


def normalize_fonction(fonction):
    """
    Normalise les noms de fonctions pour regrouper certaines catégories.
    """
    if not fonction:
        return "Non spécifié"

    fonction_upper = fonction.upper()

    # Regrouper "Chef " et "Responsable d'unite" sous "Chef/Cheftaine"
    if fonction.lower().startswith("chef ") or fonction.lower().startswith("responsable d'unite"):
        return "Chef/Cheftaine"

    # Fusionner LOUVETEAU et MOUSSAILLON
    if fonction_upper in ["LOUVETEAU", "MOUSSAILLON"]:
        return "LOUVETEAU/MOUSSAILLON"

    # Fusionner MOUSSE et SCOUT
    if fonction_upper in ["MOUSSE", "SCOUT"]:
        return "SCOUT/MOUSSE"

    # Fusionner PIONNIER et MARIN
    if fonction_upper in ["PIONNIER", "MARIN"]:
        return "PIONNIER/MARIN"

    # Retourner la fonction originale pour les autres cas
    return fonction


def load_structures_mapping(filepath):
    """
    Charge le fichier structure.json et crée un mapping codeStructure -> nomStructure.
    Ne prend que les structures de type "Groupe".
    """
    mapping = {}

    def parse_structure(item):
        """Fonction récursive pour parser l'arbre de structures."""
        if isinstance(item, dict):
            code = item.get('codeStructure')
            if code and 'data' in item:
                # Ne prendre que les structures de type "Groupe"
                type_structure = item['data'].get('typeStructure', '')
                if type_structure == "Groupe":
                    nom = item['data'].get('nomStructure', 'Non spécifié')
                    mapping[code] = nom

            # Parser les enfants récursivement
            if 'children' in item and isinstance(item['children'], list):
                for child in item['children']:
                    parse_structure(child)

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Parser chaque élément de la liste
        if isinstance(data, list):
            for item in data:
                parse_structure(item)
        else:
            parse_structure(data)

        return mapping
    except Exception as e:
        st.error(f"Erreur lors du chargement du fichier structure.json : {e}")
        return {}


def sort_branches(branches):
    """
    Trie les branches selon l'ordre souhaité.
    """
    ordre_branches = [
        'farfadet',
        'louveteau_jeannette',
        'scout_guide',
        'pionnier_caravelle',
        'compagnon',
        'audace',
        'adulte'
    ]

    # Créer un dictionnaire pour l'ordre de priorité
    ordre_dict = {branche: i for i, branche in enumerate(ordre_branches)}

    # Trier les branches selon l'ordre défini, mettre les non-définies à la fin
    return sorted(branches, key=lambda x: ordre_dict.get(x.lower(), 999))


# --- Fonction principale pour charger les données (mise en cache) ---

DOSSIER_DATA = "data"


@st.cache_data
def load_data(dossier_path):
    """Charge et traite les données JSON à partir d'un dossier spécifié."""
    result = defaultdict(nested_defaultdict_factory)
    fichiers_traites = 0
    adherents_traites = 0
    adherents_ignores = 0
    fichiers_erreur = []

    # Charger le mapping des structures (uniquement les groupes)
    structure_mapping_path = os.path.join(dossier_path, "structure.json")
    structure_mapping = load_structures_mapping(structure_mapping_path)

    if not os.path.exists(dossier_path):
        st.error(f"Le dossier spécifié n'existe pas : {dossier_path}")
        return result, fichiers_traites, adherents_traites, adherents_ignores, structure_mapping, fichiers_erreur

    for filepath in glob.glob(os.path.join(dossier_path, "*.json")):
        # Ignorer le fichier structure.json
        if os.path.basename(filepath) == "structure.json":
            continue

        try:
            with open(filepath, "r", encoding="utf-8") as file:
                content = file.read().strip()

                # Vérifier si le fichier est vide
                if not content:
                    fichiers_erreur.append(f"{os.path.basename(filepath)} (fichier vide)")
                    continue

                # Tenter de parser le JSON
                try:
                    data = json.loads(content)
                except json.JSONDecodeError as je:
                    fichiers_erreur.append(f"{os.path.basename(filepath)} (JSON invalide: {str(je)})")
                    continue

                if isinstance(data, list):
                    st.warning(f"⚠️ {os.path.basename(filepath)} ignoré (format attendu : objet JSON, reçu : liste)")
                    fichiers_erreur.append(f"{os.path.basename(filepath)} (format liste)")
                    continue

                fichiers_traites += 1

                # Dictionnaire pour regrouper les adhérents par codeAdherent
                adherents_grouped = defaultdict(list)

                for adherent in data.get("adherents", []):
                    code_adherent = adherent.get("codeAdherent")
                    adherents_grouped[code_adherent].append(adherent)

                for adherents in adherents_grouped.values():
                    # Fusionner les informations des adhérents ayant le même codeAdherent
                    merged_adherent = {
                        "codeAdherent": adherents[0].get("codeAdherent"),
                        "branche": adherents[0].get("branche"),
                        "codeGroupe": adherents[0].get("codeGroupe"),
                        "codeStructure": adherents[0].get("codeStructure"),
                        "nomStructure": adherents[0].get("nomStructure", "Non spécifié"),
                        "fonction": adherents[0].get("fonction"),
                        "status": adherents[0].get("status", "ADHERENT"),
                        "prenom": adherents[0].get("prenom", ""),
                        "nom": adherents[0].get("nom", ""),
                        "diplomeJS": adherents[0].get("diplomeJS"),
                        "qualificationDir": adherents[0].get("qualificationDir"),
                        "appro": adherents[0].get("appro"),
                        "tech": adherents[0].get("tech"),
                        "apf": adherents[0].get("apf")
                    }

                    branche = merged_adherent.get("branche")
                    code_groupe = merged_adherent.get("codeGroupe")
                    code_structure = merged_adherent.get("codeStructure")
                    nom_structure = merged_adherent.get("nomStructure", "Non spécifié")
                    fonction = merged_adherent.get("fonction")
                    status = merged_adherent.get("status", "ADHERENT")

                    # Utiliser codeStructure au lieu de codeGroupe
                    if branche and fonction and code_structure:
                        # Normaliser la fonction avant de l'enregistrer
                        fonction_normalisee = normalize_fonction(fonction)

                        # S'assurer que la structure existe
                        if fonction_normalisee not in result[branche][code_structure]['functions']:
                            result[branche][code_structure]['functions'][fonction_normalisee] = status_dict_factory()

                        # Compter en fonction du statut
                        if status in ["ADHERENT", "PREINSCRIT"]:
                            result[branche][code_structure]['functions'][fonction_normalisee][status] += 1
                        else:
                            result[branche][code_structure]['functions'][fonction_normalisee]['ADHERENT'] += 1

                        # Stocker le nom de structure
                        if 'nom_structure' not in result[branche][code_structure]:
                            result[branche][code_structure]['nom_structure'] = nom_structure

                        adherents_traites += 1

                        is_chef = (
                                fonction.lower().startswith("chef")
                                or fonction.lower().startswith("responsable")
                                or fonction.lower().startswith("compagnon")
                                or fonction.lower().startswith("accompagnateur")
                        )

                        if is_chef:
                            prenom = (
                                    merged_adherent.get("prenom", "").capitalize()
                                    + " "
                                    + merged_adherent.get("nom", "").capitalize()
                            )

                            # Déterminer le diplôme JS
                            diplomJS = "-"
                            if (
                                    merged_adherent.get('diplomeJS') == "Scout Dir"
                                    or (
                                    merged_adherent.get('qualificationDir')
                                    and isinstance(merged_adherent.get('qualificationDir'), dict)
                                    and "directeur" in merged_adherent.get('qualificationDir').get('type', '').lower()
                            )
                            ):
                                diplomJS = "Directeur"
                            elif merged_adherent.get('appro'):
                                diplomJS = "Appro"
                            elif merged_adherent.get('tech'):
                                diplomJS = "Tech"
                            elif merged_adherent.get('apf'):
                                diplomJS = "APF"

                            # Compter les diplômes par fonction pour cette structure
                            result[branche][code_structure]['diplomes'][fonction_normalisee][diplomJS] += 1

                            result[branche][code_structure]['chefs'].append({
                                "prenom": prenom,
                                "diplomeJS": diplomJS,
                                "status": status,
                                "fonction": fonction_normalisee,
                                "codeStructure": code_structure,
                                "nomStructure": nom_structure,
                                "codeGroupe": code_groupe
                            })
                    else:
                        adherents_ignores += 1

        except Exception as e:
            fichiers_erreur.append(f"{os.path.basename(filepath)} ({str(e)})")
            continue

    return result, fichiers_traites, adherents_traites, adherents_ignores, structure_mapping, fichiers_erreur


def highlight_row(row, cols_fonctions):
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
        if 'Chef/Cheftaine' in cols_fonctions:
            try:
                val = str(row['Chef/Cheftaine'])
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
        if 'Chef/Cheftaine' in cols_fonctions:
            try:
                val = str(row['Chef/Cheftaine'])
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


# --- Configuration de l'application Streamlit ---
st.set_page_config(
    page_title="Analytiscout - Dashboard",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Analytiscout - Dashboard des Adhérents")
st.markdown("Visualisation interactive des données extraites des fichiers JSON.")

# --- Chargement des données ---
with st.spinner("Chargement des données en cours..."):
    data, fichiers_traites, adherents_traites, adherents_ignores, structure_mapping, fichiers_erreur = load_data(DOSSIER_DATA)

# Affichage des informations de chargement
st.info(
    f"📁 {fichiers_traites} fichier(s) traité(s) | ✅ {adherents_traites} affectation(s) unique(s) chargée(s) | ⚠️ {adherents_ignores} adhérent(s) ignoré(s) (données incomplètes) | 🏢 {len(structure_mapping)} groupe(s) chargé(s)")

# Afficher les fichiers en erreur si présents
if fichiers_erreur:
    with st.expander(f"⚠️ {len(fichiers_erreur)} fichier(s) non traité(s) - Cliquez pour voir les détails"):
        for erreur in fichiers_erreur:
            st.warning(f"• {erreur}")

# --- Préparation des DataFrames pour Streamlit ---
function_data = []
for branche, structures in data.items():
    for code_structure, infos in structures.items():
        # Récupérer le nom de la structure
        nom_structure = infos.get('nom_structure', 'Non spécifié')

        for fonction, statuts in infos['functions'].items():
            # Récupérer les diplômes pour cette fonction
            diplomes = infos['diplomes'].get(fonction, {})

            adherent_count = statuts.get('ADHERENT', 0)
            preinscrit_count = statuts.get('PREINSCRIT', 0)

            function_data.append({
                "Branche": branche,
                "Code Structure": code_structure,
                "Nom Structure": nom_structure,
                "Fonction": fonction,
                "Nombre Adherent": adherent_count,
                "Nombre Preinscrit": preinscrit_count,
                "Nombre Total": adherent_count + preinscrit_count,
                "Directeur": diplomes.get("Directeur", 0),
                "Appro": diplomes.get("Appro", 0),
                "Tech": diplomes.get("Tech", 0),
                "APF": diplomes.get("APF", 0),
                "Sans diplôme": diplomes.get("-", 0)
            })
df_functions = pd.DataFrame(function_data)

chef_data = []
for branche, structures in data.items():
    for code_structure, infos in structures.items():
        for chef in infos['chefs']:
            chef_data.append({
                "Branche": branche,
                "Code Structure": code_structure,
                "Nom Structure": chef.get('nomStructure', 'Non spécifié'),
                "Code Groupe": chef.get('codeGroupe', 'Non spécifié'),
                "Nom Groupe": structure_mapping.get(chef.get('codeGroupe'), 'Non spécifié'),
                "Fonction": chef.get('fonction', 'Non spécifié'),
                "Prénom": chef['prenom'],
                "Diplôme JS": chef['diplomeJS'],
                "Statut": chef['status']
            })
df_chefs = pd.DataFrame(chef_data)

# Vérification si des données ont été chargées
if df_functions.empty:
    st.error("❌ Aucune donnée n'a pu être chargée. Vérifiez que :")
    st.markdown("""
    - Le chemin du dossier est correct
    - Les fichiers JSON contiennent des adhérents
    - Les adhérents ont bien les champs `branche`, `fonction` et `codeStructure`
    """)
    st.stop()

# --- Interface utilisateur Streamlit - FILTRES ---

st.sidebar.header("🔍 Filtres")

# === OPTION POUR INCLURE LES PRÉINSCRITS ===
st.sidebar.subheader("⚙️ Options d'affichage")
inclure_preinscrits = st.sidebar.checkbox(
    "Inclure les préinscrits dans les calculs",
    value=True,
    key="inclure_preinscrits",
    help="Si coché, les préinscrits sont inclus dans les totaux. Sinon, ils sont exclus complètement."
)

st.sidebar.markdown("---")

# Extraction de toutes les branches et tri selon l'ordre souhaité
all_branches = sort_branches(list(data.keys()))

# === FILTRE PAR BRANCHES (Cases à cocher) ===
st.sidebar.subheader("📋 Branches")

# Initialisation de l'état de sélection pour les branches
if 'branch_selections' not in st.session_state:
    st.session_state.branch_selections = {branche: True for branche in all_branches}

col_b1, col_b2 = st.sidebar.columns(2)
with col_b1:
    if st.button("Tout sélectionner", key="btn_select_all_branches", use_container_width=True):
        for branche in all_branches:
            st.session_state.branch_selections[branche] = True
        st.rerun()
with col_b2:
    if st.button("Tout désélectionner", key="btn_deselect_all_branches", use_container_width=True):
        for branche in all_branches:
            st.session_state.branch_selections[branche] = False
        st.rerun()

# Création des cases à cocher pour chaque branche
branche_selected = []
for branche in all_branches:
    checked = st.sidebar.checkbox(
        branche,
        value=st.session_state.branch_selections.get(branche, True),
        key=f"branche_{branche}"
    )
    st.session_state.branch_selections[branche] = checked
    if checked:
        branche_selected.append(branche)

st.sidebar.markdown("---")

# === FILTRE PAR CODE GROUPE (Cases à cocher) ===
st.sidebar.subheader("🏢 Groupes")

# Filtrer les codes groupes disponibles en fonction des branches sélectionnées
if branche_selected:
    # Récupérer les groupes uniques des structures sélectionnées
    available_groupes = set()
    for _, row in df_chefs[df_chefs['Branche'].isin(branche_selected)].iterrows():
        available_groupes.add((row['Code Groupe'], structure_mapping.get(row['Code Groupe'], "Non spécifié")))
    available_groupes = sorted(list(available_groupes))
else:
    available_groupes = []

if available_groupes:
    # Initialisation de l'état de sélection pour les groupes
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

    # Création des cases à cocher pour chaque code groupe
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
    st.sidebar.info("Sélectionnez d'abord une branche")
    groupe_selected = []

# Filtrer les DataFrames en fonction des sélections
if branche_selected:
    df_functions_filtered = df_functions[df_functions['Branche'].isin(branche_selected)]
    df_chefs_filtered = df_chefs[df_chefs['Branche'].isin(branche_selected)]

    # Filtrer par groupe si sélectionné
    if groupe_selected:
        df_chefs_filtered = df_chefs_filtered[df_chefs_filtered['Code Groupe'].isin(groupe_selected)]
        # Récupérer les codes structures correspondant aux groupes sélectionnés
        structures_selectionnees = df_chefs_filtered['Code Structure'].unique()
        df_functions_filtered = df_functions_filtered[
            df_functions_filtered['Code Structure'].isin(structures_selectionnees)]

    # Filtrer les PREINSCRITS si l'option est décochée
    if not inclure_preinscrits:
        df_chefs_filtered = df_chefs_filtered[df_chefs_filtered['Statut'] != 'PREINSCRIT']
else:
    df_functions_filtered = pd.DataFrame()
    df_chefs_filtered = pd.DataFrame()

# --- Affichage des résultats ---
st.sidebar.markdown("---")
st.sidebar.markdown(f"**Branches sélectionnées:** {len(branche_selected)}")
st.sidebar.markdown(f"**Groupes sélectionnés:** {len(groupe_selected)}")

# Métriques globales en haut de la page
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Branches sélectionnées", len(branche_selected))
with col2:
    st.metric("Groupes sélectionnés", len(groupe_selected))
with col3:
    if inclure_preinscrits:
        total_adherents = int(df_functions_filtered['Nombre Total'].sum()) if not df_functions_filtered.empty else 0
    else:
        total_adherents = int(df_functions_filtered['Nombre Adherent'].sum()) if not df_functions_filtered.empty else 0
    st.metric("Total Adhérents", total_adherents)
with col4:
    st.metric("Total Responsables", len(df_chefs_filtered))

st.markdown("---")

# === CONTENU PRINCIPAL (sans tabs) ===

if not df_functions_filtered.empty:
    # Données détaillées des fonctions PAR BRANCHE - Une ligne par Structure
    st.subheader("📋 Données détaillées des fonctions par branche")

    # Obtenir la liste des branches filtrées et les trier selon l'ordre souhaité
    branches_filtrees = sort_branches(list(df_functions_filtered['Branche'].unique()))

    for branche in branches_filtrees:
        st.markdown(f"#### {branche}")

        # Filtrer les données pour cette branche
        df_branche = df_functions_filtered[df_functions_filtered['Branche'] == branche].copy()

        # Créer un dictionnaire pour stocker les données formatées par fonction
        data_formatted_fonctions = {}

        # Créer un dictionnaire pour les totaux par structure
        totaux_par_structure = {}

        for _, row in df_branche.iterrows():
            nom_structure = row['Nom Structure']
            fonction = row['Fonction']
            adherent = row['Nombre Adherent']
            preinscrit = row['Nombre Preinscrit']

            if nom_structure not in data_formatted_fonctions:
                data_formatted_fonctions[nom_structure] = {}
                totaux_par_structure[nom_structure] = 0

            # Format dépend de l'option inclure_preinscrits
            if inclure_preinscrits:
                # Afficher le total (adhérents + préinscrits)
                total = adherent + preinscrit
                data_formatted_fonctions[nom_structure][fonction] = str(total)
                totaux_par_structure[nom_structure] += total
            else:
                # Afficher uniquement les adhérents
                data_formatted_fonctions[nom_structure][fonction] = str(adherent)
                totaux_par_structure[nom_structure] += adherent

        # Convertir en DataFrame
        df_pivot_branche = pd.DataFrame.from_dict(data_formatted_fonctions, orient='index').fillna("0")

        # Ajouter les colonnes de diplômes (agrégées par structure) - en format numérique
        diplomes_par_structure = df_branche.groupby('Nom Structure')[
            ['Directeur', 'Appro', 'Tech', 'APF', 'Sans diplôme']].sum()

        # Combiner les DataFrames
        df_final = pd.concat([df_pivot_branche, diplomes_par_structure], axis=1)

        # Ajouter la colonne TOTAL
        df_final['TOTAL'] = df_final.index.map(lambda nom: str(totaux_par_structure[nom]))

        # Obtenir les colonnes de fonctions (avant les diplômes)
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

        # Afficher la liste des responsables pour cette branche
        st.markdown(f"##### 👨‍💼 Liste des Responsables - {branche}")
        df_chefs_branche = df_chefs_filtered[df_chefs_filtered['Branche'] == branche]

        if not df_chefs_branche.empty:
            # Sélectionner uniquement les colonnes nécessaires pour l'affichage
            df_chefs_display = df_chefs_branche[['Nom Structure', 'Nom Groupe', 'Fonction', 'Prénom', 'Diplôme JS', 'Statut']].copy()

            # Appliquer le style pour mettre en surbrillance les responsables sans diplôme
            styled_chefs = df_chefs_display.style.apply(highlight_chef_sans_diplome, axis=1)
            st.dataframe(styled_chefs, use_container_width=True, hide_index=True)

            # Vérifier s'il y a des responsables sans diplôme
            nb_sans_diplome = len(df_chefs_branche[df_chefs_branche['Diplôme JS'] == '-'])
            if nb_sans_diplome > 0:
                st.markdown("🟥 <span style='background-color: #ffcccc; padding: 2px 8px;'>Rouge clair</span> : Responsable sans diplôme", unsafe_allow_html=True)
        else:
            st.info(f"Aucun responsable trouvé pour la branche {branche}.")

        st.markdown("---")

    # Résumé par fonction
    st.subheader("📈 Résumé par fonction")

    if inclure_preinscrits:
        fonction_summary = df_functions_filtered.groupby('Fonction')['Nombre Total'].sum().sort_values(ascending=False)
    else:
        fonction_summary = df_functions_filtered.groupby('Fonction')['Nombre Adherent'].sum().sort_values(ascending=False)

    st.dataframe(fonction_summary, use_container_width=True)

    st.markdown("---")

    # Statistiques globales des responsables
    st.subheader("📊 Statistiques globales des responsables")

    if not df_chefs_filtered.empty:
        col1, col2, col3 = st.columns(3)

        with col1:
            st.write("**Répartition des diplômes:**")
            diplomes_count = df_chefs_filtered['Diplôme JS'].value_counts()
            st.dataframe(diplomes_count, use_container_width=True)

        with col2:
            st.write("**Répartition des fonctions:**")
            fonctions_count = df_chefs_filtered['Fonction'].value_counts()
            st.dataframe(fonctions_count, use_container_width=True)

        with col3:
            st.write("**Répartition des statuts:**")
            statuts_count = df_chefs_filtered['Statut'].value_counts()
            st.dataframe(statuts_count, use_container_width=True)
    else:
        st.info("Aucun responsable trouvé pour les filtres sélectionnés.")

else:
    st.info("Aucune donnée de fonction disponible pour les filtres sélectionnés.")

# Options de téléchargement
st.sidebar.markdown("---")
st.sidebar.header("📥 Téléchargement")
st.sidebar.download_button(
    label="Télécharger les fonctions (CSV)",
    data=df_functions_filtered.to_csv(index=False).encode('utf-8') if not df_functions_filtered.empty else "".encode(
        'utf-8'),
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
st.sidebar.info("Application Streamlit v3.5 🚀")