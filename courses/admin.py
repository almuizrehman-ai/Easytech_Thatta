"""
Django admin for courses app.

Primary UI is the custom CRUD views, but admin provides a
backup management interface for the Principal.
"""
from django.contrib import admin

from .models import Course, FeeCategory


class FeeCategoryInline(admin.TabularInline):
    """Inline fee categories inside the Course admin page."""

    model = FeeCategory
    extra = 1
    fields = ('name', 'amount', 'is_active')
    ordering = ('name',)
    show_change_link = True


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'name',
        'duration_months',
        'is_active',
        'total_fee_categories',
        'created_at',
    )
    list_filter = ('is_active',)
    search_fields = ('name', 'code')
    ordering = ('-is_active', 'name')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [FeeCategoryInline]

    fieldsets = (
        (None, {
            'fields': ('name', 'code', 'duration_months', 'description'),
        }),
        ('Status', {'fields': ('is_active',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )

    @admin.display(description='Categories')
    def total_fee_categories(self, obj):
        return obj.fee_categories.count()


@admin.register(FeeCategory)
class FeeCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'course', 'amount', 'is_active', 'updated_at')
    list_filter = ('is_active', 'course')
    search_fields = ('name', 'course__name', 'course__code')
    ordering = ('course', 'name')
    readonly_fields = ('created_at', 'updated_at')
    list_select_related = ('course',)