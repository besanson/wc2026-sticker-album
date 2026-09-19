"""Evaluation metrics: RPS, Brier score, log-likelihood vs a naive baseline,
and calibration binning (spec section 6)."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from matchsim.sim.scoreline import outcome_probs


def observed_outcome(home_goals: float, away_goals: float) -> int:
    if home_goals > away_goals:
        return 0
    if home_goals == away_goals:
        return 1
    return 2


def ranked_probability_score_from_probs(probs, home_goals: float, away_goals: float) -> float:
    """3-class (home/draw/away) RPS, the standard ordinal metric in the football
    forecasting literature (e.g. Constantinou & Fenton)."""
    outcome = observed_outcome(home_goals, away_goals)
    cum_p = np.cumsum(probs)
    cum_e = np.cumsum([1.0 if i == outcome else 0.0 for i in range(3)])
    return float(np.sum((cum_p[:-1] - cum_e[:-1]) ** 2) / (len(probs) - 1))


def brier_score_from_probs(probs, home_goals: float, away_goals: float) -> float:
    probs = np.asarray(probs)
    outcome = observed_outcome(home_goals, away_goals)
    actual = np.zeros(3)
    actual[outcome] = 1.0
    return float(np.sum((probs - actual) ** 2))


def log_likelihood_from_probs(probs, home_goals: float, away_goals: float, floor: float = 1e-10) -> float:
    outcome = observed_outcome(home_goals, away_goals)
    return float(np.log(max(probs[outcome], floor)))


def ranked_probability_score(matrix: np.ndarray, home_goals: float, away_goals: float) -> float:
    return ranked_probability_score_from_probs(outcome_probs(matrix), home_goals, away_goals)


def brier_score(matrix: np.ndarray, home_goals: float, away_goals: float) -> float:
    return brier_score_from_probs(outcome_probs(matrix), home_goals, away_goals)


def naive_baseline_probs(train_matches: pd.DataFrame) -> tuple[float, float, float]:
    """League-average home/draw/away rates -- a bookmaker-free baseline."""
    outcomes = [observed_outcome(h, a) for h, a in zip(train_matches["home_goals"], train_matches["away_goals"])]
    counts = np.bincount(outcomes, minlength=3)
    return tuple((counts / counts.sum()).tolist())


@dataclass
class CalibrationBin:
    bin_low: float
    bin_high: float
    n: int
    mean_predicted: float
    observed_frequency: float


def calibration_bins(predicted_p_home: np.ndarray, actual_home_win: np.ndarray, n_bins: int = 10) -> list[CalibrationBin]:
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    bin_idx = np.clip(np.digitize(predicted_p_home, edges[1:-1]), 0, n_bins - 1)
    bins = []
    for i in range(n_bins):
        mask = bin_idx == i
        n = int(mask.sum())
        bins.append(
            CalibrationBin(
                bin_low=float(edges[i]),
                bin_high=float(edges[i + 1]),
                n=n,
                mean_predicted=float(predicted_p_home[mask].mean()) if n else float("nan"),
                observed_frequency=float(actual_home_win[mask].mean()) if n else float("nan"),
            )
        )
    return bins


def plot_calibration(bins: list[CalibrationBin], path: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    valid = [b for b in bins if b.n > 0]
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot([0, 1], [0, 1], linestyle="--", color="grey", label="perfect calibration")
    ax.scatter([b.mean_predicted for b in valid], [b.observed_frequency for b in valid], color="C0")
    for b in valid:
        ax.annotate(str(b.n), (b.mean_predicted, b.observed_frequency), fontsize=7, xytext=(3, 3), textcoords="offset points")
    ax.set_xlabel("Predicted P(home win)")
    ax.set_ylabel("Observed frequency")
    ax.set_title("Calibration: predicted vs observed P(home)")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
