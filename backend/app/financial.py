"""Explainable planning over the supplied fictional catalogue, never an insurer price."""

from decimal import ROUND_HALF_UP, Decimal

from .domain import money


def _aed(fils: int) -> str:
    return f"AED {Decimal(fils) / 100:,.2f}"


def financial_scenario(quote: dict, *, monthly_budget_aed: int, outpatient_spend_aed: int,
                       contribution_aed: int, priority: str) -> dict:
    """Model one year of eligible in-network general outpatient bills.

    Deductible and copay are applied once to the aggregate illustration. Real claims,
    service-level limits and insurer adjudication are intentionally outside this model.
    """
    budget_fils = money(monthly_budget_aed) * 12
    spend_fils = money(outpatient_spend_aed)
    contribution_fils = money(contribution_aed)
    rows = []
    for item in quote["items"]:
        plan = item["plan"]
        premium = item["premium_fils"]
        member_premium = max(0, premium - contribution_fils)
        deductible = money(plan["deductible"])
        copay = plan["outpatient_copay_pct"]
        after_deductible = max(0, spend_fils - deductible)
        illustrative_copay = int(
            (Decimal(after_deductible) * Decimal(copay) / 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        )
        illustrative_member_care = min(spend_fils, deductible) + illustrative_copay
        annual_planning_total = member_premium + illustrative_member_care
        rows.append({
            "plan_id": plan["id"],
            "name": plan["name"],
            "fit_status": item["status"],
            "premium_fils": premium,
            "member_premium_fils": member_premium,
            "monthly_budget_equivalent_fils": int(
                (Decimal(member_premium) / 12).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            ),
            "illustrative_member_care_fils": illustrative_member_care,
            "annual_planning_total_fils": annual_planning_total,
            "monthly_planning_equivalent_fils": int(
                (Decimal(annual_planning_total) / 12).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            ),
            "within_budget": member_premium <= budget_fils,
            "budget_gap_fils": max(0, member_premium - budget_fils),
            "deductible_fils": deductible,
            "copay_pct": copay,
            "reasons": list(item["reasons"]),
            "gaps": list(item["gaps"]),
            "unknowns": list(item["unknowns"]),
            "tradeoffs": list(item["tradeoffs"]),
        })
    eligible = [row for row in rows if row["fit_status"] == "supported"]
    within_budget = [row for row in eligible if row["within_budget"]]
    candidates = within_budget or eligible
    def rank(row):
        if priority == "lower_member_cost":
            return row["illustrative_member_care_fils"], row["member_premium_fils"], row["plan_id"]
        if priority == "lower_premium":
            return row["member_premium_fils"], row["illustrative_member_care_fils"], row["plan_id"]
        return row["annual_planning_total_fils"], row["member_premium_fils"], row["plan_id"]

    recommended = min(candidates, key=rank) if candidates else None
    if recommended:
        budget_note = (
            f"Its member-funded annual premium is {_aed(recommended['member_premium_fils'])}, "
            f"or {_aed(recommended['monthly_budget_equivalent_fils'])} per month as a budgeting equivalent."
        )
        reply = (
            f"For your {priority.replace('_', ' ')} priority, {recommended['name']} is the best supported "
            f"fictional option in this scenario. {budget_note} Your illustrative eligible outpatient share "
            f"would be {_aed(recommended['illustrative_member_care_fils'])} at the spending level you chose. "
        )
        if not within_budget:
            reply += "No supported plan is within your stated premium budget. Review the gap before choosing."
        else:
            reply += "This is a planning illustration, not an insurer instalment offer or a claim prediction."
    else:
        reply = (
            "None of the supplied fictional plans meets all known requirements. Adjusting a budget slider "
            "does not remove a coverage gap; review the plan conditions first."
        )
    return {
        "recommended_plan_id": recommended["plan_id"] if recommended else None,
        "reply": reply,
        "rows": rows,
        "assumptions": [
            "One year of eligible in-network general outpatient bills is illustrated as a single aggregate.",
            "Deductible and copay come from the supplied fictional plan terms; other benefits, exclusions and annual limits are not modelled here.",
            "Employer or sponsor contribution reduces the member's budgeting share only; it does not change the insurer premium.",
            "Monthly amounts are budgeting equivalents. No monthly instalment or financing offer is inferred.",
        ],
        "mode": "synthetic_financial_planning",
    }
