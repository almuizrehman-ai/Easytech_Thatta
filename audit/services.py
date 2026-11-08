"""
Audit logging services.

All audit entries flow through log_action() — single point of truth
for how audit records are created.
"""
import json
from datetime import date, datetime
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType

from .models import AuditLog


def _safe_json_value(value):
    """
    Convert a model field value to something JSON can serialize.
    Handles Decimal, dates, times, UUIDs.
    """
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def serialize_model(instance, fields=None):
    """
    Serialize a model instance to a JSON-safe dict.

    Args:
        instance: Django model instance
        fields: optional iterable of field names to include.
                If None, includes all concrete non-pk fields.
    """
    if instance is None:
        return {}

    if fields is None:
        fields = [
            f.name for f in instance._meta.concrete_fields
            if not f.primary_key
        ]

    result = {}
    for field_name in fields:
        try:
            value = getattr(instance, field_name)
            result[field_name] = _safe_json_value(value)
        except (AttributeError, Exception):
            continue
    return result


def log_action(
    *,
    user,
    action,
    module,
    target=None,
    object_repr='',
    change_summary='',
    previous_value=None,
    new_value=None,
    ip_address=None,
    user_agent='',
    notes='',
):
    """
    Create an audit log entry.

    Args:
        user: CustomUser (or None for system actions)
        action: AuditLog.ACTION_* constant
        module: AuditLog.MODULE_* constant
        target: model instance (optional; uses ContentType + object_id)
        object_repr: human-readable snapshot
        change_summary: short summary for scanning
        previous_value: dict or JSON string (before snapshot)
        new_value: dict or JSON string (after snapshot)
        ip_address: string (optional)
        user_agent: string (optional)
        notes: additional context (optional)

    Returns:
        Created AuditLog instance.
    """
    content_type = None
    object_id = ''

    if target is not None and hasattr(target, '_meta'):
        content_type = ContentType.objects.get_for_model(target, for_concrete_model=False)
        object_id = str(getattr(target, 'pk', '') or '')

    # Serialize previous/new if dicts passed
    if isinstance(previous_value, dict):
        previous_value = json.dumps(previous_value, default=str)
    elif previous_value is None:
        previous_value = ''

    if isinstance(new_value, dict):
        new_value = json.dumps(new_value, default=str)
    elif new_value is None:
        new_value = ''

    return AuditLog.objects.create(
        user=user if (user and getattr(user, 'is_authenticated', False)) else None,
        action=action,
        module=module,
        content_type=content_type,
        object_id=object_id,
        object_repr=(object_repr or '')[:255],
        change_summary=(change_summary or '')[:500],
        previous_value=previous_value,
        new_value=new_value,
        ip_address=ip_address,
        user_agent=(user_agent or '')[:300],
        notes=notes or '',
    )


def log_from_request(
    request,
    action,
    module,
    target=None,
    object_repr='',
    change_summary='',
    previous_value=None,
    new_value=None,
    notes='',
):
    """
    Convenience: create audit entry pulling user/IP/UA from request.
    """
    ip = _get_client_ip(request)
    ua = request.META.get('HTTP_USER_AGENT', '')[:300] if request else ''

    return log_action(
        user=getattr(request, 'user', None),
        action=action,
        module=module,
        target=target,
        object_repr=object_repr,
        change_summary=change_summary,
        previous_value=previous_value,
        new_value=new_value,
        ip_address=ip,
        user_agent=ua,
        notes=notes,
    )


def _get_client_ip(request):
    """Extract client IP from request, handling proxies."""
    if not request:
        return None
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')