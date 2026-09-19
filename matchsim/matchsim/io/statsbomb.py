"""StatsBomb open-data loader (Mode B: demo and validation only). Everything this
loader returns must be labelled as demo data wherever it surfaces (CLAUDE.md)."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
import socceraction.spadl as spadl
from socceraction.data.statsbomb import StatsBombLoader

DEMO_LABEL = "StatsBomb open data (demo/validation only — not 2026-27 Serie A)"
PERIOD_2_OFFSET_SECONDS = 45 * 60


@dataclass
class StatsBombDataset:
    competition_id: int
    season_id: int
    games: pd.DataFrame
    actions: pd.DataFrame  # SPADL actions + possession_team_id, home_on_pitch, away_on_pitch
    players: pd.DataFrame  # one row per (game_id, player_id): team_id, is_starter, minutes_played
    label: str = DEMO_LABEL


def _period_relative_seconds(period_id: pd.Series, minute: pd.Series, second: pd.Series) -> pd.Series:
    raw = minute * 60 + second
    return raw.where(period_id == 1, raw - PERIOD_2_OFFSET_SECONDS)


def _encode_time(period_id, t):
    return period_id * 10000.0 + t


def _build_team_snapshots(starters: set, subs_for_team: pd.DataFrame) -> tuple[np.ndarray, list]:
    keys = [0.0]
    snapshots = [frozenset(starters)]
    current = set(starters)
    for _, row in subs_for_team.sort_values("t").iterrows():
        current = set(current)
        current.discard(row["player_out"])
        if row["player_in"] is not None:
            current.add(row["player_in"])
        keys.append(_encode_time(row["period_id"], row["t"]))
        snapshots.append(frozenset(current))
    return np.array(keys), snapshots


def _lookup_on_pitch(keys: np.ndarray, snapshots: list, period_ids: np.ndarray, times: np.ndarray) -> list:
    query = _encode_time(period_ids, times)
    idx = np.searchsorted(keys, query, side="right") - 1
    idx = np.clip(idx, 0, len(snapshots) - 1)
    return [snapshots[i] for i in idx]


def _on_pitch_columns(events: pd.DataFrame, players: pd.DataFrame, actions: pd.DataFrame, home_team_id: int, away_team_id: int) -> pd.DataFrame:
    """Starting XI + substitution timeline per team. Does not model red cards
    (a documented simplification -- a sent-off player stays marked on-pitch)."""
    starters = {
        tid: set(players.loc[(players["team_id"] == tid) & players["is_starter"], "player_id"])
        for tid in (home_team_id, away_team_id)
    }

    subs = events[events["type_name"] == "Substitution"].copy()
    subs["t"] = _period_relative_seconds(subs["period_id"], subs["minute"], subs["second"])
    subs["player_out"] = subs["player_id"]
    subs["player_in"] = subs["extra"].apply(lambda e: (e or {}).get("substitution", {}).get("replacement", {}).get("id"))

    period_ids = actions["period_id"].to_numpy()
    times = actions["time_seconds"].to_numpy()

    out = pd.DataFrame(index=actions.index)
    for side, tid in (("home", home_team_id), ("away", away_team_id)):
        keys, snapshots = _build_team_snapshots(starters[tid], subs[subs["team_id"] == tid])
        out[f"{side}_on_pitch"] = _lookup_on_pitch(keys, snapshots, period_ids, times)
    return out


def load_statsbomb(competition_id: int, season_id: int, max_games: int = 30) -> StatsBombDataset:
    """Fetch and convert a bounded, chronologically-first subset of a StatsBomb
    open-data competition/season into SPADL actions with on-pitch context.
    Demo/validation scale, not a full-season production fetch -- see CLAUDE.md
    and matchsim/README.md for why (no 2026-27 Serie A event data exists)."""
    loader = StatsBombLoader(getter="remote")
    games = loader.games(competition_id, season_id).sort_values("game_date").head(max_games).reset_index(drop=True)

    action_frames = []
    player_frames = []

    for _, game in games.iterrows():
        game_id = int(game["game_id"])
        home_team_id = int(game["home_team_id"])
        away_team_id = int(game["away_team_id"])

        events = loader.events(game_id)
        players = loader.players(game_id)
        players["game_id"] = game_id
        player_frames.append(players)

        actions = spadl.statsbomb.convert_to_actions(events, home_team_id)
        actions = spadl.add_names(actions)
        actions["game_id"] = game_id

        poss = events[["event_id", "possession", "possession_team_id"]]
        actions = actions.merge(poss, left_on="original_event_id", right_on="event_id", how="left")

        on_pitch = _on_pitch_columns(events, players, actions, home_team_id, away_team_id)
        actions = pd.concat([actions, on_pitch], axis=1)

        action_frames.append(actions)

    return StatsBombDataset(
        competition_id=competition_id,
        season_id=season_id,
        games=games,
        actions=pd.concat(action_frames, ignore_index=True),
        players=pd.concat(player_frames, ignore_index=True),
    )
