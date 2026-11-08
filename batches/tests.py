"""
Tests for the batches application.

Coverage:
- Auto-calculation of end_month from course duration.
- Start-month normalization to first-of-month.
- Duplicate (course, start_month) prevention.
- Form validation.
- Principal-only access enforcement.
- Soft-delete preserves records.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomUser
from courses.models import Course

from .forms import BatchForm
from .models import Batch


class BatchModelTests(TestCase):
    def setUp(self):
        self.dit = Course.objects.create(
            name='DIT', code='DIT', duration_months=12,
        )
        self.cit = Course.objects.create(
            name='CIT', code='CIT', duration_months=6,
        )

    def test_end_month_auto_calculated_dit(self):
        """DIT (12 months) starting Mar 2027 -> ends Feb 2028."""
        batch = Batch.objects.create(
            course=self.dit,
            start_month=date(2027, 3, 15),
            monthly_fee=Decimal('1500.00'),
        )
        self.assertEqual(batch.start_month, date(2027, 3, 1))
        self.assertEqual(batch.end_month, date(2028, 2, 29))  # 2028 leap year

    def test_end_month_auto_calculated_cit(self):
        """CIT (6 months) starting Mar 2027 -> ends Aug 2027."""
        batch = Batch.objects.create(
            course=self.cit,
            start_month=date(2027, 3, 1),
            monthly_fee=Decimal('800.00'),
        )
        self.assertEqual(batch.end_month, date(2027, 8, 31))

    def test_end_month_crosses_year(self):
        """CIT Sep 2027 -> Feb 2028 (matches spec example)."""
        batch = Batch.objects.create(
            course=self.cit,
            start_month=date(2027, 9, 1),
            monthly_fee=Decimal('800.00'),
        )
        self.assertEqual(batch.end_month, date(2028, 2, 29))

    def test_display_name_auto_generated(self):
        batch = Batch.objects.create(
            course=self.dit,
            start_month=date(2027, 3, 1),
            monthly_fee=Decimal('1500.00'),
        )
        self.assertEqual(batch.display_name, 'DIT Mar 2027 – Feb 2028')

    def test_custom_name_overrides_auto(self):
        batch = Batch.objects.create(
            course=self.dit,
            name='Evening Shift DIT',
            start_month=date(2027, 3, 1),
            monthly_fee=Decimal('1500.00'),
        )
        self.assertEqual(batch.display_name, 'Evening Shift DIT')

    def test_duration_months_matches_course(self):
        batch = Batch.objects.create(
            course=self.dit,
            start_month=date(2027, 3, 1),
            monthly_fee=Decimal('1500.00'),
        )
        self.assertEqual(batch.duration_months, 12)

    def test_duplicate_course_start_month_rejected(self):
        Batch.objects.create(
            course=self.dit,
            start_month=date(2027, 3, 1),
            monthly_fee=Decimal('1500.00'),
        )
        with self.assertRaises(Exception):
            Batch.objects.create(
                course=self.dit,
                start_month=date(2027, 3, 20),  # normalizes to 3-01 -> conflict
                monthly_fee=Decimal('2000.00'),
            )

    def test_end_month_recalculates_on_course_duration_change(self):
        """If course duration changes, editing the batch recalcs end_month."""
        batch = Batch.objects.create(
            course=self.cit,
            start_month=date(2027, 3, 1),
            monthly_fee=Decimal('800.00'),
        )
        self.assertEqual(batch.end_month, date(2027, 8, 31))

        # Change course duration to 8 months
        self.cit.duration_months = 8
        self.cit.save()

        batch.save()  # triggers recalc
        self.assertEqual(batch.end_month, date(2027, 10, 31))


class BatchFormTests(TestCase):
    def setUp(self):
        self.dit = Course.objects.create(
            name='DIT', code='DIT', duration_months=12,
        )

    def test_valid_form_creates_batch(self):
        form = BatchForm(data={
            'course': self.dit.pk,
            'name': '',
            'start_month': '2027-03',
            'monthly_fee': '1500.00',
            'is_active': True,
        })
        self.assertTrue(form.is_valid(), form.errors)
        batch = form.save()
        self.assertEqual(batch.start_month, date(2027, 3, 1))
        self.assertEqual(batch.end_month, date(2028, 2, 29))

    def test_invalid_start_month_format(self):
        form = BatchForm(data={
            'course': self.dit.pk,
            'start_month': '03/2027',  # wrong format
            'monthly_fee': '1500.00',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('start_month', form.errors)

    def test_duplicate_batch_rejected_by_form(self):
        Batch.objects.create(
            course=self.dit,
            start_month=date(2027, 3, 1),
            monthly_fee=Decimal('1500.00'),
        )
        form = BatchForm(data={
            'course': self.dit.pk,
            'start_month': '2027-03',
            'monthly_fee': '1500.00',
            'is_active': True,
        })
        self.assertFalse(form.is_valid())
        self.assertTrue(form.non_field_errors())


class BatchViewAccessTests(TestCase):
    def setUp(self):
        self.principal = CustomUser.objects.create_user(
            username='prin_b', password='P@ssw0rd123', role='principal',
            is_staff=True,
        )
        self.staff = CustomUser.objects.create_user(
            username='staff_b', password='P@ssw0rd123', role='staff',
        )
        self.course = Course.objects.create(
            name='DIT', code='DIT', duration_months=12,
        )
        self.batch = Batch.objects.create(
            course=self.course,
            start_month=date(2027, 3, 1),
            monthly_fee=Decimal('1500.00'),
        )

    def test_staff_blocked_from_batch_list(self):
        self.client.login(username='staff_b', password='P@ssw0rd123')
        response = self.client.get(reverse('batches:list'))
        self.assertEqual(response.status_code, 403)

    def test_principal_can_access_batch_list(self):
        self.client.login(username='prin_b', password='P@ssw0rd123')
        response = self.client.get(reverse('batches:list'))
        self.assertEqual(response.status_code, 200)

    def test_principal_can_create_batch(self):
        self.client.login(username='prin_b', password='P@ssw0rd123')
        response = self.client.post(reverse('batches:create'), data={
            'course': self.course.pk,
            'name': '',
            'start_month': '2027-06',
            'monthly_fee': '1500.00',
            'is_active': True,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Batch.objects.filter(course=self.course, start_month=date(2027, 6, 1)).exists()
        )

    def test_toggle_does_not_delete(self):
        self.client.login(username='prin_b', password='P@ssw0rd123')
        response = self.client.post(
            reverse('batches:toggle', kwargs={'pk': self.batch.pk})
        )
        self.assertEqual(response.status_code, 302)
        self.batch.refresh_from_db()
        self.assertFalse(self.batch.is_active)
        self.assertTrue(Batch.objects.filter(pk=self.batch.pk).exists())

    def test_toggle_requires_post(self):
        self.client.login(username='prin_b', password='P@ssw0rd123')
        response = self.client.get(
            reverse('batches:toggle', kwargs={'pk': self.batch.pk})
        )
        self.assertEqual(response.status_code, 405)