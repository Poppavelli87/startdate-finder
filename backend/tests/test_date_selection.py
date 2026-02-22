from app.schemas import JobSettings
from app.services.selection import choose_start_date


def test_selection_prefers_ct_when_confident():
    settings = JobSettings(high_confidence_threshold=0.85)
    ct = {
        "registration_date": "2010-01-10",
        "confidence": 0.95,
        "query_notes": "",
    }
    domain = {"domain_created_date": "2015-01-01", "source": "domain_rdap", "lookup_notes": ""}
    social = {"social_created_hint_date": "", "social_lookup_notes": "", "confidence": 0.0}
    result = choose_start_date(ct, domain, social, settings)
    assert result["chosen_source"] == "ct_registry"
    assert result["chosen_start_date"] == "2010-01-10"


def test_selection_falls_back_to_domain_when_ct_low_confidence():
    settings = JobSettings(high_confidence_threshold=0.90)
    ct = {
        "registration_date": "2010-01-10",
        "confidence": 0.80,
        "query_notes": "",
    }
    domain = {"domain_created_date": "2012-03-04", "source": "domain_rdap", "lookup_notes": ""}
    social = {"social_created_hint_date": "", "social_lookup_notes": "", "confidence": 0.0}
    result = choose_start_date(ct, domain, social, settings)
    assert result["chosen_source"] == "domain_rdap"
    assert result["chosen_start_date"] == "2012-03-04"


def test_selection_prefer_earliest_known_date():
    settings = JobSettings(prefer_earliest_known_date=True)
    ct = {
        "registration_date": "2017-01-10",
        "confidence": 0.95,
        "query_notes": "",
    }
    domain = {"domain_created_date": "2014-03-04", "source": "domain_rdap", "lookup_notes": ""}
    social = {"social_created_hint_date": "2016-02-01", "social_lookup_notes": "", "confidence": 0.6}
    result = choose_start_date(ct, domain, social, settings)
    assert result["chosen_source"] == "domain_rdap"
    assert result["chosen_start_date"] == "2014-03-04"

