"""Evaluation metrics: RPS, Brier score. Ablation table and calibration plot land with
the full eval report (spec section 6)."""

import numpy as np

from matchsim.sim.scoreline import outcome_probs


def _observed_outcome(home_goals: float, away_goals: float) -> int:
    if home_goals > away_goals:
        return 0
    if home_goals == away_goals:
        return 1
    return 2


def ranked_probability_score(matrix: np.ndarray, home_goals: float, away_goals: float) -> float:
    """3-class (home/draw/away) RPS, the standard ordinal metric in the football
    forecasting literature (e.g. Constantinou & Fenton)."""
    probs = outcome_probs(matrix)
    outcome = _observed_outcome(home_goals, away_goals)

    cum_p = np.cumsum(probs)
    cum_e = np.cumsum([1.0 if i == outcome else 0.0 for i in range(3)])
    return float(np.sum((cum_p[:-1] - cum_e[:-1]) ** 2) / (len(probs) - 1))


def brier_score(matrix: np.ndarray, home_goals: float, away_goals: float) -> float:
    probs = np.array(outcome_probs(matrix))
    outcome = _observed_outcome(home_goals, away_goals)
    actual = np.zeros(3)
    actual[outcome] = 1.0
    return float(np.sum((probs - actual) ** 2))
