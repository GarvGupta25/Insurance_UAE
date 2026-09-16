"""Export the deterministic fixture tour as reviewer-readable Markdown and JSON."""

import json
from pathlib import Path

from app.fixture_tour import run_fixture_tour

OUT = Path(__file__).resolve().parents[2] / "docs" / "deliverable"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tour = run_fixture_tour()
    (OUT / "fixture_tour_report.json").write_text(json.dumps(tour, indent=2), encoding="utf-8")
    lines = ["# Helm AI fixture tour", "", "Generated from `app.fixture_tour.run_fixture_tour()`.", ""]
    for applicant in tour["applicants"]:
        lines += [f"## {applicant['profile_id']}", f"Cohort: `{applicant['classification']['cohort']}`.", ""]
        for quote in applicant["quotes"]:
            lines.append(f"- {quote['plan_id']}: AED {quote['annual_premium']}; `{quote['status']}`.")
        lines.append("")
    lines += ["## Events", "", "| Event | Outcome | Plan pays | Member pays | Reason |", "|---|---|---:|---:|---|"]
    for event in tour["events"]:
        lines.append(f"| {event['event_id']} | {event['outcome']} | {event['plan_pays']} | {event['member_pays']} | {event['reason_code']} |")
    (OUT / "fixture_tour_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
