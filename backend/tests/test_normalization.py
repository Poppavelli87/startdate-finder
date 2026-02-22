from app.utils import normalize_business_name


def test_normalize_business_name_removes_suffixes_and_punctuation():
    assert normalize_business_name("Acme Plumbing, LLC.") == "ACME PLUMBING"
    assert normalize_business_name("North-Star Incorporated") == "NORTHSTAR"
    assert normalize_business_name("   Beta   Co   ") == "BETA"

