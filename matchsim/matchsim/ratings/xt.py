"""Expected Threat (xT): a Markov value-iteration model of possession value by
pitch zone (Singh 2018 methodology), fit fresh from the loaded action data on
each run -- not a copied grid, so every cell traces back to counts in the
input data (CLAUDE.md section 1)."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

PITCH_LENGTH = 105.0
PITCH_WIDTH = 68.0
MOVE_TYPES = {"pass", "dribble", "cross", "take_on"}


@dataclass
class XTGrid:
    values: np.ndarray  # shape (n_y, n_x)
    n_x: int
    n_y: int

    def zone(self, x: float, y: float) -> tuple[int, int]:
        xi = int(np.clip(x / PITCH_LENGTH * self.n_x, 0, self.n_x - 1))
        yi = int(np.clip(y / PITCH_WIDTH * self.n_y, 0, self.n_y - 1))
        return xi, yi

    def value(self, x: float, y: float) -> float:
        xi, yi = self.zone(x, y)
        return float(self.values[yi, xi])


def _zone_indices(x: pd.Series, y: pd.Series, n_x: int, n_y: int) -> tuple[np.ndarray, np.ndarray]:
    xi = np.clip((x.to_numpy() / PITCH_LENGTH * n_x).astype(int), 0, n_x - 1)
    yi = np.clip((y.to_numpy() / PITCH_WIDTH * n_y).astype(int), 0, n_y - 1)
    return xi, yi


def fit_xt_grid(actions: pd.DataFrame, n_x: int = 16, n_y: int = 12, n_iterations: int = 10) -> XTGrid:
    """actions needs start_x, start_y, end_x, end_y, type_name, result_name (SPADL, named)."""
    n_cells = n_x * n_y

    start_xi, start_yi = _zone_indices(actions["start_x"], actions["start_y"], n_x, n_y)
    start_cell = start_yi * n_x + start_xi

    move_mask = actions["type_name"].isin(MOVE_TYPES) & (actions["result_name"] == "success")
    shot_mask = actions["type_name"] == "shot"

    n_actions_per_cell = np.bincount(start_cell[move_mask | shot_mask], minlength=n_cells).astype(float)
    n_shots_per_cell = np.bincount(start_cell[shot_mask], minlength=n_cells).astype(float)
    n_goals_per_cell = np.bincount(
        start_cell[shot_mask & (actions["result_name"] == "success").to_numpy()], minlength=n_cells
    ).astype(float)
    n_moves_per_cell = np.bincount(start_cell[move_mask], minlength=n_cells).astype(float)

    shot_prob = np.divide(n_shots_per_cell, n_actions_per_cell, out=np.zeros(n_cells), where=n_actions_per_cell > 0)
    move_prob = np.divide(n_moves_per_cell, n_actions_per_cell, out=np.zeros(n_cells), where=n_actions_per_cell > 0)
    goal_prob = np.divide(n_goals_per_cell, n_shots_per_cell, out=np.zeros(n_cells), where=n_shots_per_cell > 0)

    end_xi, end_yi = _zone_indices(actions.loc[move_mask, "end_x"], actions.loc[move_mask, "end_y"], n_x, n_y)
    end_cell = end_yi * n_x + end_xi
    transition_counts = np.zeros((n_cells, n_cells))
    np.add.at(transition_counts, (start_cell[move_mask.to_numpy()], end_cell), 1)
    row_sums = transition_counts.sum(axis=1, keepdims=True)
    transition_matrix = np.divide(transition_counts, row_sums, out=np.zeros_like(transition_counts), where=row_sums > 0)

    values = np.zeros(n_cells)
    for _ in range(n_iterations):
        values = shot_prob * goal_prob + move_prob * (transition_matrix @ values)

    return XTGrid(values=values.reshape(n_y, n_x), n_x=n_x, n_y=n_y)


def action_xt_delta(row: pd.Series, grid: XTGrid) -> float:
    """Per-action possession-value delta: reaching a goal is worth 1, a missed
    shot or lost ball forfeits the starting zone's value, a successful
    pass/carry/dribble is worth the zone-to-zone value gained."""
    start_v = grid.value(row["start_x"], row["start_y"])
    if row["type_name"] == "shot":
        return (1.0 if row["result_name"] == "success" else 0.0) - start_v
    if row["type_name"] in MOVE_TYPES and row["result_name"] == "success":
        return grid.value(row["end_x"], row["end_y"]) - start_v
    return -start_v
