import pytest

from app.database import Database
from app.services.domain_lookup import DomainLookupService
from app.services.http_client import RetryHttpClient
from app.utils import extract_registrable_domain


def test_extract_registrable_domain():
    assert extract_registrable_domain("https://www.blog.acmeplumbing.com/about") == "acmeplumbing.com"
    assert extract_registrable_domain("acme.org") == "acme.org"
    assert extract_registrable_domain("") == ""


@pytest.mark.asyncio
async def test_denylisted_domain_skips_lookup(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    http = RetryHttpClient()
    service = DomainLookupService(db, http, test_mode=True)
    try:
        result = await service.lookup_from_url(
            "https://www.yelp.com/biz/acme",
            denylist_domains=["yelp.com"],
            enable_rdap_lookup=True,
            enable_whois_fallback=True,
        )
    finally:
        await http.close()
    assert result["domain"] == "yelp.com"
    assert result["domain_created_date"] == ""
    assert result["lookup_notes"] == "domain_on_denylist"

