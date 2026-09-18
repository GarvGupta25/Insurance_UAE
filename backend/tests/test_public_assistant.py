"""
Tests for POST /api/public/assistant/messages
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.public_assistant import _rate_store


@pytest.fixture(autouse=True)
def clear_rate_store():
    """Ensure rate-limit store is clean between tests."""
    _rate_store.clear()
    yield
    _rate_store.clear()


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=True)


# ── 1. Normal question gets a reply under ~80 words ───────────────────────────
def test_normal_question_returns_reply(client: TestClient):
    mock_reply = (
        "Individual health insurance in the UAE is mandatory for residents who are "
        "not covered by an employer scheme. If you are self-sponsored, you must arrange "
        "your own policy to comply with visa and residency requirements. "
        "Helm AI can help you compare the three available demo plans."
    )
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content=mock_reply))]

    with patch("app.public_assistant.Groq") as MockGroq:
        MockGroq.return_value.chat.completions.create.return_value = mock_response
        resp = client.post(
            "/api/public/assistant/messages",
            json={"message": "Do I need insurance if I'm self-sponsored?"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "reply" in data
    assert len(data["reply"].split()) <= 100  # ~80 words with some tolerance


# ── 2. Quote request redirects to sign-up, never a fabricated number ──────────
def test_quote_request_redirects_not_fabricated(client: TestClient):
    redirect_reply = (
        "To get an actual quote or eligibility decision, you need to sign in so Helm "
        "AI's comparison engine can evaluate your specific situation. Visit the sign-up "
        "page to get started."
    )
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content=redirect_reply))]

    with patch("app.public_assistant.Groq") as MockGroq:
        MockGroq.return_value.chat.completions.create.return_value = mock_response
        resp = client.post(
            "/api/public/assistant/messages",
            json={"message": "Give me a quote for a 35-year-old non-smoker."},
        )

    assert resp.status_code == 200
    data = resp.json()
    # Reply should mention sign-in/sign-up, never contain a bare AED number like "AED 5,400"
    reply_lower = data["reply"].lower()
    assert any(word in reply_lower for word in ["sign", "log in", "engine", "comparison"])
    # Should not contain a fabricated AED premium number (e.g. "5,400" or "AED 5400")
    import re
    assert not re.search(r"aed\s*[\d,]+", reply_lower)


# ── 3. 11th request within an hour from the same IP gets 429 ─────────────────
def test_rate_limit_429_on_11th_request(client: TestClient):
    mock_reply = "A waiting period is a timeframe after your policy starts during which certain benefits are not yet available."
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content=mock_reply))]

    with patch("app.public_assistant.Groq") as MockGroq:
        MockGroq.return_value.chat.completions.create.return_value = mock_response
        for i in range(10):
            resp = client.post(
                "/api/public/assistant/messages",
                json={"message": f"What is a deductible? (request {i})"},
                headers={"X-Forwarded-For": "10.0.0.42"},
            )
            assert resp.status_code == 200, f"Request {i + 1} should succeed"

        # 11th request must be rejected
        resp = client.post(
            "/api/public/assistant/messages",
            json={"message": "What is a deductible? (11th)"},
            headers={"X-Forwarded-For": "10.0.0.42"},
        )
    assert resp.status_code == 429


# ── 4a. Empty message gets 422 ────────────────────────────────────────────────
def test_empty_message_gets_422(client: TestClient):
    resp = client.post(
        "/api/public/assistant/messages",
        json={"message": ""},
    )
    assert resp.status_code == 422


# ── 4b. Message over 500 characters gets 422 ─────────────────────────────────
def test_too_long_message_gets_422(client: TestClient):
    long_message = "x" * 501
    resp = client.post(
        "/api/public/assistant/messages",
        json={"message": long_message},
    )
    assert resp.status_code == 422


# ── 4c. Whitespace-only message gets 422 ─────────────────────────────────────
def test_whitespace_only_message_gets_422(client: TestClient):
    resp = client.post(
        "/api/public/assistant/messages",
        json={"message": "   "},
    )
    assert resp.status_code == 422


# ── 5. Groq unavailable returns graceful fallback ─────────────────────────────
def test_groq_failure_returns_graceful_fallback(client: TestClient):
    with patch("app.public_assistant.Groq") as MockGroq:
        MockGroq.return_value.chat.completions.create.side_effect = Exception("Groq timeout")
        resp = client.post(
            "/api/public/assistant/messages",
            json={"message": "What is a co-pay?"},
        )
    assert resp.status_code == 200
    assert "try" in resp.json()["reply"].lower() or "FAQ" in resp.json()["reply"]


# ── 6. Different IPs have independent rate-limit buckets ─────────────────────
def test_different_ips_have_independent_limits(client: TestClient):
    mock_reply = "A deductible is the amount you pay before insurance kicks in."
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content=mock_reply))]

    with patch("app.public_assistant.Groq") as MockGroq:
        MockGroq.return_value.chat.completions.create.return_value = mock_response
        for i in range(10):
            client.post(
                "/api/public/assistant/messages",
                json={"message": f"question {i}"},
                headers={"X-Forwarded-For": "10.0.0.99"},
            )
        # A completely different IP should still succeed
        resp = client.post(
            "/api/public/assistant/messages",
            json={"message": "What is a network tier?"},
            headers={"X-Forwarded-For": "10.0.0.100"},
        )
    assert resp.status_code == 200
