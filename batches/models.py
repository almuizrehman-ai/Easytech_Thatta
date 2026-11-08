"""
Models for the batches application.
"""
import calendar
from datetime import datetime
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from courses.models import Course


def _first_of_month(date_obj):
    return date_obj.replace(day=1)


def _add_months(date_obj, months):
    total_month_index = (date_obj.year * 12 + date_obj.month - 1) + months
    year = total_month_index // 12
    month = total_month_index % 12 + 1
    return date_obj.replace(year=year, month=month, day=1)


def _last_day_of_month(date_obj):
    return date_obj.replace(
        day=calendar.monthrange(date_obj.year, date_obj.month)[1]
    )


class Batch(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.PROTECT,
        related_name='batches',
        help_text="The course this batch belongs to.",
    )
    name = models.CharField(
        max_length=150,
        blank=True,
        help_text="Optional display name. Auto-generated if left blank.",
    )
    start_month = models.DateField(
        help_text="First day of the batch's starting month.",
    )
    end_month = models.DateField(
        editable=False,
        help_text="Auto-calculated from course duration.",
    )
    monthly_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Monthly fee for students in this batch (PKR).",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Inactive batches remain in records but do not accept new admissions.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_active', '-start_month']
        verbose_name = 'Batch'
        verbose_name_plural = 'Batches'
        constraints = [
            models.UniqueConstraint(
                fields=['course', 'start_month'],
                name='uniq_batch_course_start_month',
            ),
        ]
        indexes = [
            models.Index(fields=['course', 'is_active']),
            models.Index(fields=['start_month']),
        ]

    def __str__(self):
        return self.display_name

    def save(self, *args, **kwargs):
        # Safety: Agar start_month string hai toh usko date banao
        if self.start_month and isinstance(self.start_month, str):
            try:
                if len(self.start_month) == 7:  # e.g. "2026-02"
                    self.start_month = datetime.strptime(self.start_month, '%Y-%m').date()
            except ValueError:
                pass

        if self.start_month:
            self.start_month = _first_of_month(self.start_month)

            duration = self.course.duration_months
            last_month_first = _add_months(self.start_month, duration - 1)
            self.end_month = _last_day_of_month(last_month_first)

        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('batches:detail', kwargs={'pk': self.pk})

    @property
    def display_name(self):
        if self.name:
            return self.name
        return self.auto_name

    @property
    def auto_name(self):
        if not (self.start_month and self.end_month):
            return f"{self.course.code if self.course_id else 'BATCH'} (incomplete)"
        start_label = self.start_month.strftime('%b %Y')
        end_label = self.end_month.strftime('%b %Y')
        return f"{self.course.code} {start_label} – {end_label}"

    @property
    def duration_months(self):
        if not (self.start_month and self.end_month):
            return 0
        return (
            (self.end_month.year - self.start_month.year) * 12
            + (self.end_month.month - self.start_month.month)
            + 1
        )

    @property
    def is_ended(self):
        if not self.end_month:
            return False
        return timezone.localdate() > self.end_month

    def has_students(self):
        if hasattr(self, 'students'):
            return self.students.exists()
        return False

    def student_count(self):
        if hasattr(self, 'students'):
            return self.students.count()
        return 0