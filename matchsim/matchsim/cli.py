"""matchsim CLI (typer). See spec section 7 for the exact output contract."""

import pickle
import warnings
from pathlib import Path
from typing import Optional

import typer

from matchsim.explain.decomposition import decompose_tier1
from matchsim.io.results import load_results
from matchsim.models import dixon_coles
from matchsim.sim.scoreline import scoreline_matrix, summarize

app = typer.Typer(help="Tiered Udinese vs Cagliari match simulator.")

DEFAULT_MODEL_PATH = Path("models/dixon_coles.pkl")


@app.command()
def fit(
    results: Path = typer.Option(Path("data/results.csv"), help="Path to results.csv"),
    events: Optional[str] = typer.Option(
        None, help="Event-data source for Tier 2 (e.g. 'statsbomb'). Not implemented yet."
    ),
    out: Path = typer.Option(Path("models/"), help="Directory to write fitted model artifacts"),
    xi: float = typer.Option(dixon_coles.DEFAULT_XI, help="Time-decay rate for match weighting"),
):
    """Fit Tier 1 (Dixon-Coles) on results.csv and save it to --out."""
    if events:
        typer.echo(f"Note: --events {events!r} (Tier 2 data pipeline) is not implemented yet; fitting Tier 1 only.")

    matches = load_results(results)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = dixon_coles.fit(matches, xi=xi)
        for w in caught:
            typer.echo(f"WARNING: {w.message}")

    out.mkdir(parents=True, exist_ok=True)
    model_path = out / "dixon_coles.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(result, f)

    typer.echo(f"Fitted Dixon-Coles on {result.n_matches} matches ({len(result.teams)} teams).")
    typer.echo(f"Home advantage: {result.home_advantage_goals:.3f} goals.  rho: {result.rho:.3f}")
    typer.echo(f"Saved to {model_path}")


def _load_or_fit_tier1(results: Path, model_path: Path, xi: float) -> dixon_coles.DixonColesResult:
    if model_path.exists():
        with open(model_path, "rb") as f:
            return pickle.load(f)
    typer.echo(f"No fitted model at {model_path}; fitting Tier 1 from {results} now.\n")
    matches = load_results(results)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = dixon_coles.fit(matches, xi=xi)
        for w in caught:
            typer.echo(f"WARNING: {w.message}")
    return result


@app.command()
def predict(
    home: str = typer.Option(..., help="Home team name, verbatim as in results.csv"),
    away: str = typer.Option(..., help="Away team name, verbatim as in results.csv"),
    date: str = typer.Option(..., help="Fixture date, YYYY-MM-DD"),
    tier: int = typer.Option(1, help="1 = Dixon-Coles team level, 2 = lineup/player level"),
    results: Path = typer.Option(Path("data/results.csv"), help="Path to results.csv"),
    lineups: Optional[Path] = typer.Option(None, help="Lineup scenario file (required for --tier 2)"),
    model_path: Path = typer.Option(DEFAULT_MODEL_PATH, help="Path to a fitted Tier 1 model"),
    bootstrap_draws: int = typer.Option(200, help="Case-resampling bootstrap draws for the 90% interval"),
):
    """Predict a fixture."""
    if tier == 2:
        typer.echo("Tier 2 (player-level lineup model) is not implemented yet. Use --tier 1.")
        raise typer.Exit(code=1)
    if tier != 1:
        typer.echo(f"Unknown tier {tier}; use 1 or 2.")
        raise typer.Exit(code=1)

    result = _load_or_fit_tier1(results, model_path, dixon_coles.DEFAULT_XI)

    if home not in result.attack:
        typer.echo(f"Unknown home team {home!r}. Known teams:\n  " + "\n  ".join(result.teams))
        raise typer.Exit(code=1)
    if away not in result.attack:
        typer.echo(f"Unknown away team {away!r}. Known teams:\n  " + "\n  ".join(result.teams))
        raise typer.Exit(code=1)

    lam_h, lam_a = dixon_coles.predict_lambdas(result, home, away)
    matrix = scoreline_matrix(lam_h, lam_a, rho=result.rho, max_goals=8)
    summary = summarize(matrix, lam_h, lam_a)

    typer.echo(f"\n{home} vs {away} — {date} (Tier 1: Dixon-Coles)")
    typer.echo("=" * 64)
    typer.echo(f"P(home) = {summary.p_home:.1%}   P(draw) = {summary.p_draw:.1%}   P(away) = {summary.p_away:.1%}")
    typer.echo(f"Most likely score: {home} {summary.most_likely_score[0]}-{summary.most_likely_score[1]} {away}")
    typer.echo(f"Expected goals: {home} {lam_h:.2f}  –  {lam_a:.2f} {away}")

    if bootstrap_draws > 0:
        matches = load_results(results)
        interval = dixon_coles.bootstrap_predict_interval(matches, home, away, n_draws=bootstrap_draws)
        ph_lo, ph_hi = interval["p_home"]
        pd_lo, pd_hi = interval["p_draw"]
        pa_lo, pa_hi = interval["p_away"]
        typer.echo(
            f"90% interval ({interval['n_draws_used']} case-resampling draws over the match log):"
        )
        typer.echo(f"  P(home) [{ph_lo:.1%}, {ph_hi:.1%}]   P(draw) [{pd_lo:.1%}, {pd_hi:.1%}]   P(away) [{pa_lo:.1%}, {pa_hi:.1%}]")

    typer.echo("\nExplanation (expected goals, decomposed — each line traces to a fitted count):")
    decomposition = decompose_tier1(result, home, away)
    typer.echo(f"  {home} (home):")
    for label, value in decomposition.home_components.items():
        typer.echo(f"    {label:20s} {value:+.3f}")
    typer.echo(f"    {'TOTAL':20s} {sum(decomposition.home_components.values()):.3f}")
    typer.echo(f"  {away} (away):")
    for label, value in decomposition.away_components.items():
        typer.echo(f"    {label:20s} {value:+.3f}")
    typer.echo(f"    {'TOTAL':20s} {sum(decomposition.away_components.values()):.3f}")

    typer.echo("\nData provenance:")
    typer.echo(f"  Source: {results} — {result.n_matches} real Serie A results (not demo data).")
    typer.echo(f"  Fitted as of {result.as_of.date()}, time-decay xi={result.xi}.")
    typer.echo("  Known gaps: see data/README.md (2024-25 and 2025-26 each missing some matches).")


@app.command()
def whatif(
    scenario: Path = typer.Option(..., help="Path to a what-if scenario YAML file"),
):
    """Print the delta versus the base prediction for a what-if lineup scenario."""
    typer.echo("whatif requires the Tier 2 lineup model, which is not implemented yet.")
    raise typer.Exit(code=1)


@app.command(name="eval")
def eval_cmd(
    season: str = typer.Option(..., help="Held-out season, e.g. 2025-26"),
    report: Path = typer.Option(Path("reports/eval.md"), help="Where to write the eval report"),
):
    """Evaluate model quality (RPS, Brier, calibration, ablations) on a held-out season."""
    typer.echo("The full eval report (calibration plot + ablation table) is not implemented yet.")
    raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
