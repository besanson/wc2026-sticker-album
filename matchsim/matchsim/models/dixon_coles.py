"""Dixon-Coles bivariate-Poisson team model (Dixon & Coles 1997) with exponential time decay.

Reference: Dixon and Coles (1997); bivariate Poisson of Karlis and Ntzoufras (2003).
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import gammaln

DEFAULT_XI = 0.0018
HOME_ADVANTAGE_WARN_LOW = 0.25
HOME_ADVANTAGE_WARN_HIGH = 0.40


@dataclass
class DixonColesResult:
    teams: list[str]
    attack: dict[str, float]
    defence: dict[str, float]
    gamma: float
    rho: float
    mu: float
    xi: float
    as_of: pd.Timestamp
    n_matches: int
    home_advantage_goals: float


def _dc_tau(x: np.ndarray, y: np.ndarray, lam_h: np.ndarray, lam_a: np.ndarray, rho: float) -> np.ndarray:
    tau = np.ones_like(lam_h)
    m00 = (x == 0) & (y == 0)
    m10 = (x == 1) & (y == 0)
    m01 = (x == 0) & (y == 1)
    m11 = (x == 1) & (y == 1)
    tau[m00] = 1 - lam_h[m00] * lam_a[m00] * rho
    tau[m10] = 1 + lam_h[m10] * rho
    tau[m01] = 1 + lam_a[m01] * rho
    tau[m11] = 1 - rho
    return tau


def _neg_log_likelihood(theta, home_idx, away_idx, home_goals, away_goals, weights, n_teams):
    attack = theta[:n_teams]
    defence = theta[n_teams : 2 * n_teams]
    gamma = theta[2 * n_teams]
    rho = theta[2 * n_teams + 1]

    log_lam_h = attack[home_idx] + defence[away_idx] + gamma
    log_lam_a = attack[away_idx] + defence[home_idx]
    lam_h = np.exp(log_lam_h)
    lam_a = np.exp(log_lam_a)

    tau = _dc_tau(home_goals, away_goals, lam_h, lam_a, rho)
    tau = np.clip(tau, 1e-10, None)

    log_lik = (
        np.log(tau)
        + home_goals * log_lam_h
        - lam_h
        - gammaln(home_goals + 1)
        + away_goals * log_lam_a
        - lam_a
        - gammaln(away_goals + 1)
    )
    return -np.sum(weights * log_lik)


def fit(matches: pd.DataFrame, xi: float = DEFAULT_XI, as_of: pd.Timestamp | None = None) -> DixonColesResult:
    matches = matches.dropna(subset=["home_id", "away_id", "home_goals", "away_goals", "date"])
    teams = sorted(set(matches["home_id"]) | set(matches["away_id"]))
    n_teams = len(teams)
    team_idx = {t: i for i, t in enumerate(teams)}

    home_idx = matches["home_id"].map(team_idx).to_numpy()
    away_idx = matches["away_id"].map(team_idx).to_numpy()
    home_goals = matches["home_goals"].to_numpy(dtype=float)
    away_goals = matches["away_goals"].to_numpy(dtype=float)

    as_of = pd.Timestamp(as_of) if as_of is not None else matches["date"].max()
    days_ago = (as_of - matches["date"]).dt.days.to_numpy().clip(min=0)
    weights = np.exp(-xi * days_ago)

    x0 = np.concatenate([np.zeros(n_teams), np.zeros(n_teams), [0.2], [0.0]])
    bounds = [(None, None)] * (2 * n_teams) + [(None, None), (-0.9, 0.9)]

    res = minimize(
        _neg_log_likelihood,
        x0,
        args=(home_idx, away_idx, home_goals, away_goals, weights, n_teams),
        method="L-BFGS-B",
        bounds=bounds,
    )

    attack = res.x[:n_teams]
    defence = res.x[n_teams : 2 * n_teams]
    gamma = float(res.x[2 * n_teams])
    rho = float(res.x[2 * n_teams + 1])

    # sum(attack) = 0 for identifiability; (attack + t, defence - t) is an exact flat
    # direction of this likelihood, so recentring here doesn't change any fitted lambda.
    t = attack.mean()
    attack = attack - t
    defence = defence + t
    mu = float(defence.mean())

    home_advantage_goals = float(np.exp(mu + gamma) - np.exp(mu))
    if not (HOME_ADVANTAGE_WARN_LOW <= home_advantage_goals <= HOME_ADVANTAGE_WARN_HIGH):
        warnings.warn(
            f"Fitted home advantage is {home_advantage_goals:.3f} goals, outside the "
            f"expected Serie A range [{HOME_ADVANTAGE_WARN_LOW}, {HOME_ADVANTAGE_WARN_HIGH}]."
        )

    return DixonColesResult(
        teams=teams,
        attack=dict(zip(teams, attack.tolist())),
        defence=dict(zip(teams, defence.tolist())),
        gamma=gamma,
        rho=rho,
        mu=mu,
        xi=xi,
        as_of=pd.Timestamp(as_of),
        n_matches=len(matches),
        home_advantage_goals=home_advantage_goals,
    )


def predict_lambdas(result: DixonColesResult, home_team: str, away_team: str) -> tuple[float, float]:
    lam_h = np.exp(result.attack[home_team] + result.defence[away_team] + result.gamma)
    lam_a = np.exp(result.attack[away_team] + result.defence[home_team])
    return float(lam_h), float(lam_a)


def bootstrap_predict_interval(
    matches: pd.DataFrame,
    home_team: str,
    away_team: str,
    xi: float = DEFAULT_XI,
    n_draws: int = 200,
    seed: int = 0,
) -> dict[str, tuple[float, float]]:
    """Case-resampling bootstrap over historical matches: refit Dixon-Coles on
    resamples of the actual match log and report percentile intervals. Every
    draw is a resample of real observed matches, so this stays traceable to
    counts in the input data (CLAUDE.md section 1)."""
    from matchsim.sim.scoreline import scoreline_matrix, summarize

    rng = np.random.default_rng(seed)
    n = len(matches)
    p_home_draws, p_draw_draws, p_away_draws = [], [], []

    for _ in range(n_draws):
        sample = matches.iloc[rng.integers(0, n, size=n)]
        if home_team not in set(sample["home_id"]) | set(sample["away_id"]):
            continue
        if away_team not in set(sample["home_id"]) | set(sample["away_id"]):
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = fit(sample, xi=xi)
        lam_h, lam_a = predict_lambdas(result, home_team, away_team)
        matrix = scoreline_matrix(lam_h, lam_a, rho=result.rho, max_goals=8)
        summary = summarize(matrix, lam_h, lam_a)
        p_home_draws.append(summary.p_home)
        p_draw_draws.append(summary.p_draw)
        p_away_draws.append(summary.p_away)

    def interval(values):
        if not values:
            return (float("nan"), float("nan"))
        return (float(np.percentile(values, 5)), float(np.percentile(values, 95)))

    return {
        "p_home": interval(p_home_draws),
        "p_draw": interval(p_draw_draws),
        "p_away": interval(p_away_draws),
        "n_draws_used": len(p_home_draws),
    }
