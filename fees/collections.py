"""
Collection aggregation services for the fees application.

Separate from services.py (which handles transactions).
This module answers "how much / how many / which ones" questions
for dashboards, lists, and reports.

All functions are read-only and safe to call from any view.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone

from batches.models import Batch
from courses.models import Course
from students.models import Student

from . import constants as C
from .models import FeeObligation, FeePayment


# ============================================================
# TODAY / PERIOD COLLECTIONS
# ============================================================

def get_today_collections(staff_user=None):
    """
    Return dict summarizing today's collections.

    If `staff_user` is provided, restricts to payments received by
    that staff member (staff portal use case).
    Principal passes None → sees all.

    Returns:
        {
            'total': Decimal,
            'count': int,
            'payments': QuerySet,
        }
    """
    today = timezone.localdate()
    start = timezone.make_aware(
        timezone.datetime.combine(today, timezone.datetime.min.time())
    )
    end = start + timedelta(days=1)

    qs = (
        FeePayment.objects
        .filter(
            payment_date__gte=start,
            payment_date__lt=end,
            is_reversed=False,
        )
        .select_related('obligation__student', 'received_by')
        .order_by('-payment_date')
    )

    if staff_user:
        qs = qs.filter(received_by=staff_user)

    agg = qs.aggregate(total=Sum('amount'), count=Count('id'))

    return {
        'total': agg['total'] or C.ZERO,
        'count': agg['count'] or 0,
        'payments': qs,
    }


def get_period_collections(start_date, end_date, staff_user=None):
    """
    Return collections in [start_date, end_date] inclusive.

    Both dates are Python `date` objects; converted to datetimes.
    Staff filter optional.
    """
    start = timezone.make_aware(
        timezone.datetime.combine(start_date, timezone.datetime.min.time())
    )
    end = timezone.make_aware(
        timezone.datetime.combine(end_date, timezone.datetime.max.time())
    )

    qs = (
        FeePayment.objects
        .filter(
            payment_date__gte=start,
            payment_date__lte=end,
            is_reversed=False,
        )
        .select_related('obligation__student', 'received_by')
        .order_by('-payment_date')
    )

    if staff_user:
        qs = qs.filter(received_by=staff_user)

    agg = qs.aggregate(total=Sum('amount'), count=Count('id'))

    return {
        'total': agg['total'] or C.ZERO,
        'count': agg['count'] or 0,
        'payments': qs,
        'start_date': start_date,
        'end_date': end_date,
    }


# ============================================================
# DASHBOARD KPIs
# ============================================================

def get_collection_kpis(staff_user=None):
    """
    Return KPI dict for dashboards.

    If staff_user is provided, today's collection reflects only that
    staff's payments (staff dashboard behavior). Principal passes None.

    Returns:
        {
            'today_total': Decimal,
            'today_count': int,
            'month_total': Decimal,
            'month_count': int,
            'pending_total': Decimal,
            'pending_count': int,
            'overdue_total': Decimal,
            'overdue_count': int,
        }
    """
    today_result = get_today_collections(staff_user=staff_user)

    today = timezone.localdate()
    month_start = today.replace(day=1)
    month_result = get_period_collections(month_start, today, staff_user=staff_user)

    # Pending / overdue — computed at row-level (outstanding needs per-row calc)
    pending_total = C.ZERO
    pending_count = 0
    overdue_total = C.ZERO
    overdue_count = 0

    qs = (
        FeeObligation.objects
        .select_related('student')
        .filter(status__in=C.OPEN_STATUSES)
        .prefetch_related('payments', 'adjustments')
    )

    # FIX: chunk_size added for prefetch_related().iterator()
    for obl in qs.iterator(chunk_size=500):
        outstanding = obl.outstanding_amount
        if outstanding <= C.ZERO:
            continue
        pending_total += outstanding
        pending_count += 1
        if obl.is_overdue:
            overdue_total += outstanding
            overdue_count += 1

    return {
        'today_total': today_result['total'],
        'today_count': today_result['count'],
        'month_total': month_result['total'],
        'month_count': month_result['count'],
        'pending_total': pending_total,
        'pending_count': pending_count,
        'overdue_total': overdue_total,
        'overdue_count': overdue_count,
    }


# ============================================================
# PENDING BY COURSE / BATCH
# ============================================================

def get_pending_by_course():
    """
    Return list of dicts:
        [
            {'course': Course, 'pending_total': Decimal, 'student_count': int},
            ...
        ]
    Ordered by pending_total desc.
    """
    qs = (
        FeeObligation.objects
        .select_related('student__course')
        .filter(status__in=C.OPEN_STATUSES)
        .prefetch_related('payments', 'adjustments')
    )

    by_course = {}
    # FIX: chunk_size added
    for obl in qs.iterator(chunk_size=500):
        outstanding = obl.outstanding_amount
        if outstanding <= C.ZERO:
            continue
        course = obl.student.course
        bucket = by_course.setdefault(
            course.pk,
            {
                'course': course,
                'pending_total': C.ZERO,
                'student_ids': set(),
            }
        )
        bucket['pending_total'] += outstanding
        bucket['student_ids'].add(obl.student_id)

    result = [
        {
            'course': v['course'],
            'pending_total': v['pending_total'],
            'student_count': len(v['student_ids']),
        }
        for v in by_course.values()
    ]
    result.sort(key=lambda x: x['pending_total'], reverse=True)
    return result


def get_pending_by_batch():
    """
    Return list of dicts:
        [
            {'batch': Batch, 'pending_total': Decimal, 'student_count': int},
            ...
        ]
    Ordered by pending_total desc.
    """
    qs = (
        FeeObligation.objects
        .select_related('student__batch__course')
        .filter(status__in=C.OPEN_STATUSES)
        .prefetch_related('payments', 'adjustments')
    )

    by_batch = {}
    # FIX: chunk_size added
    for obl in qs.iterator(chunk_size=500):
        outstanding = obl.outstanding_amount
        if outstanding <= C.ZERO:
            continue
        batch = obl.student.batch
        bucket = by_batch.setdefault(
            batch.pk,
            {
                'batch': batch,
                'pending_total': C.ZERO,
                'student_ids': set(),
            }
        )
        bucket['pending_total'] += outstanding
        bucket['student_ids'].add(obl.student_id)

    result = [
        {
            'batch': v['batch'],
            'pending_total': v['pending_total'],
            'student_count': len(v['student_ids']),
        }
        for v in by_batch.values()
    ]
    result.sort(key=lambda x: x['pending_total'], reverse=True)
    return result


# ============================================================
# OVERDUE AGING BUCKETS
# ============================================================

def get_overdue_aging_buckets():
    """
    Return overdue amounts bucketed by days past due:
        0–30, 31–60, 61–90, 90+

    Returns:
        [
            {'label': '0–30 days', 'total': Decimal, 'count': int},
            {'label': '31–60 days', 'total': Decimal, 'count': int},
            {'label': '61–90 days', 'total': Decimal, 'count': int},
            {'label': '90+ days', 'total': Decimal, 'count': int},
        ]
    """
    buckets = [
        {'label': '0–30 days', 'total': C.ZERO, 'count': 0},
        {'label': '31–60 days', 'total': C.ZERO, 'count': 0},
        {'label': '61–90 days', 'total': C.ZERO, 'count': 0},
        {'label': '90+ days', 'total': C.ZERO, 'count': 0},
    ]

    today = timezone.localdate()
    qs = (
        FeeObligation.objects
        .filter(
            due_date__lt=today,
            status__in=(C.STATUS_PENDING, C.STATUS_PARTIAL, C.STATUS_OVERDUE),
        )
        .prefetch_related('payments', 'adjustments')
    )

    # FIX: chunk_size added
    for obl in qs.iterator(chunk_size=500):
        outstanding = obl.outstanding_amount
        if outstanding <= C.ZERO:
            continue
        if obl.is_waived:
            continue

        days = (today - obl.due_date).days
        if days <= 30:
            idx = 0
        elif days <= 60:
            idx = 1
        elif days <= 90:
            idx = 2
        else:
            idx = 3

        buckets[idx]['total'] += outstanding
        buckets[idx]['count'] += 1

    return buckets


# ============================================================
# SEARCH & QUICK COLLECT
# ============================================================

def search_students_for_collection(query, limit=20):
    """
    Search active students matching `query` (name/ID/mobile) that
    have at least one open obligation.

    Returns list of dicts:
        [
            {
                'student': Student,
                'outstanding_total': Decimal,
                'overdue_total': Decimal,
                'open_count': int,
            },
            ...
        ]
    Ordered by overdue_total desc (worst first), then name.
    """
    if not query or not query.strip():
        return []

    q = query.strip()
    students = (
        Student.objects
        .select_related('course', 'batch')
        .filter(
            Q(student_name__icontains=q)
            | Q(student_id__icontains=q)
            | Q(student_mobile__icontains=q)
            | Q(father_name__icontains=q)
        )
        .filter(is_active=True)[:limit]
    )

    results = []
    for student in students:
        obligations = (
            FeeObligation.objects
            .filter(
                student=student,
                status__in=C.OPEN_STATUSES,
            )
            .prefetch_related('payments', 'adjustments')
        )

        outstanding_total = C.ZERO
        overdue_total = C.ZERO
        open_count = 0

        # Plain iteration (no .iterator()) — small result set, no chunk_size needed
        for obl in obligations:
            outstanding = obl.outstanding_amount
            if outstanding <= C.ZERO:
                continue
            outstanding_total += outstanding
            open_count += 1
            if obl.is_overdue:
                overdue_total += outstanding

        if open_count > 0:
            results.append({
                'student': student,
                'outstanding_total': outstanding_total,
                'overdue_total': overdue_total,
                'open_count': open_count,
            })

    results.sort(key=lambda r: (-float(r['overdue_total']), r['student'].student_name))
    return results


def get_student_quick_obligations(student):
    """
    Return open obligations for a student (for quick collect page).

    Ordered by due_date asc (oldest first) so the most urgent are at top.
    """
    obligations = (
        FeeObligation.objects
        .filter(
            student=student,
            status__in=C.OPEN_STATUSES,
        )
        .select_related('fee_category')
        .prefetch_related('payments', 'adjustments')
        .order_by('due_date', 'id')
    )

    # Filter to actual outstanding > 0
    return [o for o in obligations if o.outstanding_amount > C.ZERO and not o.is_waived]