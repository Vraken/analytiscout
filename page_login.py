"""
Page de connexion à Analytiscout
"""

import streamlit as st
from analytiscout_api import AnalytiscoutAPI


def render_login_page():
    """Affiche la page de connexion"""

    st.title("🔐 Connexion Analytiscout")

    st.markdown("---")

    # Zone de connexion
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.subheader("Veuillez vous identifier")

        with st.form("login_form", clear_on_submit=False):
            username = st.text_input(
                "Identifiant",
                placeholder="Votre login",
                help="Votre identifiant Analytiscout"
            )

            password = st.text_input(
                "Mot de passe",
                type="password",
                placeholder="Votre mot de passe"
            )

            st.markdown("")  # Espacement

            submit_button = st.form_submit_button(
                "🔓 Se connecter",
                use_container_width=True,
                type="primary"
            )

            if submit_button:
                handle_login(username, password)


def handle_login(username: str, password: str):
    """
    Gère la tentative de connexion

    Args:
        username: Identifiant utilisateur
        password: Mot de passe
    """
    if not username or not password:
        st.warning("⚠️ Veuillez renseigner vos identifiants")
        return

    with st.spinner("🔄 Connexion en cours..."):
        # Créer une instance de l'API
        api = AnalytiscoutAPI()
        success, message = api.login(username, password)

        if success:
            # Sauvegarder l'instance API dans la session
            st.session_state.logged_in = True
            st.session_state.api_instance = api
            st.session_state.username = username

            st.success(f"✅ {message}")
            st.balloons()

            # Attendre un peu avant de recharger
            import time
            time.sleep(1)
            st.rerun()
        else:
            st.error(f"❌ {message}")




# Point d'entrée de la page
if __name__ == "__main__":
    render_login_page()
