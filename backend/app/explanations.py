"""Audience-specific prose generated from the same deterministic records."""

from typing import Literal

Audience = Literal["member", "broker"]


def servicing_explanation(event: dict, audience: Audience) -> str:
    outcome = event.get("outcome", "decision").replace("_", " ")
    if audience == "member":
        next_step = " You can ask for a review if you think information was missed." if outcome in {"denied", "declined"} else " Your updated balance is shown in your policy."
        return f"Your request was {outcome}. {event.get('calculation', ['We applied the saved policy terms.'])[0]}{next_step}"
    return f"Servicing outcome={outcome}; reason_code={event.get('reason_code')}; calculation={event.get('calculation', [])}; reviewer evidence must be retained."


def recommendation_explanation(item: dict, audience: Audience) -> str:
    if audience == "member":
        return "This option fits the details you shared: " + " ".join(item.get("reasons", []))
    return "Routing and evidence context: status=" + item.get("status", "unknown") + "; gaps=" + "; ".join(item.get("gaps", [])) + "; flags require review."
