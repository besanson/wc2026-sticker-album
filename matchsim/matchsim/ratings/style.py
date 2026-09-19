"""Per-team style vectors: possession share, directness, press intensity proxy,
width, shot distance (spec section 4.4, a light version of TacticAI-style
matchup thinking -- we have no tracking data, only event coordinates)."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

GOAL_X, GOAL_Y = 105.0, 34.0
PROGRESSIVE_PASS_MIN_GAIN = 10.0  # metres of forward progress
OPPONENT_THIRD_X = 105.0 * 2 / 3
DEFENSIVE_ACTION_TYPES = {"tackle", "interception", "clearance"}
PASS_LIKE_TYPES = {"pass", "cross"}


@dataclass
class TeamStyle:
    team_id: int
    possession_share: float
    directness: float  # progressive passes per possession
    press_intensity: float  # defensive actions in opponent third per opponent possession
    width: float  # std-dev of this team's own action y-coordinate
    shot_distance: float  # mean distance to goal at the moment of shooting


def compute_style_vectors(actions: pd.DataFrame) -> dict[int, TeamStyle]:
    """actions: SPADL actions with possession, possession_team_id merged in
    (matchsim.io.statsbomb's output)."""
    actions = actions.dropna(subset=["possession_team_id"])
    team_ids = sorted(set(actions["team_id"]) | set(actions["possession_team_id"]))

    n_possessions_by_team = actions.groupby("possession_team_id")["possession"].nunique()
    total_possessions = actions.groupby("game_id")["possession"].nunique().sum()

    styles = {}
    for team_id in team_ids:
        own_actions = actions[actions["team_id"] == team_id]
        own_possessions = max(n_possessions_by_team.get(team_id, 0), 1)
        opponent_possessions = max(total_possessions - n_possessions_by_team.get(team_id, 0), 1)

        passes = own_actions[own_actions["type_name"].isin(PASS_LIKE_TYPES) & (own_actions["result_name"] == "success")]
        progress = passes["end_x"] - passes["start_x"]
        n_progressive = int((progress > PROGRESSIVE_PASS_MIN_GAIN).sum())

        defensive = own_actions[own_actions["type_name"].isin(DEFENSIVE_ACTION_TYPES) & (own_actions["start_x"] > OPPONENT_THIRD_X)]

        shots = own_actions[own_actions["type_name"] == "shot"]
        shot_dist = np.sqrt((GOAL_X - shots["start_x"]) ** 2 + (GOAL_Y - shots["start_y"]) ** 2)

        styles[team_id] = TeamStyle(
            team_id=team_id,
            possession_share=float(n_possessions_by_team.get(team_id, 0) / max(total_possessions, 1)),
            directness=float(n_progressive / own_possessions),
            press_intensity=float(len(defensive) / opponent_possessions),
            width=float(own_actions["start_y"].std() or 0.0),
            shot_distance=float(shot_dist.mean()) if len(shots) else float("nan"),
        )
    return styles


@dataclass
class MatchupInteractionAblation:
    rps_without_interaction: float
    rps_with_interaction: float
    interaction_p_value: float
    n_train_games: int
    n_holdout_games: int
    kept: bool


def evaluate_matchup_interaction(
    actions: pd.DataFrame, games: pd.DataFrame, players: pd.DataFrame, rapm_result, seed: int = 0
) -> MatchupInteractionAblation:
    """Fit the calibrated link with and without a directness x press-intensity
    interaction term on an 80/20 train/holdout game split, and compare held-out
    RPS. Spec 4.4: keep the term only if it improves held-out RPS; otherwise
    drop it and say so -- `kept` records that decision."""
    import numpy as np
    import statsmodels.api as sm

    from matchsim.eval import ranked_probability_score
    from matchsim.models.lineup import build_lineup_strength
    from matchsim.sim.scoreline import scoreline_matrix

    styles = compute_style_vectors(actions)
    starters = players[players["is_starter"]]

    rng = np.random.default_rng(seed)
    game_ids = games["game_id"].to_numpy().copy()
    rng.shuffle(game_ids)
    n_train = int(len(game_ids) * 0.8)
    train_ids, holdout_ids = set(game_ids[:n_train]), set(game_ids[n_train:])
    train_games = games[games["game_id"].isin(train_ids)]
    holdout_games = games[games["game_id"].isin(holdout_ids)]

    def team_lineup(gp: pd.DataFrame, team_id) -> list[dict]:
        rows = gp[gp["team_id"] == team_id]
        return [{"player_id": p, "expected_minutes": m} for p, m in zip(rows["player_id"], rows["minutes_played"])]

    def training_rows(games_subset: pd.DataFrame) -> pd.DataFrame:
        rows = []
        for _, game in games_subset.iterrows():
            gp = starters[starters["game_id"] == game["game_id"]]
            for side, team_id, opp_id, goals in (
                ("home", game["home_team_id"], game["away_team_id"], game["home_score"]),
                ("away", game["away_team_id"], game["home_team_id"], game["away_score"]),
            ):
                own = build_lineup_strength(team_lineup(gp, team_id), rapm_result.ratings)
                opp = build_lineup_strength(team_lineup(gp, opp_id), rapm_result.ratings)
                ts, to = styles.get(team_id), styles.get(opp_id)
                rows.append(
                    {
                        "goals": goals,
                        "attack_diff": own.attack - opp.defence,
                        "is_home": 1.0 if side == "home" else 0.0,
                        "interaction": ts.directness * to.press_intensity if ts and to else 0.0,
                    }
                )
        return pd.DataFrame(rows)

    train_rows = training_rows(train_games)

    base_X = sm.add_constant(train_rows[["attack_diff", "is_home"]])
    base_model = sm.GLM(train_rows["goals"], base_X, family=sm.families.Poisson()).fit()

    int_X = sm.add_constant(train_rows[["attack_diff", "is_home", "interaction"]])
    int_model = sm.GLM(train_rows["goals"], int_X, family=sm.families.Poisson()).fit()

    def holdout_rps(params: dict, use_interaction: bool) -> float:
        values = []
        for _, game in holdout_games.iterrows():
            gp = starters[starters["game_id"] == game["game_id"]]
            home_strength = build_lineup_strength(team_lineup(gp, game["home_team_id"]), rapm_result.ratings)
            away_strength = build_lineup_strength(team_lineup(gp, game["away_team_id"]), rapm_result.ratings)

            def lam(own, opp, is_home, team_id=None, opp_id=None):
                log_l = params["const"] + params["attack_diff"] * (own - opp) + params["is_home"] * (1.0 if is_home else 0.0)
                if use_interaction:
                    ts, to = styles.get(team_id), styles.get(opp_id)
                    log_l += params["interaction"] * (ts.directness * to.press_intensity if ts and to else 0.0)
                return float(np.exp(log_l))

            lam_h = lam(home_strength.attack, away_strength.defence, True, game["home_team_id"], game["away_team_id"])
            lam_a = lam(away_strength.attack, home_strength.defence, False, game["away_team_id"], game["home_team_id"])
            matrix = scoreline_matrix(lam_h, lam_a, rho=0.0, max_goals=8)
            values.append(ranked_probability_score(matrix, game["home_score"], game["away_score"]))
        return float(np.mean(values))

    rps_base = holdout_rps(dict(base_model.params), use_interaction=False)
    rps_int = holdout_rps(dict(int_model.params), use_interaction=True)

    return MatchupInteractionAblation(
        rps_without_interaction=rps_base,
        rps_with_interaction=rps_int,
        interaction_p_value=float(int_model.pvalues["interaction"]),
        n_train_games=len(train_games),
        n_holdout_games=len(holdout_games),
        kept=rps_int < rps_base,
    )
