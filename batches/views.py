"""
Views for the batches application.

All views are Principal-only (server-side enforced via decorators).
Batches are never hard-deleted; use `toggle_active`.
"""
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from accounts.decorators import principal_required
from courses.models import Course

from .forms import BatchForm
from .models import Batch


# ============================================================
# BATCH VIEWS
# ============================================================

@principal_required
@require_http_methods(["GET"])
def batch_list(request):
    """List all batches with course filter + status filter + search."""
    q = (request.GET.get('q') or '').strip()
    status = request.GET.get('status', 'all')
    course_filter = request.GET.get('course', '')

    qs = Batch.objects.select_related('course').annotate(
        student_count=Count('students') if hasattr(Batch, 'students') else Count('pk'),
    )

    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(course__name__icontains=q)
            | Q(course__code__icontains=q)
        )

    if status == 'active':
        qs = qs.filter(is_active=True)
    elif status == 'inactive':
        qs = qs.filter(is_active=False)

    if course_filter and course_filter.isdigit():
        qs = qs.filter(course_id=int(course_filter))

    # Counts for tabs
    total_count = Batch.objects.count()
    active_count = Batch.objects.filter(is_active=True).count()
    inactive_count = Batch.objects.filter(is_active=False).count()

    context = {
        'page_title': 'Batch Management',
        'page_subtitle': 'Manage course batches, durations, and monthly fees.',
        'active_menu': 'batches',
        'batches': qs,
        'courses': Course.objects.order_by('-is_active', 'name'),
        'search_query': q,
        'status_filter': status,
        'course_filter': course_filter,
        'total_count': total_count,
        'active_count': active_count,
        'inactive_count': inactive_count,
        'crumbs': [
            {'label': 'Home', 'url': reverse('accounts:redirect_after_login')},
            {'label': 'Batches'},
        ],
    }
    return render(request, 'batches/list.html', context)


@principal_required
@require_http_methods(["GET", "POST"])
def batch_create(request):
    """Create a new batch. end_month is auto-computed by model.save()."""
    form = BatchForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            batch = form.save()
        messages.success(
            request,
            f"Batch '{batch.display_name}' created — "
            f"runs {batch.start_month.strftime('%b %Y')} to {batch.end_month.strftime('%b %Y')}."
        )
        return redirect('batches:detail', pk=batch.pk)

    context = {
        'page_title': 'New Batch',
        'page_subtitle': 'Create a batch under an existing course.',
        'active_menu': 'batches',
        'form': form,
        'form_action': reverse('batches:create'),
        'cancel_url': reverse('batches:list'),
        'crumbs': [
            {'label': 'Home', 'url': reverse('accounts:redirect_to_login') if False else reverse('accounts:redirect_after_login')},
            {'label': 'Batches', 'url': reverse('batches:list')},
            {'label': 'New Batch'},
        ],
    }
    return render(request, 'batches/form.html', context)


@principal_required
@require_http_methods(["GET"])
def batch_detail(request, pk):
    """Batch detail — shows info and (future) enrolled students."""
    batch = get_object_or_404(
        Batch.objects.select_related('course'),
        pk=pk,
    )

    context = {
        'page_title': batch.display_name,
        'page_subtitle': f'{batch.course.code} · {batch.duration_months} months',
        'active_menu': 'batches',
        'batch': batch,
        'crumbs': [
            {'label': 'Home', 'url': reverse('accounts:redirect_after_login')},
            {'label': 'Batches', 'url': reverse('batches:list')},
            {'label': batch.display_name},
        ],
    }
    return render(request, 'batches/detail.html', context)


@principal_required
@require_http_methods(["GET", "POST"])
def batch_edit(request, pk):
    """Edit an existing batch."""
    batch = get_object_or_404(Batch.objects.select_related('course'), pk=pk)
    form = BatchForm(request.POST or None, instance=batch)

    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            form.save()
        messages.success(request, f"Batch '{batch.display_name}' updated.")
        return redirect('batches:detail', pk=batch.pk)

    context = {
        'page_title': f'Edit Batch — {batch.display_name}',
        'page_subtitle': 'Update batch details. End month is auto-calculated.',
        'active_menu': 'batches',
        'form': form,
        'batch': batch,
        'form_action': reverse('batches:edit', kwargs={'pk': batch.pk}),
        'cancel_url': reverse('batches:detail', kwargs={'pk': batch.pk}),
        'crumbs': [
            {'label': 'Home', 'url': reverse('accounts:redirect_after_login')},
            {'label': 'Batches', 'url': reverse('batches:list')},
            {'label': batch.display_name, 'url': reverse('batches:detail', kwargs={'pk': batch.pk})},
            {'label': 'Edit'},
        ],
    }
    return render(request, 'batches/form.html', context)


@principal_required
@require_POST
def batch_toggle_active(request, pk):
    """
    Toggle batch active status. Never deletes.

    Safety: batches with enrolled students can still be deactivated —
    this stops new admissions but preserves all student fee ledgers.
    """
    batch = get_object_or_404(Batch, pk=pk)
    batch.is_active = not batch.is_active
    batch.save(update_fields=['is_active', 'updated_at'])

    state = "activated" if batch.is_active else "deactivated"
    messages.success(request, f"Batch '{batch.display_name}' {state}.")
    return redirect('batches:detail', pk=batch.pk)