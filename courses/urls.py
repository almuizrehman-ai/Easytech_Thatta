"""URL configuration for the courses application."""
from django.urls import path

from . import views

app_name = 'courses'

urlpatterns = [
    # Course CRUD
    path('', views.course_list, name='list'),
    path('new/', views.course_create, name='create'),
    path('<int:pk>/', views.course_detail, name='detail'),
    path('<int:pk>/edit/', views.course_edit, name='edit'),
    path('<int:pk>/toggle/', views.course_toggle_active, name='toggle'),

    # Fee categories (nested under a course)
    path(
        '<int:course_pk>/fees/new/',
        views.fee_category_create,
        name='fee_create',
    ),
    path(
        '<int:course_pk>/fees/<int:pk>/edit/',
        views.fee_category_edit,
        name='fee_edit',
    ),
    path(
        '<int:course_pk>/fees/<int:pk>/toggle/',
        views.fee_category_toggle_active,
        name='fee_toggle',
    ),
]