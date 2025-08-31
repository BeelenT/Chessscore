import streamlit as st
import pandas as pd

def chess_icon(rank: int) -> str:
    return {1:"♔",2:"♕",3:"♖",4:"♗",5:"♘"}.get(rank,"♙")

def render_sidebar_leaderboard(df: pd.DataFrame) -> None:
    st.header("Classement (ELO)")
    if df.empty:
        st.caption("Aucun joueur"); return
    top = df[["player","rating"]].sort_values("rating", ascending=False).reset_index(drop=True)
    for i, row in top.iterrows():
        rank = i+1
        icon = chess_icon(rank)
        size = "1.6rem" if rank==1 else ("1.4rem" if rank==2 else ("1.2rem" if rank==3 else "1.0rem"))
        weight = "900" if rank==1 else ("800" if rank==2 else ("700" if rank==3 else "600"))
        bg = ("background:rgba(255,215,0,0.25);" if rank==1 else
              "background:rgba(192,192,192,0.25);" if rank==2 else
              "background:rgba(205,127,50,0.25);" if rank==3 else "")
        label = "🥇" if rank==1 else ("🥈" if rank==2 else ("🥉" if rank==3 else f"{rank}."))
        html = f"""
        <div style='display:flex;align-items:center;justify-content:space-between;padding:4px 6px;{bg}border-radius:6px;'>
            <div style='flex:1;display:flex;align-items:center;gap:0.5rem;font-size:{size};font-weight:{weight};'>
                <span>{label}</span><span>{icon}</span><span>{row['player']}</span>
            </div>
            <div style='font-size:{size};font-weight:{weight};font-variant-numeric:tabular-nums;'>
                {int(round(row['rating']))}
            </div>
        </div>"""
        st.markdown(html, unsafe_allow_html=True)
        if i < len(top)-1:
            st.markdown("<hr style='margin:2px 0; opacity:0.25'>", unsafe_allow_html=True)
