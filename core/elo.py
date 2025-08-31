import numpy as np
import pandas as pd

def expected_score(ra: float, rb: float) -> float:
    return 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))

def update_elo(ra: float, rb: float, sa: float, k: float) -> tuple[float, float]:
    ea = expected_score(ra, rb)
    eb = 1.0 - ea
    return ra + k * (sa - ea), rb + k * ((1.0 - sa) - eb)

def compute_ratings(
    games: pd.DataFrame,
    start_rating: int,
    base_k: int,
    newbie_games: int,
    newbie_k: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = games.copy()
    if df.empty:
        return (
            pd.DataFrame(columns=["player","rating","games","wins","draws","losses"]),
            df.assign(
                white_rating_pre=np.nan, black_rating_pre=np.nan,
                white_rating_post=np.nan, black_rating_post=np.nan,
                k_white=np.nan, k_black=np.nan, exp_white=np.nan, exp_black=np.nan
            ),
        )

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.sort_values("date").reset_index(drop=True)

    ratings, counts = {}, {}
    enrich = {k: [] for k in [
        "white_rating_pre","black_rating_pre","white_rating_post","black_rating_post",
        "k_white","k_black","exp_white","exp_black"
    ]}

    for _, row in df.iterrows():
        w, b = str(row["white"]).strip(), str(row["black"]).strip()
        # normalise result
        try:
            s_white = float(row["result"])
        except Exception:
            v = str(row["result"]).replace(" ", "").lower()
            if v in ("1-0","w","white"): s_white = 1.0
            elif v in ("0-1","b","black"): s_white = 0.0
            elif v in ("0.5-0.5","1/2-1/2","d","draw"): s_white = 0.5
            else: raise ValueError(f"Invalid result: {row['result']}")

        rw, rb = ratings.get(w, start_rating), ratings.get(b, start_rating)
        cw, cb = counts.get(w, 0), counts.get(b, 0)
        k_w = newbie_k if cw < newbie_games else base_k
        k_b = newbie_k if cb < newbie_games else base_k

        ew = expected_score(rw, rb)
        rb_exp = 1.0 - ew

        rw_new, _ = update_elo(rw, rb, s_white, k_w)
        s_black = 1.0 - s_white
        rb_new = rb + k_b * (s_black - rb_exp)

        ratings[w], ratings[b] = rw_new, rb_new
        counts[w], counts[b] = cw + 1, cb + 1

        enrich["white_rating_pre"].append(rw)
        enrich["black_rating_pre"].append(rb)
        enrich["white_rating_post"].append(rw_new)
        enrich["black_rating_post"].append(rb_new)
        enrich["k_white"].append(k_w)
        enrich["k_black"].append(k_b)
        enrich["exp_white"].append(ew)
        enrich["exp_black"].append(rb_exp)

    rows = []
    for p, r in ratings.items():
        n = counts.get(p, 0)
        m_w, m_b = df[df.white.astype(str)==p], df[df.black.astype(str)==p]
        w_w = m_w["result"].astype(str).isin(["1","1.0","1-0","w","white"]).sum()
        l_w = m_w["result"].astype(str).isin(["0","0.0","0-1","b","black"]).sum()
        d_w = len(m_w) - w_w - l_w
        w_b = m_b["result"].astype(str).isin(["0","0.0","0-1","b","black"]).sum()
        l_b = m_b["result"].astype(str).isin(["1","1.0","1-0","w","white"]).sum()
        d_b = len(m_b) - w_b - l_b
        rows.append(dict(player=p, rating=round(r,1), games=n, wins=w_w+w_b, draws=d_w+d_b, losses=l_w+l_b))

    rating_table = pd.DataFrame(rows).sort_values(["rating","games"], ascending=[False, True]).reset_index(drop=True)
    return rating_table, df.assign(**enrich)
