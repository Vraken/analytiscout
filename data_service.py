"""
Service de gestion des données
"""

import json
import os
import glob
import streamlit as st
from collections import defaultdict
from typing import Dict, Tuple, List, Set, Any
import pandas as pd
import time
from random import randint
import shutil

refFolder = "data"

# === FACTORIES ===

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


# === NORMALISATION ET MAPPING ===

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


def load_structures_mapping(filepath: str) -> Dict[str, str]:
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


def sort_branches(branches: List[str]) -> List[str]:
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


# === CHARGEMENT DES DONNÉES ===
#
# @st.cache_data
def load_data(dossier_path: str) -> Tuple[Dict, int, int, int, Dict[str, str], List[str]]:

    fetch_responsables(dossier_path)

    """Charge et traite les données JSON à partir d'un dossier spécifié."""
    result = defaultdict(nested_defaultdict_factory)
    fichiers_traites = 0
    adherents_traites = 0
    adherents_ignores = 0
    fichiers_erreur = []

    # Dictionnaire pour dédupliquer les adhérents par codeAdherent
    adherents_uniques = {}

    # Charger le mapping des structures (uniquement les groupes)
    structure_mapping_path = os.path.join(dossier_path, "structure.json")
    structure_mapping = load_structures_mapping(structure_mapping_path)

    if not os.path.exists(dossier_path):
        st.error(f"Le dossier spécifié n'existe pas : {dossier_path}")
        return result, fichiers_traites, adherents_traites, adherents_ignores, structure_mapping, fichiers_erreur

    # PREMIÈRE PASSE : Collecter tous les adhérents uniques
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

                for adherent in data.get("adherents", []):
                    code_adherent = adherent.get("codeAdherent")

                    if code_adherent:
                        # Si c'est la première fois qu'on voit cet adhérent, on le stocke
                        if code_adherent not in adherents_uniques:
                            adherents_uniques[code_adherent] = adherent
                        else:
                            # Sinon, on fusionne les informations (priorité aux valeurs non vides)
                            adherent_existant = adherents_uniques[code_adherent]

                            # Fusionner les champs (priorité aux valeurs non vides/non nulles)
                            for key, value in adherent.items():
                                if value and not adherent_existant.get(key):
                                    adherent_existant[key] = value
                    else:
                        # Si pas de codeAdherent, on traite l'adhérent normalement (sans fusion)
                        adherents_uniques[id(adherent)] = adherent

        except Exception as e:
            fichiers_erreur.append(f"{os.path.basename(filepath)} ({str(e)})")
            continue

    # DEUXIÈME PASSE : Traiter les adhérents uniques
    for code_adherent, adherent in adherents_uniques.items():
        branche = adherent.get("branche")
        code_groupe = adherent.get("codeGroupe")
        code_structure = adherent.get("codeStructure")
        nom_structure = adherent.get("nomStructure", "Non spécifié")
        fonction = adherent.get("fonction")
        status = adherent.get("status", "ADHERENT")

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
                        adherent.get("prenom", "").capitalize()
                        + " "
                        + adherent.get("nom", "").capitalize()
                )

                # Déterminer le diplôme JS
                diplomJS = "-"
                if (
                        adherent.get('diplomeJS') == "Scout Dir"
                        or (
                        adherent.get('qualificationDir')
                        and isinstance(adherent.get('qualificationDir'), dict)
                        and "directeur" in adherent.get('qualificationDir').get('type', '').lower()
                )
                ):
                    diplomJS = "Directeur"
                elif adherent.get('appro'):
                    diplomJS = "Appro"
                elif adherent.get('tech'):
                    diplomJS = "Tech"
                elif adherent.get('apf'):
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
                    "codeGroupe": code_groupe,
                    "codeAdherent": adherent.get("codeAdherent", "N/A")
                })
        else:
            adherents_ignores += 1

    return result, fichiers_traites, adherents_traites, adherents_ignores, structure_mapping, fichiers_erreur


# === PRÉPARATION DES DATAFRAMES ===

def prepare_dataframes(data: Dict, structure_mapping: Dict[str, str]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Prépare les DataFrames pour l'affichage."""

    # DataFrame des fonctions
    function_data = []
    for branche, structures in data.items():
        for code_structure, infos in structures.items():
            nom_structure = infos.get('nom_structure', 'Non spécifié')

            for fonction, statuts in infos['functions'].items():
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

    # DataFrame des chefs
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

    return df_functions, df_chefs


def filter_dataframes(df_functions: pd.DataFrame, df_chefs: pd.DataFrame,
                      groupe_selected: List[str], inclure_preinscrits: bool) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Filtre les DataFrames selon les critères sélectionnés."""

    df_functions_filtered = df_functions.copy()
    df_chefs_filtered = df_chefs.copy()

    if groupe_selected:
        df_chefs_filtered = df_chefs_filtered[df_chefs_filtered['Code Groupe'].isin(groupe_selected)]
        structures_selectionnees = df_chefs_filtered['Code Structure'].unique()
        df_functions_filtered = df_functions_filtered[
            df_functions_filtered['Code Structure'].isin(structures_selectionnees)]

    if not inclure_preinscrits:
        df_chefs_filtered = df_chefs_filtered[df_chefs_filtered['Statut'] != 'PREINSCRIT']

    return df_functions_filtered, df_chefs_filtered


def get_available_groupes(df_chefs: pd.DataFrame, structure_mapping: Dict[str, str]) -> List[Tuple[str, str]]:
    """Récupère la liste des groupes disponibles."""
    available_groupes = set()
    for _, row in df_chefs.iterrows():
        available_groupes.add((row['Code Groupe'], structure_mapping.get(row['Code Groupe'], "Non spécifié")))
    return sorted(list(available_groupes))


# === FETCH API ===

def iter_data(structures):
    """Itère récursivement sur tous les .data dans l'arborescence"""
    for node in structures:
        if "data" in node:
            yield node["data"]
        if "children" in node and node["children"]:
            yield from iter_data(node["children"])


def fetchAll(data_structures, isYoung, outputFolder):

    """Récupère toutes les données depuis l'API."""
    api = st.session_state.api_instance
    for data in iter_data(data_structures):
        if not data['typeStructure'].startswith("Unité"):
            continue
        labelPrefixYoung = 'jeunes' if isYoung else 'chefs'
        label = f"{labelPrefixYoung}_{data['nomStructure']} ({data['typeStructure']})".replace(" ", "_").replace("/", "_")
        outputFile = f"{outputFolder}/{label}.json"
        refOutputFile = f"{refFolder}/{label}.json"
        if os.path.exists(outputFile):
            continue
        if os.path.exists(refOutputFile):
            shutil.copy(refOutputFile,outputFile)
            continue

        print(f"{data['nomStructure']} ({data['typeStructure']})")
        print(f"fetching {data}")
        data_responsables = get_responsables(api, data, isYoung)

        if data_responsables:

            with open(outputFile, "w", encoding="utf-8") as outfile:
                json.dump(data_responsables, outfile, indent=4, ensure_ascii=False)

            shutil.copy(outputFile, refOutputFile)


            st.toast(f"✅ Données récupérées avec succès : {label}")
            print("✓ Responsables récupérés")

        time.sleep(randint(1, 2))


def clearAndReload(userFolder):
    if os.path.exists(userFolder):
        shutil.rmtree(userFolder)
        print(f"Dossier supprimé avec succès : {userFolder}")
    if os.path.exists(refFolder):
        shutil.rmtree(refFolder)
        print(f"Dossier supprimé avec succès : {refFolder}")

    fetch_responsables(userFolder)

def fetch_responsables(userFolder):
    structureFile = f"{userFolder}/structure.json"
    api = st.session_state.api_instance
    account_info = api.get_account_info()

    structure = account_info['structuresFonctions'][0]

    if not os.path.exists(userFolder):
        os.mkdir(userFolder)

    if not os.path.exists(refFolder):
        os.mkdir(refFolder)

    if not os.path.exists(structureFile):
        print("Récupération des structures hiérarchiques...")
        data_structures = get_structures_hierarchy(api, structure)
        if data_structures:
            with open(structureFile, "w", encoding="utf-8") as outfile:
                json.dump(data_structures, outfile, indent=4, ensure_ascii=False)

        print("✓ Structures récupérées")

    with open(structureFile, "r", encoding="utf-8") as file:
        data_structures = json.load(file)


        fetchAll(data_structures, False, userFolder)
        fetchAll(data_structures, True, userFolder)

@st.cache_data
def get_structures_hierarchy(_api, structure: dict[str, int | str]) -> Any:
    return _api.get_structures_hierarchy(structure)


@st.cache_data
def get_responsables(_api, data, isYoung) -> Any:
    return _api.get_responsables(data, isYoung)
