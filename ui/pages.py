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
    if "data_version" not in st.session_state:
        st.session_state.data_version = 0

    games_df = load_games(st.session_state.data_version)
    players_df = load_players(st.session_state.data_version)

    # --- Ajout d'un joueur (un seul bouton) ---
    st.session_state.setdefault("show_add_player", False)

    col_add, _ = st.columns([1, 3])
    with col_add:
        if st.button("➕ Ajouter un joueur", key="btn_show_add_player"):
            st.session_state.show_add_player = True

    if st.session_state.show_add_player:
        with st.form("form_add_player", clear_on_submit=True):
            new_player = st.text_input("Nom du nouveau joueur", key="new_player_name", placeholder="Ex: Alice")
            cpa, cpb = st.columns([1, 1])
            with cpa:
                submitted_add_player = st.form_submit_button("Valider", type="primary")
            with cpb:
                cancel_add_player = st.form_submit_button("Annuler")

        # Annuler -> referme le panneau, rien d'autre
        if 'cancel_add_player' in locals() and cancel_add_player:
            st.session_state.show_add_player = False
            st.stop()

        # Valider -> validations + insertion + refresh
        if 'submitted_add_player' in locals() and submitted_add_player:
            name = (new_player or "").strip()
            errors = []
            if len(name) < 2:
                errors.append("Nom trop court (2 caractères minimum).")

            # Unicité (casse comprise -> comparaison EXACTE)
            dfp = load_players()
            if "name" in dfp.columns and name in set(dfp["name"].astype(str)):
                errors.append(f"Le joueur « {name} » existe déjà.")

            if errors:
                for e in errors: st.warning(e)
            else:
                # Append puis sauvegarde (table players unique sur name)
                if "name" not in dfp.columns:
                    dfp = pd.DataFrame(columns=["name", "alias"])
                dfp = pd.concat([dfp, pd.DataFrame([{"name": name, "alias": None}])], ignore_index=True)
                save_players_df(dfp)
                st.success(f"Joueur « {name} » ajouté.")

                # Fermer le panneau + invalider caches + recharger l'UI
                st.session_state.show_add_player = False
                st.session_state.data_version += 1
                st.rerun()

    # -------- Formulaire d'ajout : rerun uniquement au submit --------
    with st.form("form_add_game", clear_on_submit=True):
        st.subheader("Ajouter une partie")

        c1, c2, c3 = st.columns(3)

        # options joueurs existants (à partir des données cachées)
        players_df = load_players()
        combined = pd.concat([
            games_df["white"], games_df["black"], players_df.get("name", pd.Series(dtype=str))
        ], ignore_index=True).dropna()
        existing = sorted(set(combined.astype(str).str.strip().unique()))
        options = ["<nouveau>"] + existing

        with c1:
            white_sel = st.selectbox("Blancs", options=options, index=1 if len(options)>1 else 0)
            white = st.text_input("Nom du joueur (Blancs)", key="white_new").strip() if white_sel=="<nouveau>" else white_sel
        with c2:
            black_sel = st.selectbox("Noirs", options=options, index=2 if len(options)>2 else 0)
            black = st.text_input("Nom du joueur (Noirs)", key="black_new").strip() if black_sel=="<nouveau>" else black_sel
        with c3:
            date_val = st.date_input("Date", value=datetime.today().date())

        res_map = {"Blancs gagnent 1-0": 1.0, "Noirs gagnent 0-1": 0.0, "Nulle ½-½": 0.5}
        res_label = st.radio("Résultat", list(res_map.keys()), horizontal=True)
        result_val = res_map[res_label]

        valid = white and black and white != black
        submitted_add = st.form_submit_button("Enregistrer la partie", type="primary", disabled=not valid)

    if submitted_add:
        save_game_row(date_val, white.strip(), black.strip(), result_val)
        st.success("Partie ajoutée.")
        st.session_state.data_version += 1   # invalide le cache
        st.rerun()

    # -------- Historique (édition) --------
    st.subheader("Historique des parties")
    st.caption("Astuce: corrigez une ligne puis cliquez « Sauvegarder ».")
    st.markdown(
        "<small><b>Légende résultat :</b> ⚪ = Blancs (1) · ⚫ = Noirs (0) · 🤝 = Nulle (0.5)</small>",
        unsafe_allow_html=True,
    )

    display_df = games_df.copy()

    # masquer id côté UI (si présent)
    column_order = ["date", "white", "black", "result"]
    if "id" in display_df.columns:
        # on garde 'id' pour la sauvegarde complète si tu veux, mais on ne l'affiche pas
        pass

    # mapping chiffres -> emojis pour l'affichage
    def _to_num_or_keep(x):
        try: return float(x)
        except Exception: return x
    display_df["result"] = display_df["result"].apply(_to_num_or_keep)
    display_df["result"] = display_df["result"].map({1.0:"⚪", 0.0:"⚫", 0.5:"🤝"}).fillna(display_df["result"])

    with st.form("form_save_history"):
        edit_df = st.data_editor(
            display_df,
            num_rows="dynamic",
            use_container_width=True,
            column_order=column_order,
            column_config={
                "date":  st.column_config.DateColumn("date"),
                "white": st.column_config.TextColumn("white"),
                "black": st.column_config.TextColumn("black"),
                "result":st.column_config.TextColumn("result", help="⚪=Blancs, ⚫=Noirs, 🤝=Nulle (1/0/0.5 acceptés)"),
            },
            key="editor_games",
        )
        submitted_hist = st.form_submit_button("Sauvegarder l'historique")

    if submitted_hist:
        df_save = edit_df.copy()

        # conversion inverse emojis/texte vers 1.0 / 0.0 / 0.5
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

        # réécrit tout l'historique (comme avant)
        save_games_df(df_save)
        st.success("Sauvegardé.")
        st.session_state.data_version += 1   # invalide le cache
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
    if "data_version" not in st.session_state:
        st.session_state.data_version = 0

    st.subheader("Exporter vers Excel (XLSX)")

    if st.button("Préparer le fichier"):
        games_df = load_games(st.session_state.data_version)
        ratings, games_enriched = compute_ratings(games_df, params["start_rating"], params["base_k"],
                                                            params["newbie_games"], params["newbie_k"])

        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            ratings.to_excel(writer, index=False, sheet_name="Classement")
            games_enriched.to_excel(writer, index=False, sheet_name="Historique")
            pd.DataFrame({"date":[datetime.today().date()], "white":["Alice"], "black":["Bob"], "result":[1.0]}).to_excel(
                writer, index=False, sheet_name="TemplatePartie"
            )
        st.session_state["last_export"] = buf.getvalue()

    if "last_export" in st.session_state:
        st.download_button(
            label="Télécharger le fichier Excel",
            data=st.session_state["last_export"],
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
