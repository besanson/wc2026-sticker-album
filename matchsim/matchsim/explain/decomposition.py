"""Decompose Tier 1 predicted expected goals into coach-readable, exactly-summing components."""

from dataclasses import dataclass

import numpy as np

from matchsim.models.dixon_coles import DixonColesResult


@dataclass
class Tier1Decomposition:
    home_components: dict[str, float]
    away_components: dict[str, float]


def decompose_tier1(result: DixonColesResult, home_team: str, away_team: str) -> Tier1Decomposition:
    """Waterfall in goal units: base rate -> home advantage -> attack -> defence.
    Each step is an exp() delta along one fitted term, so the steps telescope
    exactly to lambda_home / lambda_away (see test_explanation_decomposes_to_lambda)."""
    mu = result.mu
    gamma = result.gamma
    attack_home = result.attack[home_team]
    attack_away = result.attack[away_team]
    defence_home_centered = result.defence[home_team] - mu
    defence_away_centered = result.defence[away_team] - mu

    lam0 = np.exp(mu)
    lam1 = np.exp(mu + gamma)
    lam2_home = np.exp(mu + gamma + attack_home)
    lam3_home = np.exp(mu + gamma + attack_home + defence_away_centered)

    home_components = {
        "base_rate": float(lam0),
        "home_advantage": float(lam1 - lam0),
        "attack_difference": float(lam2_home - lam1),
        "defence_difference": float(lam3_home - lam2_home),
    }

    lam1_away = np.exp(mu + attack_away)
    lam2_away = np.exp(mu + attack_away + defence_home_centered)

    away_components = {
        "base_rate": float(lam0),
        "attack_difference": float(lam1_away - lam0),
        "defence_difference": float(lam2_away - lam1_away),
    }

    return Tier1Decomposition(home_components=home_components, away_components=away_components)
