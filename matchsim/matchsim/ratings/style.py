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
