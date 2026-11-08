"""URL configuration for the batches application."""
from django.urls import path

from . import views

app_name = 'batches'

urlpatterns = [
    path('', views.batch_list, name='list'),
    path('new/', views.batch_create, name='create'),
    path('<int:pk>/', views.batch_detail, name='detail'),
    path('<int:pk>/edit/', views.batch_edit, name='edit'),
    path('<int:pk>/toggle/', views.batch_toggle_active, name='toggle'),
]