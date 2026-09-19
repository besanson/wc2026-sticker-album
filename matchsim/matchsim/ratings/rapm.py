"""Possession-sequence RAPM player ratings (ridge regression on possession value).
Reference: possession-sequence RAPM (arXiv 2407.17832)."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.linear_model import RidgeCV

from matchsim.ratings.xt import action_xt_delta, fit_xt_grid

THIN_SAMPLE_MINUTES = 900.0


@dataclass
class PlayerRating:
    player_id: object
    off_rating: float
    def_rating: float
    minutes: float
    possessions: int
    thin_sample: bool


def make_rating(player_id, off_rating: float, def_rating: float, minutes: float, possessions: int) -> PlayerRating:
    return PlayerRating(
        player_id=player_id,
        off_rating=off_rating,
        def_rating=def_rating,
        minutes=minutes,
        possessions=possessions,
        thin_sample=minutes < THIN_SAMPLE_MINUTES,
    )


def _possession_table(actions: pd.DataFrame, games: pd.DataFrame, grid) -> pd.DataFrame:
    """One row per (game_id, possession): attacking/defending on-pitch player sets,
    a home indicator, and the xT-delta possession value."""
    actions = actions.dropna(subset=["possession", "possession_team_id"]).copy()
    actions["xt_delta"] = actions.apply(lambda r: action_xt_delta(r, grid), axis=1)

    home_by_game = dict(zip(games["game_id"], games["home_team_id"]))
    away_by_game = dict(zip(games["game_id"], games["away_team_id"]))

    rows = []
    for (game_id, possession), group in actions.groupby(["game_id", "possession"], sort=False):
        attacking_team = group["possession_team_id"].iloc[0]
        home_team = home_by_game[game_id]
        away_team = away_by_game[game_id]
        is_home_attacking = attacking_team == home_team

        attackers = group["home_on_pitch"].iloc[0] if is_home_attacking else group["away_on_pitch"].iloc[0]
        defenders = group["away_on_pitch"].iloc[0] if is_home_attacking else group["home_on_pitch"].iloc[0]

        # only the possessing team's own actions count toward its possession value;
        # the same possession id also carries the opponent's failed defensive actions
        value = group.loc[group["team_id"] == attacking_team, "xt_delta"].sum()

        rows.append(
            {
                "game_id": game_id,
                "possession": possession,
                "attackers": attackers,
                "defenders": defenders,
                "home_indicator": 1.0 if is_home_attacking else -1.0,
                "value": value,
            }
        )
    return pd.DataFrame(rows)


@dataclass
class RAPMResult:
    ratings: dict  # player_id -> PlayerRating
    alpha: float
    n_possessions: int


def fit_rapm(
    actions: pd.DataFrame,
    players: pd.DataFrame,
    games: pd.DataFrame,
    n_folds: int = 5,
    alphas: np.ndarray | None = None,
) -> RAPMResult:
    """Possession-level ridge regression: +1 (own off column) for each attacking
    on-pitch player, +1 (own def column) for each defending on-pitch player, plus
    a home indicator. Response is the xT-delta possession value, fit fresh from
    `actions` by fit_xt_grid (spec section 4.1)."""
    grid = fit_xt_grid(actions)
    possessions = _possession_table(actions, games, grid)
    if possessions.empty:
        raise ValueError("no possessions with a resolvable attacking team to fit RAPM on")

    all_players = sorted(set().union(*possessions["attackers"], *possessions["defenders"]))
    player_col = {p: i for i, p in enumerate(all_players)}
    n_players = len(all_players)
    n_possessions = len(possessions)

    rows, cols, data = [], [], []
    for i, (attackers, defenders) in enumerate(zip(possessions["attackers"], possessions["defenders"])):
        for p in attackers:
            rows.append(i)
            cols.append(player_col[p])
            data.append(1.0)
        for p in defenders:
            rows.append(i)
            cols.append(n_players + player_col[p])
            data.append(1.0)

    home_col = pd.DataFrame({"home": possessions["home_indicator"].to_numpy()})
    design = sparse.coo_matrix((data, (rows, cols)), shape=(n_possessions, 2 * n_players)).tocsr()
    design = sparse.hstack([design, sparse.csr_matrix(home_col.to_numpy())]).tocsr()

    y = possessions["value"].to_numpy()
    if alphas is None:
        alphas = np.logspace(-2, 8, 40)
    model = RidgeCV(alphas=alphas, cv=n_folds)
    model.fit(design, y)
    if model.alpha_ >= alphas[-1]:
        import warnings

        warnings.warn(
            f"RidgeCV selected the largest offered alpha ({model.alpha_:g}); widen the search range."
        )

    minutes_by_player = players.assign(player_id=players["player_id"].astype("int64")).groupby("player_id")[
        "minutes_played"
    ].sum()
    attacker_counts = possessions["attackers"].explode().value_counts()
    defender_counts = possessions["defenders"].explode().value_counts()

    ratings = {}
    for p in all_players:
        off_rating = float(model.coef_[player_col[p]])
        def_rating = float(model.coef_[n_players + player_col[p]])
        n_poss = int(attacker_counts.get(p, 0) + defender_counts.get(p, 0))
        minutes = float(minutes_by_player.get(int(p), 0.0))
        ratings[p] = make_rating(p, off_rating, def_rating, minutes, n_poss)

    return RAPMResult(ratings=ratings, alpha=float(model.alpha_), n_possessions=n_possessions)
