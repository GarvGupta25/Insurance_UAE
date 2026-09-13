from app.fixture_tour import run_fixture_tour


def test_original_thirteen_events_match_required_reference_outputs():
    tour = run_fixture_tour()
    assert len(tour["applicants"]) == 5
    assert [item["event_id"] for item in tour["events"]] == [
        "CLM-1", "CLM-6", "PRE-1", "CLM-2", "CLM-7", "CLM-3", "APP-1",
        "CLM-8", "CLM-4", "APP-2", "PRE-2", "CLM-5", "CLM-9",
    ]
    expected = [
        ("covered", 1190, 2010, "covered", 1500, 1190, 0),
        ("covered", 1260, 540, "covered", 1500, 2450, 0),
        ("approved_with_limit", 25000, 15000, "covered", 0, 0, 0),
        ("covered", 25000, 15000, "covered", 0, 25000, 25000),
        ("denied", 0, 3000, "sublimit_exhausted", 0, 25000, 25000),
        ("denied", 0, 2800, "waiting_period_not_elapsed", 0, 0, 0),
        ("upheld", 0, 2800, "waiting_period_not_elapsed", 0, 0, 0),
        ("covered", 1680, 920, "covered", 500, 1680, 0),
        ("denied", 0, 6000, "provider_out_of_network", 0, 0, 0),
        ("overturned", 4400, 1600, "covered", 500, 4400, 0),
        ("approved", 22400, 5600, "covered", 500, 4400, 0),
        ("covered", 162000, 18000, "covered", 0, 162000, 0),
        ("insufficient_data", None, None, "insufficient_data", 0, 162000, 0),
    ]
    observed = [
        (item["outcome"], item["plan_pays"], item["member_pays"], item["reason_code"],
         item["ledger"]["deductible_met"], item["ledger"]["annual_paid"], item["ledger"]["maternity_paid"])
        for item in tour["events"]
    ]
    assert observed == expected
    assert tour["events"][-1]["cash_already_paid"] == 4500
    assert [tour["final_ledgers"][key]["annual_paid"] for key in ("P1", "P2", "P3", "P4", "P5")] == [2450, 25000, 1680, 4400, 162000]


def test_fixture_recommendations_use_intake_only_and_preserve_approved_plans():
    tour = run_fixture_tour()
    assert [item["recommended_plan_id"] for item in tour["applicants"]] == ["plan_a", "plan_c", "plan_b", "plan_b", "plan_c"]
    assert [item["approved_plan_id"] for item in tour["applicants"]] == ["plan_a", "plan_c", "plan_b", "plan_b", "plan_c"]
    assert all(len(item["quotes"]) == 3 for item in tour["applicants"])
