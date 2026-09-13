import calendar
import hashlib
import json
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def plans():
    return json.loads((DATA / "hackathon_data.json").read_text(encoding="utf-8-sig"))["plans"]


def source_data():
    return json.loads((DATA / "hackathon_data.json").read_text(encoding="utf-8-sig"))


def money(value):
    return int((Decimal(str(value)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def compare(facts):
    results = []
    for plan in plans():
        gaps, unknowns, reasons = [], [], []
        if facts.get("maternity"):
            term = plan["maternity"]
            if not term["covered"]:
                gaps.append("Maternity is excluded.")
            elif term["waiting_period_months"] > facts.get("maximum_maternity_wait", 24):
                gaps.append(
                    f"Maternity starts after {term['waiting_period_months']} months, later than your stated need."
                )
            else:
                reasons.append(
                    f"Maternity becomes available after {term['waiting_period_months']} months, within your stated wait."
                )
        if facts.get("diagnosed_conditions") == "yes":
            term = plan["chronic_preexisting"]
            if not term["covered"]:
                gaps.append("Declared existing conditions are excluded.")
            elif term["waiting_period_months"] and facts.get("immediate_chronic_cover"):
                gaps.append(f"Existing-condition cover has a {term['waiting_period_months']}-month gap.")
            else:
                reasons.append(f"Existing-condition waiting period: {term['waiting_period_months']} months.")
        if facts.get("diagnosed_conditions") in ["unknown", "declined"]:
            unknowns.append("Existing-condition requirements need clarification.")
        tiers = {"restricted": 0, "standard": 1, "wide": 2}
        preferred = facts.get("preferred_network")
        if preferred and tiers[plan["network"]] < tiers[preferred]:
            gaps.append("The network is narrower than your requested access.")
        dental = facts.get("dental")
        if (
            dental
            and {"none": 0, "basic": 1, "full": 2}[plan["dental_optical"]]
            < {"none": 0, "basic": 1, "full": 2}[dental]
        ):
            gaps.append("Dental/optical benefits do not meet your preference.")
        if facts.get("preferred_provider"):
            unknowns.append("Your named provider needs exact network verification.")
        if facts.get("geography") in ["international", "unsure"]:
            unknowns.append("The supplied plans do not specify overseas coverage.")
        budget = facts.get("annual_budget")
        if budget is not None and plan["annual_premium"] > budget:
            text = f"Annual premium is AED {plan['annual_premium'] - budget:,} above your budget."
            (gaps if facts.get("strict_budget") else reasons).append(text)
        reasons.append(
            f"{plan['network'].capitalize()} network; {plan['outpatient_copay_pct']}% member copay after the deductible."
        )
        results.append(
            {
                "plan": plan,
                "status": "does_not_meet_requirement"
                if gaps
                else "needs_more_information"
                if unknowns
                else "supported",
                "gaps": gaps,
                "unknowns": unknowns,
                "reasons": reasons,
                "premium_fils": money(plan["annual_premium"]),
                "monthly_budget_equivalent_fils": int(
                    (Decimal(plan["annual_premium"]) * 100 / 12).quantize(
                        Decimal("1"), rounding=ROUND_HALF_UP
                    )
                ),
                "source": "Supplied fictional challenge catalogue v3",
                "source_id": plan["id"],
            }
        )
    # Explicit access/benefit constraints precede premium; low member-cost preference is a transparent tie-breaker.
    results.sort(
        key=lambda x: (
            {"supported": 0, "needs_more_information": 1, "does_not_meet_requirement": 2}[x["status"]],
            x["plan"]["outpatient_copay_pct"] if facts.get("cost_sharing") == "lower_member_cost" else 0,
            x["premium_fils"],
            x["plan"]["id"],
        )
    )
    return results


def reassess_fit(current_plan_id, facts, servicing_history):
    """Explain whether present needs still fit frozen terms; never switches a policy automatically."""
    comparison = compare(facts)
    current = next(item for item in comparison if item["plan"]["id"] == current_plan_id)
    effective = {}
    for event in servicing_history:
        if event["record_type"] in {"decision", "revision"}:
            effective[event["root_id"]] = event
    covered = [event for event in effective.values() if event["outcome"] == "covered"]
    findings = [*current["gaps"], *current["unknowns"]]
    if not findings:
        findings.append("The current fictional plan remains supported by the saved profile details.")
    if covered:
        findings.append(f"This assessment considered {len(covered)} covered servicing event(s) in the recorded history.")
    alternatives = [item for item in comparison if item["plan"]["id"] != current_plan_id and item["status"] == "supported"]
    return {
        "outcome": "review" if current["gaps"] or current["unknowns"] else "retain",
        "current": current,
        "alternatives": alternatives,
        "findings": findings,
        "history_event_ids": [event["root_id"] for event in effective.values()],
    }


def installments(total_fils: int, start: str, count: int):
    if total_fils < 0 or count not in (1, 12):
        raise ValueError("Unsupported schedule")
    initial = date.fromisoformat(start)
    base, remainder = divmod(total_fils, count)
    rows = []
    for index in range(count):
        absolute_month = initial.year * 12 + initial.month - 1 + index
        year, month_zero = divmod(absolute_month, 12)
        day = min(initial.day, calendar.monthrange(year, month_zero + 1)[1])
        rows.append(
            {
                "position": index + 1,
                "due_date": date(year, month_zero + 1, day).isoformat(),
                "amount": base + (remainder if index == count - 1 else 0),
            }
        )
    return rows


def map_application(plan_id, facts, email):
    if plan_id == "plan_a":
        payload = {
            "applicant": {
                "full_name": facts.get("legal_name"),
                "birth_date": facts.get("date_of_birth"),
                "emirate": facts.get("emirate"),
                "email": email,
            },
            "health_declaration": {k: facts.get(k) for k in ["diagnosed_conditions", "conditions", "smoker"]},
            "funding": {
                k: facts.get(k) for k in ["payer", "company_name", "sponsor_name", "contribution_aed"]
            },
        }
        schema = "sandbox-essential-v1"
    else:
        payload = {
            "memberName": facts.get("legal_name"),
            "dob": facts.get("date_of_birth"),
            "residence": {"region": facts.get("emirate"), "category": facts.get("residency")},
            "contactEmail": email,
            "medical": {
                "declared": facts.get("diagnosed_conditions"),
                "conditions": facts.get("conditions", []),
                "smoking": facts.get("smoker"),
            },
            "payerType": facts.get("payer"),
            "sponsor": facts.get("company_name") or facts.get("sponsor_name"),
            "contributionAED": facts.get("contribution_aed"),
        }
        schema = "sandbox-extended-v1"
    return {
        "schema": schema,
        "payload": payload,
        "destination": "Helm in-app carrier sandbox",
        "provenance": {key: "saved profile" for key in payload},
    }


# Servicing is deliberately deterministic. The language layer may help capture a request,
# but it never selects a rule, calculates a liability, or mutates a benefit balance.
def empty_ledger():
    return {
        "deductible_met_fils": 0,
        "annual_paid_fils": 0,
        "maternity_paid_fils": 0,
        "financial_event_ids": [],
    }


def _fils_to_aed(value):
    return None if value is None else Decimal(value) / Decimal(100)


def _round_fils(value):
    return int(Decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _plan_by_id(plan_id):
    return next(plan for plan in plans() if plan["id"] == plan_id)


def _amount_fils(operation):
    for name in ("billed_amount", "estimated_amount", "amount_paid_by_member"):
        if operation.get(name) is not None:
            return money(operation[name])
    raise ValueError("The operation does not contain an amount.")


def _benefit_term(plan, benefit_class):
    if benefit_class == "maternity":
        return plan["maternity"]
    if benefit_class == "chronic_preexisting":
        return plan["chronic_preexisting"]
    return {"covered": True, "waiting_period_months": 0, "limit": None}


def _result(operation, ledger, outcome, reason_code, plan_pays_fils, member_pays_fils, calculation):
    return {
        "event_id": operation["id"],
        "kind": operation["kind"],
        "policy_month": operation.get("policy_month"),
        "outcome": outcome,
        "reason_code": reason_code,
        "plan_pays": _fils_to_aed(plan_pays_fils),
        "member_pays": _fils_to_aed(member_pays_fils),
        "plan_pays_fils": plan_pays_fils,
        "member_pays_fils": member_pays_fils,
        "calculation": calculation,
        "ledger_before": dict(ledger),
        "ledger_after": dict(ledger),
    }


def evaluate_servicing(plan, operation, ledger=None):
    """Return a pure servicing decision and resulting ledger projection.

    Monetary values in inputs are AED, while all intermediate and projection values use fils.
    Pre-authorizations are immutable forecasts and never consume a balance.
    """
    ledger = dict(ledger or empty_ledger())
    kind = operation["kind"]
    if kind not in {"claim", "preauth", "reimbursement"}:
        raise ValueError("Only financial servicing operations can be evaluated.")
    if operation.get("geography") == "abroad":
        return _result(
            operation,
            ledger,
            "insufficient_data",
            "insufficient_data",
            None,
            None,
            ["The available policy terms do not define overseas cover."],
        )

    amount_fils = _amount_fils(operation)
    benefit = operation["benefit_class"]
    term = _benefit_term(plan, benefit)
    if not term["covered"]:
        return _result(operation, ledger, "declined" if kind == "preauth" else "denied", "benefit_excluded", 0, amount_fils, ["This benefit is excluded."])
    if operation.get("policy_month", 0) < term.get("waiting_period_months", 0):
        return _result(operation, ledger, "declined" if kind == "preauth" else "denied", "waiting_period_not_elapsed", 0, amount_fils, ["The applicable waiting period has not elapsed."])

    allowed = source_data()["provider_tiers"].get(plan["network"], [])
    if operation.get("provider_tier") not in allowed:
        return _result(operation, ledger, "declined" if kind == "preauth" else "denied", "provider_out_of_network", 0, amount_fils, ["The provider tier is outside this plan's network."])

    sublimit_fils = money(term["limit"]) if term.get("limit") is not None else None
    used_fils = ledger["maternity_paid_fils"] if benefit == "maternity" else 0
    if sublimit_fils is not None and used_fils >= sublimit_fils:
        return _result(operation, ledger, "declined" if kind == "preauth" else "denied", "sublimit_exhausted", 0, amount_fils, ["The benefit sublimit is already exhausted."])

    annual_limit_fils = money(plan["annual_limit"])
    if ledger["annual_paid_fils"] >= annual_limit_fils:
        return _result(operation, ledger, "declined" if kind == "preauth" else "denied", "annual_limit_reached", 0, amount_fils, ["The annual plan-payment limit is already exhausted."])

    deductible_remaining = max(money(plan["deductible"]) - ledger["deductible_met_fils"], 0)
    deductible_applied = min(deductible_remaining, amount_fils)
    covered_after_deductible = amount_fils - deductible_applied
    plan_share = _round_fils(
        Decimal(covered_after_deductible) * (Decimal(100 - plan["outpatient_copay_pct"]) / Decimal(100))
    )
    if sublimit_fils is not None:
        plan_share = min(plan_share, max(sublimit_fils - used_fils, 0))
    plan_share = min(plan_share, max(annual_limit_fils - ledger["annual_paid_fils"], 0))
    member_share = amount_fils - plan_share
    limited = plan_share < _round_fils(
        Decimal(covered_after_deductible) * (Decimal(100 - plan["outpatient_copay_pct"]) / Decimal(100))
    )
    calculation = [
        f"Amount: AED {_fils_to_aed(amount_fils)}.",
        f"Deductible applied: AED {_fils_to_aed(deductible_applied)}.",
        f"Plan payment after copay and applicable limits: AED {_fils_to_aed(plan_share)}.",
    ]
    outcome = "approved_with_limit" if kind == "preauth" and limited else "approved" if kind == "preauth" else "covered"
    result = _result(operation, ledger, outcome, "covered", plan_share, member_share, calculation)
    if kind == "preauth":
        return result

    updated = dict(ledger)
    updated["deductible_met_fils"] += deductible_applied
    updated["annual_paid_fils"] += plan_share
    if benefit == "maternity":
        updated["maternity_paid_fils"] += plan_share
    updated["financial_event_ids"] = [*ledger["financial_event_ids"], operation["id"]]
    result["ledger_after"] = updated
    return result


def replay_servicing(plan, operations):
    """Evaluate effective financial roots in supplied chronological order."""
    ledger = empty_ledger()
    results = []
    for operation in operations:
        decision = evaluate_servicing(plan, operation, ledger)
        results.append(decision)
        if operation["kind"] != "preauth" and decision["outcome"] == "covered":
            ledger = decision["ledger_after"]
    return results, ledger
