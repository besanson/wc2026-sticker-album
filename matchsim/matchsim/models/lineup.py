"""Lineup strength to match-probability model (Tier 2)."""

from dataclasses import dataclass


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


def build_lineup_strength(*args, **kwargs):
    raise NotImplementedError("Lineup-strength-to-lambda link not yet implemented.")
