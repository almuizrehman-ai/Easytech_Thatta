"""URL configuration for the staff management application."""
from django.urls import path

from . import views

app_name = 'staff'

urlpatterns = [
    path('', views.staff_list, name='list'),
    path('new/', views.staff_create, name='create'),
    path('<int:pk>/edit/', views.staff_edit, name='edit'),
    path('<int:pk>/toggle/', views.staff_toggle_active, name='toggle'),
    path('<int:pk>/reset-password/', views.staff_password_reset, name='password_reset'),
]