"""
Tests for Phase 1: authentication, role enforcement, dashboard routing.
Run with: python manage.py test accounts
"""
from django.test import TestCase
from django.urls import reverse

from .models import CustomUser


class CustomUserModelTests(TestCase):
    """Model-level tests."""

    def test_create_staff_user(self):
        user = CustomUser.objects.create_user(
            username='staff_test',
            password='Secret@123',
            full_name='Staff Tester',
        )
        self.assertEqual(user.role, 'staff')
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.is_portal_staff)
        self.assertFalse(user.is_principal)

    def test_create_superuser_forces_principal_role(self):
        user = CustomUser.objects.create_superuser(
            username='principal_test',
            password='Secret@123',
        )
        self.assertEqual(user.role, 'principal')
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_principal)

    def test_username_is_unique(self):
        CustomUser.objects.create_user(username='dup', password='Secret@123')
        with self.assertRaises(Exception):
            CustomUser.objects.create_user(username='dup', password='Secret@123')


class LoginPageTests(TestCase):
    """Login page render and validation."""

    def test_login_page_loads(self):
        response = self.client.get(reverse('accounts:login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'EASYTECH THATTA')

    def test_invalid_credentials_show_error(self):
        response = self.client.post(
            reverse('accounts:login'),
            {'username': 'ghost', 'password': 'wrong'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ghalat')


class RoleRedirectTests(TestCase):
    """Verify that each role lands on its correct dashboard."""

    def setUp(self):
        self.staff = CustomUser.objects.create_user(
            username='staff01',
            password='Staff@123',
            role='staff',
            full_name='Staff One',
        )
        self.principal = CustomUser.objects.create_user(
            username='principal01',
            password='Principal@123',
            role='principal',
            full_name='Principal One',
            is_staff=True,
        )

    def test_staff_redirects_to_staff_dashboard(self):
        self.client.login(username='staff01', password='Staff@123')
        response = self.client.get(reverse('accounts:redirect_after_login'))
        self.assertRedirects(response, reverse('dashboard:staff'))

    def test_principal_redirects_to_principal_dashboard(self):
        self.client.login(username='principal01', password='Principal@123')
        response = self.client.get(reverse('accounts:redirect_after_login'))
        self.assertRedirects(response, reverse('dashboard:principal'))


class AccessControlTests(TestCase):
    """Cross-role enforcement — the security cornerstone."""

    def setUp(self):
        self.staff = CustomUser.objects.create_user(
            username='staff02',
            password='Staff@123',
            role='staff',
        )
        self.principal = CustomUser.objects.create_user(
            username='principal02',
            password='Principal@123',
            role='principal',
            is_staff=True,
        )

    def test_staff_cannot_access_principal_dashboard(self):
        self.client.login(username='staff02', password='Staff@123')
        response = self.client.get(reverse('dashboard:principal'))
        self.assertEqual(response.status_code, 403)

    def test_principal_cannot_access_staff_dashboard(self):
        self.client.login(username='principal02', password='Principal@123')
        response = self.client.get(reverse('dashboard:staff'))
        self.assertEqual(response.status_code, 403)

    def test_anonymous_user_redirected_to_login(self):
        response = self.client.get(reverse('dashboard:staff'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response.url)

    def test_inactive_user_cannot_login(self):
        user = CustomUser.objects.create_user(
            username='inactive01',
            password='Secret@123',
            is_active=False,
        )
        response = self.client.post(
            reverse('accounts:login'),
            {'username': 'inactive01', 'password': 'Secret@123'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)


class LogoutTests(TestCase):
    """Logout must be POST-only."""

    def setUp(self):
        self.staff = CustomUser.objects.create_user(
            username='staff03',
            password='Staff@123',
            role='staff',
        )
        self.client.login(username='staff03', password='Staff@123')

    def test_logout_via_post(self):
        response = self.client.post(reverse('accounts:logout'))
        self.assertRedirects(response, reverse('accounts:login'))

    def test_logout_get_not_allowed(self):
        response = self.client.get(reverse('accounts:logout'))
        self.assertEqual(response.status_code, 405)