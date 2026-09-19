"""Shared Dixon-Coles / bivariate-Poisson scoreline machinery (Dixon & Coles 1997)."""

from dataclasses import dataclass

import numpy as np
from scipy.stats import poisson


def _dc_tau(x: int, y: int, lambda_home: float, lambda_away: float, rho: float) -> float:
    if x == 0 and y == 0:
        return 1 - lambda_home * lambda_away * rho
    if x == 1 and y == 0:
        return 1 + lambda_home * rho
    if x == 0 and y == 1:
        return 1 + lambda_away * rho
    if x == 1 and y == 1:
        return 1 - rho
    return 1.0


def scoreline_matrix(lambda_home: float, lambda_away: float, rho: float = 0.0, max_goals: int = 8) -> np.ndarray:
    """P(home scores i, away scores j) for i, j in [0, max_goals], low-score adjusted and renormalized."""
    home_pmf = poisson.pmf(np.arange(max_goals + 1), lambda_home)
    away_pmf = poisson.pmf(np.arange(max_goals + 1), lambda_away)
    matrix = np.outer(home_pmf, away_pmf)

    for x in (0, 1):
        for y in (0, 1):
            matrix[x, y] *= _dc_tau(x, y, lambda_home, lambda_away, rho)

    matrix = np.clip(matrix, 0, None)
    matrix /= matrix.sum()
    return matrix


@dataclass
class ScorelineSummary:
    p_home: float
    p_draw: float
    p_away: float
    most_likely_score: tuple[int, int]
    xg_home: float
    xg_away: float


def summarize(matrix: np.ndarray, lambda_home: float, lambda_away: float) -> ScorelineSummary:
    n = matrix.shape[0]
    rows, cols = np.indices((n, n))
    p_home = float(matrix[rows > cols].sum())
    p_draw = float(matrix[rows == cols].sum())
    p_away = float(matrix[rows < cols].sum())
    flat_idx = int(np.argmax(matrix))
    most_likely = (flat_idx // n, flat_idx % n)
    return ScorelineSummary(
        p_home=p_home,
        p_draw=p_draw,
        p_away=p_away,
        most_likely_score=most_likely,
        xg_home=lambda_home,
        xg_away=lambda_away,
    )


def outcome_probs(matrix: np.ndarray) -> tuple[float, float, float]:
    n = matrix.shape[0]
    rows, cols = np.indices((n, n))
    return (
        float(matrix[rows > cols].sum()),
        float(matrix[rows == cols].sum()),
        float(matrix[rows < cols].sum()),
    )
