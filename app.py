"""
Application Analytiscout - Point d'entrée principal
"""

import streamlit as st
from page_login import render_login_page, show_login_info
from page_statistiques import render_statistiques_page


def init_session_state():
    """Initialise les variables de session"""
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'api_instance' not in st.session_state:
        st.session_state.api_instance = None
    if 'username' not in st.session_state:
        st.session_state.username = None


def main():
    """Fonction principale de l'application"""

    # Configuration de la page
    st.set_page_config(
        page_title="Analytiscout",
        page_icon="🔐",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

    # Initialisation de la session
    init_session_state()

    # Routing : afficher la page appropriée selon l'état de connexion
    if st.session_state.logged_in:
        render_statistiques_page()
    else:
        render_login_page()
        show_login_info()


if __name__ == "__main__":
    main()