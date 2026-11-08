"""
Tests for the students application.

Coverage:
- Student ID auto-generation (format + uniqueness across calls).
- Fee snapshots derived correctly.
- Mobile normalization on save.
- Course auto-synced from batch.
- Duplicate active student rejection.
- Batch-course consistency validation.
- Access control: Staff can create/edit, cannot toggle.
- Principal-only toggle enforcement.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomUser
from batches.models import Batch
from courses.models import Course, FeeCategory

from .forms import AdmissionForm
from .models import Student
from .services import generate_student_id


class StudentIDGenerationTests(TestCase):
    def test_first_id_of_year_starts_at_0001(self):
        sid = generate_student_id()
        self.assertTrue(sid.startswith('EST-'))
        self.assertTrue(sid.endswith('-0001'))

    def test_sequential_ids(self):
        sid1 = generate_student_id()
        # Simulate persistence
        Student.objects.create(
            student_id=sid1,
            student_name='Ali', father_name='Khan',
            student_mobile='03001234567', father_mobile='03001234568',
            course=self._course(), batch=self._batch(),
        )
        sid2 = generate_student_id()
        self.assertNotEqual(sid1, sid2)
        self.assertTrue(sid2.endswith('-0002'))

    def _course(self):
        return Course.objects.create(
            name='DIT', code='DIT', duration_months=12,
        )

    def _batch(self):
        return Batch.objects.create(
            course=self._course(),
            start_month=date(2027, 3, 1),
            monthly_fee=Decimal('1500.00'),
        )


class StudentModelTests(TestCase):
    def setUp(self):
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
            start_month=date(2027, 3, 1),
            monthly_fee=Decimal('1500.00'),
        )

    def test_student_id_assigned_on_save(self):
        student = Student.objects.create(
            student_name='Ali', father_name='Khan',
            student_mobile='03001234567', father_mobile='03001234568',
            course=self.course, batch=self.batch,
        )
        self.assertTrue(student.student_id.startswith('EST-'))

    def test_mobile_normalized_on_save(self):
        student = Student.objects.create(
            student_name='Ali', father_name='Khan',
            student_mobile='+923001234567',
            father_mobile='923001234567',
            course=self.course, batch=self.batch,
        )
        self.assertEqual(student.student_mobile, '03001234567')
        self.assertEqual(student.father_mobile, '03001234567')

    def test_course_synced_from_batch(self):
        other_course = Course.objects.create(
            name='CIT', code='CIT', duration_months=6,
        )
        # Deliberately mismatch: batch belongs to DIT
        student = Student(
            student_name='Ali', father_name='Khan',
            student_mobile='03001234567', father_mobile='03001234568',
            course=other_course, batch=self.batch,
        )
        # Must raise on clean() (view form triggers this)
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            student.full_clean()

    def test_duplicate_active_student_rejected(self):
        Student.objects.create(
            student_name='Ali', father_name='Khan',
            student_mobile='03001234567', father_mobile='03001234568',
            course=self.course, batch=self.batch,
        )
        with self.assertRaises(Exception):
            Student.objects.create(
                student_name='Ali', father_name='Khan',
                student_mobile='03001234567', father_mobile='03009999999',
                course=self.course, batch=self.batch,
            )

    def test_inactive_batch_blocks_new_admission(self):
        inactive_batch = Batch.objects.create(
            course=self.course,
            start_month=date(2027, 6, 1),
            monthly_fee=Decimal('1500.00'),
            is_active=False,
        )
        from django.core.exceptions import ValidationError
        student = Student(
            student_name='Ali', father_name='Khan',
            student_mobile='03001234567', father_mobile='03001234568',
            course=self.course, batch=inactive_batch,
        )
        with self.assertRaises(ValidationError):
            student.full_clean()

    def test_derive_fee_snapshots(self):
        snapshots = Student.derive_fee_snapshots(self.course, self.batch)
        self.assertEqual(snapshots['admission_fee_amount'], Decimal('5000.00'))
        self.assertEqual(snapshots['registration_fee_amount'], Decimal('1000.00'))
        self.assertEqual(snapshots['monthly_fee_at_admission'], Decimal('1500.00'))


class AdmissionFormTests(TestCase):
    def setUp(self):
        self.course = Course.objects.create(
            name='DIT', code='DIT', duration_months=12,
        )
        FeeCategory.objects.create(
            course=self.course, name='Admission Fee',
            amount=Decimal('5000.00'),
        )
        self.batch = Batch.objects.create(
            course=self.course,
            start_month=date(2027, 3, 1),
            monthly_fee=Decimal('1500.00'),
        )

    def _base_data(self, **overrides):
        data = {
            'student_name': 'Ali Khan',
            'father_name': 'Muhammad Khan',
            'student_mobile': '03001234567',
            'father_mobile': '03001234568',
            'course': self.course.pk,
            'batch': self.batch.pk,
            'admission_date': '2027-03-15',
            'gender': 'M',
            'enrollment_status': 'active',
        }
        data.update(overrides)
        return data

    def test_valid_admission_saves_with_snapshots(self):
        form = AdmissionForm(data=self._base_data())
        self.assertTrue(form.is_valid(), form.errors)
        student = form.save()
        self.assertEqual(student.admission_fee_amount, Decimal('5000.00'))
        self.assertEqual(student.monthly_fee_at_admission, Decimal('1500.00'))
        self.assertTrue(student.student_id.startswith('EST-'))

    def test_batch_course_mismatch_rejected(self):
        other_course = Course.objects.create(
            name='CIT', code='CIT', duration_months=6,
        )
        # Course=CIT but batch belongs to DIT
        form = AdmissionForm(data=self._base_data(course=other_course.pk))
        self.assertFalse(form.is_valid())
        self.assertIn('batch', form.errors)

    def test_invalid_mobile_format(self):
        form = AdmissionForm(data=self._base_data(student_mobile='12345'))
        self.assertFalse(form.is_valid())
        self.assertIn('student_mobile', form.errors)


class StudentViewAccessTests(TestCase):
    def setUp(self):
        self.principal = CustomUser.objects.create_user(
            username='prin_s', password='P@ssw0rd123', role='principal',
            is_staff=True,
        )
        self.staff = CustomUser.objects.create_user(
            username='staff_s', password='P@ssw0rd123', role='staff',
        )
        self.course = Course.objects.create(
            name='DIT', code='DIT', duration_months=12,
        )
        self.batch = Batch.objects.create(
            course=self.course,
            start_month=date(2027, 3, 1),
            monthly_fee=Decimal('1500.00'),
        )
        self.student = Student.objects.create(
            student_name='Ali', father_name='Khan',
            student_mobile='03001234567', father_mobile='03001234568',
            course=self.course, batch=self.batch,
        )

    def test_staff_can_access_list(self):
        self.client.login(username='staff_s', password='P@ssw0rd123')
        response = self.client.get(reverse('students:list'))
        self.assertEqual(response.status_code, 200)

    def test_staff_can_access_create(self):
        self.client.login(username='staff_s', password='P@ssw0rd123')
        response = self.client.get(reverse('students:create'))
        self.assertEqual(response.status_code, 200)

    def test_staff_can_create_student(self):
        self.client.login(username='staff_s', password='P@ssw0rd123')
        response = self.client.post(reverse('students:create'), data={
            'student_name': 'Bilal',
            'father_name': 'Ahmed',
            'student_mobile': '03007654321',
            'father_mobile': '03008765432',
            'course': self.course.pk,
            'batch': self.batch.pk,
            'admission_date': '2027-03-20',
            'gender': 'M',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Student.objects.filter(student_name='Bilal').exists())

    def test_staff_blocked_from_toggle(self):
        self.client.login(username='staff_s', password='P@ssw0rd123')
        response = self.client.post(
            reverse('students:toggle', kwargs={'pk': self.student.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_principal_can_toggle(self):
        self.client.login(username='prin_s', password='P@ssw0rd123')
        response = self.client.post(
            reverse('students:toggle', kwargs={'pk': self.student.pk})
        )
        self.assertEqual(response.status_code, 302)
        self.student.refresh_from_db()
        self.assertFalse(self.student.is_active)

    def test_toggle_requires_post(self):
        self.client.login(username='prin_s', password='P@ssw0rd123')
        response = self.client.get(
            reverse('students:toggle', kwargs={'pk': self.student.pk})
        )
        self.assertEqual(response.status_code, 405)

    def test_no_delete_view_exists(self):
        """Ensure we never expose a delete URL (spec: never delete students)."""
        self.client.login(username='prin_s', password='P@ssw0rd123')
        # Attempting to hit a non-existent delete URL should 404
        response = self.client.get(f'/students/{self.student.pk}/delete/')
        self.assertEqual(response.status_code, 404)