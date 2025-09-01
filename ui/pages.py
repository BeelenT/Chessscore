from datetime import datetime
from io import BytesIO

import numpy as np
import pandas as pd
import streamlit as st

from db.repo import load_games, save_games_df, save_game_row, load_players, save_players_df
from core.elo import compute_ratings

def _existing_players() -> list[str]:
    games_df = load_games()
    players_df = load_players()
    combined = pd.concat([
        games_df["white"], games_df["black"], players_df.get("name", pd.Series(dtype=str))
    ], ignore_index=True).dropna()
    return sorted(set(combined.astype(str).str.strip().unique()))

def render_tab_saisie_histo(params: dict):
    games_df = load_games()
    st.subheader("Ajouter une partie")
    c1, c2, c3 = st.columns(3)
    options = ["<nouveau>"] + _existing_players()
    with c1:
        white = st.selectbox("Blancs", options=options, index=1 if len(options)>1 else 0)
        if white == "<nouveau>":
            white = st.text_input("Nom du joueur (Blancs)", key="white_new").strip()
    with c2:
        black = st.selectbox("Noirs", options=options, index=2 if len(options)>2 else 0)
        if black == "<nouveau>":
            black = st.text_input("Nom du joueur (Noirs)", key="black_new").strip()
    with c3:
        date_val = st.date_input("Date", value=datetime.today().date())

    res_map = {"Blancs gagnent 1-0": 1.0, "Noirs gagnent 0-1": 0.0, "Nulle ½-½": 0.5}
    res_label = st.radio("Résultat", list(res_map.keys()), horizontal=True)
    result_val = res_map[res_label]

    valid = white and black and white != black
    if not valid:
        st.info("Sélectionnez deux joueurs distincts.")

    if st.button("Enregistrer la partie", type="primary", disabled=not valid):
        save_game_row(date_val, white.strip(), black.strip(), result_val)
        st.success("Partie ajoutée.")
        st.rerun()

    # Historique (émoticônes)
    st.subheader("Historique des parties")
    st.caption("Astuce: corrigez une ligne puis cliquez « Sauvegarder ».")
    st.markdown(
        "<small><b>Légende résultat :</b> ⚪ = Blancs (1) · ⚫ = Noirs (0) · 🤝 = Nulle (0.5)</small>",
        unsafe_allow_html=True,
    )

    display_df = games_df.copy()

    def _to_num_or_keep(x):
        try: return float(x)
        except Exception: return x

    display_df["result"] = display_df["result"].apply(_to_num_or_keep)
    display_df["result"] = display_df["result"].map({1.0:"⚪", 0.0:"⚫", 0.5:"🤝"}).fillna(display_df["result"])

    edit_df = st.data_editor(
        display_df,
        num_rows="dynamic",
        use_container_width=True,
        column_order=["date", "white", "black", "result"],  # cache id
        column_config={
            "id": st.column_config.TextColumn("id", disabled=True),  # pas affiché si column_order défini
            "date": st.column_config.DateColumn("date"),
            "white": st.column_config.TextColumn("white"),
            "black": st.column_config.TextColumn("black"),
            "result": st.column_config.TextColumn("result", help="⚪=Blancs, ⚫=Noirs, 🤝=Nulle (1/0/0.5)"),
        },
        key="editor_games",
    )

    if st.button("Sauvegarder l'historique"):
        df_save = edit_df.copy()

        def convert_result(val):
            if pd.isna(val): return np.nan
            s = str(val).strip().lower()
            if s in {"⚪","⚪️","white","w","1-0","1","1.0"}: return 1.0
            if s in {"⚫","⚫️","black","b","0-1","0","0.0"}: return 0.0
            if s in {"🤝","draw","d","nulle","1/2-1/2","0.5-0.5","0.5","0,5"}: return 0.5
            try:
                f = float(s.replace(",", "."))
                if f in (0.0, 0.5, 1.0): return f
            except Exception: pass
            return s

        df_save["result"] = df_save["result"].apply(convert_result)
        df_save["date"] = pd.to_datetime(df_save["date"], errors="coerce").dt.date
        save_games_df(df_save)
        st.success("Sauvegardé.")
        st.rerun()

def render_tab_classement(params: dict):
    games_df = load_games()
    ratings, games_enriched = compute_ratings(
        games_df,
        start_rating=params["start_rating"],
        base_k=params["base_k"],
        newbie_games=params["newbie_games"],
        newbie_k=params["newbie_k"],
    )
    st.subheader("Classement actuel")
    st.dataframe(ratings, use_container_width=True)
    with st.expander("Détails de calcul par partie"):
        st.dataframe(games_enriched, use_container_width=True)

def render_tab_export(params: dict):
    games_df = load_games()
    ratings, games_enriched = compute_ratings(
        games_df,
        start_rating=params["start_rating"],
        base_k=params["base_k"],
        newbie_games=params["newbie_games"],
        newbie_k=params["newbie_k"],
    )
    st.subheader("Exporter vers Excel (XLSX)")
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        ratings.to_excel(writer, index=False, sheet_name="Classement")
        games_enriched.to_excel(writer, index=False, sheet_name="Historique")
        pd.DataFrame({"date":[datetime.today().date()], "white":["Alice"], "black":["Bob"], "result":[1.0]}).to_excel(
            writer, index=False, sheet_name="TemplatePartie"
        )
    st.download_button(
        label="Télécharger le fichier Excel",
        data=buf.getvalue(),
        file_name="chessscore_export.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

def render_tab_params(params: dict):
    st.subheader("Paramètres ELO")
    st.caption("Ces paramètres impactent tous les classements et exports.")
    c1, c2 = st.columns(2)
    with c1:
        start_rating_new = st.number_input("Élo initial", min_value=600, max_value=2400, value=int(params["start_rating"]), step=50)
        base_k_new      = st.slider("K (joueurs établis)", min_value=8, max_value=64, value=int(params["base_k"]), step=1)
    with c2:
        newbie_games_new= st.slider("Nb matchs 'nouveau'", min_value=0, max_value=30, value=int(params["newbie_games"]), step=1)
        newbie_k_new    = st.slider("K (nouveau)", min_value=8, max_value=64, value=int(params["newbie_k"]), step=1)

    if st.button("Enregistrer les paramètres"):
        st.session_state.elo_params = {
            "start_rating": int(start_rating_new),
            "base_k": int(base_k_new),
            "newbie_games": int(newbie_games_new),
            "newbie_k": int(newbie_k_new),
        }
        st.success("Paramètres mis à jour.")
        st.rerun()

def render_tab_admin():
    st.subheader("Gestion des joueurs (optionnel)")
    df = load_players()
    if df.empty:
        df = pd.DataFrame({"name":["Alice","Bob"], "alias":["A.","B."]})
    edit = st.data_editor(df, num_rows="dynamic", use_container_width=True, key="editor_players")
    if st.button("Sauvegarder la liste des joueurs"):
        save_players_df(edit)
        st.success("Joueurs sauvegardés.")
