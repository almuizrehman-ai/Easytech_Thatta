"""
Model for the students application.

Design principles (from spec):
- Student IDs are auto-generated (EST-YYYY-NNNN) with atomic sequence.
- Fee amounts are SNAPSHOTTED at admission time:
    - admission_fee_amount : from Course's 'Admission Fee' category
    - registration_fee_amount : from Course's 'Registration Fee' category
    - monthly_fee_at_admission : from the selected Batch
  This preserves historical accuracy if the institute changes fees later.
- Students are NEVER hard-deleted. Use `is_active` to deactivate.
- A student's batch must belong to the student's course (validated).
- Mobile numbers are normalized to '03XXXXXXXXX' form on save.
- Duplicate active students with same (name, father_name, phone) are rejected.
"""
import os

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal

from batches.models import Batch
from courses.models import Course, FeeCategory

from .services import generate_student_id
from .validators import validate_mobile, validate_photo


def student_photo_upload_to(instance, filename):
    """
    Upload path: media/students/photos/<student_id>/<filename>

    If student_id is not yet assigned (during creation), fall back to
    a temporary 'pending' directory. The file stays there — that is fine
    because Student.save() assigns the ID before the file is persisted
    in most cases, but defensive fallback keeps uploads safe.
    """
    ext = os.path.splitext(filename)[1].lower() or '.jpg'
    folder = instance.student_id or 'pending'
    # Keep filename minimal — avoid path injection
    return f"students/photos/{folder}/photo{ext}"


class Student(models.Model):
    """An enrolled student in the institute."""

    # ---------- Gender ----------
    GENDER_CHOICES = (
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    )

    STATUS_CHOICES = (
        ('active', 'Active'),
        ('graduated', 'Graduated'),
        ('dropped', 'Dropped Out'),
    )

    # ---------- Auto ID ----------
    student_id = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        db_index=True,
        help_text="Auto-generated: EST-YYYY-NNNN.",
    )

    # ---------- Personal Information ----------
    student_name = models.CharField(
        max_length=120,
        db_index=True,
        help_text="Student's full name.",
    )
    father_name = models.CharField(
        max_length=120,
        help_text="Father's full name.",
    )
    gender = models.CharField(
        max_length=1,
        choices=GENDER_CHOICES,
        blank=True,
    )
    CAMPUS_CHOICES = (
        ('thatta', 'Thatta Campus'),
        ('sujawal', 'Sujawal Campus'),
    )
    campus = models.CharField(
        max_length=20,
        choices=CAMPUS_CHOICES,
        default='thatta',
        help_text="Student ka campus select karein."
    )
    date_of_birth = models.DateField(
        blank=True,
        null=True,
    )
    cnic_or_bform = models.CharField(
        max_length=20,
        blank=True,
        help_text="Optional CNIC or B-Form number.",
    )
    address = models.TextField(
        blank=True,
        help_text="Optional residential address.",
    )

    # ---------- Contact ----------
    student_mobile = models.CharField(
        max_length=20,
        validators=[validate_mobile],
        db_index=True,
        help_text="Student's mobile in 03XXXXXXXXX format.",
    )
    father_mobile = models.CharField(
        max_length=20,
        validators=[validate_mobile],
        help_text="Father's/guardian's mobile in 03XXXXXXXXX format.",
    )
    student_email = models.EmailField(
        blank=True,
    )

    # ---------- Photo ----------
    photo = models.ImageField(
        upload_to=student_photo_upload_to,
        validators=[validate_photo],
        blank=True,
        null=True,
        help_text="Optional profile photo. JPEG/PNG/WEBP, max 2 MB.",
    )
    # Previous Education
    previous_degree = models.CharField(max_length=100, blank=True, help_text="e.g. Matric / F.Sc")
    previous_passing_year = models.CharField(max_length=20, blank=True, help_text="e.g. 2025")
    previous_obtained_marks = models.CharField(max_length=20, blank=True, help_text="e.g. 750")
    previous_total_marks = models.CharField(max_length=20, blank=True, help_text="e.g. 850")
    previous_grade = models.CharField(max_length=20, blank=True, help_text="e.g. A1 / A")
    previous_board = models.CharField(max_length=150, blank=True, help_text="e.g. BISE Hyderabad")

    # Fee Status
    admission_fee_paid = models.BooleanField(
        default=False, 
        help_text="Check karein agar admission fee abhi receive ho chuki hai."
    )
        # Portal Credentials (Plain text for admin visibility)
    portal_password = models.CharField(
        max_length=50, 
        blank=True, 
        help_text="Student portal ka raw password (admin ke dekhne ke liye)."
    )
    # ---------- Academic placement ----------
    course = models.ForeignKey(
        Course,
        on_delete=models.PROTECT,
        related_name='students',
        db_index=True,
        help_text="The course the student is enrolled in.",
    )
    batch = models.ForeignKey(
        Batch,
        on_delete=models.PROTECT,
        related_name='students',
        db_index=True,
        help_text="The batch within the course.",
    )

    # ---------- Fee snapshots ----------
    admission_fee_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Admission fee frozen at enrollment time (from course's Admission Fee).",
    )
    registration_fee_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Registration fee frozen at enrollment time (from course's Registration Fee).",
    )
    monthly_fee_at_admission = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Monthly fee frozen at enrollment time (from the batch).",
    )

    # ---------- Status ----------
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Inactive students remain in records but cannot be edited or receive new obligations.",
    )
    enrollment_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        db_index=True,
        help_text="Overall academic status: active, graduated, dropped.",
    )
    admission_date = models.DateField(
        default=timezone.localdate,
        editable=True,
        help_text="Date of admission (defaults to today).",
    )

    # ---------- Audit ----------
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='students_created',
        help_text="Staff/Principal who created this record.",
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Student'
        verbose_name_plural = 'Students'
        constraints = [
            # Prevent duplicate active students with same name + father + phone
            models.UniqueConstraint(
                fields=['student_name', 'father_name', 'student_mobile'],
                condition=Q(is_active=True),
                name='uniq_active_student_identity',
            ),
        ]
        indexes = [
            models.Index(fields=['is_active', 'enrollment_status']),
            models.Index(fields=['course', 'batch']),
            models.Index(fields=['student_mobile']),
            models.Index(fields=['admission_date']),
        ]

    # ============================================================
    # SAVE / CLEAN
    # ============================================================
    def save(self, *args, **kwargs):
        """Assign ID on first save; normalize mobiles; sync course from batch."""
        is_new = self._state.adding

        # --- Normalize mobile numbers ---
        if self.student_mobile:
            self.student_mobile = self._normalize_mobile_safe(self.student_mobile)
        if self.father_mobile:
            self.father_mobile = self._normalize_mobile_safe(self.father_mobile)

        # --- Sync course from batch (batch is authoritative) ---
        if self.batch_id and (not self.course_id or self.course_id != self.batch.course_id):
            self.course = self.batch.course

        # --- Assign student_id for new records ---
        if is_new and not self.student_id:
            self.student_id = generate_student_id()

        super().save(*args, **kwargs)

    def clean(self):
        """Server-side validation beyond form-level checks."""
        from django.core.exceptions import ValidationError

        # Batch must belong to the selected course
        if self.batch_id and self.course_id and self.batch.course_id != self.course_id:
            raise ValidationError({
                'batch': "Selected batch is course ke andar nahi hai. "
                         "Course ke mutabiq batch choose karein."
            })

        # Inactive batch cannot receive new students
        if self._state.adding and self.batch_id and not self.batch.is_active:
            raise ValidationError({
                'batch': "Yeh batch deactivate hai. Naye admission ke liye active batch choose karein."
            })

    @staticmethod
    def _normalize_mobile_safe(raw: str) -> str:
        """
        Normalize mobile if possible; if invalid, return as-is so
        field validator can raise the user-facing error.
        """
        from .validators import normalize_mobile
        from django.core.exceptions import ValidationError
        try:
            return normalize_mobile(raw)
        except ValidationError:
            return raw

    # ============================================================
    # CONVENIENCE
    # ============================================================
    def __str__(self):
        return f"{self.student_name} ({self.student_id})"

    def get_absolute_url(self):
        return reverse('students:detail', kwargs={'pk': self.pk})

    @property
    def full_identity(self):
        """Display helper: 'Name s/o Father'."""
        return f"{self.student_name} s/o {self.father_name}"

    @property
    def age(self):
        """Age in years based on DOB, or None."""
        if not self.date_of_birth:
            return None
        today = timezone.localdate()
        return (
            today.year - self.date_of_birth.year
            - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
        )

    @property
    def is_active_student(self):
        return self.is_active and self.enrollment_status == 'active'

    # ============================================================
    # FEE HELPERS (Phase 5 will populate real values)
    # ============================================================
    def has_pending_fees(self) -> bool:
        """
        True if any fee obligation is unpaid or partially paid.

        Phase 4: returns False (no FeeObligation model yet).
        Phase 5: will query related obligations.
        """
        if hasattr(self, 'fee_obligations'):
            return self.fee_obligations.filter(
                status__in=['pending', 'partial', 'overdue']
            ).exists()
        return False

    def has_overdue_fees(self) -> bool:
        """True if any fee obligation is overdue."""
        if hasattr(self, 'fee_obligations'):
            return self.fee_obligations.filter(status='overdue').exists()
        return False

    # ============================================================
    # FEE SNAPSHOT HELPERS (used by AdmissionForm)
    # ============================================================
    @classmethod
    def derive_fee_snapshots(cls, course, batch):
        """
        Return dict with admission_fee_amount, registration_fee_amount,
        monthly_fee_at_admission based on current course & batch state.

        Called by AdmissionForm before saving. Values frozen into the
        student record — later changes do NOT retroactively alter this.

        Returns:
            {
                'admission_fee_amount': Decimal,
                'registration_fee_amount': Decimal,
                'monthly_fee_at_admission': Decimal,
            }
        """
        def _find_fee(name_fragment):
            fee = (
                FeeCategory.objects
                .filter(
                    course=course,
                    is_active=True,
                    name__icontains=name_fragment,
                )
                .order_by('name')
                .first()
            )
            return fee.amount if fee else Decimal('0.00')

        return {
            'admission_fee_amount': _find_fee('admission'),
            'registration_fee_amount': _find_fee('registration'),
            'monthly_fee_at_admission': batch.monthly_fee if batch else Decimal('0.00'),
        }