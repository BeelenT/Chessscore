# app.py
# Streamlit ELO chess tracker – aucune macro Excel, saisie simple et export XLSX
# Usage:
#   1) pip install streamlit pandas numpy openpyxl
#   2) streamlit run app.py

import math
import os
from datetime import datetime
from io import BytesIO

import numpy as np
import pandas as pd
import streamlit as st

# --------------------
# Constantes & stockage
# --------------------
DATA_DIR = "data"
GAMES_CSV = os.path.join(DATA_DIR, "games.csv")
PLAYERS_CSV = os.path.join(DATA_DIR, "players.csv")  # optionnel, pour alias

DEFAULT_START_RATING = 1200
DEFAULT_K = 20
NEWBIE_GAMES = 10
NEWBIE_K = 40

os.makedirs(DATA_DIR, exist_ok=True)

# --------------------
# Helpers fichiers
# --------------------

def load_games() -> pd.DataFrame:
    if os.path.exists(GAMES_CSV):
        df = pd.read_csv(GAMES_CSV)
        cols = {c.lower(): c for c in df.columns}
        rename_map = {
            cols.get("date", "date"): "date",
            cols.get("white", "white"): "white",
            cols.get("black", "black"): "black",
            cols.get("result", "result"): "result",
        }
        df = df.rename(columns=rename_map)[["date", "white", "black", "result"]]
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
        return df
    else:
        return pd.DataFrame(columns=["date", "white", "black", "result"])


def save_games(df: pd.DataFrame) -> None:
    df = df.copy()
    df.to_csv(GAMES_CSV, index=False)


def load_players() -> pd.DataFrame:
    if os.path.exists(PLAYERS_CSV):
        df = pd.read_csv(PLAYERS_CSV)
        if "name" not in df.columns:
            df = pd.DataFrame(columns=["name", "alias"])
        return df
    return pd.DataFrame(columns=["name", "alias"])


def save_players(df: pd.DataFrame) -> None:
    df.to_csv(PLAYERS_CSV, index=False)

# --------------------
# ELO core
# --------------------

def expected_score(ra: float, rb: float) -> float:
    return 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))


def update_elo(ra: float, rb: float, sa: float, k: float) -> tuple[float, float]:
    ea = expected_score(ra, rb)
    eb = 1.0 - ea
    ra_new = ra + k * (sa - ea)
    rb_new = rb + (k * ((1.0 - sa) - eb))
    return ra_new, rb_new


def compute_ratings(
    games: pd.DataFrame,
    start_rating: int = DEFAULT_START_RATING,
    base_k: int = DEFAULT_K,
    newbie_games: int = NEWBIE_GAMES,
    newbie_k: int = NEWBIE_K,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = games.copy()
    if df.empty:
        return (
            pd.DataFrame(columns=["player", "rating", "games", "wins", "draws", "losses"]),
            df.assign(
                white_rating_pre=np.nan,
                black_rating_pre=np.nan,
                white_rating_post=np.nan,
                black_rating_post=np.nan,
                k_white=np.nan,
                k_black=np.nan,
                exp_white=np.nan,
                exp_black=np.nan,
            ),
        )

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.sort_values(["date"]).reset_index(drop=True)

    ratings: dict[str, float] = {}
    counts: dict[str, int] = {}

    enrich_cols = {
        "white_rating_pre": [],
        "black_rating_pre": [],
        "white_rating_post": [],
        "black_rating_post": [],
        "k_white": [],
        "k_black": [],
        "exp_white": [],
        "exp_black": [],
    }

    for _, row in df.iterrows():
        w = str(row["white"]).strip()
        b = str(row["black"]).strip()
        res = row["result"]
        try:
            s_white = float(res)
        except Exception:
            val = str(res).replace(" ", "").lower()
            if val in ("1-0", "w", "white"):
                s_white = 1.0
            elif val in ("0-1", "b", "black"):
                s_white = 0.0
            elif val in ("0.5-0.5", "1/2-1/2", "d", "draw"):
                s_white = 0.5
            else:
                raise ValueError(f"Résultat invalide: {res}")

        rw = ratings.get(w, start_rating)
        rb_ = ratings.get(b, start_rating)
        cw = counts.get(w, 0)
        cb = counts.get(b, 0)

        k_w = NEWBIE_K if cw < newbie_games else base_k
        k_b = NEWBIE_K if cb < newbie_games else base_k

        ew = expected_score(rw, rb_)
        rb_exp = 1.0 - ew

        rw_new, _ = update_elo(rw, rb_, s_white, k_w)
        s_black = 1.0 - s_white
        rb_new = rb_ + k_b * (s_black - rb_exp)

        ratings[w] = rw_new
        ratings[b] = rb_new
        counts[w] = cw + 1
        counts[b] = cb + 1

        enrich_cols["white_rating_pre"].append(rw)
        enrich_cols["black_rating_pre"].append(rb_)
        enrich_cols["white_rating_post"].append(rw_new)
        enrich_cols["black_rating_post"].append(rb_new)
        enrich_cols["k_white"].append(k_w)
        enrich_cols["k_black"].append(k_b)
        enrich_cols["exp_white"].append(ew)
        enrich_cols["exp_black"].append(rb_exp)

    rows = []
    for p, r in ratings.items():
        n = counts.get(p, 0)
        m_white = df[df.white.astype(str) == p]
        m_black = df[df.black.astype(str) == p]
        w_w = (m_white["result"].astype(str).isin(["1", "1.0", "1-0", "w", "white"]).sum())
        l_w = (m_white["result"].astype(str).isin(["0", "0.0", "0-1", "b", "black"]).sum())
        d_w = len(m_white) - w_w - l_w
        w_b = (m_black["result"].astype(str).isin(["0", "0.0", "0-1", "b", "black"]).sum())
        l_b = (m_black["result"].astype(str).isin(["1", "1.0", "1-0", "w", "white"]).sum())
        d_b = len(m_black) - w_b - l_b
        wins = w_w + w_b
        draws = d_w + d_b
        losses = l_w + l_b
        rows.append({
            "player": p,
            "rating": round(r, 1),
            "games": n,
            "wins": int(wins),
            "draws": int(draws),
            "losses": int(losses),
        })
    rating_table = pd.DataFrame(rows).sort_values(["rating", "games"], ascending=[False, True]).reset_index(drop=True)

    games_enriched = df.assign(**enrich_cols)
    return rating_table, games_enriched

# --------------------
# UI helpers
# --------------------

def render_sidebar_leaderboard(df: pd.DataFrame) -> None:
    st.header("Classement (ELO)")
    if df.empty:
        st.caption("Aucun joueur")
        return
    top = df[["player", "rating"]].sort_values("rating", ascending=False).reset_index(drop=True)

    def chess_icon(rank: int) -> str:
        return {1: "♔", 2: "♕", 3: "♖", 4: "♗", 5: "♘"}.get(rank, "♙")

    for i, row in top.iterrows():
        rank = i + 1
        icon = chess_icon(rank)

        # tailles / graisses
        size = "1.6rem" if rank == 1 else ("1.4rem" if rank == 2 else ("1.2rem" if rank == 3 else "1.0rem"))
        weight = "900" if rank == 1 else ("800" if rank == 2 else ("700" if rank == 3 else "600"))

        # fond coloré
        if rank == 1:
            bg = "background:rgba(255,215,0,0.25);border-radius:6px;"   # or
            label = "🥇"
        elif rank == 2:
            bg = "background:rgba(192,192,192,0.25);border-radius:6px;" # argent
            label = "🥈"
        elif rank == 3:
            bg = "background:rgba(205,127,50,0.25);border-radius:6px;"  # bronze
            label = "🥉"
        else:
            bg = ""
            label = f"{rank}."

        html = f"""
        <div style='display:flex;align-items:center;justify-content:space-between;padding:4px 6px;{bg}'>
            <div style='flex:1;display:flex;align-items:center;gap:0.5rem;font-size:{size};font-weight:{weight};'>
                <span>{label}</span>
                <span>{icon}</span>
                <span>{row['player']}</span>
            </div>
            <div style='font-size:{size};font-weight:{weight};font-variant-numeric:tabular-nums;'>
                {int(round(row['rating']))}
            </div>
        </div>
        """
        st.markdown(html, unsafe_allow_html=True)

        if i < len(top) - 1:
            st.markdown("<hr style='margin:2px 0; opacity:0.25'>", unsafe_allow_html=True)







# --------------------
# UI
# --------------------

st.set_page_config(page_title="ELO Chess – CDS", page_icon="♟️", layout="wide")
st.title("♟️ Classement ELO – CDS")

# Chargement
players_df = load_players()
games_df = load_games()

# Session state pour les paramètres ELO
if "elo_params" not in st.session_state:
    st.session_state.elo_params = {
        "start_rating": DEFAULT_START_RATING,
        "base_k": DEFAULT_K,
        "newbie_games": NEWBIE_GAMES,
        "newbie_k": NEWBIE_K,
    }

p = st.session_state.elo_params

# Classement rapide (sidebar) – design cards
ratings_sidebar, _ = compute_ratings(
    games_df,
    start_rating=p["start_rating"],
    base_k=p["base_k"],
    newbie_games=p["newbie_games"],
    newbie_k=p["newbie_k"],
)
with st.sidebar:
    render_sidebar_leaderboard(ratings_sidebar)

existing_players = sorted(set(pd.concat([
    games_df["white"], games_df["black"], players_df.get("name", pd.Series(dtype=str))
], ignore_index=True).dropna().astype(str).str.strip().unique()))

# Onglets (paramètres déplacés après Export)


tab_saisie_hist, tab_classement, tab_export, tab_params, tab_admin = st.tabs([
    "Saisir / Historique",
    "Classement",
    "Export",
    "Paramètres",
    "Admin",
])

with tab_saisie_hist:
    st.subheader("Ajouter une partie")
    col1, col2, col3 = st.columns(3)
    with col1:
        white = st.selectbox("Blancs", options=["<nouveau>"] + existing_players, index=1 if len(existing_players) else 0)
        if white == "<nouveau>":
            white = st.text_input("Nom du joueur (Blancs)", key="white_new").strip()
    with col2:
        black = st.selectbox("Noirs", options=["<nouveau>"] + existing_players, index=2 if len(existing_players) > 1 else 0)
        if black == "<nouveau>":
            black = st.text_input("Nom du joueur (Noirs)", key="black_new").strip()
    with col3:
        date_val = st.date_input("Date", value=datetime.today().date())

    res_map = {"Blancs gagnent 1-0": 1.0, "Noirs gagnent 0-1": 0.0, "Nulle ½-½": 0.5}
    res_label = st.radio("Résultat", list(res_map.keys()), horizontal=True)
    result_val = res_map[res_label]

    valid_inputs = white and black and white != black
    if not valid_inputs:
        st.info("Sélectionnez deux joueurs distincts.")

    if st.button("Enregistrer la partie", type="primary", disabled=not valid_inputs):
        new_row = {"date": date_val, "white": white.strip(), "black": black.strip(), "result": result_val}
        games_df = pd.concat([games_df, pd.DataFrame([new_row])], ignore_index=True)
        save_games(games_df)
        st.success("Partie ajoutée.")
        st.rerun()

    st.subheader("Historique des parties")
    st.caption("Astuce: vous pouvez corriger une ligne puis cliquer 'Sauvegarder'.")
    st.markdown(
        "<small><b>Légende résultat :</b> ⚪ = Blancs (1) · ⚫ = Noirs (0) · 🤝 = Nulle (0.5)</small>",
        unsafe_allow_html=True,
    )

    # Affichage avec emojis ; conversion inverse au moment de la sauvegarde
    display_df = games_df.copy()


    # si 'result' est string, tenter float, sinon on garde pour le mapping visuel
    def _to_num_or_keep(x):
        try:
            return float(x)
        except Exception:
            return x


    display_df["result"] = display_df["result"].apply(_to_num_or_keep)
    display_df["result"] = display_df["result"].map({1.0: "⚪", 0.0: "⚫", 0.5: "🤝"}).fillna(display_df["result"])

    edit_df = st.data_editor(
        display_df,
        num_rows="dynamic",
        width='stretch',
        column_config={
            "date": st.column_config.DateColumn("date"),
            "white": st.column_config.TextColumn("white"),
            "black": st.column_config.TextColumn("black"),
            # TextColumn pour accepter les emojis
            "result": st.column_config.TextColumn("result", help="⚪=Blancs, ⚫=Noirs, 🤝=Nulle (1/0/0.5 aussi acceptés)"),
        },
        key="editor_games",
    )

    if st.button("Sauvegarder l'historique"):
        df_save = edit_df.copy()


        # Conversion inverse emojis / texte libre -> 1.0 / 0.0 / 0.5
        def convert_result(val):
            if pd.isna(val):
                return np.nan
            s = str(val).strip().lower()
            # emojis & alias
            if s in {"⚪", "⚪️", "white", "w", "1-0", "1", "1.0"}:
                return 1.0
            if s in {"⚫", "⚫️", "black", "b", "0-1", "0", "0.0"}:
                return 0.0
            if s in {"🤝", "draw", "d", "nulle", "1/2-1/2", "0.5-0.5", "0.5", "0,5"}:
                return 0.5
            # essai float
            try:
                f = float(s.replace(",", "."))
                if f in (0.0, 0.5, 1.0):
                    return f
            except Exception:
                pass
            # sinon on laisse tel quel (compute_ratings lèvera en cas d'invalidité)
            return s


        df_save["result"] = df_save["result"].apply(convert_result)
        # Coerce dates
        df_save["date"] = pd.to_datetime(df_save["date"], errors="coerce").dt.date

        save_games(df_save)
        st.success("Sauvegardé.")
        # >>> rafraîchir immédiatement affichage + classement
        st.rerun()

with tab_classement:
    st.subheader("Classement actuel")
    ratings, games_enriched = compute_ratings(
        games_df,
        start_rating=p["start_rating"],
        base_k=p["base_k"],
        newbie_games=p["newbie_games"],
        newbie_k=p["newbie_k"],
    )
    st.dataframe(ratings, width='stretch')

    with st.expander("Détails de calcul par partie"):
        st.dataframe(games_enriched, width='stretch')

with tab_export:
    st.subheader("Exporter vers Excel (XLSX)")
    ratings, games_enriched = compute_ratings(
        games_df,
        start_rating=p["start_rating"],
        base_k=p["base_k"],
        newbie_games=p["newbie_games"],
        newbie_k=p["newbie_k"],
    )
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        ratings.to_excel(writer, index=False, sheet_name="Classement")
        games_enriched.to_excel(writer, index=False, sheet_name="Historique")
        pd.DataFrame({"date": [datetime.today().date()], "white": ["Alice"], "black": ["Bob"], "result": [1.0]}).to_excel(
            writer, index=False, sheet_name="TemplatePartie"
        )
    st.download_button(
        label="Télécharger le fichier Excel",
        data=buf.getvalue(),
        file_name="classement_elo.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

with tab_params:
    st.subheader("Paramètres ELO")
    st.caption("Ces paramètres impactent tous les classements et exports.")
    c1, c2 = st.columns(2)
    with c1:
        start_rating_new = st.number_input("Élo initial", min_value=600, max_value=2400, value=int(p["start_rating"]), step=50)
        base_k_new = st.slider("K (joueurs établis)", min_value=8, max_value=64, value=int(p["base_k"]), step=1)
    with c2:
        newbie_games_new = st.slider("Nb matchs 'nouveau'", min_value=0, max_value=30, value=int(p["newbie_games"]), step=1)
        newbie_k_new = st.slider("K (nouveau)", min_value=8, max_value=64, value=int(p["newbie_k"]), step=1)

    if st.button("Enregistrer les paramètres"):
        st.session_state.elo_params = {
            "start_rating": int(start_rating_new),
            "base_k": int(base_k_new),
            "newbie_games": int(newbie_games_new),
            "newbie_k": int(newbie_k_new),
        }
        st.success("Paramètres mis à jour.")
        st.rerun()

with tab_admin:
    st.subheader("Gestion des joueurs (optionnel)")
