"""
Dashboard analytics services.

Provides KPIs, chart data, and recent activity feeds for both
staff and principal dashboards.

All queries are read-only and optimized (select_related,
aggregations at DB level where possible, bounded result sets).
"""
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.utils import timezone

from accounts.models import CustomUser
from batches.models import Batch
from courses.models import Course
from fees import constants as FC
from fees.models import FeeObligation, FeePayment
from students.models import Student


# ============================================================
# HELPERS
# ============================================================

def _aware_start(date_obj: date) -> datetime:
    """Return timezone-aware datetime at 00:00:00 for `date_obj`."""
    return timezone.make_aware(
        datetime.combine(date_obj, time.min),
        timezone.get_current_timezone(),
    )


def _aware_end(date_obj: date) -> datetime:
    """Return timezone-aware datetime at 23:59:59.999999 for `date_obj`."""
    return timezone.make_aware(
        datetime.combine(date_obj, time.max),
        timezone.get_current_timezone(),
    )


def _month_first(date_obj: date) -> date:
    """Return first of month."""
    return date_obj.replace(day=1)


def _month_iter_back(months: int, end_date: date):
    """
    Yield first-of-month dates going back `months` from `end_date`'s month.
    Oldest first.
    """
    cursor = _month_first(end_date)
    results = [cursor]
    for _ in range(months - 1):
        if cursor.month == 1:
            cursor = cursor.replace(year=cursor.year - 1, month=12)
        else:
            cursor = cursor.replace(month=cursor.month - 1)
        results.append(cursor)
    return list(reversed(results))


# ============================================================
# STAFF DASHBOARD KPIs
# ============================================================

def get_staff_dashboard_kpis(user) -> dict:
    """
    Staff dashboard KPIs. Today's collection restricted to `user`'s payments.
    """
    today = timezone.localdate()
    today_start = _aware_start(today)
    today_end = _aware_end(today)
    month_first = _month_first(today)
    month_start = _aware_start(month_first)

    # Total active students (institute-wide, informational)
    total_students = Student.objects.filter(
        is_active=True, enrollment_status='active',
    ).count()

    # Today's admissions (institute-wide — staff should know)
    today_admissions = Student.objects.filter(admission_date=today).count()

    # Today's collection (this staff only)
    today_collection_agg = FeePayment.objects.filter(
        payment_date__gte=today_start,
        payment_date__lte=today_end,
        is_reversed=False,
        received_by=user,
    ).aggregate(total=Sum('amount'), count=Count('id'))
    today_collection = today_collection_agg['total'] or Decimal('0.00')
    today_txn_count = today_collection_agg['count'] or 0

    # Month collection (this staff only)
    month_collection_agg = FeePayment.objects.filter(
        payment_date__gte=month_start,
        payment_date__lte=today_end,
        is_reversed=False,
        received_by=user,
    ).aggregate(total=Sum('amount'), count=Count('id'))
    month_collection = month_collection_agg['total'] or Decimal('0.00')
    month_txn_count = month_collection_agg['count'] or 0

    # Pending + overdue (institute-wide)
    pending_total = Decimal('0.00')
    pending_count = 0
    overdue_total = Decimal('0.00')
    overdue_count = 0

    obligations = (
        FeeObligation.objects
        .filter(status__in=FC.OPEN_STATUSES)
        .prefetch_related('payments', 'adjustments')
    )
    for obl in obligations.iterator(chunk_size=500):
        outstanding = obl.outstanding_amount
        if outstanding <= Decimal('0.00'):
            continue
        pending_total += outstanding
        pending_count += 1
        if obl.is_overdue:
            overdue_total += outstanding
            overdue_count += 1

    return {
        'total_students': total_students,
        'today_admissions': today_admissions,
        'today_collection': today_collection,
        'today_txn_count': today_txn_count,
        'month_collection': month_collection,
        'month_txn_count': month_txn_count,
        'pending_total': pending_total,
        'pending_count': pending_count,
        'overdue_total': overdue_total,
        'overdue_count': overdue_count,
    }


# ============================================================
# PRINCIPAL DASHBOARD KPIs
# ============================================================

def get_principal_dashboard_kpis() -> dict:
    """
    Principal dashboard KPIs. Institute-wide totals (all staff combined).
    """
    today = timezone.localdate()
    today_start = _aware_start(today)
    today_end = _aware_end(today)
    month_first = _month_first(today)
    month_start = _aware_start(month_first)

    # Student counts
    total_students = Student.objects.filter(
        is_active=True, enrollment_status='active',
    ).count()
    today_admissions = Student.objects.filter(admission_date=today).count()

    # Course / Batch counts
    active_courses = Course.objects.filter(is_active=True).count()
    active_batches = Batch.objects.filter(is_active=True).count()

    # Staff count (portal staff, not principal)
    total_staff = CustomUser.objects.filter(role='staff', is_active=True).count()

    # Today's collection (all staff)
    today_agg = FeePayment.objects.filter(
        payment_date__gte=today_start,
        payment_date__lte=today_end,
        is_reversed=False,
    ).aggregate(total=Sum('amount'), count=Count('id'))
    today_collection = today_agg['total'] or Decimal('0.00')
    today_txn_count = today_agg['count'] or 0

    # Month collection
    month_agg = FeePayment.objects.filter(
        payment_date__gte=month_start,
        payment_date__lte=today_end,
        is_reversed=False,
    ).aggregate(total=Sum('amount'), count=Count('id'))
    month_collection = month_agg['total'] or Decimal('0.00')
    month_txn_count = month_agg['count'] or 0

    # Pending / overdue (institute-wide)
    pending_total = Decimal('0.00')
    pending_count = 0
    overdue_total = Decimal('0.00')
    overdue_count = 0

    obligations = (
        FeeObligation.objects
        .filter(status__in=FC.OPEN_STATUSES)
        .prefetch_related('payments', 'adjustments')
    )
    for obl in obligations.iterator(chunk_size=500):
        outstanding = obl.outstanding_amount
        if outstanding <= Decimal('0.00'):
            continue
        pending_total += outstanding
        pending_count += 1
        if obl.is_overdue:
            overdue_total += outstanding
            overdue_count += 1

    return {
        'total_students': total_students,
        'today_admissions': today_admissions,
        'active_courses': active_courses,
        'active_batches': active_batches,
        'total_staff': total_staff,
        'today_collection': today_collection,
        'today_txn_count': today_txn_count,
        'month_collection': month_collection,
        'month_txn_count': month_txn_count,
        'pending_total': pending_total,
        'pending_count': pending_count,
        'overdue_total': overdue_total,
        'overdue_count': overdue_count,
    }


# ============================================================
# CHART: Daily Collection (Line)
# ============================================================

def get_daily_collection_chart(days: int = 30, user=None) -> dict:
    """
    Line chart data: daily collection for last `days` days.

    Returns:
        {
            'labels': ['DD MMM', ...],       # N labels, oldest first
            'values': [Decimal, ...],         # N values matching labels
            'total': Decimal,
        }
    """
    today = timezone.localdate()
    start_date = today - timedelta(days=days - 1)
    start_dt = _aware_start(start_date)
    end_dt = _aware_end(today)

    qs = FeePayment.objects.filter(
        payment_date__gte=start_dt,
        payment_date__lte=end_dt,
        is_reversed=False,
    )
    if user:
        qs = qs.filter(received_by=user)

    # Aggregate per date
    agg = (
        qs.annotate(day=TruncDate('payment_date'))
        .values('day')
        .annotate(total=Sum('amount'))
        .order_by('day')
    )
    by_day = {row['day']: row['total'] for row in agg}

    labels = []
    values = []
    total = Decimal('0.00')
    for i in range(days):
        d = start_date + timedelta(days=i)
        labels.append(d.strftime('%d %b'))
        val = by_day.get(d, Decimal('0.00'))
        values.append(float(val))
        total += val

    return {
        'labels': labels,
        'values': values,
        'total': total,
    }


# ============================================================
# CHART: Monthly Revenue (Bar)
# ============================================================

def get_monthly_revenue_chart(months: int = 6) -> dict:
    """
    Bar chart data: monthly collection for last `months` months.

    Returns:
        {
            'labels': ['Aug 2025', ...],
            'values': [Decimal, ...],
            'total': Decimal,
        }
    """
    today = timezone.localdate()
    month_starts = _month_iter_back(months, today)
    start_dt = _aware_start(month_starts[0])
    end_dt = _aware_end(today)

    agg = (
        FeePayment.objects
        .filter(
            payment_date__gte=start_dt,
            payment_date__lte=end_dt,
            is_reversed=False,
        )
        .annotate(month=TruncMonth('payment_date'))
        .values('month')
        .annotate(total=Sum('amount'))
        .order_by('month')
    )
    by_month = {row['month'].date() if hasattr(row['month'], 'date') else row['month']: row['total'] for row in agg}

    labels = []
    values = []
    total = Decimal('0.00')
    for m_start in month_starts:
        labels.append(m_start.strftime('%b %Y'))
        val = by_month.get(m_start, Decimal('0.00'))
        values.append(float(val))
        total += val

    return {
        'labels': labels,
        'values': values,
        'total': total,
    }


# ============================================================
# CHART: Course Distribution (Doughnut)
# ============================================================

def get_course_distribution_chart() -> dict:
    """
    Doughnut chart data: student count per active course.

    Returns:
        {
            'labels': ['DIT', 'CIT', ...],
            'values': [45, 20, ...],
            'total': int,
        }
    """
    rows = (
        Student.objects
        .filter(is_active=True, enrollment_status='active')
        .values('course__code', 'course__name')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    labels = []
    values = []
    total = 0
    for row in rows:
        labels.append(row['course__code'] or row['course__name'])
        values.append(row['count'])
        total += row['count']

    return {
        'labels': labels,
        'values': values,
        'total': total,
    }


# ============================================================
# CHART: Batch Distribution (Bar)
# ============================================================

def get_batch_distribution_chart(limit: int = 8) -> dict:
    """
    Bar chart data: student count per active batch (top N by count).

    Returns:
        {
            'labels': ['DIT Mar 2027 - Feb 2028', ...],
            'values': [30, 25, ...],
        }
    """
    rows = (
        Student.objects
        .filter(is_active=True, enrollment_status='active')
        .values('batch_id', 'batch__course__code', 'batch__start_month', 'batch__end_month')
        .annotate(count=Count('id'))
        .order_by('-count')[:limit]
    )

    labels = []
    values = []
    for row in rows:
        start = row['batch__start_month']
        end = row['batch__end_month']
        label = (
            f"{row['batch__course__code']} "
            f"{start.strftime('%b %y') if start else '?'} – "
            f"{end.strftime('%b %y') if end else '?'}"
        )
        labels.append(label)
        values.append(row['count'])

    return {
        'labels': labels,
        'values': values,
    }


# ============================================================
# CHART: Fee Status Distribution (Doughnut)
# ============================================================

def get_fee_status_chart() -> dict:
    """
    Doughnut chart data: obligation count per effective status.

    Uses live computation (not stored status) to be accurate.
    """
    counts = {
        FC.STATUS_PAID: 0,
        FC.STATUS_PARTIAL: 0,
        FC.STATUS_PENDING: 0,
        FC.STATUS_OVERDUE: 0,
        FC.STATUS_WAIVED: 0,
    }

    obligations = (
        FeeObligation.objects
        .prefetch_related('payments', 'adjustments')
    )
    for obl in obligations.iterator(chunk_size=500):
        status = obl.effective_status
        if status in counts:
            counts[status] += 1

    labels = ['Paid', 'Partial', 'Pending', 'Overdue', 'Waived']
    values = [
        counts[FC.STATUS_PAID],
        counts[FC.STATUS_PARTIAL],
        counts[FC.STATUS_PENDING],
        counts[FC.STATUS_OVERDUE],
        counts[FC.STATUS_WAIVED],
    ]

    return {
        'labels': labels,
        'values': values,
        'total': sum(values),
    }


# ============================================================
# RECENT ACTIVITY
# ============================================================

def get_recent_admissions(limit: int = 5) -> list:
    """Recent students admitted — newest first."""
    return list(
        Student.objects
        .select_related('course', 'batch')
        .order_by('-created_at')[:limit]
    )


def get_recent_payments(limit: int = 10, user=None) -> list:
    """Recent payments — newest first. If user provided, only theirs."""
    qs = (
        FeePayment.objects
        .select_related('obligation__student', 'received_by')
        .filter(is_reversed=False)
        .order_by('-payment_date')
    )
    if user:
        qs = qs.filter(received_by=user)
    return list(qs[:limit])


def get_recent_audit_activity(limit: int = 5) -> list:
    """
    Placeholder — Phase 8 will implement audit log. Returns empty for now.
    """
    return []