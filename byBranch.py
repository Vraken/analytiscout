import json
from collections import defaultdict
import glob
import os

result = defaultdict(
    lambda: defaultdict(lambda: {'functions': defaultdict(int), 'chefs': []})
)

# Spécifiez le chemin de votre dossier
dossier = "C:/Users/mielp/PycharmProjects/Analytiscout/data"

# Boucle sur tous les fichiers JSON dans le dossier
for filepath in glob.glob(os.path.join(dossier, "*.json")):
    with open(filepath, "r", encoding="utf-8") as file:
        data = json.load(file)
        # Parcourir chaque adhérent du fichier
        if isinstance(data, list):
            print(filepath + " ignoré")
            continue
        for adherent in data.get("adherents", []):
            # if adherent.get('status') == "PREINSCRIT":
            #     continue
            branche = adherent.get("branche")
            fonction = adherent.get("fonction")
            nom_structure = adherent.get("nomStructure")

            if branche and fonction and nom_structure:
                # Incrémente le compteur de la fonction pour la branche et la structure
                result[branche][nom_structure]['functions'][fonction] += 1

                # Vérifier si la fonction est "chef" (comparaison insensible à la casse)
                if fonction.lower().startswith("chef") or fonction.lower().startswith("RESPONSABLE".lower())  or fonction.lower().startswith("compagnon") or fonction.lower().startswith("accompagnateur") :
                    prenom = adherent.get("prenom").capitalize() + " "+ adherent.get("nom").capitalize()
                    diplomJS = "-"
                    if adherent.get('diplomeJS') == "Scout Dir" or (adherent.get('qualificationDir') and "directeur" in adherent.get('qualificationDir').get('type').lower() ):
                        diplomJS = "Directeur"
                    elif adherent.get('appro'):
                        diplomJS = "Appro"
                    elif adherent.get('tech'):
                        diplomJS = "Tech"
                    elif adherent.get('apf'):
                        diplomJS = "APF"

                    result[branche][nom_structure]['chefs'].append({
                        "prenom": prenom,
                        "diplomeJS": diplomJS,
                        "status": adherent['status']
                    })

# Affichage des résultats
for branche, structures in result.items():
    print("===================================================================================================================")
    print(f"Branche : {branche}")
    for nom_structure, infos in structures.items():
        print(f"  Structure : {nom_structure}")
        # print("    Répartition par fonction :")
        for fonction, count in infos['functions'].items():
            print(f"      {fonction} : {count}")
        # Affichage des chefs
        if infos['chefs']:
            print(f"    Responsables [{len(infos['chefs'])}] :")
            for chef in infos['chefs']:
                diplome_info = chef["diplomeJS"] if chef["diplomeJS"] is not None else "Aucun diplôme renseigné"
                print(f"      {chef['status']} - {chef['prenom']}  - {diplome_info}")
        elif branche != 'ADULTE':
            print("    Pas de responsable enregistré.")
        print()