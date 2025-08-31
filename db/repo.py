import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text


SCHEMA = "chessscore"

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
        # créer schéma + tables + index si absents
        con.exec_driver_sql(f"create schema if not exists {SCHEMA};")
        con.exec_driver_sql(f"""
        create table if not exists {SCHEMA}.games(
          id bigserial primary key,
          date date not null,
          white text not null,
          black text not null,
          result real not null check (result in (0, 0.5, 1))
        );""")
        con.exec_driver_sql(f"""
        create table if not exists {SCHEMA}.players(
          id bigserial primary key,
          name text unique not null,
          alias text
        );""")
        con.exec_driver_sql(f"create index if not exists games_date_idx  on {SCHEMA}.games(date);")
        con.exec_driver_sql(f"create index if not exists games_white_idx on {SCHEMA}.games(white);")
        con.exec_driver_sql(f"create index if not exists games_black_idx on {SCHEMA}.games(black);")
        con.exec_driver_sql(f"create unique index if not exists games_uniq_triplet on {SCHEMA}.games(date, white, black);")

def load_games() -> pd.DataFrame:
    q = "select date, white, black, result from chessscore.games order by date;"
    return pd.read_sql(q, engine())

def save_game_row(date, white, black, result):
    with engine().begin() as con:
        con.execute(text("""
            insert into chessscore.games(date, white, black, result)
            values (:d, :w, :b, :r)
            on conflict (date, white, black) do update set result = EXCLUDED.result;
        """), {"d": str(date), "w": white, "b": black, "r": float(result)})

def save_games_df(df: pd.DataFrame):
    with engine().begin() as con:
        con.execute(text("truncate table chessscore.games;"))
        df.to_sql("games", con.connection, if_exists="append", index=False, schema="chessscore")

# Players (optionnel)
def load_players() -> pd.DataFrame:
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
