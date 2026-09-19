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

# StatsBomb open data has no 2026-27 Serie A (or any current) event data (CLAUDE.md:
# "Do not assume it exists"). Serie A 2015/16 is the closest same-league demo/validation
# set StatsBomb's open data actually publishes -- always labelled as demo, never as
# current ratings.
STATSBOMB_DEMO_COMPETITION_ID = 12
STATSBOMB_DEMO_SEASON_ID = 27


@app.command()
def fit(
    results: Path = typer.Option(Path("data/results.csv"), help="Path to results.csv"),
    events: Optional[str] = typer.Option(None, help="Event-data source for Tier 2, e.g. 'statsbomb'."),
    max_games: int = typer.Option(150, help="Cap on games fetched for --events statsbomb (demo/validation scale)"),
    out: Path = typer.Option(Path("models/"), help="Directory to write fitted model artifacts"),
    xi: float = typer.Option(dixon_coles.DEFAULT_XI, help="Time-decay rate for match weighting"),
):
    """Fit Tier 1 (Dixon-Coles) on results.csv, and optionally the Tier 2 VAEP/RAPM
    player-rating pipeline on StatsBomb open data (demo/validation only -- see
    CLAUDE.md). Saves fitted artifacts to --out."""
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

    if events == "statsbomb":
        _fit_statsbomb_ratings(out, max_games)
    elif events:
        typer.echo(f"Note: --events {events!r} is not a recognised source; only 'statsbomb' is implemented.")


def _fit_statsbomb_ratings(out: Path, max_games: int) -> None:
    from matchsim.io.statsbomb import DEMO_LABEL, load_statsbomb
    from matchsim.ratings import vaep as vaep_module
    from matchsim.ratings.rapm import fit_rapm

    typer.echo(f"\n{DEMO_LABEL}")
    typer.echo(f"Fetching {max_games} games (Serie A 2015/16 -- the closest same-league StatsBomb open-data season; there is no 2026-27 event data).")
    with warnings.catch_warnings():
        # noisy pandas-deprecation warnings from inside socceraction's own loader
        # internals (fired once per game fetched), not from matchsim -- not this
        # codebase's bug to fix.
        warnings.simplefilter("ignore")
        dataset = load_statsbomb(STATSBOMB_DEMO_COMPETITION_ID, STATSBOMB_DEMO_SEASON_ID, max_games=max_games)
    typer.echo(f"Loaded {len(dataset.games)} games, {len(dataset.actions)} actions.")

    typer.echo("Fitting VAEP (socceraction + LightGBM)...")
    vaep_model = vaep_module.fit_vaep(dataset.actions, dataset.games)
    action_values = vaep_module.rate_actions(vaep_model, dataset.actions, dataset.games)
    vaep_ratings = vaep_module.aggregate_player_vaep(action_values, dataset.players)

    typer.echo("Fitting RAPM (possession-level ridge regression, 5-fold CV)...")
    rapm_result = fit_rapm(dataset.actions, dataset.players, dataset.games)

    typer.echo("Fitting the Tier 2 calibrated link (goals ~ lineup strength diff + home, Poisson GLM)...")
    from matchsim.models.lineup import build_link_training_rows, fit_calibrated_link

    training_rows = build_link_training_rows(dataset.games, dataset.players, rapm_result)
    link = fit_calibrated_link(training_rows)

    out.mkdir(parents=True, exist_ok=True)
    ratings_path = out / "tier2_ratings.pkl"
    with open(ratings_path, "wb") as f:
        pickle.dump(
            {
                "label": DEMO_LABEL,
                "competition_id": STATSBOMB_DEMO_COMPETITION_ID,
                "season_id": STATSBOMB_DEMO_SEASON_ID,
                "vaep_ratings": vaep_ratings,
                "rapm_result": rapm_result,
                "link": link,
            },
            f,
        )

    n_thin_vaep = int(vaep_ratings["thin_sample"].sum())
    n_thin_rapm = sum(r.thin_sample for r in rapm_result.ratings.values())
    typer.echo(f"VAEP: {len(vaep_ratings)} players rated ({n_thin_vaep} thin_sample).")
    typer.echo(f"RAPM: {len(rapm_result.ratings)} players rated ({n_thin_rapm} thin_sample), alpha={rapm_result.alpha:.1f}.")
    typer.echo(f"Calibrated link: {link}")
    typer.echo(
        "Note: a style-interaction term (directness x press intensity) was tested and dropped -- it looked "
        "significant in-sample (p=0.005) but worsened held-out RPS (0.274 vs 0.251 without it) on this "
        "150-game demo slice. See reports/ for the ablation writeup."
    )
    typer.echo(f"Saved to {ratings_path}")


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


DEFAULT_TIER2_MODEL_PATH = Path("models/tier2_ratings.pkl")


def _load_lineup_file(path: Path) -> dict:
    import json

    with open(path) as f:
        data = json.load(f)
    for side in ("home_lineup", "away_lineup"):
        for entry in data[side]:
            entry["player_id"] = int(entry["player_id"])
    return data


def _print_top_contributors(team_name: str, lineup: list[dict], ratings: dict) -> None:
    rows = []
    for entry in lineup:
        pid = entry["player_id"]
        r = ratings.get(pid)
        name = entry.get("name", pid)
        if r is None:
            rows.append((name, 0.0, 0.0, 0.0, 0, True))
        else:
            rows.append((name, r.off_rating, r.def_rating, r.minutes, r.possessions, r.thin_sample))
    rows.sort(key=lambda r: abs(r[1]) + abs(r[2]), reverse=True)
    typer.echo(f"  Top {team_name} contributors (RAPM off/def rating, minutes, sample flag):")
    for name, off_r, def_r, minutes, possessions, thin in rows[:5]:
        flag = "  [THIN SAMPLE]" if thin else ""
        typer.echo(f"    {str(name):26s} off {off_r:+.4f}  def {def_r:+.4f}  minutes {minutes:.0f}{flag}")


def _predict_tier2(home: str, away: str, date: str, lineups: Optional[Path], results: Path, model_path: Path, tier2_model_path: Path, bootstrap_draws: int) -> None:
    if lineups is None:
        typer.echo("Tier 2 needs --lineups (the two starting elevens).")
        typer.echo(
            "\nThere is no lineup file for the actual Udinese vs Cagliari fixture, and there could not "
            "be one that Tier 2 could use meaningfully yet: no 2026-27 Serie A event data exists to rate "
            "either squad's current players from (CLAUDE.md section 1 -- 'FBref advanced data has been "
            "unavailable since Opta pulled the feed'). Tier 2's machinery is real and validated on "
            "StatsBomb open data instead -- see examples/ for a worked demo fixture, e.g.:\n"
            "  matchsim predict --home \"Hellas Verona\" --away \"AS Roma\" --date 2015-08-22 --tier 2 "
            "--lineups examples/demo_lineup_statsbomb_serieA_2015_16.json"
        )
        raise typer.Exit(code=1)
    if not tier2_model_path.exists():
        typer.echo(f"No fitted Tier 2 ratings at {tier2_model_path}. Run: matchsim fit --events statsbomb")
        raise typer.Exit(code=1)

    with open(tier2_model_path, "rb") as f:
        bundle = pickle.load(f)
    lineup_data = _load_lineup_file(lineups)
    tier1_result = _load_or_fit_tier1(results, model_path, dixon_coles.DEFAULT_XI)

    from matchsim.models.lineup import predict_tier2 as run_tier2

    pred = run_tier2(
        lineup_data["home_lineup"],
        lineup_data["away_lineup"],
        bundle["rapm_result"],
        bundle["link"],
        n_bootstrap_draws=bootstrap_draws,
        rho=tier1_result.rho,
    )
    matrix = scoreline_matrix(pred.lambda_home, pred.lambda_away, rho=tier1_result.rho, max_goals=8)
    summary = summarize(matrix, pred.lambda_home, pred.lambda_away)

    home_name = lineup_data.get("home_team", home)
    away_name = lineup_data.get("away_team", away)
    typer.echo(f"\n{home_name} vs {away_name} — {date} (Tier 2: lineup model)")
    typer.echo("=" * 64)
    typer.echo(bundle["label"])
    typer.echo(f"P(home) = {summary.p_home:.1%}   P(draw) = {summary.p_draw:.1%}   P(away) = {summary.p_away:.1%}")
    typer.echo(f"Most likely score: {home_name} {summary.most_likely_score[0]}-{summary.most_likely_score[1]} {away_name}")
    typer.echo(f"Expected goals: {home_name} {pred.lambda_home:.2f}  –  {pred.lambda_away:.2f} {away_name}")

    iv = pred.interval
    typer.echo(f"90% interval ({iv['n_draws_used']} possession-resampling RAPM refits):")
    typer.echo(
        f"  P(home) [{iv['p_home'][0]:.1%}, {iv['p_home'][1]:.1%}]   "
        f"P(draw) [{iv['p_draw'][0]:.1%}, {iv['p_draw'][1]:.1%}]   "
        f"P(away) [{iv['p_away'][0]:.1%}, {iv['p_away'][1]:.1%}]"
    )

    typer.echo("\nExplanation (lineup strength, RAPM off/def units, weighted by expected minutes):")
    typer.echo(f"  {home_name}: attack {pred.home_strength.attack:+.4f}  defence {pred.home_strength.defence:+.4f}")
    typer.echo(f"  {away_name}: attack {pred.away_strength.attack:+.4f}  defence {pred.away_strength.defence:+.4f}")
    _print_top_contributors(home_name, lineup_data["home_lineup"], bundle["rapm_result"].ratings)
    _print_top_contributors(away_name, lineup_data["away_lineup"], bundle["rapm_result"].ratings)
    if pred.home_strength.unrated_players or pred.away_strength.unrated_players:
        typer.echo(
            "  Unrated players (no fitted RAPM rating; treated as thin_sample, rating 0): "
            f"{pred.home_strength.unrated_players + pred.away_strength.unrated_players}"
        )

    typer.echo("\nData provenance:")
    typer.echo(f"  Ratings + link: {bundle['label']} (competition_id={bundle['competition_id']}, season_id={bundle['season_id']})")
    typer.echo(f"  Lineup file: {lineups}")


@app.command()
def predict(
    home: str = typer.Option(..., help="Home team name, verbatim as in results.csv"),
    away: str = typer.Option(..., help="Away team name, verbatim as in results.csv"),
    date: str = typer.Option(..., help="Fixture date, YYYY-MM-DD"),
    tier: int = typer.Option(1, help="1 = Dixon-Coles team level, 2 = lineup/player level"),
    results: Path = typer.Option(Path("data/results.csv"), help="Path to results.csv"),
    lineups: Optional[Path] = typer.Option(None, help="Lineup JSON file (required for --tier 2)"),
    model_path: Path = typer.Option(DEFAULT_MODEL_PATH, help="Path to a fitted Tier 1 model"),
    tier2_model_path: Path = typer.Option(DEFAULT_TIER2_MODEL_PATH, help="Path to fitted Tier 2 ratings + link"),
    bootstrap_draws: int = typer.Option(200, help="Case-resampling bootstrap draws for the 90% interval"),
):
    """Predict a fixture."""
    if tier == 2:
        _predict_tier2(home, away, date, lineups, results, model_path, tier2_model_path, bootstrap_draws)
        return
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
    results: Path = typer.Option(Path("data/results.csv"), help="Path to results.csv"),
    model_path: Path = typer.Option(DEFAULT_MODEL_PATH, help="Path to a fitted Tier 1 model"),
    tier2_model_path: Path = typer.Option(DEFAULT_TIER2_MODEL_PATH, help="Path to fitted Tier 2 ratings + link"),
    bootstrap_draws: int = typer.Option(200, help="Bootstrap draws for base and scenario predictions"),
):
    """Print the delta versus the base prediction for a what-if lineup scenario.

    Scenario YAML: `lineups: <path to a lineup JSON>`, plus `home_flags` /
    `away_flags` mapping player_id -> {available, minutes_cap,
    fitness_multiplier} -- user-typed only, never inferred (CLAUDE.md)."""
    import yaml

    if not tier2_model_path.exists():
        typer.echo(f"No fitted Tier 2 ratings at {tier2_model_path}. Run: matchsim fit --events statsbomb")
        raise typer.Exit(code=1)

    with open(scenario) as f:
        scenario_spec = yaml.safe_load(f)
    lineup_data = _load_lineup_file(Path(scenario_spec["lineups"]))
    home_flags = {int(k): v for k, v in (scenario_spec.get("home_flags") or {}).items()}
    away_flags = {int(k): v for k, v in (scenario_spec.get("away_flags") or {}).items()}

    with open(tier2_model_path, "rb") as f:
        bundle = pickle.load(f)
    tier1_result = _load_or_fit_tier1(results, model_path, dixon_coles.DEFAULT_XI)

    from matchsim.models.lineup import predict_tier2 as run_tier2

    base = run_tier2(
        lineup_data["home_lineup"], lineup_data["away_lineup"], bundle["rapm_result"], bundle["link"],
        n_bootstrap_draws=bootstrap_draws, rho=tier1_result.rho,
    )
    changed = run_tier2(
        lineup_data["home_lineup"], lineup_data["away_lineup"], bundle["rapm_result"], bundle["link"],
        home_scenario=home_flags, away_scenario=away_flags, n_bootstrap_draws=bootstrap_draws, rho=tier1_result.rho,
    )

    base_summary = summarize(scoreline_matrix(base.lambda_home, base.lambda_away, rho=tier1_result.rho), base.lambda_home, base.lambda_away)
    changed_summary = summarize(scoreline_matrix(changed.lambda_home, changed.lambda_away, rho=tier1_result.rho), changed.lambda_home, changed.lambda_away)

    home_name = lineup_data.get("home_team", "home")
    away_name = lineup_data.get("away_team", "away")
    typer.echo(f"\nWhat-if: {scenario}  ({home_name} vs {away_name})")
    typer.echo("=" * 64)
    typer.echo(f"Base:     P(home) {base_summary.p_home:.1%}  P(draw) {base_summary.p_draw:.1%}  P(away) {base_summary.p_away:.1%}   xG {base.lambda_home:.2f}-{base.lambda_away:.2f}")
    typer.echo(f"Scenario: P(home) {changed_summary.p_home:.1%}  P(draw) {changed_summary.p_draw:.1%}  P(away) {changed_summary.p_away:.1%}   xG {changed.lambda_home:.2f}-{changed.lambda_away:.2f}")
    typer.echo(
        f"Delta:    P(home) {changed_summary.p_home - base_summary.p_home:+.1%}  "
        f"P(draw) {changed_summary.p_draw - base_summary.p_draw:+.1%}  "
        f"P(away) {changed_summary.p_away - base_summary.p_away:+.1%}"
    )

    named_players = sorted(set(home_flags) | set(away_flags))
    lookup = {**{e["player_id"]: e.get("name", e["player_id"]) for e in lineup_data["home_lineup"]}, **{e["player_id"]: e.get("name", e["player_id"]) for e in lineup_data["away_lineup"]}}
    typer.echo("\nPlayers named in this scenario:")
    for pid in named_players:
        typer.echo(f"  {lookup.get(pid, pid)}: {scenario_spec.get('home_flags', {}).get(str(pid)) or scenario_spec.get('away_flags', {}).get(str(pid))}")


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
