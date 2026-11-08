"""
Django admin for students app.

Primary UI is the custom views, but admin provides a
backup management interface for the Principal.
"""
from django.contrib import admin
from django.utils.html import format_html

from .models import Student


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = (
        'student_id',
        'student_name',
        'father_name',
        'course',
        'batch',
        'student_mobile',
        'is_active',
        'admission_date',
    )
    list_filter = (
        'is_active',
        'enrollment_status',
        'course',
        'gender',
        'admission_date',
    )
    search_fields = (
        'student_id',
        'student_name',
        'father_name',
        'student_mobile',
        'father_mobile',
    )
    ordering = ('-created_at',)
    readonly_fields = (
        'student_id',
        'photo_preview',
        'created_at',
        'updated_at',
    )
    list_select_related = ('course', 'batch')
    date_hierarchy = 'admission_date'
    list_per_page = 50

    fieldsets = (
        ('Identification', {
            'fields': ('student_id', 'student_name', 'father_name',
                       'gender', 'date_of_birth', 'cnic_or_bform'),
        }),
        ('Contact', {
            'fields': ('student_mobile', 'father_mobile',
                       'student_email', 'address'),
        }),
        ('Photo', {
            'fields': ('photo', 'photo_preview'),
            'classes': ('collapse',),
        }),
        ('Academic Placement', {
            'fields': ('course', 'batch', 'admission_date',
                       'enrollment_status', 'is_active'),
        }),
        ('Fee Snapshots', {
            'fields': (
                'admission_fee_amount',
                'registration_fee_amount',
                'monthly_fee_at_admission',
            ),
            'classes': ('collapse',),
        }),
        ('Audit', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Photo')
    def photo_preview(self, obj):
        if obj.photo:
            return format_html(
                '<img src="{}" style="max-height:80px;border-radius:6px;" />',
                obj.photo.url,
            )
        return '—'