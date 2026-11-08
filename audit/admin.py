"""
Django admin for audit logs.

Read-only: no add, no change, no delete.
Principal uses admin as backup; primary viewer is the custom template.
"""
from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        'created_at',
        'user',
        'action',
        'module',
        'object_repr',
        'change_summary_preview',
    )
    list_filter = ('action', 'module', 'created_at', 'user')
    search_fields = (
        'object_repr',
        'change_summary',
        'object_id',
        'user__username',
        'user__full_name',
    )
    ordering = ('-created_at',)
    list_select_related = ('user',)
    date_hierarchy = 'created_at'
    list_per_page = 100
    readonly_fields = [
        'created_at', 'user', 'action', 'module',
        'content_type', 'object_id', 'object_repr',
        'change_summary', 'previous_value', 'new_value',
        'ip_address', 'user_agent', 'notes',
    ]

    # Read-only permissions
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description='Summary')
    def change_summary_preview(self, obj):
        return obj.change_summary[:80] if obj.change_summary else '—'