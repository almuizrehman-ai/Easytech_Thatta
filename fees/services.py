"""
Business logic for the fees application.

All financial writes go through these functions. Views call services;
models hold state. This separation makes testing, auditing, and future
refactoring tractable.
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from students.models import Student

from . import constants as C
from .models import FeeAdjustment, FeeObligation, FeePayment, _default_due_date_for_month


# ============================================================
# RESULT TYPES
# ============================================================
@dataclass
class LedgerResult:
    """Result of ledger generation."""
    created: int = 0
    skipped: int = 0
    admission_created: bool = False
    registration_created: bool = False
    months_created: int = 0
    error: str | None = None


@dataclass
class PaymentResult:
    """Result of record_payment."""
    success: bool = False
    payment: FeePayment | None = None
    error: str | None = None


# ============================================================
# LEDGER GENERATION
# ============================================================
def _month_iter(start: date, end: date):
    """
    Yield first-of-month dates from `start` to `end`, inclusive.

    Example:
        _month_iter(2027-03-01, 2028-02-01) yields
        2027-03-01, 2027-04-01, ..., 2028-02-01
    """
    current = start.replace(day=1)
    end_month = end.replace(day=1)
    while current <= end_month:
        yield current
        # Advance one month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)


def generate_ledger_for_student(student: Student, *, fail_silently: bool = False) -> LedgerResult:
   
    # Ab sirf khaali result return karega, koi obligation auto generate nahi hogi
    return LedgerResult()

    if not student.batch_id:
        result.error = "Student ka koi batch assign nahi hai."
        if not fail_silently:
            raise ValueError(result.error)
        return result

    batch = student.batch
    try:
        with transaction.atomic():
            # ---------- 1. Admission fee ----------
            if student.admission_fee_amount and student.admission_fee_amount > C.ZERO:
                admission_category = _find_admission_category(student)
                exists = FeeObligation.objects.filter(
                    student=student,
                    obligation_type=C.TYPE_ADMISSION,
                    fee_category=admission_category,
                ).exists()

                if not exists:
                    obl = FeeObligation.objects.create(
                        student=student,
                        fee_category=admission_category,
                        obligation_type=C.TYPE_ADMISSION,
                        obligation_month=None,
                        description="Admission Fee",
                        amount=student.admission_fee_amount,
                        due_date=_default_due_date_for_month(student.admission_date),
                        notes="Auto-generated at admission.",
                    )
                    
                    # Agar form mein staff ne "Admission Fee Paid" tick kiya hai
                    if student.admission_fee_paid:
                        # To direct paid mark kar dein aur payment history create karein
                        obl.status = C.STATUS_PAID
                        obl.save()
                        
                        FeePayment.objects.create(
                            obligation=obl,
                            amount=obl.amount,
                            payment_method=C.METHOD_CASH,
                            payment_date=timezone.now(),
                            received_by=student.created_by,
                            notes="Marked as paid during admission."
                        )
                    result.admission_created = True
                    result.created += 1
                else:
                    result.skipped += 1

            # ---------- 2. Registration fee ----------
            if student.registration_fee_amount and student.registration_fee_amount > C.ZERO:
                reg_category = _find_registration_category(student)
                exists = FeeObligation.objects.filter(
                    student=student,
                    obligation_type=C.TYPE_REGISTRATION,
                    fee_category=reg_category,
                ).exists()

                if not exists:
                    FeeObligation.objects.create(
                        student=student,
                        fee_category=reg_category,
                        obligation_type=C.TYPE_REGISTRATION,
                        obligation_month=None,
                        description="Registration Fee",
                        amount=student.registration_fee_amount,
                        due_date=_default_due_date_for_month(student.admission_date),
                        notes="Auto-generated at admission.",
                    )
                    result.registration_created = True
                    result.created += 1
                else:
                    result.skipped += 1

            # ---------- 3. Monthly fee obligations ----------
            monthly_fee = student.monthly_fee_at_admission or batch.monthly_fee
            if monthly_fee and monthly_fee > C.ZERO:
                # Batch duration: from batch.start_month to batch.end_month INCLUSIVE
                for month in _month_iter(batch.start_month, batch.end_month):
                    exists = FeeObligation.objects.filter(
                        student=student,
                        obligation_type=C.TYPE_MONTHLY,
                        obligation_month=month,
                        fee_category=None,
                    ).exists()

                    if exists:
                        result.skipped += 1
                        continue

                    FeeObligation.objects.create(
                        student=student,
                        fee_category=None,
                        obligation_type=C.TYPE_MONTHLY,
                        obligation_month=month,
                        description=f"Monthly Fee — {month.strftime('%b %Y')}",
                        amount=monthly_fee,
                        due_date=_default_due_date_for_month(month),
                        notes="Auto-generated from batch duration.",
                    )
                    result.months_created += 1
                    result.created += 1

    except Exception as exc:
        result.error = str(exc)
        if not fail_silently:
            raise

    return result


def _find_admission_category(student: Student):
    """Return the FeeCategory that names an admission fee, if any."""
    return student.course.fee_categories.filter(
        is_active=True,
        name__icontains='admission',
    ).order_by('name').first()


def _find_registration_category(student: Student):
    """Return the FeeCategory that names a registration fee, if any."""
    return student.course.fee_categories.filter(
        is_active=True,
        name__icontains='registration',
    ).order_by('name').first()


# ============================================================
# RECORD PAYMENT
# ============================================================
def record_payment(
    obligation: FeeObligation,
    amount: Decimal,
    received_by,
    *,
    payment_method: str = C.METHOD_CASH,
    payment_date=None,
    notes: str = '',
) -> PaymentResult:
    """
    Record a payment against a fee obligation.

    Concurrency: locks the obligation row for update; two simultaneous
    calls are serialized so overshoot is impossible.

    Validation:
        - amount > 0
        - amount <= outstanding_amount
        - obligation not waived
        - obligation not already fully paid

    Returns PaymentResult with success/payment/error.
    """
    amount = Decimal(str(amount))

    if amount <= C.ZERO:
        return PaymentResult(success=False, error="Payment amount 0 se zyada honi chahiye.")

    try:
        with transaction.atomic():
            # Lock the obligation
            locked = (
                FeeObligation.objects
                .select_for_update()
                .get(pk=obligation.pk)
            )

            if locked.is_waived:
                return PaymentResult(
                    success=False,
                    error="Yeh obligation waive ho chuki hai — payment possible nahi.",
                )

            outstanding = locked.outstanding_amount
            if outstanding <= C.ZERO:
                return PaymentResult(
                    success=False,
                    error="Yeh obligation already fully paid hai.",
                )

            if amount > outstanding:
                return PaymentResult(
                    success=False,
                    error=f"Amount outstanding se zyada hai. Baqi: Rs.{outstanding:.2f}",
                )

            payment = FeePayment.objects.create(
                obligation=locked,
                amount=amount,
                payment_method=payment_method,
                payment_date=payment_date or timezone.now(),
                received_by=received_by,
                notes=notes,
            )

            # model save triggers refresh_status — but do it explicitly too
            locked.refresh_status()

            return PaymentResult(success=True, payment=payment)

    except Exception as exc:
        return PaymentResult(success=False, error=str(exc))


# ============================================================
# WAIVER / CONCESSION (PRINCIPAL ONLY)
# ============================================================
def apply_waiver(
    obligation: FeeObligation,
    reason: str,
    approved_by,
) -> FeeAdjustment:
    """
    Apply a full waiver to an obligation.

    Effect:
        Obligation becomes WAIVED.
        outstanding_amount → 0 (via is_waived property).
        Existing payments preserved (for historical audit).

    Principal-only (view layer enforces; this function should also be
    called only from a principal-guarded view).
    """
    if not reason or not reason.strip():
        raise ValidationError("Waiver reason zaroori hai (audit trail ke liye).")

    with transaction.atomic():
        locked = (
            FeeObligation.objects
            .select_for_update()
            .get(pk=obligation.pk)
        )

        if locked.is_waived:
            raise ValidationError("Yeh obligation pehle se waive hai.")

        adjustment = FeeAdjustment.objects.create(
            obligation=locked,
            adjustment_type=C.ADJUSTMENT_WAIVER,
            amount=C.ZERO,  # full waiver — implicit
            reason=reason,
            approved_by=approved_by,
        )
        locked.refresh_status()
        return adjustment


def apply_concession(
    obligation: FeeObligation,
    amount: Decimal,
    reason: str,
    approved_by,
    *,
    adjustment_type: str = C.ADJUSTMENT_CONCESSION,
) -> FeeAdjustment:
    """
    Apply a partial concession (or discount) to an obligation.

    Effect:
        outstanding_amount reduced by `amount`.
        Existing payments preserved.
        Cap checked via FeeAdjustment.clean() → effective_amount not negative.

    Principal-only.
    """
    amount = Decimal(str(amount))
    if amount <= C.ZERO:
        raise ValidationError("Concession amount 0 se zyada honi chahiye.")
    if not reason or not reason.strip():
        raise ValidationError("Concession reason zaroori hai.")

    with transaction.atomic():
        locked = (
            FeeObligation.objects
            .select_for_update()
            .get(pk=obligation.pk)
        )

        if locked.is_waived:
            raise ValidationError("Waive-shuda obligation pe concession apply nahi hoti.")

        adjustment = FeeAdjustment.objects.create(
            obligation=locked,
            adjustment_type=adjustment_type,
            amount=amount,
            reason=reason,
            approved_by=approved_by,
        )
        # FeeAdjustment.clean() already validates cap; call full_clean
        # for safety:
        adjustment.full_clean()
        locked.refresh_status()
        return adjustment


# ============================================================
# REVERSAL (Phase 8 workflow — stub here for completeness)
# ============================================================
def reverse_payment(payment: FeePayment, reason: str, performed_by) -> FeePayment:
    """
    Reverse a payment (audit-preserving).

    Effect:
        payment.is_reversed = True
        payment.reversed_at = now
        payment.reversed_by = performed_by
        payment.reversal_reason = reason
        Original row preserved for audit.
        Obligation status refreshed (outstanding increases).

    Phase 8 will add views for this; services are ready now.
    """
    if not reason or not reason.strip():
        raise ValidationError("Reversal reason zaroori hai.")

    if payment.is_reversed:
        raise ValidationError("Yeh payment already reversed hai.")

    with transaction.atomic():
        locked = (
            FeePayment.objects
            .select_for_update()
            .get(pk=payment.pk)
        )
        locked.is_reversed = True
        locked.reversed_at = timezone.now()
        locked.reversed_by = performed_by
        locked.reversal_reason = reason
        locked.save(update_fields=[
            'is_reversed', 'reversed_at', 'reversed_by',
            'reversal_reason', 'updated_at',
        ])
        locked.obligation.refresh_status()
        return locked


# ============================================================
# SUMMARY (dashboards + reports)
# ============================================================
def get_student_fee_summary(student: Student) -> dict:
    """
    Aggregate fee summary for a single student.

    Returns dict:
        {
            'total_obligated': Decimal,     # sum of effective amounts (post-concession)
            'total_paid': Decimal,           # sum of non-reversed payments
            'total_outstanding': Decimal,    # total_obligated - total_paid
            'total_overdue': Decimal,        # sum of outstanding for overdue obligations
            'count_obligations': int,
            'count_overdue': int,
        }
    """
    obligations = FeeObligation.objects.filter(student=student).prefetch_related(
        'payments', 'adjustments'
    )

    total_obligated = C.ZERO
    total_paid = C.ZERO
    total_overdue = C.ZERO
    count_overdue = 0

    for obl in obligations:
        if obl.is_waived:
            continue
        total_obligated += obl.effective_amount
        total_paid += obl.paid_amount
        if obl.is_overdue:
            total_overdue += obl.outstanding_amount
            count_overdue += 1

    return {
        'total_obligated': total_obligated,
        'total_paid': total_paid,
        'total_outstanding': max(C.ZERO, total_obligated - total_paid),
        'total_overdue': total_overdue,
        'count_obligations': obligations.count(),
        'count_overdue': count_overdue,
    }


def get_ledger_for_student(student: Student):
    """
    Return all obligations for a student, ordered chronologically.

    Prefetched payments + adjustments for N+1 avoidance.
    """
    return (
        FeeObligation.objects
        .filter(student=student)
        .select_related('fee_category')
        .prefetch_related(
            'payments__received_by',
            'adjustments__approved_by',
        )
        .order_by('obligation_month', 'due_date', 'id')
    )


# ============================================================
# UTILITIES
# ============================================================
def mark_overdue_obligations() -> int:
    """
    Optional bulk updater — sync `status='overdue'` for all
    past-due obligations with outstanding balance.

    Not required for correctness (effective_status recomputes live),
    but useful for fast dashboard queries that filter on stored status.

    Returns count of obligations updated.
    """
    today = timezone.localdate()
    candidates = FeeObligation.objects.filter(
        status__in=(C.STATUS_PENDING, C.STATUS_PARTIAL),
        due_date__lt=today,
    ).exclude(status=C.STATUS_WAIVED)

    updated = 0
    for obl in candidates.iterator(chunk_size=500):
        if obl.outstanding_amount > C.ZERO:
            FeeObligation.objects.filter(pk=obl.pk).update(
                status=C.STATUS_OVERDUE,
                updated_at=timezone.now(),
            )
            updated += 1

    return updated