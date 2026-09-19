import numpy as np
import pandas as pd


def _simulate_matches(n_teams=18, n_matches=2000, seed=0):
    rng = np.random.default_rng(seed)
    teams = [f"Team{i}" for i in range(n_teams)]

    raw_attack = rng.normal(0, 0.3, n_teams)
    raw_attack -= raw_attack.mean()
    true_attack = dict(zip(teams, raw_attack))
    true_defence = dict(zip(teams, rng.normal(0, 0.3, n_teams)))
    true_gamma = 0.3
    true_mu = 0.15

    rows = []
    for i in range(n_matches):
        home, away = rng.choice(teams, size=2, replace=False)
        lam_home = np.exp(true_mu + true_attack[home] + true_defence[away] + true_gamma)
        lam_away = np.exp(true_mu + true_attack[away] + true_defence[home])
        rows.append(
            {
                "match_id": i,
                "date": pd.Timestamp("2024-01-01") + pd.Timedelta(days=i % 300),
                "home_id": str(home),
                "away_id": str(away),
                "home_goals": rng.poisson(lam_home),
                "away_goals": rng.poisson(lam_away),
                "comp": "Test",
                "season": "2024-test",
            }
        )
    matches = pd.DataFrame(rows)
    true_params = {"attack": true_attack, "defence": true_defence, "gamma": true_gamma, "mu": true_mu}
    return matches, true_params


def test_dixon_coles_recovers_params():
    from matchsim.models.dixon_coles import fit

    matches, true_params = _simulate_matches()
    result = fit(matches, xi=0.0)  # no time decay: recency shouldn't matter for synthetic recovery

    teams = list(true_params["attack"])
    fitted_attack = np.array([result.attack[t] for t in teams])
    true_attack = np.array([true_params["attack"][t] for t in teams])
    fitted_defence = np.array([result.defence[t] for t in teams])
    true_defence = np.array([true_params["defence"][t] for t in teams])

    assert np.corrcoef(fitted_attack, true_attack)[0, 1] > 0.85
    assert np.corrcoef(fitted_defence, true_defence)[0, 1] > 0.85
    assert abs(result.gamma - true_params["gamma"]) < 0.15
    assert abs(result.mu - true_params["mu"]) < 0.2
    assert abs(sum(result.attack.values())) < 1e-6
