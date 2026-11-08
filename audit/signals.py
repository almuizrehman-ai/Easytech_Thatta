"""
Django signals for automatic audit logging.

Tracked models:
    students.Student
    fees.FeeObligation
    fees.FeePayment
    fees.FeeAdjustment
    courses.Course
    courses.FeeCategory
    batches.Batch

NOT tracked (avoid noise):
    AuditLog (infinite loop)
    Django internals (Session, LogEntry, ContentType, Permission)
    CustomUser (logged separately via views/management)
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from audit.models import AuditLog
from audit.services import log_action, serialize_model


# ============================================================
# PRE-SAVE: capture previous state
# ============================================================

# Sensitive models to track
_SENSITIVE_MODELS = set()


def _register_sensitive_models():
    """Lazy import to avoid circular imports."""
    from students.models import Student
    from fees.models import FeeObligation, FeePayment, FeeAdjustment
    from courses.models import Course, FeeCategory
    from batches.models import Batch

    _SENSITIVE_MODELS.update({
        Student, FeeObligation, FeePayment, FeeAdjustment,
        Course, FeeCategory, Batch,
    })


def _get_module_for_model(model_name):
    """Map model class name to AuditLog.MODULE_* constant."""
    mapping = {
        'Student': AuditLog.MODULE_STUDENTS,
        'FeeObligation': AuditLog.MODULE_FEES,
        'FeePayment': AuditLog.MODULE_FEES,
        'FeeAdjustment': AuditLog.MODULE_FEES,
        'Course': AuditLog.MODULE_COURSES,
        'FeeCategory': AuditLog.MODULE_COURSES,
        'Batch': AuditLog.MODULE_BATCHES,
    }
    return mapping.get(model_name, AuditLog.MODULE_SYSTEM)


def _get_object_repr(instance):
    """Human-readable label for the instance."""
    try:
        return str(instance)
    except Exception:
        return f"{instance.__class__.__name__}#{getattr(instance, 'pk', '?')}"


@receiver(pre_save)
def _capture_previous_state(sender, instance, **kwargs):
    """
    Before save, load current DB state into _previous_state attribute.
    Only for tracked models that already exist (have PK).
    """
    _register_sensitive_models()

    if sender not in _SENSITIVE_MODELS:
        return
    if not instance.pk:
        return

    try:
        old = sender.objects.get(pk=instance.pk)
        instance._previous_state = serialize_model(old)
    except sender.DoesNotExist:
        instance._previous_state = {}


# ============================================================
# POST-SAVE: log create / update
# ============================================================

@receiver(post_save)
def _log_model_change(sender, instance, created, **kwargs):
    """
    After save, create audit log entry for tracked models.
    """
    _register_sensitive_models()

    if sender not in _SENSITIVE_MODELS:
        return

    module = _get_module_for_model(sender.__name__)
    object_repr = _get_object_repr(instance)
    current_state = serialize_model(instance)

    if created:
        log_action(
            user=None,  # Will be enriched by view-level logging
            action=AuditLog.ACTION_CREATE,
            module=module,
            target=instance,
            object_repr=object_repr,
            change_summary=f"Created {sender.__name__}",
            previous_value=None,
            new_value=current_state,
            notes="Auto-logged by model signal.",
        )
    else:
        prev_state = getattr(instance, '_previous_state', {})
        if prev_state == current_state:
            return  # No changes
        changed_keys = [
            k for k in set(prev_state) | set(current_state)
            if prev_state.get(k) != current_state.get(k)
        ]
        log_action(
            user=None,
            action=AuditLog.ACTION_UPDATE,
            module=module,
            target=instance,
            object_repr=object_repr,
            change_summary=f"Updated {sender.__name__}: {', '.join(changed_keys[:5])}{'...' if len(changed_keys) > 5 else ''}",
            previous_value=prev_state,
            new_value=current_state,
            notes="Auto-logged by model signal.",
        )