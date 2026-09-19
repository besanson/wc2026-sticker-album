"""Loader for the Mode A results.csv (results only, works today). See spec section 2."""

from pathlib import Path

import pandas as pd

CANONICAL_COLUMNS = ["match_id", "date", "home_id", "away_id", "home_goals", "away_goals", "comp", "season"]


def load_results(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df["match_id"] = df.index
    df = df.rename(columns={"home": "home_id", "away": "away_id", "competition": "comp"})
    return df[CANONICAL_COLUMNS]
