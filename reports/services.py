"""
Report services — row-level detail and totals.

Used by:
    - reports/views.py (list + export trigger)
    - reports/exporters.py (Excel + PDF)
"""
from datetime import date, datetime, time
from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone

from fees import constants as FC
from fees.models import FeePayment


def _aware_start(date_obj: date) -> datetime:
    """Start-of-day aware datetime."""
    return timezone.make_aware(
        datetime.combine(date_obj, time.min),
        timezone.get_current_timezone(),
    )


def _aware_end(date_obj: date) -> datetime:
    """End-of-day aware datetime."""
    return timezone.make_aware(
        datetime.combine(date_obj, time.max),
        timezone.get_current_timezone(),
    )


def build_collection_report(*, start_date, end_date, course=None, batch=None,
                             staff=None, payment_method=None, search=''):
    """
    Build the collection report queryset and summary.

    Args:
        start_date, end_date: Python date objects (inclusive)
        course: Course instance or None
        batch: Batch instance or None
        staff: CustomUser instance or None (received_by filter)
        payment_method: str or None
        search: string to filter student name / ID / txn_id

    Returns:
        dict:
            {
                'queryset': QuerySet<FeePayment>,
                'total': Decimal,
                'count': int,
                'by_method': [{method_label, total, count}, ...],
                'start_date': date,
                'end_date': date,
            }
    """
    start_dt = _aware_start(start_date)
    end_dt = _aware_end(end_date)

    qs = (
        FeePayment.objects
        .filter(
            payment_date__gte=start_dt,
            payment_date__lte=end_dt,
            is_reversed=False,
        )
        .select_related(
            'obligation__student__course',
            'obligation__student__batch',
            'obligation__fee_category',
            'received_by',
        )
        .order_by('-payment_date')
    )

    # Optional filters
    if course:
        qs = qs.filter(obligation__student__course=course)
    if batch:
        qs = qs.filter(obligation__student__batch=batch)
    if staff:
        qs = qs.filter(received_by=staff)
    if payment_method:
        qs = qs.filter(payment_method=payment_method)
    if search:
        qs = qs.filter(
            models_Q_search(search)
        )

    # Aggregate totals — database-level
    agg = qs.aggregate(total=Sum('amount'), count=Count('id'))
    total = agg['total'] or Decimal('0.00')
    count = agg['count'] or 0

    # By-method breakdown — only when no method filter (else it's single-method anyway)
    by_method = []
    if not payment_method:
        method_rows = (
            qs.values('payment_method')
            .annotate(total=Sum('amount'), count=Count('id'))
            .order_by('-total')
        )
        method_labels = dict(FC.PAYMENT_METHOD_CHOICES)
        for row in method_rows:
            by_method.append({
                'method_key': row['payment_method'],
                'method_label': method_labels.get(row['payment_method'], row['payment_method']),
                'total': row['total'] or Decimal('0.00'),
                'count': row['count'] or 0,
            })

    return {
        'queryset': qs,
        'total': total,
        'count': count,
        'by_method': by_method,
        'start_date': start_date,
        'end_date': end_date,
    }


def models_Q_search(query):
    """Search across student name, ID, txn_id."""
    from django.db.models import Q
    q = query.strip()
    return (
        Q(obligation__student__student_name__icontains=q)
        | Q(obligation__student__student_id__icontains=q)
        | Q(obligation__student__father_name__icontains=q)
        | Q(transaction_id__icontains=q)
    )


def get_report_rows_for_export(queryset, limit=None):
    """
    Iterate queryset and yield dicts — export-friendly shape.

    Each row:
        {
            'transaction_id': str,
            'student_id': str,
            'student_name': str,
            'father_name': str,
            'course_code': str,
            'course_name': str,
            'batch_name': str,
            'fee_category': str,
            'obligation_month': str,   # 'Mar 2027' or ''
            'amount': Decimal,
            'payment_date': datetime,
            'payment_method_label': str,
            'received_by': str,
            'notes': str,
        }
    """
    iterable = queryset if not limit else queryset[:limit]

    method_labels = dict(FC.PAYMENT_METHOD_CHOICES)

    for p in iterable:
        student = p.obligation.student
        obligation = p.obligation
        yield {
            'transaction_id': p.transaction_id,
            'student_id': student.student_id,
            'student_name': student.student_name,
            'father_name': student.father_name,
            'course_code': student.course.code,
            'course_name': student.course.name,
            'batch_name': student.batch.display_name if student.batch else '',
            'fee_category': (
                obligation.fee_category.name if obligation.fee_category
                else obligation.get_obligation_type_display()
            ),
            'obligation_month': obligation.month_label if obligation.obligation_month else '',
            'amount': p.amount,
            'payment_date': p.payment_date,
            'payment_method_label': method_labels.get(p.payment_method, p.payment_method),
            'received_by': (
                p.received_by.get_full_name() if p.received_by else ''
            ),
            'notes': p.notes or '',
        }