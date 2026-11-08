"""
Role-based access decorators.

These are the ONLY sanctioned way to enforce role access.
Never rely on template-side hiding for security.

Usage:
    @staff_required
    def staff_view(request): ...

    @principal_required
    def principal_view(request): ...

    @any_portal_user
    def shared_view(request): ...

    @role_required(['staff', 'principal'])
    def custom_view(request): ...
"""
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def role_required(allowed_roles):
    """
    Factory that returns a decorator enforcing that
    the logged-in user's role is in `allowed_roles`.

    - Not authenticated           -> redirect to login
    - Authenticated, wrong role   -> 403 Forbidden
    """
    allowed = set(allowed_roles)

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            user_role = getattr(request.user, 'role', None)

            if user_role not in allowed:
                messages.error(
                    request,
                    "Aap ko is page ka access nahi hai.",
                )
                raise PermissionDenied(
                    "Your role does not have permission to access this page."
                )

            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


# Convenience shortcuts
staff_required = role_required(['staff'])
principal_required = role_required(['principal'])
any_portal_user = role_required(['staff', 'principal'])


def student_self_required(view_func):
    """
    Allows access only to the logged-in student for their OWN records.
    Staff and Principal also have access.
    """
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        user = request.user
        
        # Principal aur Staff ko allow karein
        if user.role in ['staff', 'principal']:
            return view_func(request, *args, **kwargs)
            
        # Student ko allow karein, lekin SIRF apni ID ke liye
        if user.role == 'student':
            if not user.linked_student:
                raise PermissionDenied("Student profile not linked.")
            
            # URL se student_pk ya pk nikalne ki koshish karein
            target_pk = kwargs.get('pk') or kwargs.get('student_pk')
            
            if str(target_pk) == str(user.linked_student.pk):
                return view_func(request, *args, **kwargs)
            else:
                messages.error(request, "Aap sirf apni details dekh sakte hain.")
                raise PermissionDenied("You can only view your own records.")
                
        raise PermissionDenied("Access denied.")
    return _wrapped