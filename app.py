# app.py — Chessscore
import streamlit as st
from db.repo import init_db, load_games

from core.elo import compute_ratings
from ui.components import render_sidebar_leaderboard
from ui.pages import render_tab_saisie_histo, render_tab_classement, render_tab_export, render_tab_params, render_tab_admin


# Constantes par défaut
DEFAULT_START_RATING = 1200
DEFAULT_K = 20
NEWBIE_GAMES = 10
NEWBIE_K = 40

st.set_page_config(page_title="Chessscore – ELO", page_icon="♟️", layout="wide")
st.title("♟️ Chessscore – Team ELO")

# DB init (idempotent)
try:
    init_db()
except Exception as e:
    st.error("Database init failed. Set DB_URL in Streamlit secrets.")
    st.exception(e)
    st.stop()

# Session params
if "elo_params" not in st.session_state:
    st.session_state.elo_params = {
        "start_rating": DEFAULT_START_RATING,
        "base_k": DEFAULT_K,
        "newbie_games": NEWBIE_GAMES,
        "newbie_k": NEWBIE_K,
    }
params = st.session_state.elo_params

# --- Cache & versioning des données ---
if "data_version" not in st.session_state:
    st.session_state.data_version = 0

def bump_data_version():
    st.session_state.data_version += 1

def compute_cached_for_ui():
    games_df = load_games(st.session_state.data_version)
    ratings, games_enriched = compute_ratings(games_df, st.session_state.elo_params["start_rating"],
                                                        st.session_state.elo_params["base_k"],
                                                        st.session_state.elo_params["newbie_games"],
                                                        st.session_state.elo_params["newbie_k"],)
    return games_df, ratings, games_enriched

# --- Sidebar leaderboard (utilise le cache) ---
games_df, ratings_sidebar, _ = compute_cached_for_ui()
with st.sidebar:
    render_sidebar_leaderboard(ratings_sidebar)


# Tabs
tab_saisie_hist, tab_classement, tab_export, tab_params, tab_admin = st.tabs([
    "Saisir / Historique",
    "Classement",
    "Export",
    "Paramètres",
    "Admin",
])

with tab_saisie_hist:
    render_tab_saisie_histo(params)

with tab_classement:
    render_tab_classement(params)

with tab_export:
    render_tab_export(params)

with tab_params:
    render_tab_params(params)

with tab_admin:
    render_tab_admin()
