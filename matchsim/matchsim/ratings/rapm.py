"""Possession-sequence RAPM player ratings (ridge regression on possession value).
Reference: possession-sequence RAPM (arXiv 2407.17832)."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.linear_model import Ridge, RidgeCV

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


def _design_matrix(possessions: pd.DataFrame) -> tuple[sparse.csr_matrix, dict, int]:
    all_players = sorted(set().union(*possessions["attackers"], *possessions["defenders"]))
    player_col = {p: i for i, p in enumerate(all_players)}
    n_players = len(all_players)

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

    design = sparse.coo_matrix((data, (rows, cols)), shape=(len(possessions), 2 * n_players)).tocsr()
    home_col = sparse.csr_matrix(possessions["home_indicator"].to_numpy().reshape(-1, 1))
    design = sparse.hstack([design, home_col]).tocsr()
    return design, player_col, n_players


@dataclass
class RAPMResult:
    ratings: dict  # player_id -> PlayerRating
    alpha: float
    n_possessions: int
    design: sparse.csr_matrix  # cached for bootstrap_player_ratings; not a rating output
    response: np.ndarray
    player_col: dict


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

    design, player_col, n_players = _design_matrix(possessions)
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
    for p, col in player_col.items():
        off_rating = float(model.coef_[col])
        def_rating = float(model.coef_[n_players + col])
        n_poss = int(attacker_counts.get(p, 0) + defender_counts.get(p, 0))
        minutes = float(minutes_by_player.get(int(p), 0.0))
        ratings[p] = make_rating(p, off_rating, def_rating, minutes, n_poss)

    return RAPMResult(
        ratings=ratings,
        alpha=float(model.alpha_),
        n_possessions=len(possessions),
        design=design,
        response=y,
        player_col=player_col,
    )


def bootstrap_player_ratings(result: RAPMResult, n_draws: int = 200, seed: int = 0):
    """Case-resampling bootstrap over possessions, reusing the already
    cross-validated alpha (a single Ridge solve is ~1000x faster than a fresh
    RidgeCV search -- see matchsim/README.md), so 200 real refits stay fast
    enough for on-demand use. Yields one {player_id: (off_rating, def_rating)}
    dict per draw."""
    rng = np.random.default_rng(seed)
    n = result.design.shape[0]
    n_players = len(result.player_col)

    for _ in range(n_draws):
        idx = rng.integers(0, n, size=n)
        model = Ridge(alpha=result.alpha)
        model.fit(result.design[idx], result.response[idx])
        yield {p: (float(model.coef_[col]), float(model.coef_[n_players + col])) for p, col in result.player_col.items()}
