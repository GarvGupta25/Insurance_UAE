"""Deterministic walkthrough of the original fictional challenge fixtures."""

from .domain import (
    classify,
    compare,
    empty_ledger,
    evaluate_servicing,
    fixture_facts,
    replay_servicing,
    source_data,
)


def _aed(fils):
    if fils is None:
        return None
    return fils // 100 if fils % 100 == 0 else fils / 100


def _balances(ledger):
    return {
        "deductible_met": _aed(ledger["deductible_met_fils"]),
        "annual_paid": _aed(ledger["annual_paid_fils"]),
        "maternity_paid": _aed(ledger["maternity_paid_fils"]),
        "financial_event_ids": list(ledger["financial_event_ids"]),
    }


def _row(event, outcome, decision, ledger):
    return {
        "profile_id": event["profile_id"],
        "event_id": event["id"],
        "kind": event["kind"],
        "outcome": outcome,
        "plan_pays": _aed(decision["plan_pays_fils"]),
        "member_pays": _aed(decision["member_pays_fils"]),
        "reason_code": decision["reason_code"],
        "ledger": _balances(ledger),
        "cash_already_paid": event.get("amount_paid_by_member"),
    }


def _app2_network_membership(appeal):
    """Represent the supplied registration as a separately accepted broker evidence fact."""
    evidence = appeal["evidence_attached"]
    if len(evidence) != 1 or "Gulf Physiotherapy Centre LLC" not in evidence[0] or "independently licensed outpatient facility" not in evidence[0] or "standard network tier" not in evidence[0]:
        raise ValueError("APP-2 registration evidence is missing or changed; broker review is required.")
    return {
        "provider_name": "Gulf Physiotherapy Centre LLC",
        "network_tier": "standard",
        "evidence_reference": evidence[0],
    }


def run_fixture_tour():
    source = source_data()
    plans = {plan["id"]: plan for plan in source["plans"]}
    applicants = []
    ledgers = {}
    operations = {}
    decisions = {}
    for profile in source["profiles"]:
        facts = fixture_facts(profile)
        comparison = compare(facts)
        applicants.append({
            "profile_id": profile["id"],
            "classification": classify(facts),
            "recommended_plan_id": comparison[0]["plan"]["id"],
            "approved_plan_id": profile["approved_plan_id"],
            "quotes": [{"plan_id": item["plan"]["id"], "annual_premium": item["plan"]["annual_premium"], "status": item["status"], "tradeoffs": item["tradeoffs"]} for item in comparison],
        })
        ledgers[profile["id"]] = empty_ledger()
        operations[profile["id"]] = []
        decisions[profile["id"]] = {}

    rows = []
    for event in source["servicing_events"]:
        profile_id = event["profile_id"]
        plan = plans[event["plan_id"]]
        if event["kind"] == "appeal":
            contested = event["contests"]
            if contested not in decisions[profile_id]:
                raise ValueError(f"Appeal {event['id']} precedes its contested decision.")
            if event["id"] == "APP-1":
                if event["evidence_attached"] or not event["on_file"]:
                    raise ValueError("APP-1 needs a broker evidence review; no automatic override is valid.")
                outcome = "upheld"
            elif event["id"] == "APP-2":
                membership = _app2_network_membership(event)
                operations[profile_id] = [
                    {**operation, "verified_network_membership": membership}
                    if operation["id"] == contested else operation
                    for operation in operations[profile_id]
                ]
                recalculated, ledgers[profile_id] = replay_servicing(plan, operations[profile_id])
                decisions[profile_id] = {
                    operation["id"]: decision
                    for operation, decision in zip(operations[profile_id], recalculated, strict=True)
                }
                outcome = "overturned"
            else:
                raise ValueError(f"No fixture broker review is documented for {event['id']}.")
            rows.append(_row(event, outcome, decisions[profile_id][contested], ledgers[profile_id]))
            continue

        operation = {key: value for key, value in event.items() if key not in {"profile_id", "plan_id", "event"}}
        decision = evaluate_servicing(plan, operation, ledgers[profile_id])
        operations[profile_id].append(operation)
        decisions[profile_id][event["id"]] = decision
        if event["kind"] != "preauth" and decision["outcome"] == "covered":
            ledgers[profile_id] = decision["ledger_after"]
        rows.append(_row(event, decision["outcome"], decision, ledgers[profile_id]))

    return {
        "source_version": source["meta"]["version"],
        "applicants": applicants,
        "events": rows,
        "final_ledgers": {profile_id: _balances(ledger) for profile_id, ledger in ledgers.items()},
    }
