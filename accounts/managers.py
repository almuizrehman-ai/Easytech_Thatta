"""
Custom manager for the CustomUser model.

Why a custom manager is required:
- Django's default UserManager assumes an 'email' field.
- Our model identifies users by 'username' only.
- Role defaults must be enforced (staff for normal users, principal for superusers).
"""
from django.contrib.auth.models import BaseUserManager


class CustomUserManager(BaseUserManager):
    """Manager for CustomUser supporting username-based authentication."""

    use_in_migrations = True

    def _create_user(self, username, password, **extra_fields):
        if not username:
            raise ValueError("Username must be provided.")
        if not password:
            raise ValueError("Password must be provided.")

        username = username.strip()
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, username, password=None, **extra_fields):
        """
        Create and return a regular portal user.
        Default role = 'staff'. No elevated privileges.
        """
        extra_fields.setdefault('role', 'staff')
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        extra_fields.setdefault('is_active', True)
        return self._create_user(username, password, **extra_fields)

    def create_superuser(self, username, password=None, **extra_fields):
        """
        Create and return a superuser (Principal).
        Role forced to 'principal'; Django admin access granted.
        """
        extra_fields.setdefault('role', 'principal')
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get('is_superuser') is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        if extra_fields.get('role') != 'principal':
            raise ValueError("Superuser must have role='principal'.")

        return self._create_user(username, password, **extra_fields)