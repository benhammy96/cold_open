import math

from app.priors import EntityFame, derive_prior_shares, fame_score


def test_fame_score_monotonic():
    assert fame_score(100, 10000) > fame_score(10, 1000)
    assert fame_score(50, 0) > fame_score(0, 0)


def test_empty_and_single():
    assert derive_prior_shares([]) == {}
    one = derive_prior_shares([EntityFame("a", 50, 5000)])
    assert list(one.keys()) == ["a"]
    # Single entity would be 1.0 but the 40% cap clamps it (no receivers -> stays).
    assert one["a"] == 1.0 or one["a"] <= 0.401


def test_shares_sum_to_one():
    ents = [
        EntityFame("a", 100, 30000),
        EntityFame("b", 60, 15000),
        EntityFame("c", 20, 5000),
        EntityFame("d", 5, 500),
        EntityFame("e", 1, 50),
    ]
    shares = derive_prior_shares(ents)
    assert math.isclose(sum(shares.values()), 1.0, abs_tol=1e-6)


def test_more_famous_gets_higher_share():
    ents = [
        EntityFame("famous", 100, 30000),
        EntityFame("mid", 30, 8000),
        EntityFame("deep", 2, 100),
    ]
    # Uncapped, ordering is strict by fame.
    u = derive_prior_shares(ents, max_single_share=1.0)
    assert u["famous"] > u["mid"] > u["deep"]
    # With the 40% cap, top answers may saturate and tie, but order never inverts.
    s = derive_prior_shares(ents)
    assert s["famous"] >= s["mid"] >= s["deep"]
    assert s["famous"] <= 0.40 + 1e-6


def test_single_share_cap_enforced():
    # One wildly dominant entity among weak ones; cap should hold.
    ents = [
        EntityFame("blockbuster", 500, 100000),
        EntityFame("a", 1, 10),
        EntityFame("b", 1, 10),
        EntityFame("c", 1, 10),
    ]
    s = derive_prior_shares(ents, max_single_share=0.40)
    assert s["blockbuster"] <= 0.40 + 1e-6
    assert math.isclose(sum(s.values()), 1.0, abs_tol=1e-6)


def test_gamma_concentrates_distribution():
    ents = [
        EntityFame("a", 100, 30000),
        EntityFame("b", 10, 2000),
        EntityFame("c", 1, 100),
    ]
    gentle = derive_prior_shares(ents, gamma=1.0, max_single_share=1.0)
    steep = derive_prior_shares(ents, gamma=4.0, max_single_share=1.0)
    # Higher gamma -> the famous answer takes a larger share.
    assert steep["a"] > gentle["a"]


def test_all_equal_fame_is_uniform():
    ents = [EntityFame("a", 50, 5000), EntityFame("b", 50, 5000), EntityFame("c", 50, 5000)]
    s = derive_prior_shares(ents)
    assert math.isclose(s["a"], 1 / 3, abs_tol=1e-6)
    assert math.isclose(s["b"], 1 / 3, abs_tol=1e-6)


def test_deep_cut_lands_in_rare_band():
    # A large set where the tail should reach Deep-Cut / Lost-Reel territory.
    ents = [EntityFame(f"e{i}", popularity=max(1, 120 - i * 2), vote_count=max(10, 30000 - i * 500)) for i in range(50)]
    shares = derive_prior_shares(ents)
    tail = min(shares.values())
    assert tail < 0.01  # at least one answer is Deep Cut or rarer
