"""
Staff management views — Principal only.

URL map (see urls.py):
    /staff/                         staff_list
    /staff/new/                     staff_create
    /staff/<pk>/edit/               staff_edit
    /staff/<pk>/toggle/             staff_toggle_active (POST)
    /staff/<pk>/reset-password/     staff_password_reset (GET+POST)
"""
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from accounts.decorators import principal_required
from accounts.models import CustomUser

from audit.models import AuditLog
from audit.services import log_from_request, serialize_model

from .forms import StaffCreateForm, StaffEditForm, StaffPasswordResetForm


# ============================================================
# LIST
# ============================================================

@principal_required
@require_http_methods(["GET"])
def staff_list(request):
    """List all portal staff with filters."""
    q = (request.GET.get('q') or '').strip()
    status_filter = request.GET.get('status', 'all')

    qs = CustomUser.objects.filter(role='staff').order_by('-is_active', '-date_joined')

    if q:
        qs = qs.filter(
            Q(username__icontains=q)
            | Q(full_name__icontains=q)
            | Q(phone__icontains=q)
        )

    if status_filter == 'active':
        qs = qs.filter(is_active=True)
    elif status_filter == 'inactive':
        qs = qs.filter(is_active=False)

    total_count = CustomUser.objects.filter(role='staff').count()
    active_count = CustomUser.objects.filter(role='staff', is_active=True).count()
    inactive_count = CustomUser.objects.filter(role='staff', is_active=False).count()

    context = {
        'page_title': 'Staff Management',
        'page_subtitle': 'Create and manage staff accounts.',
        'active_menu': 'staff',
        'staff_members': qs,
        'search_query': q,
        'status_filter': status_filter,
        'total_count': total_count,
        'active_count': active_count,
        'inactive_count': inactive_count,
        'crumbs': [
            {'label': 'Home', 'url': reverse('accounts:redirect_after_login')},
            {'label': 'Staff Management'},
        ],
    }
    return render(request, 'staff/list.html', context)


# ============================================================
# CREATE
# ============================================================

@principal_required
@require_http_methods(["GET", "POST"])
def staff_create(request):
    """Create a new staff account."""
    form = StaffCreateForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                user = form.save()

                log_from_request(
                    request,
                    action=AuditLog.ACTION_CREATE,
                    module=AuditLog.MODULE_ACCOUNTS,
                    target=user,
                    object_repr=user.username,
                    change_summary=f"Created staff account: {user.username}",
                    new_value=serialize_model(
                        user,
                        fields=['username', 'full_name', 'phone', 'role', 'is_active'],
                    ),
                )
            messages.success(
                request,
                f"Staff '{user.get_full_name()}' created. "
                f"Username: {user.username} · Password aap ne set kiya.",
            )
            return redirect('staff:list')
        except Exception as exc:
            messages.error(request, f"Staff create nahi hua: {exc}")

    context = {
        'page_title': 'New Staff Account',
        'page_subtitle': 'Create a login for a staff member.',
        'active_menu': 'staff',
        'form': form,
        'mode': 'create',
        'form_action': reverse('staff:create'),
        'cancel_url': reverse('staff:list'),
        'crumbs': [
            {'label': 'Home', 'url': reverse('accounts:redirect_after_login')},
            {'label': 'Staff Management', 'url': reverse('staff:list')},
            {'label': 'New Staff'},
        ],
    }
    return render(request, 'staff/form.html', context)


# ============================================================
# EDIT
# ============================================================

@principal_required
@require_http_methods(["GET", "POST"])
def staff_edit(request, pk):
    """Edit existing staff account (name, phone, active)."""
    user = get_object_or_404(CustomUser, pk=pk, role='staff')

    old_state = serialize_model(
        user, fields=['full_name', 'phone', 'is_active']
    )

    form = StaffEditForm(request.POST or None, instance=user)

    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                user = form.save()
                new_state = serialize_model(
                    user, fields=['full_name', 'phone', 'is_active']
                )
                log_from_request(
                    request,
                    action=AuditLog.ACTION_UPDATE,
                    module=AuditLog.MODULE_ACCOUNTS,
                    target=user,
                    object_repr=user.username,
                    change_summary=f"Updated staff account: {user.username}",
                    previous_value=old_state,
                    new_value=new_state,
                )
            messages.success(request, f"Staff '{user.get_full_name()}' updated.")
            return redirect('staff:list')
        except Exception as exc:
            messages.error(request, f"Update nahi hua: {exc}")

    context = {
        'page_title': f'Edit Staff — {user.username}',
        'page_subtitle': user.get_full_name(),
        'active_menu': 'staff',
        'form': form,
        'staff_user': user,
        'mode': 'edit',
        'form_action': reverse('staff:edit', kwargs={'pk': user.pk}),
        'cancel_url': reverse('staff:list'),
        'crumbs': [
            {'label': 'Home', 'url': reverse('accounts:redirect_after_login')},
            {'label': 'Staff Management', 'url': reverse('staff:list')},
            {'label': user.username},
        ],
    }
    return render(request, 'staff/form.html', context)


# ============================================================
# TOGGLE ACTIVE (POST)
# ============================================================

@principal_required
@require_POST
def staff_toggle_active(request, pk):
    """Activate/deactivate staff. Never delete."""
    user = get_object_or_404(CustomUser, pk=pk, role='staff')

    # Prevent Principal from deactivating themselves through this endpoint
    if user == request.user:
        messages.error(request, "Aap apna hi account deactivate nahi kar sakte.")
        return redirect('staff:list')

    user.is_active = not user.is_active
    user.save(update_fields=['is_active'])

    action = (
        AuditLog.ACTION_ACTIVATE if user.is_active else AuditLog.ACTION_DEACTIVATE
    )
    log_from_request(
        request,
        action=action,
        module=AuditLog.MODULE_ACCOUNTS,
        target=user,
        object_repr=user.username,
        change_summary=f"{'Activated' if user.is_active else 'Deactivated'} staff: {user.username}",
    )

    state = 'activated' if user.is_active else 'deactivated'
    messages.success(request, f"Staff '{user.get_full_name()}' {state}.")
    return redirect('staff:list')


# ============================================================
# PASSWORD RESET
# ============================================================

@principal_required
@require_http_methods(["GET", "POST"])
def staff_password_reset(request, pk):
    """Reset a staff member's password (Principal overrides, no old password)."""
    user = get_object_or_404(CustomUser, pk=pk, role='staff')

    form = StaffPasswordResetForm(request.POST or None, user=user)

    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                form.save()
                log_from_request(
                    request,
                    action=AuditLog.ACTION_UPDATE,
                    module=AuditLog.MODULE_ACCOUNTS,
                    target=user,
                    object_repr=user.username,
                    change_summary=f"Password reset by Principal for: {user.username}",
                    notes="Password change logged. New password not stored in audit trail.",
                )
            messages.success(
                request,
                f"Password reset successful for '{user.get_full_name()}'. "
                f"Naya password staff ko bata dein.",
            )
            return redirect('staff:list')
        except Exception as exc:
            messages.error(request, f"Password reset nahi hua: {exc}")

    context = {
        'page_title': f'Reset Password — {user.username}',
        'page_subtitle': user.get_full_name(),
        'active_menu': 'staff',
        'form': form,
        'staff_user': user,
        'crumbs': [
            {'label': 'Home', 'url': reverse('accounts:redirect_after_login')},
            {'label': 'Staff Management', 'url': reverse('staff:list')},
            {'label': 'Reset Password'},
        ],
    }
    return render(request, 'staff/password_reset.html', context)