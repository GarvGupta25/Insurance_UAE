from unittest.mock import patch

import pytest

from app.sources import validate_url


@pytest.mark.parametrize(
    "url",
    [
        "http://www.adnic.ae/web/guest/medical-insurance",
        "https://www.adnic.ae.evil.test/",
        "https://user:secret@www.adnic.ae/",
        "https://www.adnic.ae:444/",
        "https://127.0.0.1/",
    ],
)
def test_public_source_rejects_unapproved_urls_before_fetch(url):
    with pytest.raises(ValueError):
        validate_url(url, "www.adnic.ae")


def test_public_source_rejects_private_dns_answer():
    answer = [(2, 1, 6, "", ("127.0.0.1", 443))]
    with patch("app.sources.socket.getaddrinfo", return_value=answer):
        with pytest.raises(ValueError, match="non-public"):
            validate_url("https://www.adnic.ae/web/guest/medical-insurance", "www.adnic.ae")


def test_research_links_do_not_supply_fictional_plan_terms(fixture_client):
    client, _, _ = fixture_client
    response = client.get("/api/sources")
    assert response.status_code == 200
    result = response.json()
    assert result["items"]
    assert all(item["verification"] == "not_retrieved" for item in result["items"])
    assert all("premium" not in item for item in result["items"])


def test_provider_list_works_without_location_and_keeps_demo_provenance(fixture_client):
    client, _, _ = fixture_client
    dubai = client.get("/api/providers?plan_id=plan_b&emirate=Dubai")
    assert dubai.status_code == 200
    result = dubai.json()
    assert result["items"]
    assert all(item["mode"] == "synthetic_demo" for item in result["items"])
    assert all(item["source"] == "Synthetic provider directory v1" for item in result["items"])
    manual_fallback = client.get("/api/providers?plan_id=plan_b&emirate=Abu%20Dhabi").json()
    assert manual_fallback["items"] == []
    assert "Not a real care directory" in manual_fallback["notice"]
