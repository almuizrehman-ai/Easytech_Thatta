"""
Models for the courses application.

Design principles (from spec):
- Course durations and fee categories are NOT hardcoded.
  Each course defines its own duration_months and its own set
  of FeeCategory rows.
- Existing records are deactivated, never deleted, so historical
  data (students, batches, fee obligations) remains intact.
- Fee amounts use DecimalField with 2 decimal places.
"""
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Course(models.Model):
    """
    A course offered by the institute (e.g., DIT, CIT, Web Development).

    Fields:
        name            : Human readable name
        code            : Unique short code (e.g., 'DIT', 'CIT')
        duration_months : Duration in months (dynamic per course)
        description     : Optional notes
        is_active       : Soft-delete flag
    """

    name = models.CharField(
        max_length=120,
        unique=True,
        help_text="Course name, e.g. 'Diploma in Information Technology'.",
    )
    code = models.CharField(
        max_length=20,
        unique=True,
        help_text="Short code, e.g. 'DIT', 'CIT'. Auto-uppercased.",
    )
    duration_months = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Total duration in months, e.g. 12 for DIT, 6 for CIT.",
    )
    description = models.TextField(
        blank=True,
        help_text="Optional description.",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Inactive courses remain visible in history but cannot accept new admissions.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_active', 'name']
        verbose_name = 'Course'
        verbose_name_plural = 'Courses'
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['code']),
        ]

    def __str__(self):
        return f"{self.code} — {self.name}"

    def save(self, *args, **kwargs):
        # Normalize code to uppercase
        if self.code:
            self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('courses:detail', kwargs={'pk': self.pk})

    # ---------- Convenience ----------
    @property
    def active_fee_categories(self):
        return self.fee_categories.filter(is_active=True)

    def total_fee_categories(self):
        return self.fee_categories.count()

    def active_batches(self):
        return self.batches.filter(is_active=True)

    def has_batches(self):
        """True if any batch (active or inactive) references this course."""
        return self.batches.exists()


class FeeCategory(models.Model):
    """
    A fee category belonging to a course.

    Examples:
        For DIT:  'Admission Fee', 'Registration Fee',
                  'Semester 1 Fee', 'Semester 2 Fee'
        For CIT:  'Admission Fee', 'Registration Fee', 'Exam Fee'

    Design:
        Fee categories are RELATIONAL ROWS, not database columns.
        This allows any course to have any number of categories
        without schema changes.
    """

    course = models.ForeignKey(
        Course,
        on_delete=models.PROTECT,
        related_name='fee_categories',
        help_text="The course this fee category belongs to.",
    )
    name = models.CharField(
        max_length=100,
        help_text="Fee category name, e.g. 'Admission Fee', 'Exam Fee'.",
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Default amount for this category, in PKR.",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['course', 'name']
        verbose_name = 'Fee Category'
        verbose_name_plural = 'Fee Categories'
        # One category name per course (prevents duplicate "Admission Fee" rows)
        constraints = [
            models.UniqueConstraint(
                fields=['course', 'name'],
                name='uniq_fee_category_per_course',
            ),
        ]
        indexes = [
            models.Index(fields=['course', 'is_active']),
        ]

    def __str__(self):
        return f"{self.course.code} — {self.name} (Rs. {self.amount})"

    def has_usage(self):
        """True if this category is referenced by any fee obligation."""
        # Will be implemented in Phase 5 once FeeObligation model exists.
        # For now: safe to assume no usage constraints; deactivation is soft.
        return False