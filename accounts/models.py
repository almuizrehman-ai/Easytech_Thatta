"""
CustomUser model for EASYTECH THATTA.

A single user model serves both portals:
  - 'staff'     : Admission + Fee Collection operator
  - 'principal' : Full administrative control

Design notes:
- Login is username-based (no email field).
- Role field drives server-side permission checks via decorators.
- is_staff (Django admin access) and role are independent concepts:
  staff portal users have role='staff' but is_staff=False by default.
"""
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from .managers import CustomUserManager


class CustomUser(AbstractBaseUser, PermissionsMixin):
    """Unified user account for staff and principal portals."""

    ROLE_STAFF = 'staff'
    ROLE_PRINCIPAL = 'principal'
    ROLE_STUDENT = 'student'

    ROLE_CHOICES = (
        ('staff', 'Staff'),
        ('principal', 'Principal'),
        ('student', 'Student'),  # <--- YEH NAYA ROLE HAI
    )
    linked_student = models.OneToOneField(
        'students.Student',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='user_account',
        help_text="Link to the student profile if this is a student account."
    )
    # ---------- Identity ----------
    username = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Login username (e.g., staff01, principal01).",
    )

    # ---------- Profile ----------
    full_name = models.CharField(
        max_length=150,
        blank=True,
        help_text="Display name shown across the dashboard.",
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        help_text="Contact number (optional).",
    )

    # ---------- Authorization ----------
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_STAFF,
        db_index=True,
        help_text="Determines portal access: Staff or Principal.",
    )

    # ---------- Status flags ----------
    is_staff = models.BooleanField(
        default=False,
        help_text="Grants access to Django admin site.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive users cannot log in.",
    )

    # ---------- Timestamps ----------
    date_joined = models.DateTimeField(default=timezone.now, editable=False)
    last_login = models.DateTimeField(blank=True, null=True, editable=False)

    # ---------- Manager ----------
    objects = CustomUserManager()

    # ---------- Django auth wiring ----------
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []  # createsuperuser will only prompt for username + password

    class Meta:
        ordering = ['-date_joined']
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        indexes = [
            models.Index(fields=['role', 'is_active']),
        ]

    def __str__(self):
        display = self.full_name.strip() or self.username
        return f"{display} ({self.get_role_display()})"

    # ---------- Convenience helpers ----------
    @property
    def is_principal(self) -> bool:
        """True if this user is a Principal."""
        return self.role == self.ROLE_PRINCIPAL

    @property
    def is_portal_staff(self) -> bool:
        """True if this user is Staff (portal role, not Django admin flag)."""
        return self.role == self.ROLE_STAFF

    def get_short_name(self) -> str:
        return self.full_name.split(' ')[0] if self.full_name else self.username

    def get_full_name(self) -> str:
        return self.full_name.strip() or self.username