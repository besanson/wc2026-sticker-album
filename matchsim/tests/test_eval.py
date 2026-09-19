from pathlib import Path

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "results.csv"


def test_rps_on_holdout_below_0_23():
    from matchsim.eval import ranked_probability_score
    from matchsim.io.results import load_results
    from matchsim.models.dixon_coles import fit, predict_lambdas
    from matchsim.sim.scoreline import scoreline_matrix

    matches = load_results(DATA_PATH)

    cutoff = matches["date"].quantile(0.85)
    train = matches[matches["date"] <= cutoff]
    holdout = matches[matches["date"] > cutoff]
    assert len(holdout) > 20, "holdout split too small to be meaningful"

    result = fit(train)

    rps_values = []
    for _, row in holdout.iterrows():
        if row["home_id"] not in result.attack or row["away_id"] not in result.attack:
            continue
        lam_h, lam_a = predict_lambdas(result, row["home_id"], row["away_id"])
        matrix = scoreline_matrix(lam_h, lam_a, rho=result.rho, max_goals=8)
        rps_values.append(ranked_probability_score(matrix, row["home_goals"], row["away_goals"]))

    assert rps_values, "no evaluable holdout matches (team coverage issue)"
    avg_rps = sum(rps_values) / len(rps_values)
    assert avg_rps < 0.23
