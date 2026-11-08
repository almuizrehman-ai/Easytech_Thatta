from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('staff/', views.staff_dashboard, name='staff'),
    path('principal/', views.principal_dashboard, name='principal'),
    
    # Student Portal URLs
    path('student/', views.student_dashboard, name='student'),
    path('student/profile/', views.student_my_profile, name='student_profile'),
    path('student/ledger/', views.student_my_ledger, name='student_ledger'),
    path('student/print/', views.student_my_print, name='student_print'),
    path('student/receipt/<int:payment_pk>/', views.student_receipt_thermal, name='student_receipt'),
]