"""Print the original five-applicant, thirteen-event challenge tour as JSON."""

import json

from app.fixture_tour import run_fixture_tour

if __name__ == "__main__":
    print(json.dumps(run_fixture_tour(), indent=2))
