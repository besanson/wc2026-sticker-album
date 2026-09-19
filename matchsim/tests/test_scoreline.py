import numpy as np


def test_scoreline_matrix_sums_to_one():
    from matchsim.sim.scoreline import scoreline_matrix

    matrix = scoreline_matrix(lambda_home=1.4, lambda_away=1.1, rho=-0.1, max_goals=8)

    assert matrix.shape == (9, 9)
    assert np.all(matrix >= 0)
    assert np.isclose(matrix.sum(), 1.0, atol=1e-6)
