"""
Django admin configuration for CustomUser.

Default UserAdmin is tailored for Django's built-in User model (with email).
Here we provide custom forms so the admin works with username-based auth.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import CustomUser


class CustomUserCreationForm(UserCreationForm):
    """Form used when creating a user via admin (Phase 1 convenience)."""

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ('username', 'role', 'full_name', 'phone', 'is_active', 'is_staff')


class CustomUserChangeForm(UserChangeForm):
    """Form used when editing an existing user via admin."""

    class Meta(UserChangeForm.Meta):
        model = CustomUser
        fields = '__all__'


@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    """Admin panel for CustomUser with role-aware list display."""

    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = CustomUser

    list_display = (
        'username',
        'full_name',
        'role',
        'is_active',
        'is_staff',
        'date_joined',
    )
    list_filter = ('role', 'is_active', 'is_staff', 'is_superuser')
    search_fields = ('username', 'full_name', 'phone')
    ordering = ('-date_joined',)
    readonly_fields = ('last_login', 'date_joined')

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Profile', {'fields': ('full_name', 'phone')}),
        ('Role & Permissions', {
            'fields': ('role', 'is_active', 'is_staff', 'is_superuser',
                       'groups', 'user_permissions'),
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username',
                'role',
                'full_name',
                'phone',
                'password1',
                'password2',
                'is_active',
                'is_staff',
            ),
        }),
    )