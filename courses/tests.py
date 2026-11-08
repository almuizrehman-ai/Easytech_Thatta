"""
Tests for the courses application.

Coverage:
- Model creation, uniqueness, auto-uppercase.
- Form validation.
- Principal-only access enforcement (staff -> 403).
- Soft-delete (toggle) preserving records.
- Duplicate fee category prevention per course.
- URL routing.
"""
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomUser
from .forms import CourseForm, FeeCategoryForm
from .models import Course, FeeCategory


class CourseModelTests(TestCase):
    def test_create_course_auto_uppercases_code(self):
        course = Course.objects.create(
            name='Diploma in IT',
            code='dit',
            duration_months=12,
        )
        self.assertEqual(course.code, 'DIT')

    def test_course_code_unique(self):
        Course.objects.create(name='A', code='DIT', duration_months=12)
        with self.assertRaises(Exception):
            Course.objects.create(name='B', code='DIT', duration_months=6)

    def test_course_name_unique(self):
        Course.objects.create(name='Unique', code='U1', duration_months=6)
        with self.assertRaises(Exception):
            Course.objects.create(name='Unique', code='U2', duration_months=6)

    def test_get_absolute_url(self):
        course = Course.objects.create(
            name='DIT', code='DIT', duration_months=12,
        )
        self.assertEqual(
            course.get_absolute_url(),
            reverse('courses:detail', kwargs={'pk': course.pk}),
        )

    def test_fee_categories_related_name(self):
        course = Course.objects.create(
            name='DIT', code='DIT', duration_months=12,
        )
        FeeCategory.objects.create(course=course, name='Admission Fee',
                                   amount=Decimal('5000.00'))
        self.assertEqual(course.fee_categories.count(), 1)


class FeeCategoryModelTests(TestCase):
    def setUp(self):
        self.course = Course.objects.create(
            name='DIT', code='DIT', duration_months=12,
        )

    def test_unique_category_per_course(self):
        FeeCategory.objects.create(
            course=self.course, name='Admission Fee',
            amount=Decimal('1000.00'),
        )
        with self.assertRaises(Exception):
            FeeCategory.objects.create(
                course=self.course, name='Admission Fee',
                amount=Decimal('2000.00'),
            )

    def test_same_category_name_allowed_in_different_courses(self):
        c2 = Course.objects.create(name='CIT', code='CIT', duration_months=6)
        FeeCategory.objects.create(
            course=self.course, name='Admission Fee',
            amount=Decimal('1000.00'),
        )
        FeeCategory.objects.create(
            course=c2, name='Admission Fee',
            amount=Decimal('800.00'),
        )
        self.assertEqual(FeeCategory.objects.count(), 2)


class CourseFormTests(TestCase):
    def test_valid_form(self):
        form = CourseForm(data={
            'name': 'Web Dev',
            'code': 'web',
            'duration_months': 6,
            'is_active': True,
        })
        self.assertTrue(form.is_valid(), form.errors)
        obj = form.save()
        self.assertEqual(obj.code, 'WEB')

    def test_code_invalid_characters(self):
        form = CourseForm(data={
            'name': 'Web Dev',
            'code': 'W@B!',
            'duration_months': 6,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('code', form.errors)

    def test_duration_must_be_positive(self):
        form = CourseForm(data={
            'name': 'Web Dev',
            'code': 'WEB',
            'duration_months': 0,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('duration_months', form.errors)


class FeeCategoryFormTests(TestCase):
    def setUp(self):
        self.course = Course.objects.create(
            name='DIT', code='DIT', duration_months=12,
        )

    def test_valid_form(self):
        form = FeeCategoryForm(
            data={'name': 'Exam Fee', 'amount': '500.00', 'is_active': True},
            course=self.course,
        )
        self.assertTrue(form.is_valid(), form.errors)
        obj = form.save()
        self.assertEqual(obj.course, self.course)
        self.assertEqual(obj.amount, Decimal('500.00'))

    def test_duplicate_name_in_same_course(self):
        FeeCategory.objects.create(
            course=self.course, name='Exam Fee',
            amount=Decimal('500.00'),
        )
        form = FeeCategoryForm(
            data={'name': 'Exam Fee', 'amount': '600.00', 'is_active': True},
            course=self.course,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)


class CourseViewAccessTests(TestCase):
    """Verify Principal-only access enforcement."""

    def setUp(self):
        self.staff = CustomUser.objects.create_user(
            username='staff_c', password='P@ssw0rd123', role='staff',
        )
        self.principal = CustomUser.objects.create_user(
            username='prin_c', password='P@ssw0rd123', role='principal',
            is_staff=True,
        )
        self.course = Course.objects.create(
            name='DIT', code='DIT', duration_months=12,
        )

    def test_staff_blocked_from_course_list(self):
        self.client.login(username='staff_c', password='P@ssw0rd123')
        response = self.client.get(reverse('courses:list'))
        self.assertEqual(response.status_code, 403)

    def test_staff_blocked_from_course_create(self):
        self.client.login(username='staff_c', password='P@ssw0rd123')
        response = self.client.get(reverse('courses:create'))
        self.assertEqual(response.status_code, 403)

    def test_principal_can_access_course_list(self):
        self.client.login(username='prin_c', password='P@ssw0rd123')
        response = self.client.get(reverse('courses:list'))
        self.assertEqual(response.status_code, 200)

    def test_principal_can_create_course(self):
        self.client.login(username='prin_c', password='P@ssw0rd123')
        response = self.client.post(reverse('courses:create'), data={
            'name': 'Web Development',
            'code': 'WEB',
            'duration_months': 6,
            'is_active': True,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Course.objects.filter(code='WEB').exists())

    def test_toggle_course_does_not_delete(self):
        self.client.login(username='prin_c', password='P@ssw0rd123')
        response = self.client.post(
            reverse('courses:toggle', kwargs={'pk': self.course.pk})
        )
        self.assertEqual(response.status_code, 302)
        self.course.refresh_from_db()
        self.assertFalse(self.course.is_active)
        # Still exists in DB
        self.assertTrue(Course.objects.filter(pk=self.course.pk).exists())

    def test_toggle_requires_post(self):
        self.client.login(username='prin_c', password='P@ssw0rd123')
        response = self.client.get(
            reverse('courses:toggle', kwargs={'pk': self.course.pk})
        )
        self.assertEqual(response.status_code, 405)


class FeeCategoryViewAccessTests(TestCase):
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

    def test_principal_can_add_fee_category(self):
        self.client.login(username='prin_f', password='P@ssw0rd123')
        response = self.client.post(
            reverse('courses:fee_create', kwargs={'course_pk': self.course.pk}),
            data={'name': 'Admission Fee', 'amount': '1500.00', 'is_active': True},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            FeeCategory.objects.filter(course=self.course, name='Admission Fee').exists()
        )

    def test_staff_blocked_from_fee_create(self):
        self.client.login(username='staff_f', password='P@ssw0rd123')
        response = self.client.get(
            reverse('courses:fee_create', kwargs={'course_pk': self.course.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_toggle_fee_category_requires_post(self):
        self.client.login(username='prin_f', password='P@ssw0rd123')
        fee = FeeCategory.objects.create(
            course=self.course, name='Exam Fee', amount=Decimal('500.00'),
        )
        response = self.client.get(
            reverse('courses:fee_toggle', kwargs={'course_pk': self.course.pk, 'pk': fee.pk})
        )
        self.assertEqual(response.status_code, 405)