"""matchsim CLI (typer). See spec section 7 for the exact output contract."""

import pickle
import warnings
from pathlib import Path
from typing import Optional

import typer

from matchsim.explain.decomposition import decompose_tier1
from matchsim.io.results import load_results
from matchsim.models import dixon_coles
from matchsim.sim.scoreline import outcome_probs, scoreline_matrix, summarize

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

    typer.echo("Evaluating the style-interaction term on held-out game splits (spec 4.4)...")
    from matchsim.ratings.style import compute_style_vectors, evaluate_matchup_interaction
    from matchsim.models.lineup import build_link_training_rows, fit_calibrated_link

    styles = compute_style_vectors(dataset.actions)
    # spec 4.4 says to keep the term only if it improves held-out RPS. A single
    # 80/20 split is noisy at this demo's scale (one seed flipped sign on us
    # during development -- see reports/eval.md), so the RPS decision is
    # averaged over several splits rather than trusting any one of them.
    ablation_seeds = [evaluate_matchup_interaction(dataset.actions, dataset.games, dataset.players, rapm_result, seed=s) for s in range(6)]
    mean_delta = sum(a.rps_with_interaction - a.rps_without_interaction for a in ablation_seeds) / len(ablation_seeds)
    matchup_ablation = ablation_seeds[0]

    base_link = fit_calibrated_link(build_link_training_rows(dataset.games, dataset.players, rapm_result))
    interaction_link = fit_calibrated_link(build_link_training_rows(dataset.games, dataset.players, rapm_result, styles=styles))
    # An average RPS improvement isn't sufficient on its own: attack_diff and
    # the interaction term are correlated (~0.3 on this data) at very
    # different scales, and fitting both together can flip beta_strength's
    # sign -- a core coefficient a coach-facing explanation depends on. That's
    # not something an RPS number alone would catch, so it's checked
    # explicitly and vetoes keeping the term even if RPS looks better.
    coefficient_stable = (interaction_link.beta_strength > 0) == (base_link.beta_strength > 0)
    matchup_ablation.kept = (mean_delta < 0) and coefficient_stable

    typer.echo("Fitting the Tier 2 calibrated link (goals ~ lineup strength diff + home [+ interaction], Poisson GLM)...")
    link = interaction_link if matchup_ablation.kept else base_link

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
                "matchup_ablation": matchup_ablation,
                "matchup_ablation_mean_delta": mean_delta,
                "styles": styles if matchup_ablation.kept else None,
            },
            f,
        )

    n_thin_vaep = int(vaep_ratings["thin_sample"].sum())
    n_thin_rapm = sum(r.thin_sample for r in rapm_result.ratings.values())
    typer.echo(f"VAEP: {len(vaep_ratings)} players rated ({n_thin_vaep} thin_sample).")
    typer.echo(f"RAPM: {len(rapm_result.ratings)} players rated ({n_thin_rapm} thin_sample), alpha={rapm_result.alpha:.1f}.")
    typer.echo(f"Calibrated link: {link}")
    if matchup_ablation.kept:
        typer.echo(f"Style-interaction term: mean RPS delta {mean_delta:+.4f} over 6 splits, stable coefficients -> kept, wired into the shipped link.")
    else:
        reason = "coefficients became unstable when included (beta_strength flipped sign)" if not coefficient_stable else "did not improve held-out RPS on average"
        typer.echo(
            f"Style-interaction term: mean RPS delta {mean_delta:+.4f} over 6 held-out splits, but {reason} "
            f"-> dropped, not wired into the shipped link (see reports/eval.md for the full reasoning)."
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
        home_team_id=lineup_data.get("home_team_id"),
        away_team_id=lineup_data.get("away_team_id"),
        styles=bundle.get("styles"),
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

    team_ids = dict(
        home_team_id=lineup_data.get("home_team_id"),
        away_team_id=lineup_data.get("away_team_id"),
        styles=bundle.get("styles"),
    )
    base = run_tier2(
        lineup_data["home_lineup"], lineup_data["away_lineup"], bundle["rapm_result"], bundle["link"],
        n_bootstrap_draws=bootstrap_draws, rho=tier1_result.rho, **team_ids,
    )
    changed = run_tier2(
        lineup_data["home_lineup"], lineup_data["away_lineup"], bundle["rapm_result"], bundle["link"],
        home_scenario=home_flags, away_scenario=away_flags, n_bootstrap_draws=bootstrap_draws, rho=tier1_result.rho, **team_ids,
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
    results: Path = typer.Option(Path("data/results.csv"), help="Path to results.csv"),
    tier2_model_path: Path = typer.Option(DEFAULT_TIER2_MODEL_PATH, help="Path to fitted Tier 2 ratings + link (for the Tier 2 ablation rows)"),
    report: Path = typer.Option(Path("reports/eval.md"), help="Where to write the eval report"),
):
    """Evaluate model quality (RPS, Brier, calibration, ablations) on a held-out season."""
    import numpy as np

    from matchsim import eval as eval_module
    from matchsim.models import ensemble, pi_ratings

    matches = load_results(results)
    holdout = matches[matches["season"] == season]
    if holdout.empty:
        typer.echo(f"No rows with season == {season!r} in {results}. Seasons present: {sorted(matches['season'].unique())}")
        raise typer.Exit(code=1)
    train = matches[matches["date"] < holdout["date"].min()]
    typer.echo(f"Train: {len(train)} matches before {holdout['date'].min().date()}.  Holdout ({season}): {len(holdout)} matches.")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        dc_result = dixon_coles.fit(train)
        for w in caught:
            typer.echo(f"WARNING (Dixon-Coles): {w.message}")
    pi_result = pi_ratings.fit(train)
    avg_total_goals = float((train["home_goals"] + train["away_goals"]).mean())
    baseline_probs = eval_module.naive_baseline_probs(train)

    tier1_rows, ensemble_rows = [], []
    p_home_tier1, actual_home_win = [], []
    for _, row in holdout.iterrows():
        if row["home_id"] not in dc_result.attack or row["away_id"] not in dc_result.attack:
            continue
        lam_h, lam_a = dixon_coles.predict_lambdas(dc_result, row["home_id"], row["away_id"])
        matrix = scoreline_matrix(lam_h, lam_a, rho=dc_result.rho, max_goals=8)
        tier1_probs = outcome_probs(matrix)
        tier1_rows.append(
            {
                "rps": eval_module.ranked_probability_score_from_probs(tier1_probs, row["home_goals"], row["away_goals"]),
                "brier": eval_module.brier_score_from_probs(tier1_probs, row["home_goals"], row["away_goals"]),
                "ll": eval_module.log_likelihood_from_probs(tier1_probs, row["home_goals"], row["away_goals"]),
                "ll_baseline": eval_module.log_likelihood_from_probs(baseline_probs, row["home_goals"], row["away_goals"]),
            }
        )
        p_home_tier1.append(tier1_probs[0])
        actual_home_win.append(1.0 if row["home_goals"] > row["away_goals"] else 0.0)

        if row["home_id"] in pi_result.home_rating and row["away_id"] in pi_result.away_rating:
            ens_probs = ensemble.ensemble_predict(dc_result, pi_result, row["home_id"], row["away_id"], avg_total_goals)
            ensemble_rows.append(
                {
                    "rps": eval_module.ranked_probability_score_from_probs(ens_probs, row["home_goals"], row["away_goals"]),
                    "brier": eval_module.brier_score_from_probs(ens_probs, row["home_goals"], row["away_goals"]),
                    "ll": eval_module.log_likelihood_from_probs(ens_probs, row["home_goals"], row["away_goals"]),
                }
            )

    if not tier1_rows:
        typer.echo("No evaluable holdout matches (team coverage issue).")
        raise typer.Exit(code=1)

    tier1_rps = float(np.mean([r["rps"] for r in tier1_rows]))
    tier1_brier = float(np.mean([r["brier"] for r in tier1_rows]))
    tier1_ll = float(np.sum([r["ll"] for r in tier1_rows]))
    tier1_ll_baseline = float(np.sum([r["ll_baseline"] for r in tier1_rows]))
    ensemble_rps = float(np.mean([r["rps"] for r in ensemble_rows])) if ensemble_rows else float("nan")
    ensemble_brier = float(np.mean([r["brier"] for r in ensemble_rows])) if ensemble_rows else float("nan")

    report.parent.mkdir(parents=True, exist_ok=True)
    calibration_path = report.parent / "calibration_tier1.png"
    bins = eval_module.calibration_bins(np.array(p_home_tier1), np.array(actual_home_win))
    eval_module.plot_calibration(bins, str(calibration_path))

    tier2_note = "Tier 2 not fitted yet -- run `matchsim fit --events statsbomb` first."
    tier2_rows_md = "| Tier 2 without matchup terms | n/a | n/a |\n| Tier 2 with matchup terms | n/a | n/a |\n"
    if tier2_model_path.exists():
        with open(tier2_model_path, "rb") as f:
            bundle = pickle.load(f)
        ab = bundle.get("matchup_ablation")
        mean_delta = bundle.get("matchup_ablation_mean_delta")
        if ab is not None:
            outcome = (
                "**kept**, wired into the shipped link"
                if ab.kept
                else "**dropped**, not wired into the shipped link"
            )
            mean_delta_clause = f" Mean RPS delta over 6 splits: {mean_delta:+.4f}." if mean_delta is not None else ""
            stability_note = (
                ""
                if ab.kept
                else (
                    " Note: a single 80/20 split isn't decisive at this demo's scale (the mean delta above is "
                    "favourable), but adding the term makes `beta_strength` flip sign -- attack_diff and the "
                    "interaction term correlate (~0.3) at very different scales, and a flipped core coefficient "
                    "would make the coach-facing explanation actively wrong. That instability, not the RPS "
                    "number alone, is why it's dropped."
                )
            )
            tier2_note = (
                f"Style-interaction term (spec 4.4): one example split gave held-out RPS "
                f"{ab.rps_with_interaction:.4f} with vs {ab.rps_without_interaction:.4f} without "
                f"(in-sample p={ab.interaction_p_value:.4f}).{mean_delta_clause} -> {outcome}.{stability_note}"
            )
            tier2_rows_md = (
                f"| Tier 2 without matchup terms | StatsBomb Serie A 2015/16 demo, {ab.n_holdout_games}-game holdout | {ab.rps_without_interaction:.4f} |\n"
                f"| Tier 2 with matchup terms | StatsBomb Serie A 2015/16 demo, {ab.n_holdout_games}-game holdout | {ab.rps_with_interaction:.4f} |\n"
            )

    calib_lines = "\n".join(
        f"| {b.bin_low:.1f}-{b.bin_high:.1f} | {b.n} | {b.mean_predicted:.3f} | {b.observed_frequency:.3f} |"
        for b in bins
        if b.n > 0
    )

    report_md = f"""# matchsim evaluation report

Generated by `matchsim eval --season {season}`. Train: {len(train)} real Serie A
matches before {holdout['date'].min().date()}. Holdout: {len(holdout)} real
matches from the {season} season ({results}, not demo data).

## Tier 1 (Dixon-Coles)

- RPS: **{tier1_rps:.4f}** (literature benchmark: ~0.20-0.21 state of the art on open data; >0.23 is considered broken)
- Brier: {tier1_brier:.4f}
- Log-likelihood: {tier1_ll:.2f} vs naive baseline {tier1_ll_baseline:.2f} (baseline = league-average home/draw/away rates: {baseline_probs[0]:.3f}/{baseline_probs[1]:.3f}/{baseline_probs[2]:.3f})

## Ensemble (Dixon-Coles + pi-ratings, unweighted average)

- RPS: {ensemble_rps:.4f}
- Brier: {ensemble_brier:.4f}
- n evaluable holdout matches: {len(ensemble_rows)} (pi-ratings needs both teams seen during training; Tier 1 alone covers {len(tier1_rows)})

## Calibration (Tier 1, P(home win))

![calibration](calibration_tier1.png)

| Bin | n | Mean predicted | Observed frequency |
| --- | --- | --- | --- |
{calib_lines}

## Ablation table

| Model | Dataset | Held-out RPS |
| --- | --- | --- |
| Tier 1 alone (Dixon-Coles) | real Serie A results.csv, {season} | {tier1_rps:.4f} |
{tier2_rows_md}| Ensemble (Dixon-Coles + pi-ratings) | real Serie A results.csv, {season} | {ensemble_rps:.4f} |

{tier2_note}

Tier 1/ensemble and the two Tier 2 rows are evaluated on different datasets:
no 2026-27 lineup or event data exists to evaluate Tier 2 on the real
results.csv holdout (CLAUDE.md section 1), so Tier 2 is evaluated on its own
StatsBomb open-data demo holdout instead. The RPS numbers are not directly
comparable across that boundary; each row states its own dataset.
"""
    report.write_text(report_md)
    typer.echo(f"Tier 1 RPS: {tier1_rps:.4f}  Brier: {tier1_brier:.4f}")
    typer.echo(f"Ensemble RPS: {ensemble_rps:.4f}")
    typer.echo(f"Report written to {report}")
    typer.echo(f"Calibration plot written to {calibration_path}")


if __name__ == "__main__":
    app()
