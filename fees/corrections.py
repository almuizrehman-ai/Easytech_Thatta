"""
Payment correction workflow services.

Staff submit a correction request against a payment (with reason).
Principal approves → reversal + replacement payment created.
Principal rejects → request closed, no changes.
"""
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from audit.models import AuditLog
from audit.services import log_action, serialize_model

from . import constants as C
from . import services as fee_services
from .models import FeePayment, PaymentCorrectionRequest


# ============================================================
# SUBMIT (Staff)
# ============================================================
def submit_correction(
    payment: FeePayment,
    requested_by,
    correction_type: str,
    reason: str,
    new_amount: Decimal | None = None,
    new_payment_method: str = '',
    new_payment_date=None,
    notes: str = '',
) -> PaymentCorrectionRequest:
    """Staff submits a correction request against an existing payment."""
    if payment.is_reversed:
        raise ValidationError("Yeh payment pehle se reversed hai. Dobara correction nahi ho sakti.")

    if not reason or not reason.strip():
        raise ValidationError("Correction reason zaroori hai.")

    # Only one pending correction per payment
    if PaymentCorrectionRequest.objects.filter(
        payment=payment, status=PaymentCorrectionRequest.STATUS_PENDING,
    ).exists():
        raise ValidationError(
            "Is payment ke liye pehle se ek pending correction request hai. "
            "Principal ke decision ka intezaar karein."
        )

    # Type-specific validation
    if correction_type == PaymentCorrectionRequest.TYPE_AMOUNT_CHANGE:
        if new_amount is None:
            raise ValidationError("Amount change ke liye new_amount required hai.")
        if new_amount <= C.ZERO:
            raise ValidationError("New amount 0 se zyada honi chahiye.")
        if new_amount == payment.amount:
            raise ValidationError("New amount current se different honi chahiye.")

    elif correction_type == PaymentCorrectionRequest.TYPE_METHOD_CHANGE:
        if not new_payment_method:
            raise ValidationError("Method change ke liye new_payment_method required hai.")
        if new_payment_method not in dict(C.PAYMENT_METHOD_CHOICES):
            raise ValidationError("Sahi payment method select karein.")
        if new_payment_method == payment.payment_method:
            raise ValidationError("New method current se different honi chahiye.")

    elif correction_type == PaymentCorrectionRequest.TYPE_DATE_CHANGE:
        if not new_payment_date:
            raise ValidationError("Date change ke liye new_payment_date required hai.")

    with transaction.atomic():
        req = PaymentCorrectionRequest.objects.create(
            payment=payment,
            requested_by=requested_by,
            correction_type=correction_type,
            reason=reason.strip(),
            new_amount=new_amount,
            new_payment_method=new_payment_method,
            new_payment_date=new_payment_date,
            notes=notes.strip(),
            status=PaymentCorrectionRequest.STATUS_PENDING,
        )

        log_action(
            user=requested_by,
            action=AuditLog.ACTION_CREATE,
            module=AuditLog.MODULE_FEES,
            target=req,
            object_repr=f"Correction #{req.pk} for {payment.transaction_id}",
            change_summary=(
                f"Correction request submitted: {req.get_correction_type_display()} "
                f"on payment {payment.transaction_id}"
            ),
            new_value=serialize_model(req),
        )

        return req


# ============================================================
# APPROVE (Principal)
# ============================================================
def approve_correction(correction: PaymentCorrectionRequest, approved_by, approval_notes: str = '') -> dict:
    """
    Principal approves a correction request.
    (Ab yeh function 3 positional arguments accept karta hai)
    """
    if correction.status != PaymentCorrectionRequest.STATUS_PENDING:
        raise ValidationError(
            f"Sirf pending requests approve ho sakti hain. Current status: {correction.status}"
        )

    payment = correction.payment
    if payment.is_reversed:
        raise ValidationError("Yeh payment pehle se reversed hai.")

    with transaction.atomic():
        # Determine replacement values
        if correction.correction_type == PaymentCorrectionRequest.TYPE_AMOUNT_CHANGE:
            replacement_amount = correction.new_amount
            replacement_method = payment.payment_method
            replacement_date = payment.payment_date
        elif correction.correction_type == PaymentCorrectionRequest.TYPE_METHOD_CHANGE:
            replacement_amount = payment.amount
            replacement_method = correction.new_payment_method
            replacement_date = payment.payment_date
        elif correction.correction_type == PaymentCorrectionRequest.TYPE_DATE_CHANGE:
            replacement_amount = payment.amount
            replacement_method = payment.payment_method
            replacement_date = correction.new_payment_date or payment.payment_date
        else:
            raise ValidationError(f"Unknown correction type: {correction.correction_type}")

        # Reverse original payment
        fee_services.reverse_payment(
            payment=payment,
            reason=f"Correction #{correction.pk}: {correction.reason[:200]}",
            performed_by=approved_by,
        )

        # Create replacement payment
        result = fee_services.record_payment(
            obligation=payment.obligation,
            amount=replacement_amount,
            payment_method=replacement_method,
            payment_date=replacement_date,
            notes=(
                f"Replacement for {payment.transaction_id} (correction #{correction.pk}). "
                f"{correction.notes}"
            ).strip(),
            received_by=payment.received_by,
        )

        if not result.success:
            raise ValidationError(f"Replacement payment record nahi hui: {result.error}")

        # Mark request approved
        correction.status = PaymentCorrectionRequest.STATUS_APPROVED
        correction.reviewed_by = approved_by
        correction.reviewed_at = timezone.now()
        correction.review_notes = approval_notes.strip()
        correction.replacement_payment = result.payment
        correction.save()

        # Audit log
        log_action(
            user=approved_by,
            action=AuditLog.ACTION_APPROVE,
            module=AuditLog.MODULE_FEES,
            target=correction,
            object_repr=f"Correction #{correction.pk}",
            change_summary=(
                f"Approved correction on {payment.transaction_id} → "
                f"replacement {result.payment.transaction_id}"
            ),
            new_value=serialize_model(correction),
            notes=approval_notes,
        )

        return {
            'original_payment': payment,
            'replacement_payment': result.payment,
        }


# ============================================================
# REJECT (Principal)
# ============================================================
def reject_correction(correction: PaymentCorrectionRequest, rejected_by, rejection_reason: str) -> PaymentCorrectionRequest:
    """
    Principal rejects a correction request.
    (Ab yeh function bhi 3 positional arguments accept karta hai)
    """
    if correction.status != PaymentCorrectionRequest.STATUS_PENDING:
        raise ValidationError(
            f"Sirf pending requests reject ho sakti hain. Current status: {correction.status}"
        )

    if not rejection_reason or not rejection_reason.strip():
        raise ValidationError("Rejection reason zaroori hai.")

    with transaction.atomic():
        correction.status = PaymentCorrectionRequest.STATUS_REJECTED
        correction.reviewed_by = rejected_by
        correction.reviewed_at = timezone.now()
        correction.review_notes = rejection_reason.strip()
        correction.save()

        log_action(
            user=rejected_by,
            action=AuditLog.ACTION_REJECT,
            module=AuditLog.MODULE_FEES,
            target=correction,
            object_repr=f"Correction #{correction.pk}",
            change_summary=f"Rejected correction on {correction.payment.transaction_id}",
            notes=rejection_reason,
        )

        return correction


# ============================================================
# CANCEL (by requester, while pending)
# ============================================================
def cancel_correction(correction: PaymentCorrectionRequest, cancelled_by, reason: str = '') -> PaymentCorrectionRequest:
    """Requester can cancel their own pending correction."""
    if correction.status != PaymentCorrectionRequest.STATUS_PENDING:
        raise ValidationError("Sirf pending requests cancel ho sakti hain.")

    if correction.requested_by_id != getattr(cancelled_by, 'pk', None):
        raise ValidationError("Sirf requester apni request cancel kar sakta hai.")

    with transaction.atomic():
        correction.status = PaymentCorrectionRequest.STATUS_CANCELLED
        correction.reviewed_by = cancelled_by
        correction.reviewed_at = timezone.now()
        correction.review_notes = reason.strip() or "Cancelled by requester."
        correction.save()

        log_action(
            user=cancelled_by,
            action=AuditLog.ACTION_UPDATE,
            module=AuditLog.MODULE_FEES,
            target=correction,
            object_repr=f"Correction #{correction.pk}",
            change_summary=f"Cancelled correction on {correction.payment.transaction_id}",
            notes=reason,
        )

        return correction