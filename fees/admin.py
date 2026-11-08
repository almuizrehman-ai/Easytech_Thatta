"""
Django admin for the fees app.

Readonly on financial fields (transaction_id, created_at, etc.).
Admin is a backup interface — primary UI is the custom views.

Security: FeeObligation, FeePayment, FeeAdjustment ka delete button hidden hai
taake ghalti se financial records delete na hon.
"""
from django.contrib import admin
from django.utils.html import format_html

from .models import (
    FeeObligation,
    FeePayment,
    FeeAdjustment,
    PaymentCorrectionRequest,
)


# ============================================================
# INLINES
# ============================================================

class FeePaymentInline(admin.TabularInline):
    model = FeePayment
    extra = 0
    fields = (
        'transaction_id', 'amount', 'payment_method',
        'payment_date', 'received_by', 'is_reversed',
    )
    readonly_fields = ('transaction_id',)
    ordering = ('-payment_date',)
    show_change_link = True
    can_delete = False


class FeeAdjustmentInline(admin.TabularInline):
    model = FeeAdjustment
    extra = 0
    fields = (
        'adjustment_type', 'amount', 'reason',
        'approved_by', 'is_active',
    )
    ordering = ('-created_at',)
    show_change_link = True
    can_delete = False


# ============================================================
# FEE OBLIGATION
# ============================================================

@admin.register(FeeObligation)
class FeeObligationAdmin(admin.ModelAdmin):
    list_display = (
        'student_name_link',
        'obligation_type',
        'month_label',
        'amount',
        'due_date',
        'outstanding_display',
        'status',
    )
    list_filter = (
        'status',
        'obligation_type',
        'due_date',
    )
    search_fields = (
        'student__student_id',
        'student__student_name',
        'student__father_name',
    )
    ordering = ('-due_date',)
    date_hierarchy = 'due_date'
    list_select_related = ('student', 'fee_category')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [FeePaymentInline, FeeAdjustmentInline]
    list_per_page = 50

    fieldsets = (
        ('Student', {
            'fields': ('student',),
        }),
        ('Obligation', {
            'fields': (
                'obligation_type', 'fee_category',
                'obligation_month', 'description',
                'amount', 'due_date', 'status',
            ),
        }),
        ('Notes & Audit', {
            'fields': ('notes', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Student')
    def student_name_link(self, obj):
        return format_html(
            '<strong>{}</strong><br/><small>{}</small>',
            obj.student.student_name,
            obj.student.student_id,
        )

    @admin.display(description='Outstanding')
    def outstanding_display(self, obj):
        outstanding = obj.outstanding_amount
        if outstanding <= 0:
            return format_html('<span style="color:#047857;">Rs. 0.00</span>')
        if obj.is_overdue:
            return format_html(
                '<span style="color:#b91c1c;font-weight:600;">Rs. {}</span>',
                f"{outstanding:.2f}"
            )
        return format_html('Rs. {}', f"{outstanding:.2f}")

    @admin.display(description='Month')
    def month_label(self, obj):
        return obj.month_label

    # Security: Block delete
    def has_delete_permission(self, request, obj=None):
        return False


# ============================================================
# FEE PAYMENT
# ============================================================

@admin.register(FeePayment)
class FeePaymentAdmin(admin.ModelAdmin):
    list_display = (
        'transaction_id',
        'obligation',
        'amount',
        'payment_method',
        'payment_date',
        'received_by',
        'reversed_badge',
    )
    list_filter = (
        'payment_method',
        'is_reversed',
        'payment_date',
    )
    search_fields = (
        'transaction_id',
        'obligation__student__student_id',
        'obligation__student__student_name',
    )
    ordering = ('-payment_date',)
    date_hierarchy = 'payment_date'
    list_select_related = ('obligation__student', 'received_by')
    readonly_fields = (
        'transaction_id', 'created_at', 'updated_at',
        'reversed_at', 'reversed_by', 'reversal_reason',
    )

    fieldsets = (
        ('Transaction', {
            'fields': ('transaction_id', 'obligation', 'amount'),
        }),
        ('Details', {
            'fields': ('payment_method', 'payment_date', 'received_by', 'notes'),
        }),
        ('Reversal (Phase 8)', {
            'fields': ('is_reversed', 'reversed_at', 'reversed_by', 'reversal_reason'),
            'classes': ('collapse',),
        }),
        ('Audit', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Reversed')
    def reversed_badge(self, obj):
        if obj.is_reversed:
            return format_html(
                '<span style="color:#b91c1c;font-weight:600;">Yes</span>'
            )
        return '—'

    # Security: Block delete
    def has_delete_permission(self, request, obj=None):
        return False


# ============================================================
# FEE ADJUSTMENT
# ============================================================

@admin.register(FeeAdjustment)
class FeeAdjustmentAdmin(admin.ModelAdmin):
    list_display = (
        'obligation',
        'adjustment_type',
        'amount',
        'approved_by',
        'is_active',
        'created_at',
    )
    list_filter = ('adjustment_type', 'is_active')
    search_fields = (
        'obligation__student__student_id',
        'obligation__student__student_name',
        'reason',
    )
    ordering = ('-created_at',)
    list_select_related = ('obligation__student', 'approved_by')
    readonly_fields = ('created_at', 'updated_at', 'reversed_at')

    # Security: Block delete
    def has_delete_permission(self, request, obj=None):
        return False


# ============================================================
# PAYMENT CORRECTION REQUEST (Naya)
# ============================================================

@admin.register(PaymentCorrectionRequest)
class PaymentCorrectionRequestAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'payment',
        'correction_type',
        'status_badge',
        'requested_by',
        'created_at',
    )
    list_filter = (
        'status',
        'correction_type',
        'created_at',
    )
    search_fields = (
        'payment__transaction_id',
        'payment__obligation__student__student_id',
        'payment__obligation__student__student_name',
        'reason',
    )
    ordering = ('-created_at',)
    list_select_related = ('payment', 'requested_by', 'reviewed_by')
    readonly_fields = (
        'created_at', 'updated_at', 'reviewed_at',
        'replacement_payment',
    )

    fieldsets = (
        ('Request Info', {
            'fields': ('payment', 'correction_type', 'status',
                       'requested_by', 'created_at'),
        }),
        ('Requested Changes', {
            'fields': ('new_amount', 'new_payment_method',
                       'new_payment_date', 'reason', 'notes'),
        }),
        ('Review', {
            'fields': ('reviewed_by', 'reviewed_at',
                       'review_notes', 'replacement_payment'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Status')
    def status_badge(self, obj):
        colors = {
            'pending': '#f59e0b',
            'approved': '#10b981',
            'rejected': '#ef4444',
            'cancelled': '#94a3b8',
        }
        color = colors.get(obj.status, '#64748b')
        return format_html(
            '<span style="color:{};font-weight:600;">{}</span>',
            color,
            obj.get_status_display()
        )
