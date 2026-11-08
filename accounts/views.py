"""
Authentication views for EASYTECH THATTA.
"""
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .forms import (
    CustomPasswordResetForm,
    ForgotPasswordForm,
    PortalLoginForm,
)


@never_cache
@require_http_methods(["GET", "POST"])
def login_view(request):
    """
    Single login page for all portals (Staff, Principal, Student).
    On success, user is redirected to /post-login/ which decides destination.
    """
    if request.user.is_authenticated:
        return redirect('accounts:redirect_after_login')

    form = PortalLoginForm(request=request, data=request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(
                request,
                f"Welcome, {user.get_full_name()}!",
            )
            return redirect('accounts:redirect_after_login')

        messages.error(request, "Login fail. Details check karein.")

    return render(request, 'accounts/login.html', {'form': form})


@login_required
@require_http_methods(["POST"])
def logout_view(request):
    """Log out via POST only (CSRF-protected)."""
    logout(request)
    messages.info(request, "Aap safely logout ho gaye.")
    return redirect('accounts:login')


@login_required
def redirect_after_login(request):
    """
    Central role router.
    - Principal -> Principal dashboard
    - Student   -> Student dashboard
    - Staff     -> Staff dashboard
    """
    role = getattr(request.user, 'role', None)

    if role == 'principal':
        return redirect('dashboard:principal')
    elif role == 'student':
        return redirect('dashboard:student')
    else:
        return redirect('dashboard:staff')


@never_cache
def forgot_password_view(request):
    """Step 1: Verify username and mobile."""
    form = ForgotPasswordForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        request.session['reset_user_id'] = form.user_cache.pk
        return redirect('accounts:reset_password')

    return render(request, 'accounts/forgot_password.html', {'form': form})


@never_cache
def reset_password_view(request):
    """Step 2: Set a new password."""
    user_id = request.session.get('reset_user_id')
    if not user_id:
        messages.error(request, "Pehle apna username verify karein.")
        return redirect('accounts:forgot_password')

    form = CustomPasswordResetForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        from accounts.models import CustomUser
        try:
            user = CustomUser.objects.get(pk=user_id)
            new_pass = form.cleaned_data['new_password']
            user.set_password(new_pass)
            user.save()

            if user.role == 'student' and user.linked_student:
                student = user.linked_student
                student.portal_password = new_pass
                student.save(update_fields=['portal_password'])

            del request.session['reset_user_id']
            messages.success(
                request,
                "Password successfully reset ho gaya. Ab aap login kar sakte hain.",
            )
            return redirect('accounts:login')
        except CustomUser.DoesNotExist:
            messages.error(request, "Kuch masla ho gaya. Dobara koshish karein.")
            return redirect('accounts:forgot_password')

    return render(request, 'accounts/reset_password.html', {'form': form})