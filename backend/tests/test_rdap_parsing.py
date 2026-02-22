import json
from pathlib import Path

from app.services.domain_lookup import parse_rdap_created_date


def test_parse_rdap_created_date_from_fixture():
    fixture_path = Path(__file__).parent / "fixtures" / "rdap_example.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert parse_rdap_created_date(payload) == "1995-08-13"

