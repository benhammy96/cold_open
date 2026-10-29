from app.config import get_settings
from app.scoring import prior_weight, rarity_share, score_answer, tier_for_share

S = get_settings()


def test_prior_weight_decays_and_floors():
    assert prior_weight(0, S) == 200
    assert prior_weight(50, S) == 150
    assert prior_weight(1000, S) == 20  # floored


def test_rarity_share_returns_prior_at_cold_start():
    # total=0 -> blend equals prior_share exactly.
    assert rarity_share(0.25, 0, 0, S) == 0.25
    assert rarity_share(0.001, 0, 0, S) == 0.001


def test_rarity_share_moves_toward_observed():
    # With lots of data the observed fraction dominates.
    prior = 0.20
    observed = 10
    total = 1000
    share = rarity_share(prior, observed, total, S)
    # observed fraction is 0.01; weight floored at 20, so blend is close to 0.01.
    assert 0.009 < share < 0.02


def test_tier_boundaries():
    # Popcorn: >= 20%
    assert tier_for_share(0.50).name == "Popcorn"
    assert tier_for_share(0.20).name == "Popcorn"
    # Matinee: 10-20%
    assert tier_for_share(0.19).name == "Matinee"
    assert tier_for_share(0.10).name == "Matinee"
    # Marquee: 5-10%
    assert tier_for_share(0.09).name == "Marquee"
    assert tier_for_share(0.05).name == "Marquee"
    # Cult Classic: 1-5%
    assert tier_for_share(0.049).name == "Cult Classic"
    assert tier_for_share(0.01).name == "Cult Classic"
    # Deep Cut: 0.1-1%
    assert tier_for_share(0.009).name == "Deep Cut"
    assert tier_for_share(0.001).name == "Deep Cut"
    # Lost Reel: < 0.1%
    assert tier_for_share(0.0009).name == "Lost Reel"


def test_points_match_tiers():
    assert tier_for_share(0.50).points == 10
    assert tier_for_share(0.15).points == 25
    assert tier_for_share(0.07).points == 40
    assert tier_for_share(0.03).points == 60
    assert tier_for_share(0.005).points == 80
    assert tier_for_share(0.0001).points == 100


def test_never_submitted_is_lost_reel():
    r = score_answer(prior_share=0.0, observed_count=0, total_submissions=0, settings=S)
    assert r.name == "Lost Reel"
    assert r.points == 100


def test_common_prior_scores_popcorn_at_cold_start():
    r = score_answer(prior_share=0.25, observed_count=0, total_submissions=0, settings=S)
    assert r.name == "Popcorn"
    assert r.points == 10


def test_deep_cut_prior_scores_high_at_cold_start():
    r = score_answer(prior_share=0.004, observed_count=0, total_submissions=0, settings=S)
    assert r.name == "Deep Cut"
    assert r.points == 80
