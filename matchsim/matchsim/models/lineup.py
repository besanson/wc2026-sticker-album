"""Lineup strength to match-probability model (Tier 2). See spec section 4.3."""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import statsmodels.api as sm

from matchsim.ratings.rapm import RAPMResult, bootstrap_player_ratings


@dataclass
class ScenarioFlags:
    available: bool = True
    minutes_cap: float | None = None
    fitness_multiplier: float = 1.0


def apply_scenario_flags(player_id, scenario: dict) -> ScenarioFlags:
    """Straight pass-through of user-typed scenario flags. Never derives these from data (CLAUDE.md section 1)."""
    entry = scenario.get(player_id, {})
    return ScenarioFlags(
        available=entry.get("available", True),
        minutes_cap=entry.get("minutes_cap"),
        fitness_multiplier=entry.get("fitness_multiplier", 1.0),
    )


@dataclass
class LineupStrength:
    attack: float
    defence: float
    thin_sample_players: list = field(default_factory=list)
    unrated_players: list = field(default_factory=list)


def _player_off_def(player_id, ratings: dict) -> tuple[float, float, bool]:
    """(off_rating, def_rating, thin_sample) for one player, or a neutral
    0-rating with thin_sample=True if the player has no fitted rating at all
    -- the model never estimates a rating for a player it has no data on."""
    r = ratings.get(int(player_id))
    if r is None:
        return 0.0, 0.0, True
    return r.off_rating, r.def_rating, r.thin_sample


def build_lineup_strength(lineup: list[dict], ratings: dict, scenario: dict | None = None) -> LineupStrength:
    """lineup: list of {"player_id", "expected_minutes"} for the starting eleven
    (+ any subs the caller wants weighted in). Attack/defence are the sum of
    off/def ratings weighted by expected_minutes/90 and any scenario flags."""
    scenario = scenario or {}
    attack = defence = 0.0
    thin_players, unrated_players = [], []

    for entry in lineup:
        pid = entry["player_id"]
        flags = apply_scenario_flags(pid, scenario)
        if not flags.available:
            continue

        expected_minutes = flags.minutes_cap if flags.minutes_cap is not None else entry.get("expected_minutes", 90.0)
        off_rating, def_rating, thin = _player_off_def(pid, ratings)
        if int(pid) not in ratings:
            unrated_players.append(pid)
        if thin:
            thin_players.append(pid)

        weight = (expected_minutes / 90.0) * flags.fitness_multiplier
        attack += off_rating * weight
        defence += def_rating * weight

    return LineupStrength(attack=attack, defence=defence, thin_sample_players=thin_players, unrated_players=unrated_players)


@dataclass
class CalibratedLink:
    intercept: float
    beta_strength: float
    beta_home: float
    n_training_rows: int
    beta_interaction: float | None = None  # spec 4.4; None unless the term was validated to help

    def lambda_for(self, own_attack: float, opp_defence: float, is_home: bool, interaction: float = 0.0) -> float:
        strength_diff = own_attack - opp_defence
        log_lambda = self.intercept + self.beta_strength * strength_diff + self.beta_home * (1.0 if is_home else 0.0)
        if self.beta_interaction is not None:
            log_lambda += self.beta_interaction * interaction
        return float(np.exp(log_lambda))


def build_link_training_rows(
    games: pd.DataFrame, players: pd.DataFrame, rapm_result: RAPMResult, styles: dict | None = None
) -> pd.DataFrame:
    """One row per team-match: that team's actual goals, its lineup attack minus
    the opponent's lineup defence, and a home indicator. Lineups are each
    game's actual starting XI weighted by actual minutes_played (we know what
    happened, unlike a future fixture). If `styles` (matchsim.ratings.style
    TeamStyle per team_id) is given, also includes the directness x
    press-intensity interaction column (spec 4.4)."""
    starters = players[players["is_starter"]]
    rows = []
    for _, game in games.iterrows():
        game_id = game["game_id"]
        game_players = starters[starters["game_id"] == game_id]
        for side, team_id, opp_id, goals in (
            ("home", game["home_team_id"], game["away_team_id"], game["home_score"]),
            ("away", game["away_team_id"], game["home_team_id"], game["away_score"]),
        ):
            team_lineup = [
                {"player_id": pid, "expected_minutes": mins}
                for pid, mins in zip(
                    game_players.loc[game_players["team_id"] == team_id, "player_id"],
                    game_players.loc[game_players["team_id"] == team_id, "minutes_played"],
                )
            ]
            opp_lineup = [
                {"player_id": pid, "expected_minutes": mins}
                for pid, mins in zip(
                    game_players.loc[game_players["team_id"] == opp_id, "player_id"],
                    game_players.loc[game_players["team_id"] == opp_id, "minutes_played"],
                )
            ]
            own_strength = build_lineup_strength(team_lineup, rapm_result.ratings)
            opp_strength = build_lineup_strength(opp_lineup, rapm_result.ratings)
            row = {
                "goals": goals,
                "attack_diff": own_strength.attack - opp_strength.defence,
                "is_home": 1.0 if side == "home" else 0.0,
            }
            if styles is not None:
                ts, to = styles.get(team_id), styles.get(opp_id)
                row["interaction"] = ts.directness * to.press_intensity if ts and to else 0.0
            rows.append(row)
    return pd.DataFrame(rows)


def fit_calibrated_link(training_rows: pd.DataFrame) -> CalibratedLink:
    """Poisson GLM: goals ~ lineup strength difference + home indicator (spec
    4.3.4), plus the style-interaction term (spec 4.4) if `training_rows` has
    an "interaction" column -- callers only pass one in once it's been
    validated to improve held-out RPS (see ratings.style.evaluate_matchup_interaction)."""
    has_interaction = "interaction" in training_rows.columns
    covariates = ["attack_diff", "is_home", "interaction"] if has_interaction else ["attack_diff", "is_home"]
    X = sm.add_constant(training_rows[covariates])
    y = training_rows["goals"]
    fitted = sm.GLM(y, X, family=sm.families.Poisson()).fit()
    return CalibratedLink(
        intercept=float(fitted.params["const"]),
        beta_strength=float(fitted.params["attack_diff"]),
        beta_home=float(fitted.params["is_home"]),
        n_training_rows=len(training_rows),
        beta_interaction=float(fitted.params["interaction"]) if has_interaction else None,
    )


@dataclass
class Tier2Prediction:
    lambda_home: float
    lambda_away: float
    home_strength: LineupStrength
    away_strength: LineupStrength
    interval: dict  # {"p_home": (lo, hi), "p_draw": (lo, hi), "p_away": (lo, hi), "n_draws_used": int}


def predict_tier2(
    home_lineup: list[dict],
    away_lineup: list[dict],
    rapm_result: RAPMResult,
    link: CalibratedLink,
    home_scenario: dict | None = None,
    away_scenario: dict | None = None,
    n_bootstrap_draws: int = 200,
    rho: float = 0.0,
    home_team_id=None,
    away_team_id=None,
    styles: dict | None = None,
) -> Tier2Prediction:
    """rho: the low-score correlation term. Tier 2 doesn't refit its own -- spec
    4.3.5 says to feed the two lambdas into the same scoreline machinery as
    Tier 1, "including rho", so callers should pass in the Tier 1 fitted rho.

    home_team_id/away_team_id/styles: only needed if `link` has a validated
    interaction term (link.beta_interaction is not None) -- looks up each
    side's style vector (spec 4.4) to compute it. Without them the
    interaction term is treated as 0, same as a link that never had one."""
    from matchsim.sim.scoreline import scoreline_matrix, summarize

    home_strength = build_lineup_strength(home_lineup, rapm_result.ratings, home_scenario)
    away_strength = build_lineup_strength(away_lineup, rapm_result.ratings, away_scenario)

    home_style = styles.get(home_team_id) if styles and home_team_id is not None else None
    away_style = styles.get(away_team_id) if styles and away_team_id is not None else None
    home_interaction = home_style.directness * away_style.press_intensity if home_style and away_style else 0.0
    away_interaction = away_style.directness * home_style.press_intensity if home_style and away_style else 0.0

    lambda_home = link.lambda_for(home_strength.attack, away_strength.defence, is_home=True, interaction=home_interaction)
    lambda_away = link.lambda_for(away_strength.attack, home_strength.defence, is_home=False, interaction=away_interaction)

    p_home_draws, p_draw_draws, p_away_draws = [], [], []
    for draw_ratings in bootstrap_player_ratings(rapm_result, n_draws=n_bootstrap_draws):
        ratings_view = {pid: _RatingView(*vals) for pid, vals in draw_ratings.items()}
        hs = build_lineup_strength(home_lineup, ratings_view, home_scenario)
        aws = build_lineup_strength(away_lineup, ratings_view, away_scenario)
        lh = link.lambda_for(hs.attack, aws.defence, is_home=True, interaction=home_interaction)
        la = link.lambda_for(aws.attack, hs.defence, is_home=False, interaction=away_interaction)
        matrix = scoreline_matrix(lh, la, rho=rho, max_goals=8)
        summary = summarize(matrix, lh, la)
        p_home_draws.append(summary.p_home)
        p_draw_draws.append(summary.p_draw)
        p_away_draws.append(summary.p_away)

    def interval(values):
        return (float(np.percentile(values, 5)), float(np.percentile(values, 95)))

    return Tier2Prediction(
        lambda_home=lambda_home,
        lambda_away=lambda_away,
        home_strength=home_strength,
        away_strength=away_strength,
        interval={
            "p_home": interval(p_home_draws),
            "p_draw": interval(p_draw_draws),
            "p_away": interval(p_away_draws),
            "n_draws_used": len(p_home_draws),
        },
    )


@dataclass
class _RatingView:
    off_rating: float
    def_rating: float
    thin_sample: bool = False
