"""Pi-rating system (Constantinou & Fenton 2013): a lightweight, iteratively-updated
home/away team-strength rating. Second Tier 1 variant; an ensemble member, not the
primary (Dixon-Coles is the reference tier every other tier must beat).

Hyperparameters below are standard replication defaults, not paper-tuned values --
appropriate for an ensemble member rather than the primary model.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

STEEPNESS = 3.0
LEARNING_RATE = 0.1
CROSS_TRANSFER = 0.3


def _rating_to_goal_diff(rating_diff: float) -> float:
    return float(np.sign(rating_diff) * (np.power(STEEPNESS, np.abs(rating_diff)) - 1))


def _goal_diff_to_rating(goal_diff: float) -> float:
    return float(np.sign(goal_diff) * (np.log1p(np.abs(goal_diff)) / np.log(STEEPNESS)))


@dataclass
class PiRatingsResult:
    home_rating: dict[str, float]
    away_rating: dict[str, float]
    n_matches: int


def fit(matches: pd.DataFrame) -> PiRatingsResult:
    teams = sorted(set(matches["home_id"]) | set(matches["away_id"]))
    home_rating = {t: 0.0 for t in teams}
    away_rating = {t: 0.0 for t in teams}

    for _, row in matches.sort_values("date").iterrows():
        h, a = row["home_id"], row["away_id"]
        actual_gd = float(row["home_goals"] - row["away_goals"])

        expected_gd_h = _rating_to_goal_diff(home_rating[h] - away_rating[a])
        error_h = _goal_diff_to_rating(actual_gd) - _goal_diff_to_rating(expected_gd_h)
        home_rating[h] += LEARNING_RATE * error_h
        away_rating[h] += LEARNING_RATE * CROSS_TRANSFER * error_h

        expected_gd_a = _rating_to_goal_diff(away_rating[a] - home_rating[h])
        error_a = _goal_diff_to_rating(-actual_gd) - _goal_diff_to_rating(expected_gd_a)
        away_rating[a] += LEARNING_RATE * error_a
        home_rating[a] += LEARNING_RATE * CROSS_TRANSFER * error_a

    return PiRatingsResult(home_rating=home_rating, away_rating=away_rating, n_matches=len(matches))


def predict_goal_diff(result: PiRatingsResult, home_team: str, away_team: str) -> float:
    return _rating_to_goal_diff(result.home_rating[home_team] - result.away_rating[away_team])
