"""
Models for the fees application.

Financial ledger architecture:
    FeeObligation  — one row per (student, type, month/category)
    FeePayment     — multiple payments per obligation
    FeeAdjustment  — waivers / concessions approved by Principal

Design principles (from spec):
- Obligations are NEVER deleted. Waived via status.
- Payments are NEVER deleted or updated. Corrections Phase 8 use reversal.
- Status is computed and persisted (for fast queries) but always
  re-derivable from payments + adjustments.
- overdue is derived from (due_date < today) AND outstanding > 0.
- Every payment gets an immutable transaction_id.
- All Decimal math, no floats.
"""
import calendar
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import Sum
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser
from courses.models import FeeCategory
from students.models import Student

from . import constants as C


# ============================================================
# HELPERS
# ============================================================
def _first_of_month(date_obj):
    """Normalize to first of month."""
    return date_obj.replace(day=1)


def _default_due_date_for_month(month_date):
    """
    Given a month (first of month), return the due date.
    Due date = day `DUE_DAY_OF_MONTH` of that month.
    If that day exceeds month's length, use last day.
    """
    year, month = month_date.year, month_date.month
    last_day = calendar.monthrange(year, month)[1]
    day = min(C.DUE_DAY_OF_MONTH, last_day)
    return month_date.replace(day=day)


# ============================================================
# FEE OBLIGATION
# ============================================================
class FeeObligation(models.Model):
    """
    A single fee obligation for a student.

    Examples:
        - Admission fee (one-time, obligation_type='admission')
        - Registration fee (one-time, obligation_type='registration')
        - Monthly fee for March 2027 (obligation_type='monthly',
          obligation_month=2027-03-01)

    The obligation is created automatically by
    fees.services.generate_ledger_for_student() at admission time,
    including backdated months from batch.start_month.
    """

    student = models.ForeignKey(
        Student,
        on_delete=models.PROTECT,
        related_name='fee_obligations',
        db_index=True,
    )
    fee_category = models.ForeignKey(
        FeeCategory,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='obligations',
        help_text="Optional — linked to course fee category.",
    )
    obligation_type = models.CharField(
        max_length=20,
        choices=C.TYPE_CHOICES,
        db_index=True,
    )
    obligation_month = models.DateField(
        null=True,
        blank=True,
        db_index=True,
        help_text="First day of the month this fee belongs to. Null for non-monthly fees.",
    )
    description = models.CharField(
        max_length=200,
        blank=True,
        help_text="Human-readable label (e.g. 'Monthly fee — Mar 2027').",
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Total amount owed for this obligation.",
    )
    due_date = models.DateField(
        db_index=True,
        help_text="Payment deadline. After this, status flips to overdue if unpaid.",
    )

    status = models.CharField(
        max_length=15,
        choices=C.STATUS_CHOICES,
        default=C.STATUS_PENDING,
        db_index=True,
        help_text="Computed from payments + adjustments. Persisted for fast queries.",
    )

    notes = models.TextField(
        blank=True,
        help_text="Optional internal notes.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['student', 'obligation_month', 'due_date', 'id']
        verbose_name = 'Fee Obligation'
        verbose_name_plural = 'Fee Obligations'
        constraints = [
            # Prevent duplicate obligations of same type for same student+month
            models.UniqueConstraint(
                fields=['student', 'obligation_type', 'obligation_month', 'fee_category'],
                name='uniq_obligation_per_student_type_month',
                condition=models.Q(obligation_month__isnull=False),
            ),
        ]
        indexes = [
            models.Index(fields=['student', 'status']),
            models.Index(fields=['due_date', 'status']),
            models.Index(fields=['obligation_type', 'status']),
        ]

    # ============================================================
    # DISPLAY
    # ============================================================
    def __str__(self):
        label = self.description or self.get_obligation_type_display()
        return f"{self.student.student_id} — {label} — Rs.{self.amount} [{self.status}]"

    def get_absolute_url(self):
        return reverse('fees:obligation_detail', kwargs={'pk': self.pk})

    # ============================================================
    # COMPUTED AMOUNTS
    # ============================================================
    @property
    def paid_amount(self) -> Decimal:
        """Total of all non-reversed payments against this obligation."""
        if hasattr(self, '_paid_amount_cache'):
            return self._paid_amount_cache
        total = (
            self.payments
            .filter(is_reversed=False)
            .aggregate(s=Sum('amount'))
            .get('s')
        )
        return total or C.ZERO

    @property
    def adjustment_amount(self) -> Decimal:
        """Total of concessions/discounts (reductions — not full waivers)."""
        total = (
            self.adjustments
            .filter(is_active=True)
            .exclude(adjustment_type=C.ADJUSTMENT_WAIVER)
            .aggregate(s=Sum('amount'))
            .get('s')
        )
        return total or C.ZERO

    @property
    def is_waived(self) -> bool:
        """True if any active full-waiver adjustment exists."""
        return self.adjustments.filter(
            is_active=True,
            adjustment_type=C.ADJUSTMENT_WAIVER,
        ).exists()

    @property
    def effective_amount(self) -> Decimal:
        """Amount after concessions (waivers → 0)."""
        if self.is_waived:
            return C.ZERO
        return max(C.ZERO, self.amount - self.adjustment_amount)

    @property
    def outstanding_amount(self) -> Decimal:
        """Amount still owed = effective_amount - paid."""
        if self.is_waived:
            return C.ZERO
        return max(C.ZERO, self.effective_amount - self.paid_amount)

    @property
    def is_overdue(self) -> bool:
        """True if past due date and still has outstanding balance."""
        if self.is_waived:
            return False
        if self.outstanding_amount <= C.ZERO:
            return False
        return self.due_date < timezone.localdate()

    @property
    def effective_status(self) -> str:
        """
        Live status, ignoring the persisted `status` field.

        Priority:
            waived > paid > overdue > partial > pending
        """
        if self.is_waived:
            return C.STATUS_WAIVED
        if self.outstanding_amount <= C.ZERO:
            return C.STATUS_PAID
        if self.is_overdue:
            return C.STATUS_OVERDUE
        if self.paid_amount > C.ZERO:
            return C.STATUS_PARTIAL
        return C.STATUS_PENDING

    @property
    def status_display(self) -> str:
        """Display label for effective_status."""
        mapping = dict(C.STATUS_CHOICES)
        return mapping.get(self.effective_status, self.effective_status.title())

    def days_overdue(self) -> int:
        """Days past due (0 if not overdue)."""
        if not self.is_overdue:
            return 0
        return (timezone.localdate() - self.due_date).days

    # ============================================================
    # STATUS SYNC
    # ============================================================
    def refresh_status(self, save: bool = True) -> str:
        """
        Recompute and persist `status` from current payments + adjustments.

        Called after every payment / adjustment. Safe to call repeatedly.
        """
        new_status = self.effective_status
        if save and self.status != new_status:
            self.status = new_status
            # Use update() to avoid triggering save() side effects
            FeeObligation.objects.filter(pk=self.pk).update(
                status=new_status,
                updated_at=timezone.now(),
            )
        return new_status

    # ============================================================
    # MONTH LABEL (for templates)
    # ============================================================
    @property
    def month_label(self) -> str:
        """Human label for obligation_month, e.g. 'Mar 2027'."""
        if not self.obligation_month:
            return '—'
        return self.obligation_month.strftime('%b %Y')


# ============================================================
# FEE PAYMENT (IMMUTABLE TRANSACTION)
# ============================================================
def _generate_transaction_id() -> str:
    """
    Generate a unique payment transaction ID:
        TXN-YYYYMMDD-NNNNNN

    Sequence resets each day. Uses select_for_update to be safe
    under concurrent payments.
    """
    today = timezone.localdate()
    prefix = f"{C.PAYMENT_TXN_PREFIX}-{today.strftime('%Y%m%d')}-"

    with transaction.atomic():
        last = (
            FeePayment.objects
            .select_for_update()
            .filter(transaction_id__startswith=prefix)
            .order_by('-transaction_id')
            .values_list('transaction_id', flat=True)
            .first()
        )
        if last:
            try:
                seq = int(last.rsplit('-', 1)[1]) + 1
            except (ValueError, IndexError):
                seq = 1
        else:
            seq = 1

        # Ultra-safe: bump until free
        while FeePayment.objects.filter(
            transaction_id=f"{prefix}{seq:0{C.PAYMENT_TXN_PAD}d}"
        ).exists():
            seq += 1

        return f"{prefix}{seq:0{C.PAYMENT_TXN_PAD}d}"


class FeePayment(models.Model):
    """
    A single payment transaction against a fee obligation.

    Immutability:
        Payments are NEVER updated or deleted. Corrections Phase 8
        record a reversal (is_reversed=True + reversal_reason) and
        create a fresh payment if needed.

    Amount constraint:
        Cannot exceed `outstanding_amount` at payment time.
        Enforced in model.clean() + services.record_payment().
    """

    obligation = models.ForeignKey(
        FeeObligation,
        on_delete=models.PROTECT,
        related_name='payments',
        db_index=True,
    )
    transaction_id = models.CharField(
        max_length=30,
        unique=True,
        editable=False,
        db_index=True,
        help_text="Auto-generated: TXN-YYYYMMDD-NNNNNN.",
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    payment_date = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="Actual date & time when money was received.",
    )
    payment_method = models.CharField(
        max_length=20,
        choices=C.PAYMENT_METHOD_CHOICES,
        default=C.METHOD_CASH,
    )
    received_by = models.ForeignKey(
        CustomUser,
        on_delete=models.PROTECT,
        related_name='payments_received',
        help_text="Staff/Principal who received this payment.",
    )
    notes = models.TextField(
        blank=True,
        help_text="Optional notes about this payment.",
    )

    # Reversal (Phase 8 workflow)
    is_reversed = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Marked true if corrected. Original row preserved.",
    )
    reversed_at = models.DateTimeField(null=True, blank=True)
    reversed_by = models.ForeignKey(
        CustomUser,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='payments_reversed',
    )
    reversal_reason = models.TextField(blank=True)

    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-payment_date', '-id']
        verbose_name = 'Fee Payment'
        verbose_name_plural = 'Fee Payments'
        indexes = [
            models.Index(fields=['obligation', 'is_reversed']),
            models.Index(fields=['payment_date']),
            models.Index(fields=['received_by', 'payment_date']),
        ]

    def __str__(self):
        return f"{self.transaction_id} — Rs.{self.amount} ({self.obligation})"

    def save(self, *args, **kwargs):
        """Auto-generate transaction_id on first save."""
        if not self.transaction_id:
            self.transaction_id = _generate_transaction_id()
        super().save(*args, **kwargs)

    # ============================================================
    # VALIDATION
    # ============================================================
    def clean(self):
        from django.core.exceptions import ValidationError

        if self.amount is None or self.amount <= C.ZERO:
            raise ValidationError({'amount': "Payment amount 0 se zyada honi chahiye."})

        if not self.is_reversed and self.obligation_id:
            # Cannot exceed outstanding (ignoring this payment's own prior state)
            paid_so_far = (
                FeePayment.objects
                .filter(obligation=self.obligation, is_reversed=False)
                .exclude(pk=self.pk)
                .aggregate(s=Sum('amount'))
                .get('s') or C.ZERO
            )
            remaining = self.obligation.effective_amount - paid_so_far
            if self.amount > remaining:
                raise ValidationError({
                    'amount': (
                        f"Payment outstanding amount se zyada hai. "
                        f"Baqi: Rs.{remaining:.2f}"
                    )
                })

    # ============================================================
    # POST-SAVE HOOKS
    # ============================================================
    def save(self, *args, **kwargs):  # noqa: F811 (intentional override)
        is_new = self._state.adding
        if not self.transaction_id:
            self.transaction_id = _generate_transaction_id()
        super().save(*args, **kwargs)
        # Refresh parent obligation status
        if is_new and not self.is_reversed:
            self.obligation.refresh_status()


# ============================================================
# FEE ADJUSTMENT (waiver / concession)
# ============================================================
class FeeAdjustment(models.Model):
    """
    A reduction against a fee obligation.

    Types:
        waiver     — full waiver; obligation becomes waived (outstanding = 0)
        concession — partial reduction; amount is subtracted from obligation.amount
        discount   — same mechanics as concession (business distinction only)

    Only Principal can create these (enforced in views + form).
    """

    obligation = models.ForeignKey(
        FeeObligation,
        on_delete=models.PROTECT,
        related_name='adjustments',
        db_index=True,
    )
    adjustment_type = models.CharField(
        max_length=20,
        choices=C.ADJUSTMENT_TYPE_CHOICES,
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=C.ZERO,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Waiver: set 0 (implicit); Concession/Discount: amount to subtract.",
    )
    reason = models.TextField(
        help_text="Reason for adjustment — required for audit trail.",
    )
    approved_by = models.ForeignKey(
        CustomUser,
        on_delete=models.PROTECT,
        related_name='adjustments_approved',
        help_text="Principal who approved this adjustment.",
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Set false to reverse (audit-preserved).",
    )
    reversed_at = models.DateTimeField(null=True, blank=True)
    reversal_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Fee Adjustment'
        verbose_name_plural = 'Fee Adjustments'
        indexes = [
            models.Index(fields=['obligation', 'is_active']),
            models.Index(fields=['adjustment_type']),
        ]

    def __str__(self):
        return f"{self.get_adjustment_type_display()} — Rs.{self.amount} ({self.obligation})"

    def clean(self):
        from django.core.exceptions import ValidationError

        if not self.reason or not self.reason.strip():
            raise ValidationError({'reason': "Reason zaroori hai (audit trail ke liye)."})

        if self.adjustment_type != C.ADJUSTMENT_WAIVER and self.amount <= C.ZERO:
            raise ValidationError({
                'amount': "Concession/discount ke liye amount 0 se zyada honi chahiye."
            })

        # Concession + discount cannot exceed remaining obligation
        if self.adjustment_type != C.ADJUSTMENT_WAIVER and self.obligation_id:
            other_adj = (
                FeeAdjustment.objects
                .filter(obligation=self.obligation, is_active=True)
                .exclude(adjustment_type=C.ADJUSTMENT_WAIVER)
                .exclude(pk=self.pk)
                .aggregate(s=Sum('amount'))
                .get('s') or C.ZERO
            )
            paid = self.obligation.paid_amount
            max_allowed = self.obligation.amount - other_adj - paid
            if self.amount > max_allowed:
                raise ValidationError({
                    'amount': (
                        f"Adjustment bohat zyada hai. "
                        f"Max allowed: Rs.{max_allowed:.2f}"
                    )
                })

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new:
            self.obligation.refresh_status()


# ============================================================
# PHASE 8 — PAYMENT CORRECTION REQUEST
# ============================================================
class PaymentCorrectionRequest(models.Model):
    """
    Staff-submitted correction request against a payment.

    Workflow:
        PENDING → APPROVED (reversal + replacement created)
                → REJECTED (no changes)
                → CANCELLED (by requester)

    Only one pending correction per payment is allowed.
    """

    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = (
        (STATUS_PENDING, 'Pending Review'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_CANCELLED, 'Cancelled'),
    )

    TYPE_AMOUNT_CHANGE = 'amount_change'
    TYPE_METHOD_CHANGE = 'method_change'
    TYPE_DATE_CHANGE = 'date_change'

    TYPE_CHOICES = (
        (TYPE_AMOUNT_CHANGE, 'Amount Change'),
        (TYPE_METHOD_CHANGE, 'Payment Method Change'),
        (TYPE_DATE_CHANGE, 'Payment Date Change'),
    )

    payment = models.ForeignKey(
        FeePayment,
        on_delete=models.PROTECT,
        related_name='correction_requests',
        db_index=True,
    )
    requested_by = models.ForeignKey(
        CustomUser,
        on_delete=models.PROTECT,
        related_name='corrections_requested',
    )
    correction_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
    )
    reason = models.TextField(
        help_text="Why is this correction needed? (audit trail).",
    )
    notes = models.TextField(
        blank=True,
        help_text="Optional additional notes.",
    )

    # Requested values (populated per correction_type)
    new_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    new_payment_method = models.CharField(
        max_length=20,
        choices=C.PAYMENT_METHOD_CHOICES,
        blank=True,
    )
    new_payment_date = models.DateTimeField(
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )

    # Review outcome
    reviewed_by = models.ForeignKey(
        CustomUser,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='corrections_reviewed',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(
        blank=True,
        help_text="Reason for approval or rejection.",
    )
    replacement_payment = models.ForeignKey(
        FeePayment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='correction_replacements',
        help_text="The new payment created on approval.",
    )

    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Payment Correction Request'
        verbose_name_plural = 'Payment Correction Requests'
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['payment', 'status']),
            models.Index(fields=['requested_by', '-created_at']),
        ]

    def __str__(self):
        return f"Correction #{self.pk} · {self.get_correction_type_display()} · {self.payment.transaction_id}"

    def get_absolute_url(self):
        return reverse('fees:correction_detail', kwargs={'pk': self.pk})

    def get_new_payment_method_display(self):
        """Display label for new_payment_method (safe when empty)."""
        if not self.new_payment_method:
            return '—'
        return dict(C.PAYMENT_METHOD_CHOICES).get(
            self.new_payment_method, self.new_payment_method
        )

    def is_pending(self) -> bool:
        return self.status == self.STATUS_PENDING

    def is_approved(self) -> bool:
        return self.status == self.STATUS_APPROVED