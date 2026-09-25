from io import BytesIO
from uuid import uuid4

from PIL import Image
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session

from app.auth import User
from app.models import ClaimDocument, ClaimDocumentFile
from conftest import as_assigned_broker
from test_claim_review import add_flagged_claim, add_policy


def test_broker_can_view_member_originals_for_regular_and_emergency_claims(fixture_client):
    client, owner, engine = fixture_client
    with Session(engine) as db:
        policy = add_policy(db, owner[0].id)
        regular = add_flagged_claim(db, policy, "REGULAR")
        emergency = add_flagged_claim(db, policy, "EMERGENCY", emergency=True)
        db.commit()
        policy_id, regular_id, emergency_id = policy.id, regular.id, emergency.id

    image = Image.new("RGB", (8, 8), "white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    png = buffer.getvalue()
    pdf_buffer = BytesIO()
    pdf = canvas.Canvas(pdf_buffer)
    pdf.drawString(40, 750, "Demo invoice")
    pdf.save()
    originals = {regular_id: ("invoice.png", png, "image/png"),
                 emergency_id: ("invoice.pdf", pdf_buffer.getvalue(), "application/pdf")}
    for claim_id, (filename, content, media_type) in originals.items():
        response = client.post(
            f"/api/policies/{policy_id}/claim-intakes/{claim_id}/attachments",
            data={"doc_types": "bill"}, files={"files": (filename, content, media_type)},
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert response.status_code == 200, response.text

    with as_assigned_broker(owner, engine):
        claims = client.get("/api/broker/claims").json()
        for claim_id in (regular_id, emergency_id):
            _, content, media_type = originals[claim_id]
            document = next(doc for row in claims if row["id"] == claim_id
                            for doc in row["documents"] if doc["has_original"])
            preview = client.get(f"/api/broker/claims/{claim_id}/documents/{document['id']}/original")
            assert preview.status_code == 200
            assert preview.content == content
            assert preview.headers["content-type"] == media_type
            assert preview.headers["cache-control"] == "no-store"

    owner[0] = User(str(uuid4()), "other-broker@example.test", "broker")
    assert client.get(f"/api/broker/claims/{regular_id}/documents/{document['id']}/original").status_code == 404
    owner[0] = User(str(uuid4()), "other-member@example.test", "member")
    assert client.get(f"/api/broker/claims/{emergency_id}/documents/{document['id']}/original").status_code == 403
    with Session(engine) as db:
        assert db.query(ClaimDocumentFile).count() == 2
        assert db.query(ClaimDocument).count() == 2  # re-upload repairs legacy rows; no duplicates
