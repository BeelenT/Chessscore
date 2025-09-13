import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

def get_engine():
    url = st.secrets.get("DB_URL")
    if not url:
        raise RuntimeError("Missing DB_URL in Streamlit secrets")
    return create_engine(url, pool_pre_ping=True)

@st.cache_resource
def engine():
    return get_engine()

def init_db():
    with engine().begin() as con:
        con.execute(text("set search_path to chessscore, public;"))

@st.cache_data(show_spinner=False)
def load_games(version: int) -> pd.DataFrame:
    q = "select id, date, white, black, result from chessscore.games order by date desc, id desc"
    return pd.read_sql(q, engine())


def save_game_row(date, white, black, result):
    with engine().begin() as con:
        con.execute(text("""
            insert into chessscore.games(date, white, black, result)
            values (:d, :w, :b, :r)
        """), {"d": str(date), "w": white, "b": black, "r": float(result)})

def save_games_df(df: pd.DataFrame):
    with engine().begin() as con:
        con.execute(text("truncate table chessscore.games;"))
        df.to_sql("games", con.connection, if_exists="append", index=False, schema="chessscore")

# Players (optionnel)
@st.cache_data(show_spinner=False)
def load_players(version: int) -> pd.DataFrame:
    q = "select name, alias from chessscore.players order by name;"
    try:
        return pd.read_sql(q, engine())
    except Exception:
        # table absente : renvoyer DF vide
        return pd.DataFrame(columns=["name","alias"])

def save_players_df(df: pd.DataFrame):
    with engine().begin() as con:
        con.execute(text("truncate table chessscore.players;"))
        df.to_sql("players", con.connection, if_exists="append", index=False, schema="chessscore")
