"""
Dashboard views.
"""
import json
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from accounts.decorators import principal_required, staff_required
from . import analytics
from fees.models import FeePayment


# ============================================================
# STAFF DASHBOARD
# ============================================================
@staff_required
def staff_dashboard(request):
    kpis = analytics.get_staff_dashboard_kpis(request.user)
    daily_chart = analytics.get_daily_collection_chart(days=30, user=request.user)
    fee_status_chart = analytics.get_fee_status_chart()
    batch_chart = analytics.get_batch_distribution_chart(limit=6)
    recent_admissions = analytics.get_recent_admissions(limit=5)
    recent_payments = analytics.get_recent_payments(limit=8, user=request.user)

    chart_payload = {
        'daily': {'labels': daily_chart['labels'], 'values': daily_chart['values']},
        'feeStatus': {'labels': fee_status_chart['labels'], 'values': fee_status_chart['values']},
        'batch': {'labels': batch_chart['labels'], 'values': batch_chart['values']},
    }

    context = {
        'page_title': 'Staff Dashboard',
        'page_subtitle': 'Admission, fee collection, and student operations.',
        'active_menu': 'dashboard',
        'kpis': kpis,
        'daily_total': daily_chart['total'],
        'recent_admissions': recent_admissions,
        'recent_payments': recent_payments,
        'charts_json': json.dumps(chart_payload),
    }
    return render(request, 'dashboard/staff_dashboard.html', context)


# ============================================================
# PRINCIPAL DASHBOARD
# ============================================================
@principal_required
def principal_dashboard(request):
    kpis = analytics.get_principal_dashboard_kpis()
    daily_chart = analytics.get_daily_collection_chart(days=30)
    monthly_chart = analytics.get_monthly_revenue_chart(months=6)
    course_chart = analytics.get_course_distribution_chart()
    batch_chart = analytics.get_batch_distribution_chart(limit=8)
    fee_status_chart = analytics.get_fee_status_chart()
    recent_admissions = analytics.get_recent_admissions(limit=5)
    recent_payments = analytics.get_recent_payments(limit=10)

    chart_payload = {
        'daily': {'labels': daily_chart['labels'], 'values': daily_chart['values']},
        'monthly': {'labels': monthly_chart['labels'], 'values': monthly_chart['values']},
        'course': {'labels': course_chart['labels'], 'values': course_chart['values']},
        'batch': {'labels': batch_chart['labels'], 'values': batch_chart['values']},
        'feeStatus': {'labels': fee_status_chart['labels'], 'values': fee_status_chart['values']},
    }

    context = {
        'page_title': 'Principal Dashboard',
        'page_subtitle': 'Full administrative overview of the institute.',
        'active_menu': 'dashboard',
        'kpis': kpis,
        'daily_total': daily_chart['total'],
        'monthly_total': monthly_chart['total'],
        'course_total': course_chart['total'],
        'fee_status_total': fee_status_chart['total'],
        'recent_admissions': recent_admissions,
        'recent_payments': recent_payments,
        'charts_json': json.dumps(chart_payload),
    }
    return render(request, 'dashboard/principal_dashboard.html', context)


# ============================================================
# STUDENT DASHBOARD
# ============================================================
@login_required
def student_dashboard(request):
    """Student Portal Main Page"""
    if request.user.role != 'student' or not request.user.linked_student:
        raise PermissionDenied("Access denied.")
        
    student = request.user.linked_student
    from fees import services as fee_services
    
    obligations = fee_services.get_ledger_for_student(student)
    summary = fee_services.get_student_fee_summary(student)

    context = {
        'page_title': 'My Dashboard',
        'page_subtitle': f'Welcome, {student.student_name}',
        'active_menu': 'dashboard',
        'student': student,
        'obligations': obligations[:5], 
        'summary': summary,
    }
    return render(request, 'dashboard/student_dashboard.html', context)


# ============================================================
# STUDENT PROFILE
# ============================================================
@login_required
def student_my_profile(request):
    """Student apni profile dekhe"""
    if request.user.role != 'student' or not request.user.linked_student:
        raise PermissionDenied("Access denied.")
        
    student = request.user.linked_student
    context = {
        'page_title': 'My Profile',
        'active_menu': 'profile',
        'student': student,
    }
    return render(request, 'students/student_profile.html', context)


# ============================================================
# STUDENT LEDGER
# ============================================================
@login_required
def student_my_ledger(request):
    """Student apni fees ka ledger dekhe"""
    if request.user.role != 'student' or not request.user.linked_student:
        raise PermissionDenied("Access denied.")
        
    student = request.user.linked_student
    from fees import services as fee_services
    
    obligations = fee_services.get_ledger_for_student(student)
    summary = fee_services.get_student_fee_summary(student)

    context = {
        'page_title': 'My Fee Ledger',
        'active_menu': 'ledger',
        'student': student,
        'obligations': obligations,
        'summary': summary,
    }
    return render(request, 'fees/student_ledger_view.html', context)


# ============================================================
# STUDENT PRINT FORM
# ============================================================
@login_required
def student_my_print(request):
    """Student apna form print kare"""
    if request.user.role != 'student' or not request.user.linked_student:
        raise PermissionDenied("Access denied.")
        
    student = request.user.linked_student
    return render(request, 'students/print_admission.html', {'student': student})


# ============================================================
# THERMAL RECEIPT
# ============================================================
@login_required
def student_receipt_thermal(request, payment_pk):
    """Thermal print ke liye receipt view (sirf student apni receipt dekh sake)"""
    
    payment = get_object_or_404(
        FeePayment.objects.select_related('obligation__student__course', 'received_by'),
        pk=payment_pk
    )
    
    # Security check: student apni hi receipt dekh sake
    if request.user.role == 'student' and payment.obligation.student_id != request.user.linked_student_id:
        raise PermissionDenied("Aap sirf apni receipts dekh sakte hain.")
        
    return render(request, 'students/thermal_receipt.html', {'payment': payment})