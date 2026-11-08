import json
from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Sum, Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, JsonResponse

from accounts.decorators import any_portal_user, principal_required, student_self_required
from courses.models import Course, FeeCategory
from students.models import Student

from . import collections as collection_services
from . import constants as C
from . import services
from . import corrections as correction_services
from .forms import (
    PaymentForm, WaiverForm, ConcessionForm,
    CorrectionRequestForm, CorrectionReviewForm,
    ManualFeeForm
)
from .models import FeeObligation, FeePayment, FeeAdjustment, PaymentCorrectionRequest

# ============================================================
# LEDGER (Phase 5)
# ============================================================

@student_self_required
@require_http_methods(["GET"])
def student_ledger(request, student_pk):
    """Full fee ledger for a student."""
    student = get_object_or_404(
        Student.objects.select_related('course', 'batch'),
        pk=student_pk,
    )

    obligations = services.get_ledger_for_student(student)
    summary = services.get_student_fee_summary(student)

    context = {
        'page_title': f'Fee Ledger — {student.student_name}',
        'page_subtitle': f'Student ID: {student.student_id}',
        'active_menu': 'fees',
        'student': student,
        'obligations': obligations,
        'summary': summary,
        'crumbs': [
            {'label': 'Home', 'url': reverse('accounts:redirect_after_login')},
            {'label': 'Students', 'url': reverse('students:list')},
            {'label': student.student_id, 'url': reverse('students:detail', kwargs={'pk': student.pk})},
            {'label': 'Fee Ledger'},
        ],
    }
    return render(request, 'fees/student_ledger.html', context)


@any_portal_user
@require_http_methods(["GET"])
def obligation_detail(request, pk):
    """Single obligation with payment history + adjustments."""
    obligation = get_object_or_404(
        FeeObligation.objects
        .select_related('student__course', 'student__batch', 'fee_category')
        .prefetch_related(
            'payments__received_by',
            'adjustments__approved_by',
        ),
        pk=pk,
    )

    context = {
        'page_title': f'Obligation — {obligation.month_label if obligation.obligation_month else obligation.get_obligation_type_display()}',
        'page_subtitle': f'{obligation.student.student_name} · {obligation.student.student_id}',
        'active_menu': 'fees',
        'obligation': obligation,
        'payments': obligation.payments.order_by('-payment_date'),
        'adjustments': obligation.adjustments.order_by('-created_at'),
        'crumbs': [
            {'label': 'Home', 'url': reverse('accounts:redirect_after_login')},
            {'label': 'Students', 'url': reverse('students:list')},
            {'label': obligation.student.student_id, 'url': reverse('students:detail', kwargs={'pk': obligation.student.pk})},
            {'label': 'Fee Ledger', 'url': reverse('fees:student_ledger', kwargs={'student_pk': obligation.student.pk})},
            {'label': 'Obligation'},
        ],
    }
    return render(request, 'fees/obligation_detail.html', context)


# ============================================================
# RECORD PAYMENT (Phase 5)
# ============================================================

@any_portal_user
@require_http_methods(["GET", "POST"])
def record_payment(request, obligation_pk):
    """Record a payment against an obligation."""
    obligation = get_object_or_404(
        FeeObligation.objects.select_related('student'),
        pk=obligation_pk,
    )

    if obligation.is_waived:
        messages.warning(request, "Yeh obligation waive hai — payment possible nahi.")
        return redirect('fees:obligation_detail', pk=obligation.pk)

    if obligation.outstanding_amount <= C.ZERO:
        messages.info(request, "Yeh obligation already fully paid hai.")
        return redirect('fees:obligation_detail', pk=obligation.pk)

    form = PaymentForm(request.POST or None, obligation=obligation)

    if request.method == 'POST' and form.is_valid():
        result = services.record_payment(
            obligation=obligation,
            amount=form.cleaned_data['amount'],
            payment_method=form.cleaned_data['payment_method'],
            payment_date=form.cleaned_data.get('payment_date'),
            notes=form.cleaned_data.get('notes', ''),
            received_by=request.user,
        )

        if result.success:
            messages.success(
                request,
                f"Payment recorded. Txn: {result.payment.transaction_id} · "
                f"Rs. {result.payment.amount:.2f}"
            )
            return redirect('fees:receipt', payment_pk=result.payment.pk)
        else:
            messages.error(request, f"Payment save nahi hui: {result.error}")

    context = {
        'page_title': 'Record Payment',
        'page_subtitle': (
            f'{obligation.student.student_name} · '
            f'{obligation.month_label if obligation.obligation_month else obligation.get_obligation_type_display()}'
        ),
        'active_menu': 'fees',
        'obligation': obligation,
        'form': form,
        'crumbs': [
            {'label': 'Home', 'url': reverse('accounts:redirect_after_login')},
            {'label': 'Students', 'url': reverse('students:list')},
            {'label': obligation.student.student_id, 'url': reverse('students:detail', kwargs={'pk': obligation.student.pk})},
            {'label': 'Fee Ledger', 'url': reverse('fees:student_ledger', kwargs={'student_pk': obligation.student.pk})},
            {'label': 'Obligation', 'url': reverse('fees:obligation_detail', kwargs={'pk': obligation.pk})},
            {'label': 'Payment'},
        ],
    }
    return render(request, 'fees/payment_form.html', context)


# ============================================================
# WAIVER / CONCESSION (Phase 5)
# ============================================================

@principal_required
@require_http_methods(["GET", "POST"])
def apply_waiver(request, obligation_pk):
    """Apply full waiver — Principal only."""
    obligation = get_object_or_404(
        FeeObligation.objects.select_related('student'),
        pk=obligation_pk,
    )

    if obligation.is_waived:
        messages.info(request, "Yeh obligation pehle se waive hai.")
        return redirect('fees:obligation_detail', pk=obligation.pk)

    form = WaiverForm(request.POST or None, obligation=obligation)

    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                services.apply_waiver(
                    obligation=obligation,
                    reason=form.cleaned_data['reason'],
                    approved_by=request.user,
                )
            messages.success(request, "Waiver applied successfully.")
            return redirect('fees:obligation_detail', pk=obligation.pk)
        except Exception as exc:
            messages.error(request, f"Waiver apply nahi hua: {exc}")

    context = {
        'page_title': 'Apply Waiver',
        'page_subtitle': f'{obligation.student.student_name} · {obligation.month_label}',
        'active_menu': 'fees',
        'obligation': obligation,
        'form': form,
        'action_label': 'Apply Waiver',
        'action_class': 'btn-danger',
        'crumbs': [
            {'label': 'Home', 'url': reverse('accounts:redirect_after_login')},
            {'label': 'Obligation', 'url': reverse('fees:obligation_detail', kwargs={'pk': obligation.pk})},
            {'label': 'Waiver'},
        ],
    }
    return render(request, 'fees/adjustment_form.html', context)


@principal_required
@require_http_methods(["GET", "POST"])
def apply_concession(request, obligation_pk):
    """Apply partial concession/discount — Principal only."""
    obligation = get_object_or_404(
        FeeObligation.objects.select_related('student'),
        pk=obligation_pk,
    )

    if obligation.is_waived:
        messages.warning(request, "Waive-shuda obligation pe concession apply nahi hoti.")
        return redirect('fees:obligation_detail', pk=obligation.pk)

    form = ConcessionForm(request.POST or None, obligation=obligation)

    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                services.apply_concession(
                    obligation=obligation,
                    amount=form.cleaned_data['amount'],
                    reason=form.cleaned_data['reason'],
                    approved_by=request.user,
                    adjustment_type=form.cleaned_data['adjustment_type'],
                )
            messages.success(request, "Concession applied successfully.")
            return redirect('fees:obligation_detail', pk=obligation.pk)
        except Exception as exc:
            messages.error(request, f"Concession apply nahi hui: {exc}")

    context = {
        'page_title': 'Apply Concession',
        'page_subtitle': f'{obligation.student.student_name} · {obligation.month_label}',
        'active_menu': 'fees',
        'obligation': obligation,
        'form': form,
        'action_label': 'Apply Concession',
        'action_class': 'btn-warning',
        'crumbs': [
            {'label': 'Home', 'url': reverse('accounts:redirect_after_login')},
            {'label': 'Obligation', 'url': reverse('fees:obligation_detail', kwargs={'pk': obligation.pk})},
            {'label': 'Concession'},
        ],
    }
    return render(request, 'fees/adjustment_form.html', context)


# ============================================================
# PENDING / OVERDUE LISTS (Phase 5)
# ============================================================

@any_portal_user
@require_http_methods(["GET"])
def pending_fees(request):
    """All obligations with outstanding > 0."""
    q = (request.GET.get('q') or '').strip()
    type_filter = request.GET.get('type', '')

    qs = (
        FeeObligation.objects
        .select_related('student__course', 'student__batch')
        .filter(status__in=C.OPEN_STATUSES)
        .order_by('due_date', 'student__student_name')
    )

    if q:
        qs = qs.filter(
            Q(student__student_name__icontains=q)
            | Q(student__student_id__icontains=q)
            | Q(student__student_mobile__icontains=q)
        )

    if type_filter and type_filter in dict(C.TYPE_CHOICES):
        qs = qs.filter(obligation_type=type_filter)

    total_pending = C.ZERO
    total_overdue = C.ZERO
    pending_list = []

    for obl in qs.iterator():
        if obl.outstanding_amount <= C.ZERO:
            continue
        pending_list.append(obl)
        total_pending += obl.outstanding_amount
        if obl.is_overdue:
            total_overdue += obl.outstanding_amount

    context = {
        'page_title': 'Pending Fees',
        'page_subtitle': 'All outstanding fee obligations.',
        'active_menu': 'pending_fees',
        'obligations': pending_list,
        'total_pending': total_pending,
        'total_overdue': total_overdue,
        'search_query': q,
        'type_filter': type_filter,
        'type_choices': C.TYPE_CHOICES,
        'crumbs': [
            {'label': 'Home', 'url': reverse('accounts:redirect_after_login')},
            {'label': 'Pending Fees'},
        ],
    }
    return render(request, 'fees/obligations_list.html', context)


@any_portal_user
@require_http_methods(["GET"])
def overdue_fees(request):
    """All overdue obligations (past due + outstanding > 0)."""
    q = (request.GET.get('q') or '').strip()
    today = timezone.localdate()

    qs = (
        FeeObligation.objects
        .select_related('student__course', 'student__batch')
        .filter(
            due_date__lt=today,
            status__in=(C.STATUS_PENDING, C.STATUS_PARTIAL, C.STATUS_OVERDUE),
        )
        .order_by('due_date', 'student__student_name')
    )

    if q:
        qs = qs.filter(
            Q(student__student_name__icontains=q)
            | Q(student__student_id__icontains=q)
            | Q(student__student_mobile__icontains=q)
        )

    overdue_list = []
    total_overdue = C.ZERO
    for obl in qs.iterator():
        if obl.is_overdue and obl.outstanding_amount > C.ZERO:
            overdue_list.append(obl)
            total_overdue += obl.outstanding_amount

    context = {
        'page_title': 'Overdue Fees',
        'page_subtitle': 'Fee obligations past their due date.',
        'active_menu': 'overdue_fees',
        'obligations': overdue_list,
        'total_overdue': total_overdue,
        'count_overdue': len(overdue_list),
        'search_query': q,
        'crumbs': [
            {'label': 'Home', 'url': reverse('accounts:redirect_after_login')},
            {'label': 'Overdue Fees'},
        ],
    }
    return render(request, 'fees/obligations_list.html', context)


@principal_required
@require_POST
def regenerate_ledger(request, student_pk):
    """Regenerate ledger for a student (idempotent). Principal only."""
    student = get_object_or_404(Student, pk=student_pk)

    try:
        with transaction.atomic():
            result = services.generate_ledger_for_student(student)
        messages.success(
            request,
            f"Ledger synced: {result.created} new, {result.skipped} skipped."
        )
    except Exception as exc:
        messages.error(request, f"Ledger regeneration failed: {exc}")

    return redirect('fees:student_ledger', student_pk=student.pk)


# ============================================================
# ============================================================
# PHASE 6 — COLLECTION VIEWS
# ============================================================
# ============================================================

@any_portal_user
@require_http_methods(["GET"])
def collection_dashboard(request):
    """
    Fee collection dashboard.

    Staff sees their OWN today's collections.
    Principal sees ALL collections + all-staff KPI.
    """
    is_principal = request.user.is_principal
    staff_filter = None if is_principal else request.user

    kpis = collection_services.get_collection_kpis(staff_user=staff_filter)
    today = collection_services.get_today_collections(staff_user=staff_filter)
    aging = collection_services.get_overdue_aging_buckets()
    by_course = collection_services.get_pending_by_course()[:5]  # top 5
    by_batch = collection_services.get_pending_by_batch()[:5]

    context = {
        'page_title': 'Fee Collection',
        'page_subtitle': (
            'All collections across staff' if is_principal
            else 'Your collections today'
        ),
        'active_menu': 'fee_collection',
        'kpis': kpis,
        'today_payments': today['payments'][:15],
        'today_total': today['total'],
        'today_count': today['count'],
        'aging': aging,
        'by_course': by_course,
        'by_batch': by_batch,
        'is_principal': is_principal,
        'crumbs': [
            {'label': 'Home', 'url': reverse('accounts:redirect_after_login')},
            {'label': 'Fee Collection'},
        ],
    }
    return render(request, 'fees/collection_dashboard.html', context)


@any_portal_user
@require_http_methods(["GET"])
def collection_search(request):
    """
    Student search for collection — returns JSON when called via AJAX,
    otherwise renders a search results page.
    """
    from django.http import JsonResponse

    query = (request.GET.get('q') or '').strip()
    results = collection_services.search_students_for_collection(query, limit=20)

    # If AJAX, return JSON
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
        return JsonResponse({
            'query': query,
            'results': [
                {
                    'id': r['student'].pk,
                    'student_id': r['student'].student_id,
                    'name': r['student'].student_name,
                    'father_name': r['student'].father_name,
                    'course': r['student'].course.code,
                    'batch': r['student'].batch.display_name,
                    'outstanding': str(r['outstanding_total']),
                    'overdue': str(r['overdue_total']),
                    'open_count': r['open_count'],
                    'url': reverse('fees:quick_collect', kwargs={'student_pk': r['student'].pk}),
                }
                for r in results
            ],
        })

    # Non-AJAX fallback — render results in dashboard
    return render(request, 'fees/collection_dashboard.html', {
        'page_title': 'Fee Collection — Search',
        'page_subtitle': f'Results for "{query}"' if query else 'Search students',
        'active_menu': 'fee_collection',
        'search_query': query,
        'search_results': results,
        'crumbs': [
            {'label': 'Home', 'url': reverse('accounts:redirect_after_login')},
            {'label': 'Fee Collection', 'url': reverse('fees:collection_dashboard')},
            {'label': 'Search'},
        ],
    })


@any_portal_user
@require_http_methods(["GET", "POST"])
def quick_collect(request, student_pk):
    """
    Quick-collect page for a single student.

    GET:  Show student's open obligations + amount inputs per row.
    POST: Accept multiple obligation payments in one submit.

    POST format (form fields):
        obligation_<pk>  : amount to pay (0 or empty = skip)
        payment_method   : shared across all rows
        payment_date     : optional shared
        notes            : optional shared
    """
    student = get_object_or_404(
        Student.objects.select_related('course', 'batch'),
        pk=student_pk,
    )

    obligations = collection_services.get_student_quick_obligations(student)

    if request.method == 'POST':
        payment_method = request.POST.get('payment_method', C.METHOD_CASH)
        notes = request.POST.get('notes', '').strip()
        payment_date = request.POST.get('payment_date') or None

        # Collect non-zero amounts
        collected = []  # list of (obligation, amount)
        for obl in obligations:
            raw = request.POST.get(f'obligation_{obl.pk}', '').strip()
            if not raw:
                continue
            try:
                from decimal import Decimal, InvalidOperation
                amount = Decimal(raw)
            except (InvalidOperation, ValueError):
                messages.error(request, f"Invalid amount for {obl.month_label or obl.get_obligation_type_display()}.")
                continue
            if amount <= C.ZERO:
                continue
            collected.append((obl, amount))

        if not collected:
            messages.warning(request, "Koi amount enter nahi ki gayi. Kam az kam ek obligation pay karein.")
            return redirect('fees:quick_collect', student_pk=student.pk)

        # Process each payment in one transaction
        successful = []
        failed = []

        try:
            with transaction.atomic():
                for obl, amount in collected:
                    result = services.record_payment(
                        obligation=obl,
                        amount=amount,
                        payment_method=payment_method,
                        payment_date=payment_date,
                        notes=notes,
                        received_by=request.user,
                    )
                    if result.success:
                        successful.append(result.payment)
                    else:
                        failed.append((obl, result.error))
                        raise Exception(f"{obl.month_label or obl.get_obligation_type_display()}: {result.error}")

            # All succeeded
            total = sum(p.amount for p in successful)
            messages.success(
                request,
                f"{len(successful)} payment(s) recorded — total Rs. {total:.2f}. "
                f"Receipt generated."
            )
            if len(successful) == 1:
                return redirect('fees:receipt', payment_pk=successful[0].pk)
            else:
                # Multi-payment — show consolidated receipt for last payment
                return redirect('fees:print_receipt', payment_pk=successful[-1].pk)

        except Exception as exc:
            messages.error(request, f"Bulk payment rollback: {exc}")
            return redirect('fees:quick_collect', student_pk=student.pk)

    summary = services.get_student_fee_summary(student)

    context = {
        'page_title': f'Collect Fees — {student.student_name}',
        'page_subtitle': f'{student.student_id} · {student.course.code} · {student.batch.display_name}',
        'active_menu': 'fee_collection',
        'student': student,
        'obligations': obligations,
        'summary': summary,
        'payment_methods': C.PAYMENT_METHOD_CHOICES,
        'crumbs': [
            {'label': 'Home', 'url': reverse('accounts:redirect_after_login')},
            {'label': 'Fee Collection', 'url': reverse('fees:collection_dashboard')},
            {'label': 'Quick Collect'},
            {'label': student.student_name},
        ],
    }
    return render(request, 'fees/quick_collect.html', context)


@any_portal_user
@require_http_methods(["GET"])
def pending_summary(request):
    """Pending amounts grouped by course and batch."""
    by_course = collection_services.get_pending_by_course()
    by_batch = collection_services.get_pending_by_batch()
    aging = collection_services.get_overdue_aging_buckets()

    total_course = sum(c['pending_total'] for c in by_course)
    total_batch = sum(b['pending_total'] for b in by_batch)

    context = {
        'page_title': 'Pending Summary',
        'page_subtitle': 'Outstanding fees grouped by course and batch.',
        'active_menu': 'pending_summary',
        'by_course': by_course,
        'by_batch': by_batch,
        'aging': aging,
        'total_course': total_course,
        'total_batch': total_batch,
        'crumbs': [
            {'label': 'Home', 'url': reverse('accounts:redirect_after_login')},
            {'label': 'Pending Summary'},
        ],
    }
    return render(request, 'fees/pending_summary.html', context)


@any_portal_user
@require_http_methods(["GET"])
def receipt_view(request, payment_pk):
    """
    Receipt after payment (in-app view with print button).
    Staff can only view their own payments; Principal sees all.
    """
    payment = get_object_or_404(
        FeePayment.objects
        .select_related('obligation__student__course', 'obligation__student__batch', 'received_by'),
        pk=payment_pk,
    )

    # Staff ownership check
    if not request.user.is_principal and payment.received_by_id != request.user.pk:
        messages.error(request, "Yeh receipt kisi aur staff ne issue ki hai.")
        return redirect('fees:collection_dashboard')

    context = {
        'page_title': 'Payment Receipt',
        'page_subtitle': f'Transaction: {payment.transaction_id}',
        'active_menu': 'fee_collection',
        'payment': payment,
        'crumbs': [
            {'label': 'Home', 'url': reverse('accounts:redirect_after_login')},
            {'label': 'Fee Collection', 'url': reverse('fees:collection_dashboard')},
            {'label': 'Receipt'},
        ],
    }
    return render(request, 'fees/receipt.html', context)


@any_portal_user
@require_http_methods(["GET"])
def print_receipt(request, payment_pk):
    """Standalone printable receipt (no sidebar/navbar)."""
    payment = get_object_or_404(
        FeePayment.objects
        .select_related('obligation__student__course', 'obligation__student__batch', 'received_by'),
        pk=payment_pk,
    )

    if not request.user.is_principal and payment.received_by_id != request.user.pk:
        messages.error(request, "Yeh receipt kisi aur staff ne issue ki hai.")
        return redirect('fees:collection_dashboard')

    context = {
        'payment': payment,
    }
    return render(request, 'fees/print_receipt.html', context)


# ============================================================
# ============================================================
# PHASE 8 — CORRECTION WORKFLOW VIEWS
# ============================================================
# ============================================================

from django.db.models import Q as _CorrectionQ

from .corrections import (
    approve_correction,
    cancel_correction,
    reject_correction,
    submit_correction,
)
from .forms import CorrectionRequestForm, CorrectionReviewForm
from .models import PaymentCorrectionRequest


# ---------- Staff: Request a correction ----------

@any_portal_user
@require_http_methods(["GET", "POST"])
def request_correction(request, payment_pk):
    """Staff (or Principal) submits a correction request against a payment."""
    payment = get_object_or_404(
        FeePayment.objects.select_related('obligation__student', 'received_by'),
        pk=payment_pk,
    )

    # Only the receiving staff OR Principal can request corrections
    if not request.user.is_principal and payment.received_by_id != request.user.pk:
        messages.error(request, "Aap sirf apni payments ke corrections request kar sakte hain.")
        return redirect('fees:collection_dashboard')

    if payment.is_reversed:
        messages.warning(request, "Yeh payment pehle se reversed hai.")
        return redirect('fees:receipt', payment_pk=payment.pk)

    form = CorrectionRequestForm(request.POST or None, payment=payment)

    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                correction = submit_correction(
                    payment=payment,
                    requested_by=request.user,
                    correction_type=form.cleaned_data['correction_type'],
                    reason=form.cleaned_data['reason'],
                    new_amount=form.cleaned_data.get('new_amount'),
                    new_payment_method=form.cleaned_data.get('new_payment_method', ''),
                    new_payment_date=form.cleaned_data.get('new_payment_date'),
                    notes=form.cleaned_data.get('notes', ''),
                )
            messages.success(
                request,
                f"Correction request #{correction.pk} submitted. "
                f"Principal ke approval ka intezaar hai."
            )
            return redirect('fees:correction_detail', pk=correction.pk)
        except Exception as exc:
            messages.error(request, f"Correction submit nahi hui: {exc}")

    context = {
        'page_title': 'Request Payment Correction',
        'page_subtitle': f'Payment {payment.transaction_id}',
        'active_menu': 'fee_collection',
        'payment': payment,
        'form': form,
        'crumbs': [
            {'label': 'Home', 'url': reverse('accounts:redirect_after_login')},
            {'label': 'Fee Collection', 'url': reverse('fees:collection_dashboard')},
            {'label': 'Receipt', 'url': reverse('fees:receipt', kwargs={'payment_pk': payment.pk})},
            {'label': 'Correction Request'},
        ],
    }
    return render(request, 'fees/correction_request_form.html', context)


# ---------- Corrections list ----------

@any_portal_user
@require_http_methods(["GET"])
def corrections_list(request):
    """
    List correction requests.
    - Staff: only their own requests
    - Principal: all requests
    """
    status_filter = request.GET.get('status', 'all')

    qs = (
        PaymentCorrectionRequest.objects
        .select_related(
            'payment__obligation__student',
            'requested_by', 'reviewed_by',
        )
        .order_by('-created_at')
    )

    if not request.user.is_principal:
        qs = qs.filter(requested_by=request.user)

    if status_filter in dict(PaymentCorrectionRequest.STATUS_CHOICES):
        qs = qs.filter(status=status_filter)

    pending_count = PaymentCorrectionRequest.objects.filter(
        status=PaymentCorrectionRequest.STATUS_PENDING,
    ).count() if request.user.is_principal else (
        PaymentCorrectionRequest.objects.filter(
            status=PaymentCorrectionRequest.STATUS_PENDING,
            requested_by=request.user,
        ).count()
    )

    context = {
        'page_title': 'Payment Corrections',
        'page_subtitle': (
            'All correction requests' if request.user.is_principal
            else 'Your correction requests'
        ),
        'active_menu': 'corrections',
        'corrections': qs,
        'status_filter': status_filter,
        'status_choices': PaymentCorrectionRequest.STATUS_CHOICES,
        'pending_count': pending_count,
        'is_principal': request.user.is_principal,
        'crumbs': [
            {'label': 'Home', 'url': reverse('accounts:redirect_after_login')},
            {'label': 'Corrections'},
        ],
    }
    return render(request, 'fees/corrections_list.html', context)


# ---------- Correction detail ----------

@any_portal_user
@require_http_methods(["GET"])
def correction_detail(request, pk):
    """View a single correction request."""
    correction = get_object_or_404(
        PaymentCorrectionRequest.objects.select_related(
            'payment__obligation__student',
            'payment__received_by',
            'requested_by', 'reviewed_by',
        ),
        pk=pk,
    )

    # Staff can only see their own
    if not request.user.is_principal and correction.requested_by_id != request.user.pk:
        messages.error(request, "Yeh request aap ki nahi hai.")
        return redirect('fees:corrections_list')

    context = {
        'page_title': f'Correction #{correction.pk}',
        'page_subtitle': correction.payment.transaction_id,
        'active_menu': 'corrections',
        'correction': correction,
        'is_principal': request.user.is_principal,
        'can_review': (
            request.user.is_principal
            and correction.status == PaymentCorrectionRequest.STATUS_PENDING
        ),
        'can_cancel': (
            correction.requested_by_id == request.user.pk
            and correction.status == PaymentCorrectionRequest.STATUS_PENDING
        ),
        'crumbs': [
            {'label': 'Home', 'url': reverse('accounts:redirect_after_login')},
            {'label': 'Corrections', 'url': reverse('fees:corrections_list')},
            {'label': f'#{correction.pk}'},
        ],
    }
    return render(request, 'fees/correction_detail.html', context)


# ---------- Principal: Review (approve/reject) ----------

@principal_required
@require_http_methods(["GET", "POST"])
def review_correction(request, pk):
    correction = get_object_or_404(PaymentCorrectionRequest.objects.select_related('payment'), pk=pk)

    if correction.status != 'pending':
        messages.info(request, f"Yeh request already {correction.get_status_display()} hai.")
        return redirect('fees:correction_detail', pk=correction.pk)

    if request.method == 'POST':
        decision = request.POST.get('decision')
        notes = request.POST.get('review_notes', '')

        try:
            with transaction.atomic():
                if decision == 'approve':
                    approve_correction(correction, request.user, notes)
                    messages.success(request, "Correction approved! Original payment reversed and new payment created.")
                else:
                    reject_correction(correction, request.user, notes)
                    messages.success(request, "Correction rejected.")
            return redirect('fees:correction_detail', pk=correction.pk)
        except Exception as e:
            messages.error(request, f"Process nahi ho saka: {e}")

    context = {
        'page_title': 'Review Correction',
        'page_subtitle': f'Request #{correction.pk}',
        'correction': correction,
        'is_principal': True,
    }
    return render(request, 'fees/correction_detail.html', context)

# ---------- Requester: Cancel own pending correction ----------

@any_portal_user
@require_POST
def cancel_correction_view(request, pk):
    """Requester cancels their own pending correction."""
    correction = get_object_or_404(PaymentCorrectionRequest, pk=pk)

    try:
        cancel_correction(
            correction=correction,
            cancelled_by=request.user,
            reason=request.POST.get('reason', ''),
        )
        messages.success(request, "Correction request cancelled.")
    except Exception as exc:
        messages.error(request, f"Cancel fail: {exc}")

    return redirect('fees:correction_detail', pk=correction.pk)

# ============================================================
# MANUAL FEE ENTRY (Naya)
# ============================================================
@any_portal_user
@require_http_methods(["GET", "POST"])
def add_manual_fee(request, student_pk):
    """Add a new fee obligation manually."""
    student = get_object_or_404(Student.objects.select_related('course', 'batch'), pk=student_pk)
    
    # Form ko student pass karein taake course/categories set hon
    form = ManualFeeForm(request.POST or None, student=student)

    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                fee_category = form.cleaned_data.get('fee_category')
                month_date = form.cleaned_data.get('month')
                
                # Determine Obligation Type based on Category name
                obligation_type = C.TYPE_OTHER
                if fee_category:
                    name_lower = fee_category.name.lower()
                    if 'admission' in name_lower:
                        obligation_type = C.TYPE_ADMISSION
                    elif 'registration' in name_lower:
                        obligation_type = C.TYPE_REGISTRATION
                    elif 'exam' in name_lower:
                        obligation_type = C.TYPE_EXAM
                    elif 'sem' in name_lower or 'month' in name_lower:
                        obligation_type = C.TYPE_MONTHLY

                description = form.cleaned_data.get('notes', '').strip()
                if not description and fee_category:
                    description = fee_category.name

                obligation = FeeObligation.objects.create(
                    student=student,
                    fee_category=fee_category,
                    obligation_type=obligation_type,
                    obligation_month=month_date,
                    amount=form.cleaned_data['amount'],
                    due_date=form.cleaned_data['due_date'],
                    description=description,
                )

                if form.cleaned_data.get('is_paid'):
                    FeePayment.objects.create(
                        obligation=obligation,
                        amount=obligation.amount,
                        payment_method=C.METHOD_CASH,
                        payment_date=timezone.now(),
                        received_by=request.user,
                        notes="Paid during manual fee entry."
                    )
                    obligation.refresh_status()

            messages.success(request, f"Fee '{obligation.description}' successfully add ho gayi.")
            return redirect('fees:student_ledger', student_pk=student.pk)
        except Exception as e:
            messages.error(request, f"Fee add nahi hui: {e}")

    context = {
        'form': form, 
        'student': student, 
        'page_title': 'Add New Fee',
    }
    return render(request, 'fees/add_manual_fee.html', context)