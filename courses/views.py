"""
Views for the courses application.

All views are Principal-only (server-side enforced).
Course records are never hard-deleted — use `toggle_active` to
deactivate. Fee categories follow the same soft-delete pattern.

URL map (see urls.py):
    /courses/                        list
    /courses/new/                    create
    /courses/<pk>/                   detail
    /courses/<pk>/edit/              edit
    /courses/<pk>/toggle/            activate/deactivate (POST)
    /courses/<pk>/fees/new/          create fee category
    /courses/<course_pk>/fees/<pk>/edit/   edit fee category
    /courses/<course_pk>/fees/<pk>/toggle/ toggle fee category (POST)
"""
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Prefetch
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from accounts.decorators import principal_required

from .forms import CourseForm, FeeCategoryForm
from .models import Course, FeeCategory


# ============================================================
# COURSE VIEWS
# ============================================================

@principal_required
@require_http_methods(["GET"])
def course_list(request):
    """List all courses with search, filter, pagination."""
    q = (request.GET.get('q') or '').strip()
    status = request.GET.get('status', 'all')

    qs = Course.objects.prefetch_related(
        Prefetch('fee_categories', queryset=FeeCategory.objects.order_by('name'))
    ).annotate(category_count=Count('fee_categories'))

    if q:
        qs = qs.filter(name__icontains=q) | qs.filter(code__icontains=q)

    if status == 'active':
        qs = qs.filter(is_active=True)
    elif status == 'inactive':
        qs = qs.filter(is_active=False)

    # Counts for tabs
    total_count = Course.objects.count()
    active_count = Course.objects.filter(is_active=True).count()
    inactive_count = Course.objects.filter(is_active=False).count()

    context = {
        'page_title': 'Course Management',
        'page_subtitle': 'Create and manage institute courses and their fee categories.',
        'active_menu': 'courses',
        'courses': qs,
        'search_query': q,
        'status_filter': status,
        'total_count': total_count,
        'active_count': active_count,
        'inactive_count': inactive_count,
        'crumbs': [
            {'label': 'Home', 'url': reverse('accounts:redirect_after_login')},
            {'label': 'Courses'},
        ],
    }
    return render(request, 'courses/list.html', context)


@principal_required
@require_http_methods(["GET", "POST"])
def course_create(request):
    """Create a new course."""
    form = CourseForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        course = form.save()
        messages.success(request, f"Course '{course.name}' successfully created.")
        return redirect('courses:detail', pk=course.pk)

    context = {
        'page_title': 'New Course',
        'page_subtitle': 'Add a new course to the institute catalog.',
        'active_menu': 'courses',
        'form': form,
        'form_action': reverse('courses:create'),
        'cancel_url': reverse('courses:list'),
        'crumbs': [
            {'label': 'Home', 'url': reverse('accounts:redirect_after_login')},
            {'label': 'Courses', 'url': reverse('courses:list')},
            {'label': 'New Course'},
        ],
    }
    return render(request, 'courses/form.html', context)


@principal_required
@require_http_methods(["GET"])
def course_detail(request, pk):
    """Course detail — shows basic info + fee categories + batches."""
    course = get_object_or_404(
        Course.objects.prefetch_related(
            'fee_categories',
            'batches',
        ),
        pk=pk,
    )

    # Ensure fee categories are fresh
    fee_categories = course.fee_categories.order_by('-is_active', 'name')

    context = {
        'page_title': course.name,
        'page_subtitle': f'Course Code: {course.code}',
        'active_menu': 'courses',
        'course': course,
        'fee_categories': fee_categories,
        'crumbs': [
            {'label': 'Home', 'url': reverse('accounts:redirect_after_login')},
            {'label': 'Courses', 'url': reverse('courses:list')},
            {'label': course.code},
        ],
    }
    return render(request, 'courses/detail.html', context)


@principal_required
@require_http_methods(["GET", "POST"])
def course_edit(request, pk):
    """Edit an existing course."""
    course = get_object_or_404(Course, pk=pk)
    form = CourseForm(request.POST or None, instance=course)

    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f"Course '{course.name}' updated.")
        return redirect('courses:detail', pk=course.pk)

    context = {
        'page_title': f'Edit {course.code}',
        'page_subtitle': 'Update course information.',
        'active_menu': 'courses',
        'form': form,
        'course': course,
        'form_action': reverse('courses:edit', kwargs={'pk': course.pk}),
        'cancel_url': reverse('courses:detail', kwargs={'pk': course.pk}),
        'crumbs': [
            {'label': 'Home', 'url': reverse('accounts:redirect_after_login')},
            {'label': 'Courses', 'url': reverse('courses:list')},
            {'label': course.code, 'url': reverse('courses:detail', kwargs={'pk': course.pk})},
            {'label': 'Edit'},
        ],
    }
    return render(request, 'courses/form.html', context)


@principal_required
@require_POST
def course_toggle_active(request, pk):
    """
    Toggle course active status. Never deletes.
    Safe because FeeCategory FK is PROTECT and Batch FK will be PROTECT.
    """
    course = get_object_or_404(Course, pk=pk)
    course.is_active = not course.is_active
    course.save(update_fields=['is_active', 'updated_at'])
    state = "activated" if course.is_active else "deactivated"
    messages.success(request, f"Course '{course.name}' {state}.")
    return redirect('courses:detail', pk=course.pk)


# ============================================================
# FEE CATEGORY VIEWS (nested under a course)
# ============================================================

@principal_required
@require_http_methods(["GET", "POST"])
def fee_category_create(request, course_pk):
    """Create a new fee category for the given course."""
    course = get_object_or_404(Course, pk=course_pk)

    form = FeeCategoryForm(
        request.POST or None,
        course=course,
    )

    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            fee = form.save()
        messages.success(
            request,
            f"Fee category '{fee.name}' added to {course.code}."
        )
        return redirect('courses:detail', pk=course.pk)

    context = {
        'page_title': f'New Fee Category — {course.code}',
        'page_subtitle': f'Add a fee category to {course.name}.',
        'active_menu': 'courses',
        'form': form,
        'course': course,
        'form_action': reverse('courses:fee_create', kwargs={'course_pk': course.pk}),
        'cancel_url': reverse('courses:detail', kwargs={'pk': course.pk}),
        'crumbs': [
            {'label': 'Home', 'url': reverse('accounts:redirect_after_login')},
            {'label': 'Courses', 'url': reverse('courses:list')},
            {'label': course.code, 'url': reverse('courses:detail', kwargs={'pk': course.pk})},
            {'label': 'New Fee Category'},
        ],
    }
    return render(request, 'courses/fee_form.html', context)


@principal_required
@require_http_methods(["GET", "POST"])
def fee_category_edit(request, course_pk, pk):
    """Edit an existing fee category."""
    course = get_object_or_404(Course, pk=course_pk)
    fee = get_object_or_404(FeeCategory, pk=pk, course=course)

    form = FeeCategoryForm(
        request.POST or None,
        instance=fee,
        course=course,
    )

    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            form.save()
        messages.success(request, f"Fee category '{fee.name}' updated.")
        return redirect('courses:detail', pk=course.pk)

    context = {
        'page_title': f'Edit Fee Category — {course.code}',
        'page_subtitle': fee.name,
        'active_menu': 'courses',
        'form': form,
        'course': course,
        'fee': fee,
        'form_action': reverse(
            'courses:fee_edit',
            kwargs={'course_pk': course.pk, 'pk': fee.pk},
        ),
        'cancel_url': reverse('courses:detail', kwargs={'pk': course.pk}),
        'crumbs': [
            {'label': 'Home', 'url': reverse('accounts:redirect_after_login')},
            {'label': 'Courses', 'url': reverse('courses:list')},
            {'label': course.code, 'url': reverse('courses:detail', kwargs={'pk': course.pk})},
            {'label': 'Edit Fee'},
        ],
    }
    return render(request, 'courses/fee_form.html', context)


@principal_required
@require_POST
def fee_category_toggle_active(request, course_pk, pk):
    """Toggle fee category active status. Never deletes."""
    course = get_object_or_404(Course, pk=course_pk)
    fee = get_object_or_404(FeeCategory, pk=pk, course=course)

    fee.is_active = not fee.is_active
    fee.save(update_fields=['is_active', 'updated_at'])

    state = "activated" if fee.is_active else "deactivated"
    messages.success(request, f"Fee category '{fee.name}' {state}.")
    return redirect('courses:detail', pk=course.pk)