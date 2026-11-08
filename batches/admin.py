"""
Django admin for batches app.

The primary UI is the custom CRUD views, but admin provides a
backup management interface for the Principal.
"""
from django.contrib import admin

from .models import Batch


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = (
        'display_name',
        'course',
        'start_month',
        'end_month',
        'monthly_fee',
        'is_active',
    )
    list_filter = ('is_active', 'course')
    search_fields = ('name', 'course__name', 'course__code')
    ordering = ('-is_active', '-start_month')
    readonly_fields = ('end_month', 'created_at', 'updated_at')
    list_select_related = ('course',)
    date_hierarchy = 'start_month'

    fieldsets = (
        (None, {
            'fields': ('course', 'name', 'start_month', 'monthly_fee'),
        }),
        ('Auto-calculated', {
            'fields': ('end_month',),
            'classes': ('collapse',),
        }),
        ('Status', {'fields': ('is_active',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )

    @admin.display(description='Batch')
    def display_name(self, obj):
        return obj.display_name