"""
Audit log viewer — Principal only.

Provides a paginated, filterable timeline of audit entries.
"""
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from accounts.decorators import principal_required

from .models import AuditLog


@principal_required
@require_http_methods(["GET"])
def log_list(request):
    """Paginated audit log viewer with filters."""
    action_filter = request.GET.get('action', '')
    module_filter = request.GET.get('module', '')
    q = (request.GET.get('q') or '').strip()

    qs = (
        AuditLog.objects
        .select_related('user', 'content_type')
        .order_by('-created_at')
    )

    if action_filter and action_filter in dict(AuditLog.ACTION_CHOICES):
        qs = qs.filter(action=action_filter)
    if module_filter and module_filter in dict(AuditLog.MODULE_CHOICES):
        qs = qs.filter(module=module_filter)
    if q:
        qs = qs.filter(
            Q(object_repr__icontains=q)
            | Q(change_summary__icontains=q)
            | Q(user__username__icontains=q)
            | Q(user__full_name__icontains=q)
        )

    # Pagination — 50 per page
    paginator = Paginator(qs, 50)
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    # Preserve query string minus 'page' for pagination links
    query_params = request.GET.copy()
    query_params.pop('page', None)
    query_string = query_params.urlencode()

    context = {
        'page_title': 'Audit Logs',
        'page_subtitle': 'Immutable record of all important system actions.',
        'active_menu': 'audit',
        'logs': page_obj.object_list,
        'page_obj': page_obj,
        'query_string': query_string,
        'action_filter': action_filter,
        'module_filter': module_filter,
        'search_query': q,
        'action_choices': AuditLog.ACTION_CHOICES,
        'module_choices': AuditLog.MODULE_CHOICES,
        'crumbs': [
            {'label': 'Home', 'url': reverse('accounts:redirect_after_login')},
            {'label': 'Audit Logs'},
        ],
    }
    return render(request, 'audit/log_list.html', context)