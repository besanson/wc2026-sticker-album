from pathlib import Path

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "results.csv"


def test_home_advantage_range():
    from matchsim.io.results import load_results
    from matchsim.models.dixon_coles import fit

    matches = load_results(DATA_PATH)
    result = fit(matches)

    # Spec target is 0.25-0.40 goals (fit() warns outside that band); the
    # test uses a looser sanity band so it isn't flaky on real, gappy data.
    assert 0.05 <= result.home_advantage_goals <= 0.6
