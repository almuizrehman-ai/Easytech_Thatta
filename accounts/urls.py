"""URL configuration for the accounts application."""
from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    # Root path also serves login for convenience
    path('', views.login_view, name='login'),
    path('login/', views.login_view, name='login_page'),
    path('logout/', views.logout_view, name='logout'),
    path('post-login/', views.redirect_after_login, name='redirect_after_login'),
        path('forgot-password/', views.forgot_password_view, name='forgot_password'),
    path('reset-password/', views.reset_password_view, name='reset_password'),
]