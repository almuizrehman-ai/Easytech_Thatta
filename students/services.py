"""
Business logic services for the students application.

Keeping ID-generation logic separate from the model avoids
circular imports and makes the atomicity explicit.
"""
from django.db import transaction
from django.db.models import Max
from django.utils import timezone


STUDENT_ID_PREFIX = 'EST'
STUDENT_ID_PAD = 4  # EST-2027-0001 -> 4 digits


def _build_student_id(year: int, sequence: int) -> str:
    """Format 'EST-YYYY-NNNN'."""
    return f"{STUDENT_ID_PREFIX}-{year}-{sequence:0{STUDENT_ID_PAD}d}"


def generate_student_id() -> str:
    """
    Generate the next unique Student ID for the current year.

    Must be called inside a transaction with select_for_update on
    the student table to be concurrency-safe. Our caller
    (Student.save via AdmissionService) guarantees this.

    Example return:
        'EST-2027-0001', 'EST-2027-0002', ...
    """
    # Lazy import to avoid circular dependency with models.py
    from .models import Student

    year = timezone.localdate().year
    prefix = f"{STUDENT_ID_PREFIX}-{year}-"

    # Get the current maximum for this year
    with transaction.atomic():
        last = (
            Student.objects
            .select_for_update()
            .filter(student_id__startswith=prefix)
            .aggregate(max_id=Max('student_id'))
            .get('max_id')
        )

        if last:
            # Extract numeric suffix: 'EST-2027-0007' -> 7
            try:
                seq = int(last.rsplit('-', 1)[1])
            except (ValueError, IndexError):
                seq = 0
        else:
            seq = 0

        next_seq = seq + 1
        candidate = _build_student_id(year, next_seq)

        # Ultra-defensive: if somehow candidate exists (shouldn't happen
        # inside select_for_update), bump until free.
        while Student.objects.filter(student_id=candidate).exists():
            next_seq += 1
            candidate = _build_student_id(year, next_seq)

        return candidate