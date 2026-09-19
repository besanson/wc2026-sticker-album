"""Possession-sequence RAPM player ratings (ridge regression on possession value)."""

from dataclasses import dataclass

THIN_SAMPLE_MINUTES = 900.0


@dataclass
class PlayerRating:
    player_id: object
    off_rating: float
    def_rating: float
    minutes: float
    possessions: int
    thin_sample: bool


def make_rating(player_id, off_rating: float, def_rating: float, minutes: float, possessions: int) -> PlayerRating:
    return PlayerRating(
        player_id=player_id,
        off_rating=off_rating,
        def_rating=def_rating,
        minutes=minutes,
        possessions=possessions,
        thin_sample=minutes < THIN_SAMPLE_MINUTES,
    )


def fit_rapm(possessions, lambdas=None, n_folds: int = 5):
    raise NotImplementedError("RAPM ridge-regression fit not yet implemented.")
