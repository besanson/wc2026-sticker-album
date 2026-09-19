"""Combine Tier 1's two variants (Dixon-Coles + pi-ratings) into an ensemble.
Pi-ratings gives a predicted goal difference, not a scoreline distribution, so
it's turned into one by splitting a league-average total-goals figure (from
the same training data) around that predicted difference, then run through
the same Poisson scoreline machinery as Dixon-Coles."""

import numpy as np

from matchsim.models import dixon_coles, pi_ratings
from matchsim.sim.scoreline import outcome_probs, scoreline_matrix


def pi_ratings_outcome_probs(
    pi_result: pi_ratings.PiRatingsResult,
    home_team: str,
    away_team: str,
    avg_total_goals: float,
    max_goals: int = 8,
) -> tuple[float, float, float]:
    gd = pi_ratings.predict_goal_diff(pi_result, home_team, away_team)
    lambda_home = max((avg_total_goals + gd) / 2, 0.05)
    lambda_away = max((avg_total_goals - gd) / 2, 0.05)
    matrix = scoreline_matrix(lambda_home, lambda_away, rho=0.0, max_goals=max_goals)
    return outcome_probs(matrix)


def ensemble_predict(
    dc_result: dixon_coles.DixonColesResult,
    pi_result: pi_ratings.PiRatingsResult,
    home_team: str,
    away_team: str,
    avg_total_goals: float,
    weight_dc: float = 0.5,
) -> tuple[float, float, float]:
    """Simple weighted average of Dixon-Coles' and pi-ratings' outcome
    probabilities -- weight_dc=0.5 is an unweighted average, the natural
    default for two models with no track record yet to weight by."""
    lam_h, lam_a = dixon_coles.predict_lambdas(dc_result, home_team, away_team)
    dc_probs = outcome_probs(scoreline_matrix(lam_h, lam_a, rho=dc_result.rho, max_goals=8))
    pi_probs = pi_ratings_outcome_probs(pi_result, home_team, away_team, avg_total_goals)
    return tuple(weight_dc * d + (1 - weight_dc) * p for d, p in zip(dc_probs, pi_probs))
