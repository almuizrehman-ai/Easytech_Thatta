"""
Views for the students application.
"""
import random
import string
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST
from django.core.exceptions import PermissionDenied

from accounts.decorators import any_portal_user, principal_required, student_self_required
from accounts.models import CustomUser
from batches.models import Batch
from courses.models import Course
from fees import services as fee_services

from .forms import AdmissionForm, StudentEditForm
from .models import Student


# ============================================================
# LIST
# ============================================================
@any_portal_user
@require_http_methods(["GET"])
def student_list(request):
    """List students with filters: search, course, batch, status."""
    if request.user.role == 'student':
        raise PermissionDenied("Aap students ki list nahi dekh sakte.")

    q = (request.GET.get('q') or '').strip()
    course_filter = request.GET.get('course', '')
    batch_filter = request.GET.get('batch', '')
    status_filter = request.GET.get('status', 'all')

    qs = Student.objects.select_related('course', 'batch')

    if q:
        qs = qs.filter(
            Q(student_name__icontains=q)
            | Q(father_name__icontains=q)
            | Q(student_id__icontains=q)
            | Q(student_mobile__icontains=q)
        )

    if course_filter and course_filter.isdigit():
        qs = qs.filter(course_id=int(course_filter))

    if batch_filter and batch_filter.isdigit():
        qs = qs.filter(batch_id=int(batch_filter))

    if status_filter == 'active':
        qs = qs.filter(is_active=True, enrollment_status='active')
    elif status_filter == 'inactive':
        qs = qs.filter(is_active=False)
    elif status_filter == 'graduated':
        qs = qs.filter(enrollment_status='graduated')
    elif status_filter == 'dropped':
        qs = qs.filter(enrollment_status='dropped')

    total_count = Student.objects.count()
    active_count = Student.objects.filter(is_active=True, enrollment_status='active').count()
    inactive_count = Student.objects.filter(is_active=False).count()

    courses = Course.objects.order_by('-is_active', 'name')
    batches = Batch.objects.select_related('course').order_by('course', 'start_month')

    if course_filter and course_filter.isdigit():
        batches = batches.filter(course_id=int(course_filter))

    context = {
        'page_title': 'Students',
        'page_subtitle': 'Manage admissions, profiles, and academic status.',
        'active_menu': 'students',
        'students': qs,
        'courses': courses,
        'batches': batches,
        'search_query': q,
        'course_filter': course_filter,
        'batch_filter': batch_filter,
        'status_filter': status_filter,
        'total_count': total_count,
        'active_count': active_count,
        'inactive_count': inactive_count,
        'can_create': True,
        'crumbs': [
            {'label': 'Home', 'url': reverse('accounts:redirect_after_login')},
            {'label': 'Students'},
        ],
    }
    return render(request, 'students/list.html', context)


# ============================================================
# CREATE (ADMISSION) — 100% RELIABLE PORTAL CREATION
# ============================================================
@any_portal_user
@require_http_methods(["GET", "POST"])
def student_create(request):
    """New student admission. Accessible to Staff and Principal."""
    form = AdmissionForm(request.POST or None, request.FILES or None)

    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                # 1. Student Profile Save Karein (Pehle save karein taake ID generate ho)
                student = form.save(commit=False)
                student.created_by = request.user
                
                # Password generate karein
                raw_password = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
                student.portal_password = raw_password
                
                # Pehli dafa save karein taake student_id generate ho jaye
                student.save()

                # 2. Ab student_id ban chuki hai, usko username banayein
                username = student.student_id.lower()
                
                # 3. CustomUser create karein
                # Check karein ke kahin same username pehle se na ho
                if CustomUser.objects.filter(username=username).exists():
                    username = f"{username}_{student.pk}"

                CustomUser.objects.create_user(
                    username=username,
                    password=raw_password,
                    role='student',
                    full_name=student.student_name,
                    linked_student=student
                )

            messages.success(
                request,
                f"Student '{student.student_name}' admitted successfully. "
                f"Portal Username: {username} | Password: {raw_password} (Yeh note kar lein!)"
            )
            return redirect('students:detail', pk=student.pk)
        except Exception as exc:
            messages.error(request, f"Admission save nahi ho saka. Error: {exc}")

    context = {
        'page_title': 'New Student Admission',
        'page_subtitle': 'Register a new student.',
        'active_menu': 'new_admission',
        'form': form,
        'mode': 'create',
        'form_action': reverse('students:create'),
        'cancel_url': reverse('students:list'),
        'crumbs': [
            {'label': 'Home', 'url': reverse('accounts:redirect_after_login')},
            {'label': 'Students', 'url': reverse('students:list')},
            {'label': 'New Admission'},
        ],
    }
    return render(request, 'students/form.html', context)


# ============================================================
# DETAIL (Staff, Principal, and Self-Student)
# ============================================================
@student_self_required
@require_http_methods(["GET"])
def student_detail(request, pk):
    """Student profile — visible to Staff, Principal, and the Student themselves."""
    student = get_object_or_404(
        Student.objects.select_related('course', 'batch', 'created_by'),
        pk=pk,
    )

    # Fee summary attach karein
    fee_summary = fee_services.get_student_fee_summary(student)

    # ============================================================
    # FIX: Check karein ke Admission Fee ledger mein paid hai ya nahi
    # ============================================================
    from fees.models import FeeObligation
    from fees import constants as FC
    
    admission_obls = FeeObligation.objects.filter(
        student=student, 
        obligation_type=FC.TYPE_ADMISSION
    )
    
    if admission_obls.exists():
        # Agar ledger mein entry hai, toh uska actual amount aur status lein
        total_admission_amount = sum(o.amount for o in admission_obls)
        is_paid = all(o.outstanding_amount <= 0 for o in admission_obls)
        
        # Student model ko update karein taake view mein sahi dikhe
        student.admission_fee_amount = total_admission_amount
        student.admission_fee_paid = is_paid
    else:
        # Agar ledger mein kuch nahi, toh default pending
        student.admission_fee_paid = False

    context = {
        'page_title': student.student_name,
        'page_subtitle': f'Student ID: {student.student_id}',
        'active_menu': 'students' if request.user.role != 'student' else 'profile',
        'student': student,
        'fee_summary': fee_summary,
        'can_toggle': request.user.is_principal,
        'crumbs': [
            {'label': 'Home', 'url': reverse('accounts:redirect_after_login')},
            {'label': 'Students', 'url': reverse('students:list')} if request.user.role != 'student' else {'label': 'My Profile', 'url': reverse('dashboard:student_profile')},
            {'label': student.student_id},
        ],
    }
    return render(request, 'students/detail.html', context)

# ============================================================
# EDIT
# ============================================================
@any_portal_user
@require_http_methods(["GET", "POST"])
def student_edit(request, pk):
    """Edit existing student. Staff + Principal both allowed."""
    if request.user.role == 'student':
        raise PermissionDenied("Aap profile edit nahi kar sakte.")

    student = get_object_or_404(Student.objects.select_related('course', 'batch'), pk=pk)

    if not student.is_active and not request.user.is_principal:
        messages.error(request, "Inactive student ko sirf Principal edit kar sakta hai.")
        return redirect('students:detail', pk=student.pk)

    form = StudentEditForm(
        request.POST or None,
        request.FILES or None,
        instance=student,
    )

    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                form.save()
            messages.success(request, f"Student '{student.student_name}' updated.")
            return redirect('students:detail', pk=student.pk)
        except Exception as exc:
            messages.error(request, f"Update nahi ho saka. Error: {exc}")

    context = {
        'page_title': f'Edit — {student.student_name}',
        'page_subtitle': f'Student ID: {student.student_id}',
        'active_menu': 'students',
        'form': form,
        'student': student,
        'mode': 'edit',
        'form_action': reverse('students:edit', kwargs={'pk': student.pk}),
        'cancel_url': reverse('students:detail', kwargs={'pk': student.pk}),
        'crumbs': [
            {'label': 'Home', 'url': reverse('accounts:redirect_after_login')},
            {'label': 'Students', 'url': reverse('students:list')},
            {'label': student.student_id, 'url': reverse('students:detail', kwargs={'pk': student.pk})},
            {'label': 'Edit'},
        ],
    }
    return render(request, 'students/form.html', context)


# ============================================================
# TOGGLE (PRINCIPAL ONLY)
# ============================================================
@principal_required
@require_POST
def student_toggle_active(request, pk):
    """Toggle active status — Principal only."""
    student = get_object_or_404(Student, pk=pk)
    student.is_active = not student.is_active
    student.save(update_fields=['is_active', 'updated_at'])

    state = "activated" if student.is_active else "deactivated"
    messages.success(request, f"Student '{student.student_name}' {state}.")
    return redirect('students:detail', pk=student.pk)


# ============================================================
# PRINT FORM (Staff, Principal, and Self-Student)
# ============================================================
@student_self_required
@require_http_methods(["GET"])
def student_print_form(request, pk):
    """Printable Admission Form. Students can print their own."""
    student = get_object_or_404(Student.objects.select_related('course', 'batch'), pk=pk)
    context = {
        'student': student,
    }
    return render(request, 'students/print_admission.html', context)