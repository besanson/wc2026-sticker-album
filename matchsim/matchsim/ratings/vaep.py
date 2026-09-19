"""VAEP-style action values via socceraction (Decroos et al. 2019). Uses
socceraction's own SPADL/feature/label/formula machinery -- does not
reimplement the method, per spec section 4.2."""

from dataclasses import dataclass

import pandas as pd
import socceraction.spadl as spadl
import socceraction.vaep.features as fs
import socceraction.vaep.formula as fm
import socceraction.vaep.labels as lab
from lightgbm import LGBMClassifier

from matchsim.ratings.rapm import THIN_SAMPLE_MINUTES

NB_PREV_ACTIONS = 3

# socceraction's gamestates()/play_left_to_right() shift() and fillna() every
# column of what's passed in; matchsim's extra columns (on_pitch frozensets,
# possession ids) don't survive that, so strip back to plain SPADL first.
SPADL_COLUMNS = [
    "game_id", "original_event_id", "action_id", "period_id", "time_seconds", "team_id", "player_id",
    "start_x", "start_y", "end_x", "end_y", "bodypart_id", "bodypart_name", "type_id", "type_name",
    "result_id", "result_name",
]

FEATURE_FNS = [
    fs.simple(fs.actiontype_onehot),
    fs.simple(fs.result_onehot),
    fs.simple(fs.bodypart_onehot),
    fs.simple(fs.startlocation),
    fs.simple(fs.endlocation),
    fs.simple(fs.movement),
    fs.simple(fs.time),
    fs.space_delta,
    fs.goalscore,
    fs.time_delta,
]


@dataclass
class VAEPModel:
    scores_model: LGBMClassifier
    concedes_model: LGBMClassifier
    feature_columns: list[str]


def _game_features_and_labels(actions: pd.DataFrame, home_team_id: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """One game's worth of actions -> (features, scores label, concedes label).
    Must run per game: gamestates/labels assume one continuous action sequence."""
    actions = actions[SPADL_COLUMNS]
    normalized = spadl.play_left_to_right(actions, home_team_id)
    gamestates = fs.gamestates(normalized, NB_PREV_ACTIONS)
    features = pd.concat([f(gamestates) for f in FEATURE_FNS], axis=1)
    y_scores = lab.scores(actions, nr_actions=10)
    y_concedes = lab.concedes(actions, nr_actions=10)
    return features.reset_index(drop=True), y_scores.reset_index(drop=True), y_concedes.reset_index(drop=True)


def fit_vaep(actions: pd.DataFrame, games: pd.DataFrame) -> VAEPModel:
    """actions: SPADL actions for many games, with a game_id column. games:
    must have game_id, home_team_id."""
    home_by_game = dict(zip(games["game_id"], games["home_team_id"]))

    feature_frames, score_frames, concede_frames = [], [], []
    for game_id, group in actions.groupby("game_id", sort=False):
        if game_id not in home_by_game:
            continue
        feats, y_scores, y_concedes = _game_features_and_labels(group.reset_index(drop=True), home_by_game[game_id])
        feature_frames.append(feats)
        score_frames.append(y_scores)
        concede_frames.append(y_concedes)

    X = pd.concat(feature_frames, ignore_index=True).fillna(0)
    y_scores = pd.concat(score_frames, ignore_index=True)["scores"]
    y_concedes = pd.concat(concede_frames, ignore_index=True)["concedes"]

    scores_model = LGBMClassifier(n_estimators=100, max_depth=4, verbose=-1)
    scores_model.fit(X, y_scores)
    concedes_model = LGBMClassifier(n_estimators=100, max_depth=4, verbose=-1)
    concedes_model.fit(X, y_concedes)

    return VAEPModel(scores_model=scores_model, concedes_model=concedes_model, feature_columns=list(X.columns))


def rate_actions(model: VAEPModel, actions: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """Per-action VAEP values (offensive_value, defensive_value, vaep_value),
    aligned back onto `actions` (adds player_id, team_id, game_id)."""
    home_by_game = dict(zip(games["game_id"], games["home_team_id"]))

    value_frames = []
    for game_id, group in actions.groupby("game_id", sort=False):
        if game_id not in home_by_game:
            continue
        group = group.reset_index(drop=True)
        feats, _, _ = _game_features_and_labels(group, home_by_game[game_id])
        X = feats.reindex(columns=model.feature_columns, fill_value=0)
        p_scores = model.scores_model.predict_proba(X)[:, 1]
        p_concedes = model.concedes_model.predict_proba(X)[:, 1]
        values = fm.value(group, pd.Series(p_scores), pd.Series(p_concedes))
        values = pd.concat(
            [group[["game_id", "player_id", "team_id"]].reset_index(drop=True), values.reset_index(drop=True)], axis=1
        )
        value_frames.append(values)

    return pd.concat(value_frames, ignore_index=True)


def aggregate_player_vaep(action_values: pd.DataFrame, players: pd.DataFrame) -> pd.DataFrame:
    """Per-player-per-90 VAEP ratings. `players` must have player_id, minutes_played
    (one row per game the player appeared in)."""
    # SPADL actions store player_id as float64 (NaN-safe upcast); players() keeps
    # int64. Align dtypes or the groupby/join below silently matches nothing.
    action_values = action_values.assign(player_id=action_values["player_id"].astype("int64"))
    players = players.assign(player_id=players["player_id"].astype("int64"))

    minutes = players.groupby("player_id")["minutes_played"].sum().rename("minutes")

    per_player = action_values.groupby("player_id").agg(
        vaep_off_total=("offensive_value", "sum"),
        vaep_def_total=("defensive_value", "sum"),
    )
    out = per_player.join(minutes, how="left").fillna({"minutes": 0.0})
    ninety_min_multiples = (out["minutes"] / 90.0).replace(0, pd.NA)
    out["vaep_off_p90"] = (out["vaep_off_total"] / ninety_min_multiples).astype(float).fillna(0.0)
    out["vaep_def_p90"] = (out["vaep_def_total"] / ninety_min_multiples).astype(float).fillna(0.0)
    out["thin_sample"] = out["minutes"] < THIN_SAMPLE_MINUTES
    return out[["minutes", "vaep_off_p90", "vaep_def_p90", "thin_sample"]].reset_index()
