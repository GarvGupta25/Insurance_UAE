from uuid import uuid4

from sqlalchemy.orm import Session

from app.auth import User
from app.marketplace_models import (
    MarketplaceApplication,
    Provider,
    ProviderQuotation,
    ProviderUser,
)
from app.models import BrokerAssignment, Case, Profile


def quote_body(premium: int, network: str = "standard") -> dict:
    return {
        "premium": premium,
        "plan_terms": {
            "name": f"Real {network.title()} Quote",
            "network": network,
            "annual_limit": 500000,
            "deductible": 500,
            "outpatient_copay_pct": 20,
            "maternity": {"covered": True, "waiting_period_months": 6, "limit": 50000},
            "chronic_preexisting": {"covered": True, "waiting_period_months": 0},
        },
    }


def test_real_quotes_flow_from_ranking_to_three_party_policy_visibility(fixture_client):
    client, owner, engine = fixture_client
    member = owner[0]
    provider_user_a, provider_user_b, broker_id = str(uuid4()), str(uuid4()), str(uuid4())
    with Session(engine) as db:
        db.add_all(
            [
                Provider(id="selection-provider-a", name="Selection Provider A"),
                Provider(id="selection-provider-b", name="Selection Provider B"),
                ProviderUser(
                    user_id=provider_user_a,
                    provider_id="selection-provider-a",
                    display_name="Provider A User",
                ),
                ProviderUser(
                    user_id=provider_user_b,
                    provider_id="selection-provider-b",
                    display_name="Provider B User",
                ),
                BrokerAssignment(member_id=member.id, broker_id=broker_id),
                Profile(
                    owner_id=member.id,
                    facts={
                        "age": 34,
                        "annual_budget": 12000,
                        "geography": "UAE",
                        "diagnosed_conditions": "no",
                        "maternity": False,
                        "preferred_network": "standard",
                    },
                ),
                Case(id="selection-case", owner_id=member.id, status="open"),
            ]
        )
        db.flush()
        db.add_all(
            [
                MarketplaceApplication(
                    id="selection-application-a",
                    owner_id=member.id,
                    case_id="selection-case",
                    provider_id="selection-provider-a",
                    status="sent_to_providers",
                    consent_snapshot={"explicit_consent": "yes"},
                ),
                MarketplaceApplication(
                    id="selection-application-b",
                    owner_id=member.id,
                    case_id="selection-case",
                    provider_id="selection-provider-b",
                    status="sent_to_providers",
                    consent_snapshot={"explicit_consent": "yes"},
                ),
            ]
        )
        db.commit()

    owner[0] = User(provider_user_a, "a@provider.test", "provider")
    quote_a = client.post(
        "/api/provider/applications/selection-application-a/quote", json=quote_body(8000)
    )
    owner[0] = member
    waiting = client.get("/api/marketplace/cases/selection-case/quotations")
    assert waiting.status_code == 200
    assert waiting.json()["collection_ready"] is False

    owner[0] = User(provider_user_b, "b@provider.test", "provider")
    quote_b = client.post(
        "/api/provider/applications/selection-application-b/quote",
        json=quote_body(9000, "wide"),
    )
    assert quote_a.status_code == quote_b.status_code == 201

    owner[0] = member
    ranked = client.get("/api/marketplace/cases/selection-case/quotations")
    assert ranked.status_code == 200
    assert ranked.json()["collection_ready"] is True
    assert [row["premium_aed"] for row in ranked.json()["quotations"]] == [8000.0, 9000.0]
    selected_quote_id = ranked.json()["quotations"][0]["quotation_id"]
    selected_application_id = ranked.json()["quotations"][0]["application_id"]
    selection = client.post(f"/api/marketplace/quotations/{selected_quote_id}/select")
    assert selection.status_code == 200

    with Session(engine) as db:
        quotations = db.query(ProviderQuotation).order_by(ProviderQuotation.premium).all()
        assert [row.status for row in quotations] == ["selected", "declined"]
        applications = db.query(MarketplaceApplication).order_by(MarketplaceApplication.provider_id).all()
        assert sorted(row.status for row in applications) == ["customer_selected", "declined"]
        selected_provider_id = quotations[0].provider_id
        other_provider_id = quotations[1].provider_id
    selected_provider_user = provider_user_a if selected_provider_id == "selection-provider-a" else provider_user_b
    other_provider_user = provider_user_b if other_provider_id == "selection-provider-b" else provider_user_a

    owner[0] = User(selected_provider_user, "selected@provider.test", "provider")
    assert client.post(f"/api/provider/quotations/{selected_quote_id}/accept").status_code == 200
    assert client.post(f"/api/provider/policies/{selected_quote_id}/start").status_code == 403

    owner[0] = member
    assert client.get("/api/marketplace/cases/selection-case/quotations").json()["status"] == "provider_accepted"

    owner[0] = User(broker_id, "broker@example.test", "broker")
    worklist = client.get("/api/broker/worklist")
    assert any(row["id"] == selected_application_id for row in worklist.json())
    checkpoint = client.post(
        f"/api/broker/marketplace/applications/{selected_application_id}/checkpoint-2",
        json={"action": "approve", "note": "Accepted terms verified."},
    )
    assert checkpoint.status_code == 200

    owner[0] = member
    assert client.get("/api/marketplace/cases/selection-case/quotations").json()["status"] == "broker_final_review"

    owner[0] = User(selected_provider_user, "selected@provider.test", "provider")
    started = client.post(f"/api/provider/policies/{selected_quote_id}/start")
    assert started.status_code == 201
    policy_id = started.json()["id"]
    assert [row["id"] for row in client.get("/api/provider/policies").json()] == [policy_id]

    owner[0] = User(other_provider_user, "other@provider.test", "provider")
    assert client.get("/api/provider/policies").json() == []
    assert client.get(f"/api/provider/policies/{policy_id}/payments").status_code == 404

    owner[0] = member
    assert client.get("/api/marketplace/cases/selection-case/quotations").json()["status"] == "bound"
    assert [row["id"] for row in client.get("/api/marketplace/policies").json()] == [policy_id]
    owner[0] = User(str(uuid4()), "other-member@example.test")
    assert client.get("/api/marketplace/policies").json() == []

    owner[0] = User(broker_id, "broker@example.test", "broker")
    broker_case = client.get(f"/api/broker/cases/{member.id}")
    assert broker_case.status_code == 200
    assert [row["id"] for row in broker_case.json()["marketplace_policies"]] == [policy_id]
