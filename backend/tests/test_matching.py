from app.matching import best_fuzzy_match, levenshtein, normalize


def test_normalize_basics():
    assert normalize("The Godfather") == "godfather"
    assert normalize("  A   Beautiful   Mind ") == "beautiful mind"
    # Punctuation becomes a separator, so the middle dot yields two tokens.
    assert normalize("WALL·E!") == "wall e"
    assert normalize("Café Society") == "cafe society"
    assert normalize("Law & Order") == "law and order"


def test_normalize_strips_single_leading_article():
    assert normalize("An American Tail") == "american tail"
    # Only one leading article is stripped.
    assert normalize("The A-Team") == "a team"


def test_levenshtein():
    assert levenshtein("kitten", "sitting") == 3
    assert levenshtein("abc", "abc") == 0
    assert levenshtein("interstellar", "intersteller", 1) == 1


def test_fuzzy_match_accepts_close_typo():
    candidates = {"interstellar": "e1", "inception": "e2"}
    assert best_fuzzy_match("intersteller", candidates, 1) == "e1"


def test_fuzzy_match_rejects_far_input():
    candidates = {"interstellar": "e1"}
    assert best_fuzzy_match("gladiator", candidates, 1) is None


def test_fuzzy_match_short_strings_require_exact():
    candidates = {"it": "e1", "up": "e2"}
    # 'if' is distance 1 from 'it' but too short to fuzzy-match.
    assert best_fuzzy_match("if", candidates, 1) is None
    assert best_fuzzy_match("up", candidates, 1) == "e2"
