from app.domain import empty_ledger, evaluate_servicing, plans, replay_servicing


def plan(plan_id):
    return next(item for item in plans() if item["id"] == plan_id)


def test_deductible_then_copay_and_no_duplicate_consumption():
    first = evaluate_servicing(
        plan("plan_a"),
        {
            "id": "CLM-1",
            "kind": "claim",
            "policy_month": 5,
            "benefit_class": "general",
            "provider_tier": "in_network_clinic",
            "billed_amount": 3200,
        },
    )
    assert first["plan_pays"] == 1190
    assert first["member_pays"] == 2010
    second = evaluate_servicing(
        plan("plan_a"),
        {
            "id": "CLM-6",
            "kind": "claim",
            "policy_month": 8,
            "benefit_class": "general",
            "provider_tier": "in_network_clinic",
            "billed_amount": 1800,
        },
        first["ledger_after"],
    )
    assert second["plan_pays"] == 1260
    assert second["ledger_after"]["deductible_met_fils"] == 150000


def test_forecast_is_non_mutating_and_maternity_cap_is_applied_after_copay():
    forecast = evaluate_servicing(
        plan("plan_c"),
        {
            "id": "PRE-1",
            "kind": "preauth",
            "policy_month": 6,
            "benefit_class": "maternity",
            "provider_tier": "private_hospital",
            "estimated_amount": 40000,
        },
    )
    assert forecast["outcome"] == "approved_with_limit"
    assert forecast["plan_pays"] == 25000
    assert forecast["ledger_after"] == empty_ledger()


def test_wait_network_and_unknown_geography_are_distinct():
    waiting = evaluate_servicing(
        plan("plan_b"),
        {
            "id": "CLM-3",
            "kind": "claim",
            "policy_month": 4,
            "benefit_class": "chronic_preexisting",
            "provider_tier": "in_network_clinic",
            "billed_amount": 2800,
        },
    )
    assert waiting["reason_code"] == "waiting_period_not_elapsed"
    abroad = evaluate_servicing(
        plan("plan_c"),
        {
            "id": "CLM-9",
            "kind": "reimbursement",
            "policy_month": 6,
            "benefit_class": "chronic_preexisting",
            "provider_tier": "unknown_foreign",
            "geography": "abroad",
            "amount_paid_by_member": 4500,
        },
    )
    assert abroad["outcome"] == "insufficient_data"
    assert abroad["plan_pays"] is None


def test_replay_keeps_preauth_out_of_financial_ledger():
    operations = [
        {
            "id": "PRE-1",
            "kind": "preauth",
            "policy_month": 6,
            "benefit_class": "maternity",
            "provider_tier": "private_hospital",
            "estimated_amount": 40000,
        },
        {
            "id": "CLM-2",
            "kind": "claim",
            "policy_month": 9,
            "benefit_class": "maternity",
            "provider_tier": "private_hospital",
            "billed_amount": 40000,
        },
    ]
    results, ledger = replay_servicing(plan("plan_c"), operations)
    assert results[0]["ledger_after"] == empty_ledger()
    assert ledger["maternity_paid_fils"] == 2500000
    assert ledger["financial_event_ids"] == ["CLM-2"]
