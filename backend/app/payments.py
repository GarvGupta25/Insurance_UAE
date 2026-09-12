import hashlib
import hmac

import httpx
from fastapi import HTTPException
from sqlalchemy import select

from .config import settings
from .models import Installment, Receipt


def razorpay_request(method, path, payload=None):
    cfg = settings()
    if not cfg.razorpay_key_id.startswith("rzp_test_") or not cfg.razorpay_key_secret:
        raise HTTPException(503, "A Razorpay test account is not configured. Live keys are not accepted.")
    try:
        response = httpx.request(
            method,
            "https://api.razorpay.com/v1/" + path,
            json=payload,
            auth=(cfg.razorpay_key_id, cfg.razorpay_key_secret),
            timeout=15,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        raise HTTPException(
            503, "The test provider could not confirm this operation. Reconcile before retrying."
        ) from None


def settle(db, order, payment_id):
    prior = db.scalar(select(Receipt).where(Receipt.order_id == order.id))
    if prior:
        return prior
    installment = db.scalar(
        select(Installment).where(Installment.id == order.installment_id).with_for_update()
    )
    if installment.status == "paid":
        raise HTTPException(409, "This instalment already has a receipt. No second settlement was recorded.")
    receipt = Receipt(
        owner_id=order.owner_id,
        order_id=order.id,
        installment_id=installment.id,
        provider_payment_id=payment_id,
        amount=order.amount,
        currency=order.currency,
        provider=order.provider,
    )
    db.add(receipt)
    installment.status, order.status = "paid", "captured"
    db.flush()
    return receipt


def verify_order(db, order, payment_id, signature=None):
    if order.provider != "razorpay":
        raise HTTPException(422, "This is not a Razorpay order.")
    if signature is not None:
        expected = hmac.new(
            settings().razorpay_key_secret.encode(),
            f"{order.provider_order_id}|{payment_id}".encode(),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise HTTPException(422, "Payment signature did not verify.")
    payment = razorpay_request("GET", "payments/" + payment_id)
    if (
        payment.get("order_id") != order.provider_order_id
        or payment.get("amount") != order.amount
        or payment.get("currency") != order.currency
    ):
        raise HTTPException(422, "Payment does not match the saved order.")
    if payment.get("status") != "captured":
        return {"status": "pending", "message": "The provider has not confirmed captured funds."}
    receipt = settle(db, order, payment_id)
    return {"status": "captured", "receipt_id": receipt.id}
