"""URL configuration for the fees application."""
from django.urls import path

from . import views

app_name = 'fees'

urlpatterns = [
    # ============================================================
    # PHASE 5 — Ledger & Obligations
    # ============================================================
    path('student/<int:student_pk>/', views.student_ledger, name='student_ledger'),
    path('obligation/<int:pk>/', views.obligation_detail, name='obligation_detail'),

    # Payment
    path('obligation/<int:obligation_pk>/pay/', views.record_payment, name='record_payment'),

    # Adjustments
    path('obligation/<int:obligation_pk>/waiver/', views.apply_waiver, name='apply_waiver'),
    path('obligation/<int:obligation_pk>/concession/', views.apply_concession, name='apply_concession'),

    # Lists
    path('pending/', views.pending_fees, name='pending_fees'),
    path('overdue/', views.overdue_fees, name='overdue_fees'),

    # Utilities
    path('student/<int:student_pk>/regenerate/', views.regenerate_ledger, name='regenerate_ledger'),

    # ============================================================
    # PHASE 8 — Correction Workflow
    # ============================================================
    path(
        'payment/<int:payment_pk>/request-correction/',
        views.request_correction,
        name='request_correction',
    ),
    path('corrections/', views.corrections_list, name='corrections_list'),
    path(
        'corrections/<int:pk>/',
        views.correction_detail,
        name='correction_detail',
    ),
    path(
        'corrections/<int:pk>/review/',
        views.review_correction,
        name='review_correction',
    ),
    path(
        'corrections/<int:pk>/cancel/',
        views.cancel_correction_view,
        name='cancel_correction',
    ),
    path('student/<int:student_pk>/add-fee/', 
         views.add_manual_fee, name='add_manual_fee'),
    path('payment/<int:payment_pk>/request-correction/', views.request_correction, name='request_correction'),

    # ============================================================
    # PHASE 6 — Collection UI
    # ============================================================
    path('collect/', views.collection_dashboard, name='collection_dashboard'),
    path('collect/search/', views.collection_search, name='collection_search'),
    path('collect/student/<int:student_pk>/', views.quick_collect, name='quick_collect'),
    path('pending-summary/', views.pending_summary, name='pending_summary'),

    # Receipts
    path('receipt/<int:payment_pk>/', views.receipt_view, name='receipt'),
    path('receipt/<int:payment_pk>/print/', views.print_receipt, name='print_receipt'),
]