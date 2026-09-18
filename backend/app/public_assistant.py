"""
Public website assistant — /api/public/assistant/messages
==========================================================
A scoped, unauthenticated chatbot endpoint for the Helm AI marketing site.

Scope guardrail:
  - Answers ONLY general UAE health-insurance questions and site navigation.
  - Never asks for, stores, or acknowledges personal/health/financial data.
  - Never produces a quote, premium number, or eligibility decision.
  - Redirects any quote/eligibility request to the sign-up flow.
  - Uses the same Groq client setup as agents.py but is a separate call path
    and NEVER routes through the authenticated interpret() graph.

Rate limiting:
  - Simple in-memory counter: 10 requests per 60-minute rolling window per IP.
  - In-memory store (no Redis required); resets on server restart.
  - Returns HTTP 429 when limit is exceeded.
  - Choice documented: in-memory is appropriate for a demo; a production
    deployment would use Redis + e.g. slowapi.
"""

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request
from groq import Groq
from pydantic import BaseModel, field_validator

from .config import settings

# ── Rate-limit store ──────────────────────────────────────────────────────────
# { ip_address: deque of unix timestamps for requests in the rolling window }
_rate_store: dict[str, deque] = defaultdict(deque)
_rate_lock = Lock()

RATE_LIMIT_REQUESTS = 10       # max requests
RATE_LIMIT_WINDOW_SECONDS = 3600  # per 60-minute rolling window


def _check_rate_limit(ip: str) -> None:
    """Raises HTTP 429 if the IP has exceeded the rate limit."""
    now = time.monotonic()
    cutoff = now - RATE_LIMIT_WINDOW_SECONDS
    with _rate_lock:
        q = _rate_store[ip]
        # Drop timestamps outside the rolling window
        while q and q[0] < cutoff:
            q.popleft()
        if len(q) >= RATE_LIMIT_REQUESTS:
            raise HTTPException(
                status_code=429,
                detail="You've reached the message limit for now — please try again in an hour.",
            )
        q.append(now)


# ── Request / response models ─────────────────────────────────────────────────
class PublicAssistantRequest(BaseModel):
    message: str

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Message must not be empty.")
        if len(stripped) > 500:
            raise ValueError("Message must be 500 characters or fewer.")
        return stripped


class PublicAssistantResponse(BaseModel):
    reply: str


# ── System prompt ─────────────────────────────────────────────────────────────
_SYSTEM_PROMPT = (
    "You are the Helm AI website assistant. You answer general questions about UAE health "
    "insurance concepts (deductibles, co-pays, network tiers, waiting periods, who needs "
    "individual cover vs employer cover, and how the Helm AI demo product works). "
    "You do not know anything about the specific visitor. Never ask for or acknowledge "
    "personal, health, or financial information. Never generate a quote, a premium number, "
    "or an eligibility decision — if asked for one, say this requires signing in so the "
    "deterministic comparison engine can do it properly, and point to signing up. "
    "Keep answers under 80 words. If asked something outside UAE health insurance or this "
    "website, say so briefly and redirect to what you can help with."
)

_GROQ_FALLBACK = (
    "I'm having trouble answering right now — try the FAQ page or sign up to speak "
    "with the full assistant."
)


# ── Handler function (registered in main.py) ─────────────────────────────────
async def handle_public_assistant(
    body: PublicAssistantRequest, request: Request
) -> PublicAssistantResponse:
    # Derive client IP (support common proxy headers)
    forwarded_for = request.headers.get("X-Forwarded-For")
    ip = (
        forwarded_for.split(",")[0].strip()
        if forwarded_for
        else (request.client.host if request.client else "unknown")
    )

    _check_rate_limit(ip)

    cfg = settings()
    if not cfg.groq_api_key:
        return PublicAssistantResponse(reply=_GROQ_FALLBACK)

    try:
        client = Groq(api_key=cfg.groq_api_key, timeout=20, max_retries=1)
        response = client.chat.completions.create(
            model=cfg.groq_model,
            temperature=0.3,
            max_tokens=200,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": body.message},
            ],
        )
        reply = (response.choices[0].message.content or "").strip()
        if not reply:
            return PublicAssistantResponse(reply=_GROQ_FALLBACK)
        return PublicAssistantResponse(reply=reply)
    except Exception:
        return PublicAssistantResponse(reply=_GROQ_FALLBACK)
