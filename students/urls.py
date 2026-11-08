"""URL configuration for the students application."""
from django.urls import path

from . import views

app_name = 'students'

urlpatterns = [
    path('', views.student_list, name='list'),
    path('new/', views.student_create, name='create'),
    path('<int:pk>/', views.student_detail, name='detail'),
    path('<int:pk>/edit/', views.student_edit, name='edit'),
    path('<int:pk>/toggle/', views.student_toggle_active, name='toggle'),
    path('<int:pk>/print/', views.student_print_form, name='print_form'),
]