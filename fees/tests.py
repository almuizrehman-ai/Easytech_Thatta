"""
Tests for the fees application.

Coverage:
- Ledger generation from batch.start_month (including backdated months).
- Idempotency of ledger generation.
- Payment recording (full + partial).
- Overshoot prevention.
- Waiver → status WAIVED.
- Concession → outstanding reduced.
- Overdue derivation (past due + outstanding > 0).
- Access control: Staff cannot waive/concede (403).
- Reversal preserves original payment.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser
from batches.models import Batch
from courses.models import Course, FeeCategory
from students.models import Student

from . import constants as C
from . import services
from .forms import ConcessionForm, PaymentForm, WaiverForm
from .models import FeeAdjustment, FeeObligation, FeePayment


# ============================================================
# TEST FIXTURES
# ============================================================
class FeesTestBase(TestCase):
    def setUp(self):
        self.principal = CustomUser.objects.create_user(
            username='prin_f', password='P@ssw0rd123', role='principal',
            is_staff=True,
        )
        self.staff = CustomUser.objects.create_user(
            username='staff_f', password='P@ssw0rd123', role='staff',
        )

        self.course = Course.objects.create(
            name='DIT', code='DIT', duration_months=12,
        )
        FeeCategory.objects.create(
            course=self.course, name='Admission Fee',
            amount=Decimal('5000.00'),
        )
        FeeCategory.objects.create(
            course=self.course, name='Registration Fee',
            amount=Decimal('1000.00'),
        )

        self.batch = Batch.objects.create(
            course=self.course,
            start_month=date(2027, 3, 1),  # Ends Feb 2028
            monthly_fee=Decimal('1500.00'),
        )

    def make_student(self, admission_date=date(2027, 5, 15), **kwargs):
        defaults = dict(
            student_name='Ali Khan',
            father_name='Muhammad Khan',
            student_mobile='03001234567',
            father_mobile='03001234568',
            course=self.course,
            batch=self.batch,
            admission_date=admission_date,
            admission_fee_amount=Decimal('5000.00'),
            registration_fee_amount=Decimal('1000.00'),
            monthly_fee_at_admission=Decimal('1500.00'),
        )
        defaults.update(kwargs)
        return Student.objects.create(**defaults)


# ============================================================
# LEDGER GENERATION
# ============================================================
class LedgerGenerationTests(FeesTestBase):
    def test_creates_admission_and_monthly_obligations(self):
        student = self.make_student(admission_date=date(2027, 5, 15))
        result = services.generate_ledger_for_student(student)

        self.assertEqual(result.created, 1 + 1 + 12)  # admission + reg + 12 months
        self.assertTrue(result.admission_created)
        self.assertTrue(result.registration_created)
        self.assertEqual(result.months_created, 12)

    def test_backdated_months_created_from_batch_start(self):
        """Spec: student admitted May, but Mar+Apr obligations must exist."""
        student = self.make_student(admission_date=date(2027, 5, 15))
        services.generate_ledger_for_student(student)

        monthly = FeeObligation.objects.filter(
            student=student, obligation_type=C.TYPE_MONTHLY,
        ).order_by('obligation_month')

        months = list(monthly.values_list('obligation_month', flat=True))
        self.assertEqual(months[0], date(2027, 3, 1))  # Backdated
        self.assertEqual(months[1], date(2027, 4, 1))  # Backdated
        self.assertEqual(len(months), 12)

    def test_ledger_is_idempotent(self):
        student = self.make_student()
        services.generate_ledger_for_student(student)
        result = services.generate_ledger_for_student(student)
        self.assertEqual(result.created, 0)
        self.assertEqual(result.skipped, 14)  # 2 + 12

    def test_monthly_obligation_due_date_is_10th(self):
        student = self.make_student()
        services.generate_ledger_for_student(student)
        march_obl = FeeObligation.objects.get(
            student=student,
            obligation_type=C.TYPE_MONTHLY,
            obligation_month=date(2027, 3, 1),
        )
        self.assertEqual(march_obl.due_date, date(2027, 3, 10))

    def test_no_obligations_when_amount_zero(self):
        student = self.make_student(
            admission_fee_amount=Decimal('0.00'),
            registration_fee_amount=Decimal('0.00'),
            monthly_fee_at_admission=Decimal('0.00'),
        )
        result = services.generate_ledger_for_student(student)
        self.assertEqual(result.created, 0)


# ============================================================
# PAYMENT RECORDING
# ============================================================
class PaymentTests(FeesTestBase):
    def setUp(self):
        super().setUp()
        self.student = self.make_student()
        services.generate_ledger_for_student(self.student)
        self.admission_obl = FeeObligation.objects.get(
            student=self.student, obligation_type=C.TYPE_ADMISSION,
        )

    def test_full_payment_status_paid(self):
        result = services.record_payment(
            obligation=self.admission_obl,
            amount=Decimal('5000.00'),
            received_by=self.staff,
        )
        self.assertTrue(result.success)
        self.admission_obl.refresh_from_db()
        self.assertEqual(self.admission_obl.status, C.STATUS_PAID)
        self.assertEqual(self.admission_obl.outstanding_amount, Decimal('0'))

    def test_partial_payment_status_partial(self):
        result = services.record_payment(
            obligation=self.admission_obl,
            amount=Decimal('2000.00'),
            received_by=self.staff,
        )
        self.assertTrue(result.success)
        self.admission_obl.refresh_from_db()
        self.assertEqual(self.admission_obl.status, C.STATUS_PARTIAL)
        self.assertEqual(self.admission_obl.outstanding_amount, Decimal('3000.00'))

    def test_two_partial_payments_become_paid(self):
        services.record_payment(
            obligation=self.admission_obl,
            amount=Decimal('2000.00'),
            received_by=self.staff,
        )
        services.record_payment(
            obligation=self.admission_obl,
            amount=Decimal('3000.00'),
            received_by=self.staff,
        )
        self.admission_obl.refresh_from_db()
        self.assertEqual(self.admission_obl.status, C.STATUS_PAID)
        self.assertEqual(self.admission_obl.payments.count(), 2)

    def test_overshoot_payment_rejected(self):
        result = services.record_payment(
            obligation=self.admission_obl,
            amount=Decimal('6000.00'),
            received_by=self.staff,
        )
        self.assertFalse(result.success)
        self.assertIn('outstanding', result.error.lower())

    def test_payment_on_paid_obligation_rejected(self):
        services.record_payment(
            obligation=self.admission_obl,
            amount=Decimal('5000.00'),
            received_by=self.staff,
        )
        result = services.record_payment(
            obligation=self.admission_obl,
            amount=Decimal('100.00'),
            received_by=self.staff,
        )
        self.assertFalse(result.success)

    def test_transaction_id_generated(self):
        result = services.record_payment(
            obligation=self.admission_obl,
            amount=Decimal('1000.00'),
            received_by=self.staff,
        )
        self.assertTrue(result.payment.transaction_id.startswith('TXN-'))

    def test_overdue_obligation_still_accepts_payment(self):
        """Even if past due, payment must be accepted."""
        march_obl = FeeObligation.objects.get(
            student=self.student,
            obligation_type=C.TYPE_MONTHLY,
            obligation_month=date(2027, 3, 1),
        )
        # Force it into the past
        march_obl.due_date = timezone.localdate() - timedelta(days=30)
        march_obl.save()
        # is_overdue should be True (via property)
        self.assertTrue(march_obl.is_overdue)

        result = services.record_payment(
            obligation=march_obl,
            amount=Decimal('1500.00'),
            received_by=self.staff,
        )
        self.assertTrue(result.success)


# ============================================================
# WAIVER
# ============================================================
class WaiverTests(FeesTestBase):
    def setUp(self):
        super().setUp()
        self.student = self.make_student()
        services.generate_ledger_for_student(self.student)
        self.obl = FeeObligation.objects.filter(
            student=self.student, obligation_type=C.TYPE_MONTHLY,
        ).first()

    def test_waiver_sets_status_waived(self):
        services.apply_waiver(
            obligation=self.obl,
            reason="Orphan student",
            approved_by=self.principal,
        )
        self.obl.refresh_from_db()
        self.assertEqual(self.obl.status, C.STATUS_WAIVED)
        self.assertEqual(self.obl.outstanding_amount, Decimal('0'))

    def test_waiver_requires_reason(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            services.apply_waiver(
                obligation=self.obl,
                reason='',
                approved_by=self.principal,
            )


# ============================================================
# CONCESSION
# ============================================================
class ConcessionTests(FeesTestBase):
    def setUp(self):
        super().setUp()
        self.student = self.make_student()
        services.generate_ledger_for_student(self.student)
        self.obl = FeeObligation.objects.filter(
            student=self.student, obligation_type=C.TYPE_MONTHLY,
        ).first()

    def test_concession_reduces_outstanding(self):
        services.apply_concession(
            obligation=self.obl,
            amount=Decimal('500.00'),
            reason="Sibling discount",
            approved_by=self.principal,
        )
        self.obl.refresh_from_db()
        self.assertEqual(self.obl.outstanding_amount, Decimal('1000.00'))

    def test_concession_above_max_rejected(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            services.apply_concession(
                obligation=self.obl,
                amount=Decimal('2000.00'),  # > 1500
                reason="Test",
                approved_by=self.principal,
            )


# ============================================================
# OVERDUE DERIVATION
# ============================================================
class OverdueTests(FeesTestBase):
    def test_overdue_property_correct(self):
        student = self.make_student()
        services.generate_ledger_for_student(student)
        obl = FeeObligation.objects.filter(
            student=student, obligation_type=C.TYPE_MONTHLY,
        ).order_by('obligation_month').first()  # March 2027

        # Force past due
        obl.due_date = timezone.localdate() - timedelta(days=10)
        obl.save()

        self.assertTrue(obl.is_overdue)
        self.assertEqual(obl.effective_status, C.STATUS_OVERDUE)

    def test_paid_obligation_never_overdue(self):
        student = self.make_student()
        services.generate_ledger_for_student(student)
        obl = FeeObligation.objects.filter(
            student=student, obligation_type=C.TYPE_MONTHLY,
        ).first()

        obl.due_date = timezone.localdate() - timedelta(days=10)
        obl.save()
        services.record_payment(
            obligation=obl,
            amount=obl.amount,
            received_by=self.staff,
        )
        obl.refresh_from_db()
        self.assertFalse(obl.is_overdue)
        self.assertEqual(obl.effective_status, C.STATUS_PAID)


# ============================================================
# ACCESS CONTROL
# ============================================================
class FeeAccessTests(FeesTestBase):
    def setUp(self):
        super().setUp()
        self.student = self.make_student()
        services.generate_ledger_for_student(self.student)
        self.obl = FeeObligation.objects.filter(
            student=self.student, obligation_type=C.TYPE_ADMISSION,
        ).first()

    def test_staff_can_access_ledger(self):
        self.client.login(username='staff_f', password='P@ssw0rd123')
        response = self.client.get(
            reverse('fees:student_ledger', kwargs={'student_pk': self.student.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_staff_can_record_payment(self):
        self.client.login(username='staff_f', password='P@ssw0rd123')
        response = self.client.post(
            reverse('fees:record_payment', kwargs={'obligation_pk': self.obl.pk}),
            data={
                'amount': '1000.00',
                'payment_method': C.METHOD_CASH,
                'notes': 'Test payment',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(FeePayment.objects.count(), 1)

    def test_staff_blocked_from_waiver(self):
        self.client.login(username='staff_f', password='P@ssw0rd123')
        response = self.client.get(
            reverse('fees:apply_waiver', kwargs={'obligation_pk': self.obl.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_staff_blocked_from_concession(self):
        self.client.login(username='staff_f', password='P@ssw0rd123')
        response = self.client.get(
            reverse('fees:apply_concession', kwargs={'obligation_pk': self.obl.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_principal_can_waive(self):
        self.client.login(username='prin_f', password='P@ssw0rd123')
        response = self.client.post(
            reverse('fees:apply_waiver', kwargs={'obligation_pk': self.obl.pk}),
            data={'reason': 'Test waiver'},
        )
        self.assertEqual(response.status_code, 302)
        self.obl.refresh_from_db()
        self.assertEqual(self.obl.status, C.STATUS_WAIVED)


# ============================================================
# REVERSAL
# ============================================================
class ReversalTests(FeesTestBase):
    def test_reversal_preserves_original(self):
        student = self.make_student()
        services.generate_ledger_for_student(student)
        obl = FeeObligation.objects.get(
            student=student, obligation_type=C.TYPE_ADMISSION,
        )
        result = services.record_payment(
            obligation=obl,
            amount=Decimal('1000.00'),
            received_by=self.staff,
        )
        payment = result.payment

        services.reverse_payment(
            payment=payment,
            reason="Test reversal",
            performed_by=self.principal,
        )

        payment.refresh_from_db()
        self.assertTrue(payment.is_reversed)
        self.assertEqual(FeePayment.objects.filter(pk=payment.pk).count(), 1)  # Not deleted

        obl.refresh_from_db()
        self.assertEqual(obl.outstanding_amount, Decimal('5000.00'))  # Back to full


# ============================================================
# FORM VALIDATION
# ============================================================
class FormTests(FeesTestBase):
    def setUp(self):
        super().setUp()
        self.student = self.make_student()
        services.generate_ledger_for_student(self.student)
        self.obl = FeeObligation.objects.get(
            student=self.student, obligation_type=C.TYPE_ADMISSION,
        )

    def test_payment_form_rejects_overshoot(self):
        form = PaymentForm(
            data={
                'amount': '10000.00',
                'payment_method': C.METHOD_CASH,
            },
            obligation=self.obl,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('amount', form.errors)

    def test_waiver_form_requires_reason(self):
        form = WaiverForm(data={'reason': ''}, obligation=self.obl)
        self.assertFalse(form.is_valid())

    def test_concession_form_rejects_above_max(self):
        form = ConcessionForm(
            data={
                'adjustment_type': C.ADJUSTMENT_CONCESSION,
                'amount': '99999.00',
                'reason': 'Test',
            },
            obligation=self.obl,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('amount', form.errors)