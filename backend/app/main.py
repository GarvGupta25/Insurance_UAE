import hashlib
import hmac
import json
from datetime import date, datetime
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from groq import Groq
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .auth import User, current_user
from .config import settings
from .contracts import (
    AppealRequest,
    BrokerAppealReview,
    BrokerReassessmentReview,
    BrokerRecommendationReview,
    ConfirmRequest,
    MessageRequest,
    PatchRequest,
    PrepareRequest,
    ServicingRequest,
    SimulateRequest,
    VerifyPayment,
    readiness,
)
from .db import session
from .documents import extract_identity, quotation_pdf
from .domain import (
    classify,
    compare,
    digest,
    empty_ledger,
    evaluate_servicing,
    installments,
    map_application,
    money,
    plans,
    reassess_fit,
)
from .models import (
    Application,
    Audit,
    Case,
    Document,
    Installment,
    LedgerProjection,
    Message,
    PaymentOrder,
    Policy,
    PolicyReassessment,
    Quote,
    Receipt,
    Recommendation,
    ReviewDecision,
    Run,
    ServicingEvent,
    SourceSnapshot,
    now,
)
from .payments import razorpay_request, settle, verify_order
from .services import apply_facts, command, own, profile, visible_facts
from .servicing import present_event, rebuild_projection, record_financial_event
from .sources import registry
from .voice import validate_audio

app = FastAPI(title="Helm AI", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings().allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
)


@app.middleware("http")
async def request_boundary(request: Request, call_next):
    request.state.request_id = str(uuid4())
    if request.url.path in {"/api/voice/transcriptions", "/api/documents"}:
        length = request.headers.get("content-length")
        if not length or not length.isdigit():
            return JSONResponse(
                status_code=411,
                content={"code": "length_required", "message": "Upload a bounded audio or document file."},
            )
        if int(length) > 11 * 1024 * 1024:
            return JSONResponse(
                status_code=413, content={"code": "too_large", "message": "File exceeds the upload limit."}
            )
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Permissions-Policy"] = "microphone=(self), camera=(), geolocation=(self)"
    return response


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": f"http_{exc.status_code}",
            "message": str(exc.detail),
            "request_id": getattr(request.state, "request_id", ""),
            "retryable": exc.status_code in {429, 503},
        },
    )


@app.exception_handler(SQLAlchemyError)
async def database_error(request, exc):
    return JSONResponse(
        status_code=503,
        content={
            "code": "database_unavailable",
            "message": "Saved data is temporarily unavailable. Retry after the database is ready.",
            "retryable": True,
        },
    )


@app.exception_handler(RequestValidationError)
@app.exception_handler(ValidationError)
async def validation_error(request, exc):
    fields = [{"field": ".".join(str(x) for x in e["loc"]), "message": e["msg"]} for e in exc.errors()]
    return JSONResponse(
        status_code=422,
        content={
            "code": "validation",
            "message": "Please check the highlighted details.",
            "field_errors": fields,
        },
    )


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/ready")
def ready(db: Session = Depends(session)):
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(503, "Database is not ready. Check configuration and migrations.") from None
    return {"status": "ready"}


@app.get("/api/config")
def capabilities():
    cfg = settings()
    return {
        "auth_configured": bool(cfg.supabase_anon_key),
        "supabase_url": cfg.supabase_url,
        "supabase_anon_key": cfg.supabase_anon_key,
        "ai_available": bool(cfg.groq_api_key),
        "voice_available": bool(cfg.groq_api_key),
        "payment_provider": cfg.payment_provider,
        "data_mode": "synthetic_demo",
    }


@app.get("/api/catalogue")
def catalogue():
    return {"plans": plans(), "mode": "synthetic_demo", "source": "Supplied challenge catalogue v3"}


@app.get("/api/sources")
def public_sources(db: Session = Depends(session)):
    """Registry and freshness only: unreviewed pages cannot become quote terms."""
    result = []
    for entry in registry():
        latest = db.scalar(
            select(SourceSnapshot)
            .where(SourceSnapshot.source_id == entry["id"])
            .order_by(SourceSnapshot.fetched_at.desc())
            .limit(1)
        )
        result.append(
            {
                "id": entry["id"],
                "insurer": entry["insurer"],
                "title": entry["title"],
                "url": entry["url"],
                "last_checked": latest.fetched_at.isoformat() if latest else None,
                "verification": latest.verification if latest else "not_retrieved",
            }
        )
    return {"items": result, "notice": "Public research links are separate from the fictional comparison. No live insurer price or eligibility has been verified."}


@app.get("/api/me/profile")
def get_profile(user: User = Depends(current_user), db: Session = Depends(session)):
    row = profile(db, user)
    db.commit()
    return {
        "id": row.id,
        "version": row.version,
        "facts": visible_facts(row.facts),
        "provenance": row.provenance,
        "email": user.email,
        "readiness": readiness(row.facts),
    }


@app.patch("/api/me/profile")
def update_profile(body: PatchRequest, user: User = Depends(current_user), db: Session = Depends(session)):
    if body.source_message_id:
        message = own(db, Message, body.source_message_id, user)
        source = message.modality
    else:
        source = "manual"
    row = apply_facts(db, user, body, source)
    db.commit()
    return {"version": row.version, "facts": visible_facts(row.facts), "readiness": readiness(row.facts)}


@app.get("/api/cases")
def cases(user: User = Depends(current_user), db: Session = Depends(session)):
    rows = db.scalars(select(Case).where(Case.owner_id == user.id).order_by(Case.created_at.desc())).all()
    return [{"id": r.id, "status": r.status, "created_at": r.created_at.isoformat()} for r in rows]


@app.post("/api/cases")
def create_case(
    user: User = Depends(current_user), db: Session = Depends(session), idempotency_key: str = Header()
):
    def action():
        row = Case(owner_id=user.id)
        db.add(row)
        db.flush()
        return {"id": row.id}

    return command(db, user, idempotency_key, {"action": "create_case"}, action)


@app.get("/api/cases/{case_id}")
def case_detail(case_id: str, user: User = Depends(current_user), db: Session = Depends(session)):
    row = own(db, Case, case_id, user)
    messages = db.scalars(
        select(Message)
        .where(Message.case_id == row.id, Message.owner_id == user.id)
        .order_by(Message.created_at)
    ).all()
    runs = db.scalars(
        select(Run).where(
            Run.case_id == row.id, Run.owner_id == user.id, Run.status.in_(["queued", "running"])
        )
    ).all()
    return {
        "id": row.id,
        "status": row.status,
        "messages": [
            {"id": m.id, "role": m.role, "text": m.text, "details": m.details, "modality": m.modality}
            for m in messages
        ],
        "active_runs": [{"id": r.id, "status": r.status} for r in runs],
    }


@app.post("/api/cases/{case_id}/messages")
def send_message(
    case_id: str,
    body: MessageRequest,
    user: User = Depends(current_user),
    db: Session = Depends(session),
    idempotency_key: str = Header(),
):
    own(db, Case, case_id, user)
    context = {"source_ids": [p["id"] for p in plans()], "plans": plans()}
    if body.policy_id:
        policy = own(db, Policy, body.policy_id, user)
        context = {"source_ids": [policy.id], "policy": policy.snapshot, "status": policy.status}
        rows = db.scalars(
            select(Installment).where(Installment.policy_id == policy.id, Installment.owner_id == user.id)
        ).all()
        context["schedule"] = [
            {"due_date": r.due_date, "amount_fils": r.amount, "status": r.status} for r in rows
        ]

    def action():
        message = Message(
            owner_id=user.id,
            case_id=case_id,
            role="user",
            text=body.text,
            modality=body.modality,
            details={"context": context},
        )
        db.add(message)
        db.flush()
        run = Run(owner_id=user.id, case_id=case_id, message_id=message.id)
        db.add(run)
        db.flush()
        return {"run_id": run.id, "message_id": message.id}

    return command(db, user, idempotency_key, {"case": case_id, **body.model_dump()}, action)


@app.get("/api/runs/{run_id}")
def run_status(run_id: str, user: User = Depends(current_user), db: Session = Depends(session)):
    row = own(db, Run, run_id, user)
    return {"id": row.id, "status": row.status, "result": row.result}


@app.get("/api/runs/{run_id}/events")
def run_events(run_id: str, user: User = Depends(current_user), db: Session = Depends(session)):
    row = own(db, Run, run_id, user)
    # A bounded SSE snapshot; reconnect obtains persisted status. No prompts or hidden reasoning are streamed.
    payload = json.dumps({"status": row.status, "result": row.result})
    return StreamingResponse(
        iter([f"id: {row.attempts}-{row.status}\nevent: status\ndata: {payload}\n\n"]),
        media_type="text/event-stream",
    )


@app.post("/api/voice/transcriptions")
def transcribe(file: UploadFile, user: User = Depends(current_user)):
    if not settings().groq_api_key:
        raise HTTPException(503, "Voice is not configured. You can continue by typing.")
    try:
        content = file.file.read(10 * 1024 * 1024 + 1)
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(413, "Keep recordings below 10 MB and 60 seconds.")
        if not content or not (
            content.startswith(b"\x1aE\xdf\xa3")
            or content[4:8] == b"ftyp"
            or content.startswith(b"RIFF")
            or content.startswith(b"OggS")
        ):
            raise HTTPException(
                422, "This recording format is not supported. Try another browser or type your answer."
            )
        validate_audio(content)
        extension = (
            "webm"
            if content.startswith(b"\x1aE\xdf\xa3")
            else "mp4"
            if content[4:8] == b"ftyp"
            else "wav"
            if content.startswith(b"RIFF")
            else "ogg"
        )
        result = Groq(api_key=settings().groq_api_key, timeout=30, max_retries=0).audio.transcriptions.create(
            file=(f"recording.{extension}", content),
            model=settings().groq_stt_model,
            response_format="verbose_json",
            language="en",
            temperature=0,
        )
        duration = getattr(result, "duration", 0) or 0
        if duration > 61:
            raise HTTPException(422, "Keep each recording to 60 seconds.")
        if not result.text.strip():
            raise HTTPException(422, "No clear speech was found. Try again or type your answer.")
        return {"transcript": result.text[:4000], "duration": duration, "persisted_audio": False}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            503, "Transcription is temporarily unavailable. Your saved information is unchanged."
        ) from None
    finally:
        file.file.close()


@app.post("/api/documents")
def document_upload(file: UploadFile, user: User = Depends(current_user), db: Session = Depends(session)):
    try:
        content = file.file.read(10 * 1024 * 1024 + 1)
        result = extract_identity(content)
        row = Document(owner_id=user.id, sha256=hashlib.sha256(content).hexdigest(), extraction=result)
        db.add(row)
        db.commit()
        return {"id": row.id, **result}
    finally:
        file.file.close()


@app.post("/api/extractions/{document_id}/accept")
def accept_extraction(
    document_id: str, body: PatchRequest, user: User = Depends(current_user), db: Session = Depends(session)
):
    document = own(db, Document, document_id, user, lock=True)
    if document.accepted:
        raise HTTPException(409, "This extraction was already reviewed.")
    if set(body.changes) - {"legal_name", "date_of_birth", "nationality"}:
        raise HTTPException(422, "Identity extraction cannot supply health or funding facts.")
    row = apply_facts(db, user, body, "document:" + document.id)
    document.accepted = True
    db.commit()
    return {"version": row.version}


@app.post("/api/cases/{case_id}/quotes")
def create_quote(
    case_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(session),
    idempotency_key: str = Header(),
):
    own(db, Case, case_id, user)

    def action():
        row = profile(db, user)
        missing = readiness(row.facts)["missing"]
        if missing:
            raise HTTPException(422, "Complete these details first: " + ", ".join(missing))
        if date.fromisoformat(row.facts["start_date"]) < date.today():
            raise HTTPException(422, "Choose a current or future start date for this new shopping case.")
        items = compare(row.facts)
        supported = [r for r in items if r["status"] == "supported"]
        snapshot = {
            "applicant_name": row.facts["legal_name"],
            "generated_at": now().isoformat(),
            "start_date": row.facts["start_date"],
            "items": items,
            "classification": classify(row.facts),
            "mode": "synthetic_demo",
            "quote_kind": "indicative",
            "recommended_plan_id": supported[0]["plan"]["id"] if supported else None,
            "ranking_version": "needs-cost-v1",
            "catalogue_hash": digest(plans()),
            "validity": None,
        }
        quote = Quote(owner_id=user.id, case_id=case_id, profile_version=row.version, snapshot=snapshot)
        db.add(quote)
        db.flush()
        return {"id": quote.id}

    return command(db, user, idempotency_key, {"action": "quote", "case": case_id}, action)


@app.get("/api/quotes/{quote_id}")
def get_quote(quote_id: str, user: User = Depends(current_user), db: Session = Depends(session)):
    quote = own(db, Quote, quote_id, user)
    return {
        "id": quote.id,
        "case_id": quote.case_id,
        **quote.snapshot,
        "stale": quote.profile_version != profile(db, user).version
        or quote.snapshot["catalogue_hash"] != digest(plans()),
    }


@app.get("/api/quotes/{quote_id}/download")
def download_quote(quote_id: str, user: User = Depends(current_user), db: Session = Depends(session)):
    quote = own(db, Quote, quote_id, user)
    return Response(
        quotation_pdf(quote.snapshot, quote.id),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="helm-quote-{quote.id}.pdf"'},
    )


@app.post("/api/applications/prepare")
def prepare_application(
    body: PrepareRequest,
    user: User = Depends(current_user),
    db: Session = Depends(session),
    idempotency_key: str = Header(),
):
    quote = own(db, Quote, body.quote_id, user)

    def action():
        row = profile(db, user)
        if quote.profile_version != row.version or quote.snapshot["catalogue_hash"] != digest(plans()):
            raise HTTPException(409, "This quote is stale. Generate a new quotation.")
        item = next((i for i in quote.snapshot["items"] if i["plan"]["id"] == body.plan_id), None)
        if not item or item["status"] != "supported":
            raise HTTPException(
                422, "Resolve the plan's unmet or unknown requirements before preparing an application."
            )
        mapped = map_application(body.plan_id, row.facts, user.email)
        snapshot = {
            **mapped,
            "plan": item["plan"],
            "profile_version": row.version,
            "start_date": row.facts["start_date"],
            "payment_frequency": row.facts["payment_frequency"],
            "mode": "synthetic_demo",
            "prepared_at": now().isoformat(),
        }
        certainty = "tradeoff" if item["tradeoffs"] else "missing_terms" if item["unknowns"] else "clear"
        recommendation = Recommendation(
            owner_id=user.id,
            case_id=quote.case_id,
            quote_id=quote.id,
            profile_version=row.version,
            proposed_plan_id=body.plan_id,
            certainty=certainty,
            summary={
                "selected": item,
                "alternatives": [candidate for candidate in quote.snapshot["items"] if candidate["plan"]["id"] != body.plan_id],
                "decision_brief": {
                    "requested_decision": "Approve the recommended demo plan for submission.",
                    "main_uncertainty": item["unknowns"][0] if item["unknowns"] else None,
                    "next_action": "Review the plan comparison and approve or change the recommendation.",
                },
            },
        )
        db.add(recommendation)
        db.flush()
        application = Application(
            owner_id=user.id,
            quote_id=quote.id,
            recommendation_id=recommendation.id,
            snapshot=snapshot,
            payload_hash=digest(snapshot),
        )
        db.add(application)
        db.flush()
        return {"id": application.id}

    return command(db, user, idempotency_key, {"action": "prepare", **body.model_dump()}, action)


@app.get("/api/applications/{application_id}")
def application_detail(
    application_id: str, user: User = Depends(current_user), db: Session = Depends(session)
):
    row = own(db, Application, application_id, user)
    return {
        "id": row.id,
        "quote_id": row.quote_id,
        "status": row.status,
        "payload_hash": row.payload_hash,
        "recommendation_id": row.recommendation_id,
        **row.snapshot,
    }


@app.get("/api/broker/recommendations")
def broker_recommendations(user: User = Depends(current_user), db: Session = Depends(session)):
    rows = db.scalars(
        select(Recommendation)
        .where(Recommendation.owner_id == user.id)
        .order_by(Recommendation.created_at.desc())
    ).all()
    return [
        {
            "id": row.id,
            "case_id": row.case_id,
            "quote_id": row.quote_id,
            "proposed_plan_id": row.proposed_plan_id,
            "status": row.status,
            "certainty": row.certainty,
            "summary": row.summary,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@app.post("/api/broker/recommendations/{recommendation_id}/review")
def review_recommendation(
    recommendation_id: str,
    body: BrokerRecommendationReview,
    user: User = Depends(current_user),
    db: Session = Depends(session),
    idempotency_key: str = Header(),
):
    recommendation = own(db, Recommendation, recommendation_id, user, lock=True)

    def action():
        if recommendation.status != "pending_review":
            raise HTTPException(409, "This recommendation has already been reviewed.")
        quote = own(db, Quote, recommendation.quote_id, user)
        selected_plan_id = body.selected_plan_id or recommendation.proposed_plan_id
        selected = next((item for item in quote.snapshot["items"] if item["plan"]["id"] == selected_plan_id), None)
        if not selected or selected["status"] != "supported":
            raise HTTPException(422, "A broker can only approve a currently supported plan.")
        before = {"plan_id": recommendation.proposed_plan_id, "status": recommendation.status}
        recommendation.proposed_plan_id = selected_plan_id
        recommendation.status = "approved"
        application = db.scalar(
            select(Application).where(Application.recommendation_id == recommendation.id).with_for_update()
        )
        if not application:
            raise HTTPException(409, "The prepared application is unavailable.")
        application.status = "ready_for_confirmation"
        application.snapshot = {
            **application.snapshot,
            "plan": selected["plan"],
            "broker_review": {"action": body.action, "note": body.note, "approved_plan_id": selected_plan_id},
        }
        application.payload_hash = digest(application.snapshot)
        review = ReviewDecision(
            owner_id=user.id,
            recommendation_id=recommendation.id,
            action=body.action,
            note=body.note,
            before=before,
            after={"plan_id": selected_plan_id, "status": "approved"},
        )
        db.add(review)
        db.add(
            Audit(
                owner_id=user.id,
                action="recommendation_reviewed",
                subject_id=recommendation.id,
                details={"action": body.action, "plan_id": selected_plan_id},
            )
        )
        return {"recommendation_id": recommendation.id, "application_id": application.id, "status": "approved"}

    return command(
        db,
        user,
        idempotency_key,
        {"action": "review_recommendation", "recommendation": recommendation_id, **body.model_dump()},
        action,
    )


@app.post("/api/applications/{application_id}/submit")
def submit_application(
    application_id: str,
    body: ConfirmRequest,
    user: User = Depends(current_user),
    db: Session = Depends(session),
    idempotency_key: str = Header(),
):
    application = own(db, Application, application_id, user, lock=True)

    def action():
        if not body.declarations_confirmed or body.payload_hash != application.payload_hash:
            raise HTTPException(
                422, "Review the exact application and confirm the declarations before submitting."
            )
        if application.status != "ready_for_confirmation":
            raise HTTPException(409, "This application needs an approved broker recommendation before submission.")
        recommendation = own(db, Recommendation, application.recommendation_id, user)
        if recommendation.status != "approved":
            raise HTTPException(409, "The selected recommendation is not approved.")
        if application.snapshot["profile_version"] != profile(db, user).version:
            raise HTTPException(409, "Your information changed. Prepare a new application.")
        if (now() - datetime.fromisoformat(application.snapshot["prepared_at"])).total_seconds() > 1800:
            raise HTTPException(409, "This confirmation expired. Prepare a fresh application.")
        if own(db, Quote, application.quote_id, user).snapshot["catalogue_hash"] != digest(plans()):
            raise HTTPException(409, "Plan terms changed. Generate a new quote.")
        application.status = "submitted"
        policy = Policy(owner_id=user.id, application_id=application.id, snapshot=application.snapshot)
        db.add(policy)
        db.flush()
        schedule = installments(
            money(policy.snapshot["plan"]["annual_premium"]),
            policy.snapshot["start_date"],
            12 if policy.snapshot["payment_frequency"] == "monthly" else 1,
        )
        for item in schedule:
            db.add(Installment(owner_id=user.id, policy_id=policy.id, **item))
        db.add(
            Audit(
                owner_id=user.id,
                action="sandbox_application_submitted",
                subject_id=application.id,
                details={
                    "payload_hash": body.payload_hash,
                    "destination": application.snapshot["destination"],
                    "consent": True,
                },
            )
        )
        return {
            "policy_id": policy.id,
            "status": "demo_active",
            "message": "In-app sandbox policy created. No real cover was issued.",
        }

    return command(
        db, user, idempotency_key, {"action": "submit", "id": application_id, **body.model_dump()}, action
    )


@app.get("/api/policies")
def list_policies(user: User = Depends(current_user), db: Session = Depends(session)):
    return [
        {
            "id": p.id,
            "status": p.status,
            "plan": p.snapshot["plan"],
            "start_date": p.snapshot.get("start_date"),
        }
        for p in db.scalars(
            select(Policy).where(Policy.owner_id == user.id).order_by(Policy.created_at.desc())
        ).all()
    ]


@app.get("/api/policies/{policy_id}")
def policy_detail(policy_id: str, user: User = Depends(current_user), db: Session = Depends(session)):
    policy = own(db, Policy, policy_id, user)
    rows = db.scalars(
        select(Installment)
        .where(Installment.policy_id == policy.id, Installment.owner_id == user.id)
        .order_by(Installment.position)
    ).all()
    receipts = db.scalars(
        select(Receipt).where(Receipt.installment_id.in_([r.id for r in rows]), Receipt.owner_id == user.id)
    ).all()
    servicing = db.scalars(
        select(ServicingEvent)
        .where(ServicingEvent.policy_id == policy.id, ServicingEvent.owner_id == user.id)
        .order_by(ServicingEvent.sequence)
    ).all()
    servicing_ledger = db.scalar(select(LedgerProjection).where(LedgerProjection.policy_id == policy.id))
    reassessments = db.scalars(
        select(PolicyReassessment)
        .where(PolicyReassessment.policy_id == policy.id)
        .order_by(PolicyReassessment.created_at.desc())
    ).all()
    return {
        "id": policy.id,
        "status": policy.status,
        **policy.snapshot,
        "instalments": [
            {
                "id": r.id,
                "position": r.position,
                "due_date": r.due_date,
                "amount": r.amount,
                "currency": r.currency,
                "status": r.status,
            }
            for r in rows
        ],
        "receipts": [
            {"id": r.id, "amount": r.amount, "provider": r.provider, "created_at": r.created_at.isoformat()}
            for r in receipts
        ],
        "paid_fils": sum(r.amount for r in receipts),
        "total_fils": sum(r.amount for r in rows),
        "servicing": [present_event(event) for event in servicing],
        "servicing_ledger": servicing_ledger.ledger if servicing_ledger else empty_ledger(),
        "reassessments": [
            {"id": item.id, "profile_version": item.profile_version, "status": item.status, "recommended_plan_id": item.recommended_plan_id, "report": item.report, "created_at": item.created_at.isoformat()}
            for item in reassessments
        ],
    }


@app.post("/api/policies/{policy_id}/reassess")
def reassess_policy(
    policy_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(session),
    idempotency_key: str = Header(),
):
    policy = own(db, Policy, policy_id, user, lock=True)

    def action():
        if policy.status != "demo_active":
            raise HTTPException(422, "A fit reassessment needs a verified sandbox policy.")
        current_profile = profile(db, user)
        history = db.scalars(
            select(ServicingEvent).where(ServicingEvent.policy_id == policy.id).order_by(ServicingEvent.sequence)
        ).all()
        report = reassess_fit(
            policy.snapshot["plan"]["id"],
            current_profile.facts,
            [
                {
                    "root_id": event.root_id,
                    "record_type": event.record_type,
                    "outcome": event.outcome,
                }
                for event in history
            ],
        )
        assessment = PolicyReassessment(
            owner_id=user.id,
            policy_id=policy.id,
            profile_version=current_profile.version,
            report=report,
        )
        db.add(assessment)
        db.flush()
        db.add(Audit(owner_id=user.id, action="policy_reassessed", subject_id=assessment.id, details={"outcome": report["outcome"], "profile_version": current_profile.version}))
        return {"id": assessment.id, "profile_version": assessment.profile_version, "report": assessment.report}

    return command(db, user, idempotency_key, {"action": "reassess_policy", "policy_id": policy_id}, action)


@app.get("/api/broker/reassessments")
def broker_reassessments(user: User = Depends(current_user), db: Session = Depends(session)):
    rows = db.scalars(
        select(PolicyReassessment)
        .where(PolicyReassessment.owner_id == user.id)
        .order_by(PolicyReassessment.created_at.desc())
    ).all()
    return [
        {
            "id": row.id,
            "policy_id": row.policy_id,
            "profile_version": row.profile_version,
            "status": row.status,
            "recommended_plan_id": row.recommended_plan_id,
            "report": row.report,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@app.post("/api/broker/reassessments/{reassessment_id}/review")
def review_reassessment(
    reassessment_id: str,
    body: BrokerReassessmentReview,
    user: User = Depends(current_user),
    db: Session = Depends(session),
    idempotency_key: str = Header(),
):
    assessment = own(db, PolicyReassessment, reassessment_id, user, lock=True)

    def action():
        if assessment.status != "pending_review":
            raise HTTPException(409, "This reassessment has already been reviewed.")
        candidates = [assessment.report["current"], *assessment.report.get("alternatives", [])]
        selected_plan_id = body.selected_plan_id or assessment.report["current"]["plan"]["id"]
        selected = next((item for item in candidates if item["plan"]["id"] == selected_plan_id and item["status"] == "supported"), None)
        if not selected:
            raise HTTPException(422, "A review can only retain or recommend a currently supported fictional plan.")
        assessment.status = "reviewed"
        assessment.recommended_plan_id = selected_plan_id
        db.add(ReviewDecision(owner_id=user.id, reassessment_id=assessment.id, action=body.action, note=body.note, before={"outcome": assessment.report["outcome"], "current_plan_id": assessment.report["current"]["plan"]["id"]}, after={"recommended_plan_id": selected_plan_id, "status": "reviewed"}))
        db.add(Audit(owner_id=user.id, action="policy_reassessment_reviewed", subject_id=assessment.id, details={"action": body.action, "recommended_plan_id": selected_plan_id}))
        return {"id": assessment.id, "status": assessment.status, "recommended_plan_id": selected_plan_id}

    return command(db, user, idempotency_key, {"action": "review_reassessment", "reassessment_id": reassessment_id, **body.model_dump()}, action)


@app.post("/api/policies/{policy_id}/servicing")
def submit_servicing(
    policy_id: str,
    body: ServicingRequest,
    user: User = Depends(current_user),
    db: Session = Depends(session),
    idempotency_key: str = Header(),
):
    policy = own(db, Policy, policy_id, user, lock=True)

    def action():
        if policy.status != "demo_active":
            raise HTTPException(422, "Servicing estimates require a verified sandbox policy.")
        operation = {"id": body.event_id, **body.model_dump(exclude={"event_id"})}
        decision, ledger = record_financial_event(db, policy, operation)
        db.add(
            Audit(
                owner_id=user.id,
                action="servicing_decided",
                subject_id=decision["id"],
                details={"event_id": body.event_id, "outcome": decision["outcome"], "reason": decision["reason_code"]},
            )
        )
        return {"decision": decision, "ledger": ledger}

    return command(
        db,
        user,
        idempotency_key,
        {"action": "servicing", "policy_id": policy_id, **body.model_dump(mode="json")},
        action,
    )


def _next_servicing_sequence(db: Session, policy_id: str):
    return (db.scalar(select(func.max(ServicingEvent.sequence)).where(ServicingEvent.policy_id == policy_id)) or 0) + 1


@app.post("/api/policies/{policy_id}/appeals")
def submit_appeal(
    policy_id: str,
    body: AppealRequest,
    user: User = Depends(current_user),
    db: Session = Depends(session),
    idempotency_key: str = Header(),
):
    policy = own(db, Policy, policy_id, user, lock=True)

    def action():
        contested = db.scalar(
            select(ServicingEvent).where(
                ServicingEvent.policy_id == policy.id,
                ServicingEvent.root_id == body.contested_event_id,
                ServicingEvent.record_type == "decision",
            )
        )
        if not contested:
            raise HTTPException(404, "The servicing decision to appeal was not found.")
        existing = db.scalar(
            select(ServicingEvent).where(
                ServicingEvent.policy_id == policy.id,
                ServicingEvent.root_id == body.appeal_id,
                ServicingEvent.record_type == "appeal",
            )
        )
        if existing:
            return {"appeal": present_event(existing), "status": "pending_review"}
        appeal = ServicingEvent(
            owner_id=user.id,
            policy_id=policy.id,
            root_id=body.appeal_id,
            record_type="appeal",
            kind="appeal",
            effective_month=contested.effective_month,
            sequence=_next_servicing_sequence(db, policy.id),
            payload={"contested_event_id": body.contested_event_id, "statement": body.statement, "evidence": body.evidence},
            supersedes_id=contested.id,
        )
        db.add(appeal)
        db.flush()
        db.add(Audit(owner_id=user.id, action="servicing_appeal_submitted", subject_id=appeal.id, details={"contested_event_id": body.contested_event_id}))
        return {"appeal": present_event(appeal), "status": "pending_review"}

    return command(db, user, idempotency_key, {"action": "submit_appeal", "policy_id": policy_id, **body.model_dump()}, action)


@app.get("/api/broker/appeals")
def broker_appeals(user: User = Depends(current_user), db: Session = Depends(session)):
    appeals = db.scalars(
        select(ServicingEvent)
        .where(ServicingEvent.owner_id == user.id, ServicingEvent.record_type == "appeal")
        .order_by(ServicingEvent.created_at.desc())
    ).all()
    rows = []
    for appeal in appeals:
        review = db.scalar(
            select(ServicingEvent).where(ServicingEvent.record_type == "appeal_review", ServicingEvent.supersedes_id == appeal.id)
        )
        contested = db.scalar(select(ServicingEvent).where(ServicingEvent.id == appeal.supersedes_id))
        rows.append({
            "id": appeal.id,
            "appeal_id": appeal.root_id,
            "policy_id": appeal.policy_id,
            "status": "reviewed" if review else "pending_review",
            "appeal": appeal.payload,
            "contested_decision": present_event(contested) if contested else None,
            "review": present_event(review) if review else None,
            "created_at": appeal.created_at.isoformat(),
        })
    return rows


@app.post("/api/broker/appeals/{appeal_id}/review")
def review_appeal(
    appeal_id: str,
    body: BrokerAppealReview,
    user: User = Depends(current_user),
    db: Session = Depends(session),
    idempotency_key: str = Header(),
):
    appeal = own(db, ServicingEvent, appeal_id, user, lock=True)

    def action():
        if appeal.record_type != "appeal":
            raise HTTPException(422, "This record is not an appeal.")
        already_reviewed = db.scalar(select(ServicingEvent).where(ServicingEvent.record_type == "appeal_review", ServicingEvent.supersedes_id == appeal.id))
        if already_reviewed:
            raise HTTPException(409, "This appeal has already been reviewed.")
        contested = db.scalar(select(ServicingEvent).where(ServicingEvent.id == appeal.supersedes_id))
        if not contested or contested.record_type != "decision":
            raise HTTPException(409, "The original servicing decision is unavailable.")
        policy = own(db, Policy, appeal.policy_id, user, lock=True)
        review = ServicingEvent(
            owner_id=user.id,
            policy_id=policy.id,
            root_id=appeal.root_id,
            record_type="appeal_review",
            kind="appeal",
            effective_month=contested.effective_month,
            sequence=_next_servicing_sequence(db, policy.id),
            payload={"action": body.action, "note": body.note, "contested_event_id": contested.root_id},
            supersedes_id=appeal.id,
            reviewer_action=body.action,
        )
        db.add(review)
        effective = None
        if body.action == "overturn":
            corrected = {**contested.payload}
            if body.corrected_policy_month is not None:
                corrected["policy_month"] = body.corrected_policy_month
            if body.corrected_provider_tier:
                corrected["provider_tier"] = body.corrected_provider_tier
            provisional = evaluate_servicing(policy.snapshot["plan"], corrected, empty_ledger())
            revision = ServicingEvent(
                owner_id=user.id,
                policy_id=policy.id,
                root_id=contested.root_id,
                record_type="revision",
                kind=contested.kind,
                effective_month=corrected.get("policy_month"),
                sequence=_next_servicing_sequence(db, policy.id) + 1,
                payload=corrected,
                outcome=provisional["outcome"],
                reason_code=provisional["reason_code"],
                plan_pays_fils=provisional["plan_pays_fils"],
                member_pays_fils=provisional["member_pays_fils"],
                calculation=provisional["calculation"],
                ledger_before=provisional["ledger_before"],
                ledger_after=provisional["ledger_after"],
                supersedes_id=contested.id,
                reviewer_action="overturn",
            )
            db.add(revision)
            db.flush()
            ledger, decisions = rebuild_projection(db, policy)
            effective = decisions[contested.root_id]
            policy.version += 1
        else:
            db.flush()
            ledger, _ = rebuild_projection(db, policy)
        effective_summary = (
            {
                "event_id": effective["event_id"],
                "outcome": effective["outcome"],
                "reason_code": effective["reason_code"],
                "plan_pays_fils": effective["plan_pays_fils"],
                "member_pays_fils": effective["member_pays_fils"],
            }
            if effective
            else present_event(contested)
        )
        db.add(ReviewDecision(owner_id=user.id, servicing_event_id=appeal.id, action=body.action, note=body.note, before=present_event(contested), after=effective_summary))
        db.add(Audit(owner_id=user.id, action="servicing_appeal_reviewed", subject_id=appeal.id, details={"action": body.action, "contested_event_id": contested.root_id}))
        return {"appeal_id": appeal.id, "status": "reviewed", "action": body.action, "effective_decision": effective_summary if effective else None, "ledger": ledger}

    return command(db, user, idempotency_key, {"action": "review_appeal", "appeal_id": appeal_id, **body.model_dump()}, action)


class ImportRequest(BaseModel):
    plan_name: str = Field(min_length=1, max_length=100)
    insurer_name: str = Field(min_length=1, max_length=100)
    start_date: date


@app.post("/api/policies/import")
def import_policy(
    body: ImportRequest,
    user: User = Depends(current_user),
    db: Session = Depends(session),
    idempotency_key: str = Header(),
):
    def action():
        policy = Policy(
            owner_id=user.id,
            status="unverified_import",
            snapshot={
                "plan": {"name": body.plan_name, "insurer_name": body.insurer_name},
                "start_date": body.start_date.isoformat(),
                "mode": "unverified_import",
                "source": "User-entered; policy terms not verified",
            },
        )
        db.add(policy)
        db.flush()
        return {"id": policy.id}

    return command(db, user, idempotency_key, {"action": "import", **body.model_dump(mode="json")}, action)


@app.post("/api/instalments/{installment_id}/payment-order")
def payment_order(
    installment_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(session),
    idempotency_key: str = Header(),
):
    installment = own(db, Installment, installment_id, user, lock=True)

    def action():
        if installment.status == "paid":
            raise HTTPException(409, "This instalment is already paid.")
        if own(db, Policy, installment.policy_id, user).status != "demo_active":
            raise HTTPException(422, "Test payments cannot settle a real or imported policy.")
        pending = db.scalar(
            select(PaymentOrder).where(
                PaymentOrder.installment_id == installment.id, PaymentOrder.status.in_(["created", "pending"])
            )
        )
        if pending:
            return order_response(pending)
        provider = settings().payment_provider
        if provider not in {"simulator", "razorpay"}:
            raise HTTPException(503, "No supported sandbox provider is configured.")
        order = PaymentOrder(
            owner_id=user.id,
            installment_id=installment.id,
            provider=provider,
            amount=installment.amount,
            currency=installment.currency,
        )
        db.add(order)
        db.flush()
        if provider == "razorpay":
            external = razorpay_request(
                "POST", "orders", {"amount": order.amount, "currency": order.currency, "receipt": order.id}
            )
            order.provider_order_id = external["id"]
        return order_response(order)

    return command(db, user, idempotency_key, {"action": "payment_order", "id": installment_id}, action)


def order_response(order):
    return {
        "id": order.id,
        "provider": order.provider,
        "status": order.status,
        "provider_order_id": order.provider_order_id,
        "amount": order.amount,
        "currency": order.currency,
        "key_id": settings().razorpay_key_id if order.provider == "razorpay" else None,
    }


@app.post("/api/payment-orders/{order_id}/simulate")
def simulate(
    order_id: str,
    body: SimulateRequest,
    user: User = Depends(current_user),
    db: Session = Depends(session),
    idempotency_key: str = Header(),
):
    order = own(db, PaymentOrder, order_id, user, lock=True)

    def action():
        if order.provider != "simulator":
            raise HTTPException(422, "Only locally simulated orders use this action.")
        if order.status != "created":
            raise HTTPException(409, "This simulated order is already complete.")
        if body.result == "captured":
            receipt = settle(db, order, "local_" + order.id)
            return {"status": "captured", "receipt_id": receipt.id, "mode": "simulated_locally"}
        order.status = body.result
        return {"status": body.result}

    return command(
        db, user, idempotency_key, {"action": "simulate", "order": order_id, **body.model_dump()}, action
    )


@app.post("/api/payments/verify")
def verify_payment(body: VerifyPayment, user: User = Depends(current_user), db: Session = Depends(session)):
    order = own(db, PaymentOrder, body.order_id, user, lock=True)
    result = verify_order(db, order, body.razorpay_payment_id, body.razorpay_signature)
    db.commit()
    return result


@app.post("/api/webhooks/razorpay")
async def webhook(request: Request, db: Session = Depends(session)):
    secret = settings().razorpay_webhook_secret
    if not secret:
        raise HTTPException(503, "Webhook is not configured.")
    raw = await request.body()
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, request.headers.get("x-razorpay-signature", "")):
        raise HTTPException(422, "Webhook signature did not verify.")
    body = json.loads(raw)
    if body.get("event") != "payment.captured":
        return {"received": True, "settled": False}
    entity = body.get("payload", {}).get("payment", {}).get("entity", {})
    order = db.scalar(
        select(PaymentOrder)
        .where(PaymentOrder.provider_order_id == entity.get("order_id"), PaymentOrder.provider == "razorpay")
        .with_for_update()
    )
    if not order:
        return {"received": True, "settled": False}
    result = verify_order(db, order, entity.get("id", ""))
    db.commit()
    return result


@app.get("/api/policies/{policy_id}/updates")
def updates(policy_id: str, user: User = Depends(current_user), db: Session = Depends(session)):
    own(db, Policy, policy_id, user)
    return {
        "items": [],
        "message": "No verified policy notices are available. Public news does not change your saved policy terms.",
    }


@app.get("/api/providers")
def providers(plan_id: str, emirate: str = "Dubai", user: User = Depends(current_user)):
    if plan_id not in {p["id"] for p in plans()}:
        raise HTTPException(404, "Plan not found.")
    rows = [
        {
            "id": "demo-clinic",
            "name": "Harbour Community Clinic",
            "tier": "in_network_clinic",
            "emirate": "Dubai",
            "lat": 25.196,
            "lng": 55.274,
            "plans": ["plan_a", "plan_b", "plan_c"],
        },
        {
            "id": "demo-hospital",
            "name": "Crescent Private Hospital",
            "tier": "private_hospital",
            "emirate": "Dubai",
            "lat": 25.212,
            "lng": 55.291,
            "plans": ["plan_b", "plan_c"],
        },
        {
            "id": "demo-specialist",
            "name": "Palm Specialist Hospital",
            "tier": "premium_private_hospital",
            "emirate": "Dubai",
            "lat": 25.181,
            "lng": 55.259,
            "plans": ["plan_c"],
        },
    ]
    return {
        "items": [
            dict(r, source="Synthetic provider directory v1", mode="synthetic_demo")
            for r in rows
            if plan_id in r["plans"] and r["emirate"] == emirate
        ],
        "notice": "Fictional facilities and approximate demonstration locations. Not a real care directory.",
    }
