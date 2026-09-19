from pathlib import Path

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "results.csv"


def test_explanation_decomposes_to_lambda():
    from matchsim.explain.decomposition import decompose_tier1
    from matchsim.io.results import load_results
    from matchsim.models.dixon_coles import fit, predict_lambdas

    matches = load_results(DATA_PATH)
    result = fit(matches)

    home, away = "Udinese Calcio", "Cagliari Calcio"
    lam_h, lam_a = predict_lambdas(result, home, away)
    decomposition = decompose_tier1(result, home, away)

    assert round(sum(decomposition.home_components.values()), 3) == round(lam_h, 3)
    assert round(sum(decomposition.away_components.values()), 3) == round(lam_a, 3)
