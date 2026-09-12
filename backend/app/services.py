from datetime import datetime, timezone

from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import select

from .config import settings
from .contracts import Facts
from .domain import digest
from .models import Audit, Command, Profile, ProfileVersion

SENSITIVE = {"passport_number", "emirates_id"}


def own(db, cls, ident, user, lock=False):
    query = select(cls).where(cls.id == ident, cls.owner_id == user.id)
    if lock:
        query = query.with_for_update()
    row = db.scalar(query)
    if row is None:
        raise HTTPException(404, "This record is unavailable.")
    return row


def profile(db, user, lock=False):
    query = select(Profile).where(Profile.owner_id == user.id)
    if lock:
        query = query.with_for_update()
    row = db.scalar(query)
    if not row:
        row = Profile(owner_id=user.id, facts={}, provenance={})
        db.add(row)
        db.flush()
    return row


def visible_facts(facts):
    return {
        key: ("•••• saved securely" if key in SENSITIVE and value else value) for key, value in facts.items()
    }


def apply_facts(db, user, request, source="manual"):
    row = profile(db, user, lock=True)
    if row.version != request.expected_version:
        raise HTTPException(409, "Your profile changed. Reload before applying these details.")
    changes = request.changes
    if any(key in SENSITIVE and value and str(value).startswith("••••") for key, value in changes.items()):
        raise HTTPException(422, "Enter a new identity number or leave the saved field unchanged.")
    plain = {key: value for key, value in row.facts.items() if key not in SENSITIVE}
    plain.update(changes)
    validated = Facts.model_validate(plain).model_dump(mode="json", exclude_none=True)
    for key in SENSITIVE:
        if key in changes:
            value = changes[key]
            if value:
                if not settings().document_encryption_key:
                    raise HTTPException(
                        503,
                        "Secure identity storage is not configured. Continue without the document number.",
                    )
                validated[key] = (
                    Fernet(settings().document_encryption_key.encode()).encrypt(value.encode()).decode()
                )
            else:
                validated.pop(key, None)
        elif key in row.facts:
            validated[key] = row.facts[key]
    row.version += 1
    row.facts = validated
    row.provenance = {
        **row.provenance,
        **{
            key: {
                "source": source,
                "message_id": request.source_message_id,
                "confirmed_at": datetime.now(timezone.utc).isoformat(),
            }
            for key in changes
        },
    }
    db.add(ProfileVersion(owner_id=user.id, profile_id=row.id, version=row.version, facts=validated))
    db.add(
        Audit(
            owner_id=user.id,
            action="profile_updated",
            subject_id=row.id,
            details={"fields": sorted(changes), "version": row.version},
        )
    )
    return row


def command(db, user, key, payload, action):
    if not key or len(key) > 100:
        raise HTTPException(422, "A valid idempotency key is required.")
    # Lock the owner profile to serialize commands, including concurrent first submission/payment retries.
    profile(db, user, lock=True)
    hashed = digest(payload)
    prior = db.scalar(select(Command).where(Command.owner_id == user.id, Command.key == key))
    if prior:
        if prior.payload_hash != hashed:
            raise HTTPException(409, "This request key was already used for different details.")
        return prior.response
    result = action()
    db.add(Command(owner_id=user.id, key=key, payload_hash=hashed, response=result))
    db.commit()
    return result
