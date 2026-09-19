def test_rapm_thin_sample_flag():
    from matchsim.ratings.rapm import make_rating

    thin = make_rating("player_thin", off_rating=0.01, def_rating=-0.01, minutes=300, possessions=40)
    thick = make_rating("player_thick", off_rating=0.02, def_rating=-0.02, minutes=1200, possessions=180)

    assert thin.thin_sample is True
    assert thick.thin_sample is False
