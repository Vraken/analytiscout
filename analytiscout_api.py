"""
Module pour gérer toutes les interactions avec l'API Analytiscout
"""

import requests
import re
from typing import Optional, Dict, Tuple


class AnalytiscoutAPI:
    """Gestion des interactions avec l'API Analytiscout"""

    # URLs de l'API
    BASE_URL = "https://analytiscout.sgdf.fr"
    OAUTH_URL = f"{BASE_URL}/oauth2/authorization/oidc"
    STRUCTURES_URL = f"{BASE_URL}/api/analytiscout/structures/structuresHie/false"
    RESPONSABLES_URL = f"{BASE_URL}/api/analytiscout/responsables"

    def __init__(self):
        self.session: Optional[requests.Session] = None

    def login(self, username: str, password: str) -> Tuple[bool, str]:
        """
        Connexion à Analytiscout

        Args:
            username: Identifiant utilisateur
            password: Mot de passe

        Returns:
            Tuple (succès, message)
        """
        try:
            self.session = requests.Session()

            # Étape 1: Initier OAuth2
            response = self.session.get(
                self.OAUTH_URL,
                allow_redirects=True,
                timeout=10
            )

            # Étape 2: Extraire l'URL du formulaire
            action_match = re.search(r'<form[^>]+action="([^"]+)"', response.text)
            if not action_match:
                return False, "Erreur: formulaire de connexion non trouvé"

            action_url = action_match.group(1).replace("&amp;", "&")

            # Étape 3: Soumettre les identifiants
            login_data = {
                'username': username,
                'password': password,
                'credentialId': ''
            }

            response = self.session.post(
                action_url,
                data=login_data,
                allow_redirects=True,
                timeout=10
            )

            # Vérifier la connexion
            if self._is_authenticated():
                return True, "Connexion réussie"
            else:
                return False, "Identifiants incorrects"

        except requests.exceptions.Timeout:
            return False, "Délai d'attente dépassé"
        except requests.exceptions.ConnectionError:
            return False, "Erreur de connexion au serveur"
        except Exception as e:
            return False, f"Erreur inattendue: {str(e)}"

    def _is_authenticated(self) -> bool:
        """Vérifie si la session est authentifiée"""
        return (self.session is not None and
                'JSESSIONID' in self.session.cookies and
                'XSRF-TOKEN' in self.session.cookies)

    def _get_headers(self) -> Dict[str, str]:
        """Retourne les headers nécessaires pour les requêtes API"""
        if not self._is_authenticated():
            raise ValueError("Session non authentifiée")

        return {
            "Content-Type": "application/json",
            "X-XSRF-TOKEN": self.session.cookies.get("XSRF-TOKEN"),
        }

    """
    Récupère les structures hiérarchiques

    Args:
        code_structure: Code numérique de la structure
        nom_structure: Nom de la structure
        id_saison: ID de la saison

    Returns:
        Données JSON ou None en cas d'erreur
    """
    def get_structures_hierarchy(self, structure) -> Optional[Dict]:
        try:
            if not self._is_authenticated():
                raise ValueError("Non authentifié")

            payload = {"structureFonctions": structure}
            print(self.STRUCTURES_URL)
            response = self.session.post(
                self.STRUCTURES_URL,
                json=payload,
                headers=self._get_headers(),
                timeout=10
            )

            if response.status_code == 200:
                return response.json()
            else:
                return None

        except Exception as e:
            raise Exception(f"Erreur lors de la récupération des structures: {str(e)}")

    """
    Récupère les responsables
    
    Args:
        code_structure: Code numérique de la structure
        nom_structure: Nom de la structure
        id_saison: ID de la saison
    
    Returns:
        Données JSON ou None en cas d'erreur
    """
    def get_responsables(self, structure, isYoung) -> Optional[Dict]:
        youngOrResp =  'jeunes' if isYoung else 'responsables'
        url = f"{self.BASE_URL}/api/analytiscout/{youngOrResp}"

        try:
            if not self._is_authenticated():
                raise ValueError("Non authentifié")

            payload = {"structures": [structure]}

            response = self.session.post(
                url,
                json=payload,
                headers=self._get_headers(),
                timeout=10
            )

            if response.status_code == 200:
                return response.json()
            else:
                return None

        except Exception as e:
            raise Exception(f"Erreur lors de la récupération des responsables: {str(e)}")

    def logout(self):
        """Ferme la session"""
        if self.session:
            self.session.close()
            self.session = None