"""
Root URL configuration for EASYTECH THATTA Institute Management System.

URL namespace overview:
  /              -> accounts
  /dashboard/    -> dashboard
  /courses/      -> courses (Phase 3)
  /batches/      -> batches (Phase 3)
  /students/     -> students (Phase 4)
  /fees/         -> fees (Phase 5, corrections Phase 8)
  /reports/      -> reports (Phase 8)
  /staff/        -> staff management (Phase 8)
  /audit/        -> audit logs (Phase 8)
  /admin/        -> Django admin
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('accounts.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('courses/', include('courses.urls')),
    path('batches/', include('batches.urls')),
    path('students/', include('students.urls')),
    path('fees/', include('fees.urls')),
    path('reports/', include('reports.urls')),
    path('staff/', include('staff.urls')),
    path('audit/', include('audit.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)