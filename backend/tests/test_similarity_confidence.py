from app.utils import compute_ct_confidence, token_similarity


def test_similarity_scores_close_names_high():
    score = token_similarity("ACME PLUMBING", "ACME PLUMBING LLC")
    assert score >= 97


def test_confidence_rules_match_spec():
    assert compute_ct_confidence(97, city_match=True, zip_match=False) == 0.95
    assert compute_ct_confidence(95, city_match=False, zip_match=True) == 0.9
    assert compute_ct_confidence(92, city_match=False, zip_match=False) == 0.8
    assert compute_ct_confidence(80, city_match=False, zip_match=False) < 0.8

