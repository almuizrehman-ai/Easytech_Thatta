"""
AuditLog model.

Append-only audit trail for financial + administrative actions.

Design principles (from spec):
- Every important action is logged with user, action, module,
  previous value, new value, and timestamp.
- Never modified after creation.
- Uses ContentType framework so any model can be referenced
  without schema changes.
- JSON-encoded before/after snapshots support any model shape.
"""
import json

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone


class AuditLog(models.Model):
    """Immutable record of an important system action."""

    # ---------- Action choices ----------
    ACTION_CREATE = 'create'
    ACTION_UPDATE = 'update'
    ACTION_DELETE = 'delete'
    ACTION_WAIVE = 'waive'
    ACTION_CONCEDE = 'concede'
    ACTION_REVERSE = 'reverse'
    ACTION_APPROVE = 'approve'
    ACTION_REJECT = 'reject'
    ACTION_LOGIN = 'login'
    ACTION_LOGOUT = 'logout'
    ACTION_PAYMENT = 'payment'
    ACTION_ACTIVATE = 'activate'
    ACTION_DEACTIVATE = 'deactivate'

    ACTION_CHOICES = (
        (ACTION_CREATE, 'Create'),
        (ACTION_UPDATE, 'Update'),
        (ACTION_DELETE, 'Delete'),
        (ACTION_WAIVE, 'Waive'),
        (ACTION_CONCEDE, 'Concede'),
        (ACTION_REVERSE, 'Reverse'),
        (ACTION_APPROVE, 'Approve'),
        (ACTION_REJECT, 'Reject'),
        (ACTION_LOGIN, 'Login'),
        (ACTION_LOGOUT, 'Logout'),
        (ACTION_PAYMENT, 'Payment Recorded'),
        (ACTION_ACTIVATE, 'Activate'),
        (ACTION_DEACTIVATE, 'Deactivate'),
    )

    # ---------- Module choices ----------
    MODULE_STUDENTS = 'students'
    MODULE_FEES = 'fees'
    MODULE_COURSES = 'courses'
    MODULE_BATCHES = 'batches'
    MODULE_ACCOUNTS = 'accounts'
    MODULE_SYSTEM = 'system'

    MODULE_CHOICES = (
        (MODULE_STUDENTS, 'Students'),
        (MODULE_FEES, 'Fees'),
        (MODULE_COURSES, 'Courses'),
        (MODULE_BATCHES, 'Batches'),
        (MODULE_ACCOUNTS, 'Accounts'),
        (MODULE_SYSTEM, 'System'),
    )

    # ---------- Who ----------
    user = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        db_index=True,
        help_text="The user who performed the action.",
    )

    # ---------- What ----------
    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
        db_index=True,
    )
    module = models.CharField(
        max_length=20,
        choices=MODULE_CHOICES,
        db_index=True,
    )

    # ---------- Target object (generic FK) ----------
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    object_id = models.CharField(
        max_length=64,
        blank=True,
        db_index=True,
        help_text="Primary key of the affected object (string to support any PK type).",
    )
    target = GenericForeignKey('content_type', 'object_id')

    object_repr = models.CharField(
        max_length=255,
        blank=True,
        help_text="Human-readable snapshot of the affected object at the time of action.",
    )

    # ---------- Changes ----------
    change_summary = models.CharField(
        max_length=500,
        blank=True,
        help_text="One-line human summary of what changed.",
    )
    previous_value = models.TextField(
        blank=True,
        help_text="JSON-encoded snapshot before change (empty for create).",
    )
    new_value = models.TextField(
        blank=True,
        help_text="JSON-encoded snapshot after change (empty for delete).",
    )

    # ---------- Context ----------
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
    )
    user_agent = models.CharField(
        max_length=300,
        blank=True,
    )
    notes = models.TextField(
        blank=True,
        help_text="Optional explanatory notes.",
    )

    # ---------- When ----------
    created_at = models.DateTimeField(
        default=timezone.now,
        editable=False,
        db_index=True,
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        # Append-only — no updates
        # (enforced by app code; DB-level triggers optional for production)
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['module', 'action', '-created_at']),
            models.Index(fields=['content_type', 'object_id']),
        ]

    def __str__(self):
        user_label = self.user.get_full_name() if self.user else 'system'
        return f"{user_label} → {self.action} on {self.object_repr or 'N/A'} @ {self.created_at:%d %b %Y %H:%M}"

    # ---------- Helpers ----------
    def previous_dict(self):
        """Deserialize previous_value as dict."""
        if not self.previous_value:
            return {}
        try:
            return json.loads(self.previous_value)
        except (ValueError, TypeError):
            return {}

    def new_dict(self):
        """Deserialize new_value as dict."""
        if not self.new_value:
            return {}
        try:
            return json.loads(self.new_value)
        except (ValueError, TypeError):
            return {}

    def changed_fields(self):
        """
        Return list of dicts describing each changed field:
            [{'field': 'name', 'old': 'Ali', 'new': 'Ali K.'}, ...]
        """
        prev = self.previous_dict()
        new = self.new_dict()
        changes = []
        all_keys = set(prev.keys()) | set(new.keys())
        for key in all_keys:
            old_val = prev.get(key)
            new_val = new.get(key)
            if old_val != new_val:
                changes.append({'field': key, 'old': old_val, 'new': new_val})
        return changes

    def save(self, *args, **kwargs):
        """Enforce append-only: prevent updates on existing rows."""
        if self.pk and not self._state.adding:
            raise ValueError(
                "AuditLog is append-only. Records cannot be modified after creation."
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Enforce append-only: prevent deletes."""
        raise ValueError(
            "AuditLog is append-only. Records cannot be deleted."
        )