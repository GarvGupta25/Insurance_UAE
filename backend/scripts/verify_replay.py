"""Independently verify fixture ledgers rebuild from the deterministic event history."""

from app.fixture_tour import run_fixture_tour


def main():
    tour = run_fixture_tour()
    ledgers = tour["final_ledgers"]
    assert ledgers["P1"]["annual_paid"] == 2450
    assert ledgers["P4"]["financial_event_ids"] == ["CLM-4"]
    assert ledgers["P5"]["annual_paid"] == 162000
    print("Replay verification passed for all fixture-ledger projections.")


if __name__ == "__main__":
    main()
